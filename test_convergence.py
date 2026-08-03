import matplotlib.pyplot as plt
import pandas as pd
from pricing import *

S0 = 100
K = 100
T = 1
rf = 0.05
sigma = 0.2

params = MarketParams(S0, K, T, rf, sigma)

df = {'num_iterations':[], 'price': [], 'std_error': []}

for iterations in [1000, 10000, 100000, 1000000]:
    mc_pricer = MonteCarloPricer(params, iterations, 101010)
    mc_pricer.simulate_price_paths(2)
    price, std_error = mc_pricer.european_call_price_from_paths()
    
    df['num_iterations'].append(iterations)
    df['price'].append(price)
    df['std_error'].append(std_error)
    
df = pd.DataFrame(df)

# SE = sigma / sqrt(N) so log(SE) = log(sigma) - 0.5 * log(N)
# so gradient will be -0.5
# intercept is log(sigma)

fig = plt.figure()
plt.scatter(np.log(df['num_iterations']), np.log(df['std_error']))
plt.xlabel('log(N)')
plt.ylabel('log(SE)')
plt.title('Monte Carlo convergence')

gradient, intercept = np.polyfit(np.log(df['num_iterations']), np.log(df['std_error']), 1)

payoff_std = np.exp(intercept)

print(f'gradient: {gradient:.4f}')
print(f'intercept: {intercept:.4f}')
print(f'standard deviation of payoffs j(e^intercept): {payoff_std:.4f}')
plt.savefig('convergence.png')

plt.show()
