from pricing import *
from time import perf_counter


S0 = 100
K = 100
T = 1
rf = 0.05
sigma = 0.2

params = MarketParams(S0, K, T, rf, sigma)
V0 = bs_european_call_price(params)

num_simulations = 10000
rng = np.random.default_rng(20)
z = rng.normal(0, 1, num_simulations)

# simulate one GBM step of stock price to get it's price at t=10/252
# for each simulation, run MC to price the option. option has life T-10/252 left
S_10d = S0 * np.exp((rf - 0.5 * sigma ** 2)*(10/252) + sigma * np.sqrt(10/252) * z)
V = [0]*num_simulations

print("Calculating 99% 10-day VaR, varying number of iterations in MC simulations")
for iterations in [1000, 10000, 100000]:
    start = perf_counter()
    for i in range(num_simulations):    
        params = MarketParams(S_10d[i], K, T-10/252, rf, sigma)
        # using CRN here, as it reduces noise in the pnl differencess
        mc_pricer = MonteCarloPricer(params, iterations, 10101010)
        mc_pricer.simulate_terminal_prices()
        V[i], _ = mc_pricer.european_call_price()
    end = perf_counter()
        
    pnl = V - V0
    var99 = np.percentile(pnl, 1)
    print(f"{iterations} iterations: ${-var99:.4f}")
    print(f"Time taken: {end-start:.4f}s")
    
print()

start = perf_counter()
for i in range(num_simulations):    
    params = MarketParams(S_10d[i], K, T-10/252, rf, sigma)
    V[i] = bs_european_call_price(params)
end = perf_counter()

pnl = V - V0
var99 = np.percentile(pnl, 1)
print(f"Exact VaR using BS ${-var99:.4f}")
print(f"Time taken: {end-start:.4f}s")