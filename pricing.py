from scipy import stats
import numpy as np

class MarketParams:
    def __init__(self, S0, K, T, rf, sigma):
        self.S0 = S0
        self.K = K
        self.T = T
        self.rf = rf
        self.sigma = sigma
    
    def unpack(self):
        return self.S0, self.K, self.T, self.rf, self.sigma
    
class MonteCarloPricer:
    def __init__(self, params: MarketParams, iterations: int, rng_seed: int | None = None):
        self.params = params
        self.iterations = iterations
        self.rng = np.random.default_rng(rng_seed) if rng_seed is not None else np.random.default_rng()
        
    def simulate_price_paths(self):
        S, K, T, rf, sigma = self.params.unpack()
        z = self.rng.normal(0, 1, self.iterations)
        # simulate stock price at time T by simulating dS_t = \r_f*S_t*dt + \sigma * S_t * dW_t^Q
        # notice we are using risk neutral measure and using r_f instead of mu now
        # expected growth of asset = risk-free rate - the entire foundation of risk-free pricing
        self.price_simulations = S * np.exp((rf - 0.5 * sigma ** 2)*T + sigma * np.sqrt(T) * z)
    
    def price_result(self, payoffs):
        # discount to present time
        discounted_payoffs = payoffs * np.exp(-self.params.rf * self.params.T)
        # work out the average payoff amongst all simulations
        price = np.mean(discounted_payoffs)
        # standard error measures how wrong is the average likely going to be
        standard_error = np.std(discounted_payoffs) / np.sqrt(self.iterations)
        
        return price, standard_error
    
    def call_price(self) -> float:            
        payoffs = np.maximum(self.price_simulations - self.params.K, 0)
        return self.price_result(payoffs)
    
    def put_price(self):
        payoffs = np.maximum(self.params.K - self.price_simulations, 0)
        return self.price_result(payoffs)
    
def bs_call_price(params: MarketParams):
    S, K, T, rf, sigma = params.unpack()
    d1 = (np.log(S/K) + (rf + 0.5 * sigma ** 2) * (T)) / (sigma * np.sqrt(T))
    d2 = d1 - sigma * np.sqrt(T)
    return S*stats.norm.cdf(d1) - K*np.exp(-rf*(T))*stats.norm.cdf(d2)

def bs_put_price(params: MarketParams):
    S, K, T, rf, sigma = params.unpack()
    d1 = (np.log(S/K) + (rf + 0.5 * sigma ** 2) * (T)) / (sigma * np.sqrt(T))
    d2 = d1 - sigma * np.sqrt(T)
    return -S*stats.norm.cdf(-d1) + K*np.exp(-rf*(T))*stats.norm.cdf(-d2)