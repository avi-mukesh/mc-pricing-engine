from pricing import *

S0 = 100
K = 100
T = 1
rf = 0.05
sigma = 0.2
iterations = 100000

d1 = (np.log(S0/K) + (rf + 0.5 * sigma ** 2) * (T)) / (sigma * np.sqrt(T))
delta = stats.norm.cdf(d1)
print(f'exact Δ = N(d_1) = {delta:.4f}\n')

def fd_delta(h, seed_base, seed_bumped, print_details):
    params = MarketParams(S0, K, T, rf, sigma)
    mc_pricer_base = MonteCarloPricer(params, iterations, seed_base)
    mc_pricer_base.simulate_price_paths(2)
    c, _ = mc_pricer_base.european_call_price_from_paths()

    params_bumped = MarketParams(S0+h, K, T, rf, sigma)
    mc_pricer_bumped = MonteCarloPricer(params_bumped, iterations, seed_bumped)
    mc_pricer_bumped.simulate_price_paths(2)
    c_h, _ = mc_pricer_bumped.european_call_price_from_paths()
    delta_approx = (c_h - c) / h
    
    if print_details:
        print(f'=====with h={h} and {"same" if seed_base == seed_bumped else "different"} random numbers=====')
        print(f'C(S_0): {c:.4f}')
        print(f'C(S_0+h): {c_h:.4f}')
        print(f'C(S_0+h) - C(S_0) = {(c_h - c):.4f}')
        print(f'Δ ≈ (C(S_0+h) - C(S_0))/h = {delta_approx:.4f}\n')
    return delta_approx
    
# common random numbers
for h in [0.1, 0.01, 0.001, 0.0001]:
    fd_delta(h, 10101010, 10101010, True)
    
# independent draws (not CRN)
for h in [0.1, 0.01, 0.001, 0.0001]:
    fd_delta(h, 10101010, 20202020, True)

deltas = []
for i in range(50):
    deltas.append(fd_delta(0.01, 1000+i, 2000+i, False))
print(f"Non-CRN, standard deviation of the deltas (with h=0.01): {np.std(deltas):.4f}\n")

params = MarketParams(S0, K, T, rf, sigma)
mc_pricer = MonteCarloPricer(params, iterations, 10101010)

# path-wise Greeks
pathwise_delta, std_error = mc_pricer.delta_using_pathwise_differentiation()
print(f"Approximate value of Δ by differentiating pathwise: {pathwise_delta:.4f}")
print(f"Standard error {std_error:.4f}\n")
assert(abs(pathwise_delta - delta) < 2 * std_error)

# likelihood ratio
likelihood_ratio_delta, std_error = mc_pricer.delta_using_likelihood_ratio()
print(f"Approximate value of Δ using likelihood ratio: {likelihood_ratio_delta:.4f}")
print(f"Standard error {std_error:.4f}")
assert(abs(likelihood_ratio_delta - delta) < 2 * std_error)