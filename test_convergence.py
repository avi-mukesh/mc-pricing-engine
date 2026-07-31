from pricing import *

S0 = 100
K = 100
T = 1
rf = 0.05
sigma = 0.2

params = MarketParams(S0, K, T, rf, sigma)

for iterations in [1000, 10000, 100000, 1000000]:
    mc_pricer = MonteCarloPricer(params, iterations, 10101010)
    mc_pricer.price_simulations = None
    mc_pricer.simulate_price_paths()
    price, std_error = mc_pricer.european_call_price_from_paths()