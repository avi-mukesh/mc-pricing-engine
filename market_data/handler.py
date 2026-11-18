# FetchMarketData: the first state of the mc-pricer-run state machine.
# Takes the run's config as input, fetches the ticker's daily prices from Tiingo, writes a
# dated snapshot to S3 and returns the config with real S0 and sigma filled in.
# Standard library + boto3 only, because both come with the Lambda Python runtime.
import json
import math
import os
import statistics
import urllib.request
from datetime import date, timedelta

import boto3

TIINGO_URL = "https://api.tiingo.com/tiingo/daily/{ticker}/prices?startDate={start}"
TRADING_DAYS = 252


def fetch_prices(ticker, start, api_key):
    # the token goes in a header, not the URL, so it never shows up in logs or errors
    request = urllib.request.Request(
        TIINGO_URL.format(ticker=ticker, start=start.isoformat()),
        headers={"Authorization": f"Token {api_key}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=10) as response:
        return json.loads(response.read())


def snapshot_from_prices(ticker, prices, window=TRADING_DAYS):
    # prices is Tiingo's list of daily bars, oldest first
    if len(prices) < window + 1:
        raise ValueError(f"need {window + 1} daily prices for {ticker}, got {len(prices)}")
    recent = prices[-(window + 1):]

    # vol from adjusted closes, so dividends and splits don't look like price drops
    adj = [bar["adjClose"] for bar in recent]
    log_returns = [math.log(b / a) for a, b in zip(adj, adj[1:])]
    sigma = statistics.stdev(log_returns) * math.sqrt(TRADING_DAYS)

    latest = recent[-1]
    return {
        "ticker": ticker,
        # the date of the close, not the date of the run - on a weekend it's still Friday
        "as_of": latest["date"][:10],
        # the actual traded price, which is what an option's strike is compared against
        "S0": latest["close"],
        "sigma": sigma,
        "vol_window_days": window,
        "source": "tiingo",
    }


def handler(event, context):
    ticker = event["ticker"]

    ssm = boto3.client("ssm")
    api_key = ssm.get_parameter(Name=os.environ["api_key_parameter"], WithDecryption=True)["Parameter"]["Value"]

    # ~1.6 calendar years comfortably covers 252 trading days plus holidays
    prices = fetch_prices(ticker, date.today() - timedelta(days=600), api_key)
    snapshot = snapshot_from_prices(ticker, prices)

    s3 = boto3.client("s3")
    s3.put_object(
        Bucket=os.environ["s3_bucket"],
        Key=f"market/{ticker}/{snapshot['as_of']}.json",
        Body=json.dumps(snapshot),
    )

    # the config with market values filled in becomes the input to the workers
    return {**event, "S0": snapshot["S0"], "sigma": snapshot["sigma"], "market_as_of": snapshot["as_of"]}
