from pricing import *


params = MarketParams(100, 100, 1, 0.05, 0.2)


mc_pricer = MonteCarloPricer(params, 100000)
mc_price, std_error = mc_pricer.call_price()
bs_price = bs_call_price(params)

assert(abs(mc_price - bs_price) < 2 * std_error)