from pricing import *

S0 = 100
K = 100
T = 1
rf = 0.05
sigma = 0.2

params = MarketParams(S0, K, T, rf, sigma)

mc_pricer = MonteCarloPricer(params, 10000000)
mc_pricer.simulate_price_paths()

mc_call, std_error = mc_pricer.call_price()
bs_call = bs_call_price(params)
assert(abs(mc_call - bs_call) < 2 * std_error) # will fail about 5% of the time

mc_put, std_error = mc_pricer.put_price()
bs_put = bs_put_price(params)
assert(abs(mc_put - bs_put) < 2 * std_error)

# put-call parity holds for BS (should be exact)
assert(abs(bs_call - bs_put - S0 + K * np.exp(-rf * T)) == 0)

# put-call parity holds for MC (not exact, but good)
discounted_price_simulations = np.exp(-rf * T) * mc_pricer.price_simulations
std_error_pc_parity = np.std(discounted_price_simulations) / np.sqrt(mc_pricer.iterations)
assert(abs(mc_call - mc_put - S0 + K * np.exp(-rf * T)) < 2 * std_error_pc_parity)