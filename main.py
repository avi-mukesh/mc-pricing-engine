import os
from pricing import *
import boto3

S0 = float(os.environ.get("S0", 100))
K = float(os.environ.get("K", 100))
T = float(os.environ.get("T", 1))
t = float(os.environ.get("t", 1/12))
rf = float(os.environ.get("rf", 0.05))
sigma = float(os.environ.get("sigma", 0.2))

params = MarketParams(S0, K, T, rf, sigma)
V0 = bs_european_call_price(params)

num_simulations = int(os.environ.get("num_simulations", 20))
num_workers = int(os.environ.get("num_workers", 1))
worker_index = int(os.environ.get("AWS_BATCH_JOB_ARRAY_INDEX", os.environ.get("worker_index", 0)))

root = np.random.SeedSequence(12345)
child = root.spawn(num_workers)[worker_index]
rng = np.random.default_rng(child)

z = rng.normal(0, 1, num_simulations)

S_t = S0 * np.exp((rf - 0.5 * sigma ** 2)*t + sigma * np.sqrt(t) * z)
V = [0]*num_simulations
iterations = 1000

for i in range(num_simulations):    
    params = MarketParams(S_t[i], K, T-t, rf, sigma)
    mc_pricer = MonteCarloPricer(params, iterations, worker_index)
    terminal, _ = mc_pricer.simulate_terminal_prices()
    V[i], _ = mc_pricer.european_call_price(terminal)

pnl = V - V0

output_dir = os.environ.get("output_dir", ".")
local_path = f'{output_dir}/pnl_{worker_index}.npy'
np.save(local_path, pnl)

print(f'PnL array of length {len(pnl)} written to pnl_{worker_index}.npy')

bucket = os.environ.get('s3_bucket')
run_id = os.environ.get('run_id', 'local')

if bucket:
    key = f"runs/{run_id}/pnl_{worker_index}.npy"
    boto3.client("s3").upload_file(local_path, bucket, key)
    print(f'uploaded to s3://{bucket}/{key}')