from pricing import *

S0 = 100
K = 100
T = 1
rf = 0.05
sigma = 0.2
iterations = 100000

params = MarketParams(S0, K, T, rf, sigma)
mc_pricer_base = MonteCarloPricer(params, iterations, 10101010)
mc_pricer_base.simulate_price_paths(2)
c, _ = mc_pricer_base.european_call_price_from_paths()

h=0.1
params = MarketParams(S0+h, K, T, rf, sigma)
mc_pricer_bumped = MonteCarloPricer(params, iterations, 10101010)
mc_pricer_bumped.simulate_price_paths(2)
c_h, _ = mc_pricer_bumped.european_call_price_from_paths()

print(f'C(S_0): {c:.4f}')
print(f'C(S_0+h): {c_h:.4f}')

delta_approx = (c_h - c) / h
print(f'Δ ≈ (C(S_0+h) - C(S_0))/h = {delta_approx:.4f}')

d1 = (np.log(S0/K) + (rf + 0.5 * sigma ** 2) * (T)) / (sigma * np.sqrt(T))
delta = stats.norm.cdf(d1)
print(f'Δ = N(d_1) = {delta:.4f}')