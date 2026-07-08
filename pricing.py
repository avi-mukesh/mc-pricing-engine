from scipy import stats
import numpy as np

class MarketParams:
    def __init__(self, S0, K, T, rf, sigma):
        self.S0 = S0
        self.K = K
        self.T = T
        self.rf = rf
        self.sigma = sigma
    
class MonteCarloPricer:
    def __init__(self, params: MarketParams, iterations: int, rng_seed: int | None = None):
        self.S0 = params.S0
        self.K = params.K
        self.T = params.T
        self.rf = params.rf
        self.sigma = params.sigma
        self.iterations = iterations
        self.terminal_prices = None
        self.price_simulations = None
        
        self.rng = np.random.default_rng(rng_seed) if rng_seed is not None else np.random.default_rng()
        
    def simulate_price_paths(self, n: int = 252):
        if self.price_simulations is not None:
            return
        
        dt = self.T/n
        z = self.rng.normal(0, 1, (self.iterations, n))
        self.price_simulations = self.S0*np.exp(np.cumsum((self.rf-0.5*self.sigma**2)*dt+self.sigma*np.sqrt(dt)*z, axis=1))

    def simulate_terminal_prices(self):
        # simulate stock price at time T by simulating dS_t = \r_f*S_t*dt + \sigma * S_t * dW_t^Q
        # notice we are using risk neutral measure and using r_f instead of mu now
        # expected growth of asset = risk-free rate - the entire foundation of risk-free pricing
        if self.terminal_prices is not None:
            return
        
        z = self.rng.normal(0, 1, self.iterations)
        self.terminal_prices = self.S0 * np.exp((self.rf - 0.5 * self.sigma ** 2)*self.T + self.sigma * np.sqrt(self.T) * z)
    
    def price_result(self, payoffs):
        # discount to present time
        discounted_payoffs = payoffs * np.exp(-self.rf * self.T)
        # work out the average payoff amongst all simulations
        price = np.mean(discounted_payoffs)
        # standard error measures how wrong is the average likely going to be
        standard_error = np.std(discounted_payoffs) / np.sqrt(self.iterations)
        
        return price, standard_error
    
    def european_call_price(self) -> float:
        payoffs = np.maximum(self.terminal_prices - self.K, 0)
        return self.price_result(payoffs)

    def european_put_price(self):
        payoffs = np.maximum(self.K - self.terminal_prices, 0)
        return self.price_result(payoffs)

    # TODO: deduplicate some of the logic in these two methods
    def european_call_price_from_paths(self):
        terminal = np.array(self.price_simulations)[:, -1]
        mc_call_prices = np.exp(-self.rf*self.T)*np.maximum(terminal - self.K, 0)
        price = np.mean(mc_call_prices)
        std_error = np.std(mc_call_prices) / np.sqrt(self.iterations)
        return price, std_error

    def european_put_price_from_paths(self):
        terminal = np.array(self.price_simulations)[:, -1]
        mc_put_prices = np.exp(-self.rf*self.T)*np.maximum(self.K - terminal, 0)
        price = np.mean(mc_put_prices)
        std_error = np.std(mc_put_prices) / np.sqrt(self.iterations)
        return price, std_error
    
    # payoff of an asian call is max(avg price from history - K, 0)
    # so we don't just care about terminal price like a european, we care about all prices up to it
    def asian_call_price(self):
        avg_price_by_path = self.price_simulations.mean(axis=1)
        asian_payoffs = np.maximum(avg_price_by_path - self.K, 0)
        return self.price_result(asian_payoffs)
    
    def asian_put_price(self):
        avg_price_by_path = self.price_simulations.mean(axis=1)
        asian_payoffs = np.maximum(self.K - avg_price_by_path, 0)
        return self.price_result(asian_payoffs)

def bs_european_call_price(params: MarketParams):
    d1 = (np.log(params.S0/params.K) + (params.rf + 0.5 * params.sigma ** 2) * (params.T)) / (params.sigma * np.sqrt(params.T))
    d2 = d1 - params.sigma * np.sqrt(params.T)
    return params.S0*stats.norm.cdf(d1) - params.K*np.exp(-params.rf*(params.T))*stats.norm.cdf(d2)

def bs_european_put_price(params: MarketParams):
    d1 = (np.log(params.S0/params.K) + (params.rf + 0.5 * params.sigma ** 2) * (params.T)) / (params.sigma * np.sqrt(params.T))
    d2 = d1 - params.sigma * np.sqrt(params.T)
    return -params.S0*stats.norm.cdf(-d1) + params.K*np.exp(-params.rf*(params.T))*stats.norm.cdf(-d2)

def binomial_asian_call_price(params: MarketParams):
    dt = params.T/2
    
    u = np.exp(params.sigma*np.sqrt(dt)) - 1
    d = np.exp(-params.sigma*np.sqrt(dt)) - 1
    
    r = np.exp(params.rf*dt) - 1
    
    p_star = (r - d)/(u - d)
    
    S_u = params.S0 * (1+u)
    S_d = params.S0 * (1+d)
    
    S_uu = S_u * (1+u)
    S_ud = S_u * (1+d)
    S_dd = S_d * (1+d)
    
    C_uu = max((S_uu + S_u)/2 - params.K, 0)
    C_ud = max((S_ud + S_u)/2 - params.K, 0)
    C_du = max((S_ud + S_d)/2 - params.K, 0)
    C_dd = max((S_dd + S_d)/2 - params.K, 0)
    
    C_u = ((1+r)**(-1))*(p_star*C_uu + (1-p_star)*C_ud)
    C_d = ((1+r)**(-1))*(p_star*C_du + (1-p_star)*C_dd)
    
    return ((1+r)**(-1))*(p_star*C_u + (1-p_star)*C_d)

def binomial_european_call_price(params: MarketParams):
    dt = params.T/2
    
    u = np.exp(params.sigma*np.sqrt(dt)) - 1
    d = np.exp(-params.sigma*np.sqrt(dt)) - 1
    
    r = np.exp(params.rf*dt) - 1
    
    p_star = (r - d)/(u - d)
    
    S_u = params.S0 * (1+u)
    S_d = params.S0 * (1+d)
    
    S_uu = S_u * (1+u)
    S_ud = S_u * (1+d)
    S_dd = S_d * (1+d)
    
    C_uu = max(S_uu - params.K, 0)
    C_ud = max(S_ud - params.K, 0)
    C_du = C_ud
    C_dd = max(S_dd - params.K, 0)
    
    C_u = ((1+r)**(-1))*(p_star*C_uu + (1-p_star)*C_ud)
    C_d = ((1+r)**(-1))*(p_star*C_du + (1-p_star)*C_dd)
    
    return ((1+r)**(-1))*(p_star*C_u + (1-p_star)*C_d)