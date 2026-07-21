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

print('=====testing european call price: MC vs Black-Scholes=====')
mc_european_call, std_error = mc_pricer.european_call_price()
bs_european_call = bs_european_call_price(params)
print('mc european call price {:.3f}'.format(mc_european_call))
print('bs european call price {:.3f}'.format(bs_european_call))
print('standard error {:.4f}\n'.format(std_error))
assert(abs(mc_european_call - bs_european_call) < 2 * std_error) # will fail about 5% of the time

print('=====testing european put price: MC vs Black-Scholes=====')
mc_european_put, std_error = mc_pricer.european_put_price()
bs_european_put = bs_european_put_price(params)
print('mc european put price {:.3f}'.format(mc_european_put))
print('bs european put price {:.3f}'.format(bs_european_put))
print('standard error {:.4f}\n'.format(std_error))
assert(abs(mc_european_put - bs_european_put) < 2 * std_error)

print('=====testing put-call parity: Black-Scholes (exact)=====')
# put-call parity holds for BS (should be exact)
assert(abs(bs_european_call - bs_european_put - S0 + K * np.exp(-rf * T)) == 0)

print('=====testing put-call parity: MC (approximate)=====')
# put-call parity holds for MC (not exact, but good)
discounted_terminal_prices = np.exp(-rf * T) * mc_pricer.terminal_prices
std_error_pc_parity = np.std(discounted_terminal_prices) / np.sqrt(mc_pricer.iterations)
assert(abs(mc_european_call - mc_european_put - S0 + K * np.exp(-rf * T)) < 2 * std_error_pc_parity)

print('=====testing european call price from full path simulation: MC vs Black-Scholes=====')
# ensuring that the method that simulated the full price paths (instead of just the terminal prices) is valid
mc_pricer.simulate_price_paths(2)
mc_european_call_from_paths, std_error = mc_pricer.european_call_price_from_paths()

print('mc european call price (full path simulation) {:.3f}'.format(mc_european_call_from_paths))
print('bs european call price {:.3f}'.format(bs_european_call))
print('standard error {:.4f}\n'.format(std_error))
assert(abs(mc_european_call_from_paths - bs_european_call) < 2 * std_error)


print('=====testing asian call price: MC vs 2-step binomial model=====')
# attempting to validate asian call option price from MC against 2-step binomial model
# but it doesn't work because n=2 is too small for the tree itself to be accurate
mc_asian_call, std_error = mc_pricer.arithmetic_asian_call_price()
binomial_asian_call = binomial_arithmetic_asian_call_price(params)
print('mc (n=2) asian call price {:.3f}'.format(mc_asian_call))
print('binomial model (n=2) asian call price {:.3f}'.format(binomial_asian_call))
print('standard error {:.4f}\n'.format(std_error))


print('=====testing 2-step binomial model accuracy: european call price=====')
# confirming that 2-step binomial isn't accurate, by calculating european call price
# which we already validated above
binomial_european_call = binomial_european_call_price(params)
print('binomial model (n=2) european call price {:.3f}'.format(binomial_european_call))
print('bs european call price {:.3f}'.format(bs_european_call))


# TODO: geometric asian and validation