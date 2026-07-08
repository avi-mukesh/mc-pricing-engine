from pricing import *

S0 = 100
K = 100
T = 1
rf = 0.05
sigma = 0.2
iterations = 100000

params = MarketParams(S0, K, T, rf, sigma)

mc_pricer = MonteCarloPricer(params, iterations)
mc_pricer.simulate_terminal_prices()

mc_call, std_error = mc_pricer.call_price()
bs_call = bs_call_price(params)
print('mc call price {:.3f}'.format(mc_call))
print('bs call price {:.3f}'.format(bs_call))
print('standard error {:.4f}\n'.format(std_error))
assert(abs(mc_call - bs_call) < 2 * std_error) # will fail about 5% of the time

mc_put, std_error = mc_pricer.put_price()
bs_put = bs_put_price(params)
print('mc put price {:.3f}'.format(mc_put))
print('bs put price {:.3f}'.format(bs_put))
print('standard error {:.4f}\n'.format(std_error))
assert(abs(mc_put - bs_put) < 2 * std_error)

# put-call parity holds for BS (should be exact)
assert(abs(bs_call - bs_put - S0 + K * np.exp(-rf * T)) == 0)

# put-call parity holds for MC (not exact, but good)
discounted_terminal_prices = np.exp(-rf * T) * mc_pricer.terminal_prices
std_error_pc_parity = np.std(discounted_terminal_prices) / np.sqrt(mc_pricer.iterations)
assert(abs(mc_call - mc_put - S0 + K * np.exp(-rf * T)) < 2 * std_error_pc_parity)

# ensuring that the method that simulated the full price paths (instead of just the terminal prices) is valid
mc_pricer.simulate_price_paths(2)
mc_call_2, std_error = mc_pricer.call_price_from_paths()

print('mc call price (full path simulation) {:.3f}'.format(mc_call_2))
print('bs call price {:.3f}'.format(bs_call))
print('standard error {:.4f}\n'.format(std_error))
assert(abs(mc_call_2 - bs_call) < 2 * std_error)


# attempting to validate asian call option price from MC against 2-step binomial model
# but it doesn't work because n=2 is too small for the tree itself to be accurate
mc_asian_call, std_error = mc_pricer.asian_call_price()
bin_asian_call = asian_call_price(params)
print('mc (n=2) asian call price {:.3f}'.format(mc_asian_call))
print('binomial model (n=2) asian call price {:.3f}'.format(bin_asian_call))
print('standard error {:.4f}\n'.format(std_error))


# confirming that 2-step binomial isn't accurate, by calculating european call price
# which we already validated above
mc_call_binomial = call_price_binomial(params)
print('binomial model (n=2) european call price {:.3f}'.format(mc_call_binomial))
