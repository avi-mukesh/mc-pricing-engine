import json
import math

import pytest

from market_data import handler as md


def bars(adj_closes, closes=None):
    # minimal Tiingo-shaped daily bars, oldest first
    closes = closes or adj_closes
    return [
        {"date": f"2026-01-{i % 28 + 1:02d}T00:00:00.000Z", "adjClose": a, "close": c}
        for i, (a, c) in enumerate(zip(adj_closes, closes))
    ]


def test_constant_growth_has_zero_vol():
    prices = bars([100 * 1.001 ** i for i in range(253)])
    assert md.snapshot_from_prices("SPY", prices)["sigma"] == pytest.approx(0, abs=1e-12)


def test_sigma_is_annualised_stdev_of_log_returns():
    # alternating +1% / -1% moves: every log return is +-log(1.01)
    adj = [100.0]
    for i in range(252):
        adj.append(adj[-1] * (1.01 if i % 2 == 0 else 1 / 1.01))
    sigma = md.snapshot_from_prices("SPY", bars(adj))["sigma"]
    r = math.log(1.01)
    sample_stdev = r * math.sqrt(252 / 251)  # mean is 0, n-1 in the denominator
    assert sigma == pytest.approx(sample_stdev * math.sqrt(252))


def test_uses_only_the_last_window_of_prices():
    # a wild first year must not affect vol when the last 253 prices are calm
    wild = [100 * (2 if i % 2 else 1) for i in range(100)]
    calm = [100.0] * 253
    assert md.snapshot_from_prices("SPY", bars(wild + calm))["sigma"] == 0


def test_S0_is_the_unadjusted_latest_close():
    adj = [100.0] * 253
    closes = [110.0] * 252 + [123.45]
    snapshot = md.snapshot_from_prices("SPY", bars(adj, closes))
    assert snapshot["S0"] == 123.45


def test_too_little_history_fails_loudly():
    with pytest.raises(ValueError, match="need 253"):
        md.snapshot_from_prices("SPY", bars([100.0] * 100))


def test_handler_writes_snapshot_and_returns_filled_config(monkeypatch):
    prices = bars([100.0] * 253)
    puts = []

    class FakeSSM:
        def get_parameter(self, Name, WithDecryption):
            assert WithDecryption
            return {"Parameter": {"Value": "test-key"}}

    class FakeS3:
        def put_object(self, **kwargs):
            puts.append(kwargs)

    fakes = {"ssm": FakeSSM(), "s3": FakeS3()}
    monkeypatch.setattr(md.boto3, "client", lambda name: fakes[name])
    monkeypatch.setattr(md, "fetch_prices", lambda ticker, start, key: prices)
    monkeypatch.setenv("api_key_parameter", "/test/key")
    monkeypatch.setenv("s3_bucket", "test-bucket")

    config = {"ticker": "SPY", "K": 100, "num_workers": 2}
    out = md.handler(config, None)

    # config passes through, market values are added
    assert out["K"] == 100 and out["num_workers"] == 2
    assert out["S0"] == 100.0 and out["sigma"] == 0
    as_of = prices[-1]["date"][:10]
    assert out["market_as_of"] == as_of
    # one dated snapshot per ticker per close
    assert len(puts) == 1
    assert puts[0]["Key"] == f"market/SPY/{as_of}.json"
    assert json.loads(puts[0]["Body"])["source"] == "tiingo"
