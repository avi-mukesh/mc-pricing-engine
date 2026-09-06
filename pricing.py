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
        self.z = None
        self.S0 = params.S0
        self.K = params.K
        self.T = params.T
        self.rf = params.rf
        self.sigma = params.sigma
        self.iterations = iterations
        
        self.rng = np.random.default_rng(rng_seed) if rng_seed is not None else np.random.default_rng()
        
    def price_paths_from_shocks(self, dt, z):
        return self.S0*np.exp(np.cumsum((self.rf-0.5*self.sigma**2)*dt+self.sigma*np.sqrt(dt)*z, axis=1))
    
    def simulate_price_paths(self, n: int = 252):
        dt = self.T/n
        z = self.rng.normal(0, 1, (self.iterations, n))
        return self.price_paths_from_shocks(dt, z)

    def simulate_terminal_prices(self):
        # simulate stock price at time T by simulating dS_t = \r_f*S_t*dt + \sigma * S_t * dW_t^Q
        # notice we are using risk neutral measure and using r_f instead of mu now
        # expected growth of asset = risk-free rate - the entire foundation of risk-free pricing
        z = self.rng.normal(0, 1, self.iterations)
        terminal = self.S0 * np.exp((self.rf - 0.5 * self.sigma ** 2)*self.T + self.sigma * np.sqrt(self.T) * z)
        return terminal, z

    def simulate_antithetic_price_paths(self, n: int = 252):
        dt = self.T/n
        z = self.rng.normal(0, 1, (self.iterations//2, n))
        paths_pos = self.price_paths_from_shocks(dt, z)
        paths_neg = self.price_paths_from_shocks(dt, -z)
        return paths_pos, paths_neg
    
    def price_result(self, payoffs):
        # discount to present time
        discounted_payoffs = payoffs * np.exp(-self.rf * self.T)
        # work out the average payoff amongst all simulations
        price = np.mean(discounted_payoffs)
        # standard error measures how wrong is the average likely going to be
        standard_error = np.std(discounted_payoffs) / np.sqrt(self.iterations)
        
        return price, standard_error
    
    def european_call_price(self, terminal):
        payoffs = np.maximum(terminal - self.K, 0)
        return self.price_result(payoffs)

    def european_put_price(self, terminal):
        payoffs = np.maximum(self.K - terminal, 0)
        return self.price_result(payoffs)
    
    # payoff of an asian call is max(avg price from history - K, 0)
    # so we don't just care about terminal price like a european, we care about all prices up to it
    def arithmetic_asian_call_price(self, paths):
        avg_price_by_path = paths.mean(axis=1)
        payoffs = np.maximum(avg_price_by_path - self.K, 0)
        return self.price_result(payoffs)
    
    def arithmetic_asian_put_price(self, paths):
        avg_price_by_path = paths.mean(axis=1)
        payoffs = np.maximum(self.K - avg_price_by_path, 0)
        return self.price_result(payoffs)
    
    def geometric_asian_call_price(self, paths):
        geometric_avg_price_by_path = np.sqrt(paths[:,0]*paths[:,1])
        payoffs = np.maximum(geometric_avg_price_by_path-self.K, 0)
        return self.price_result(payoffs)
    
    def arithmetic_asian_call_price_with_control_variate(self, paths, exact_geometric_price):
        avg_price_by_path = paths.mean(axis=1)
        arithmetic_asian_call_payoffs = np.maximum(avg_price_by_path - self.K, 0)
        
        geometric_avg_price_by_path = np.sqrt(paths[:,0]*paths[:,1])
        geometric_asian_call_payoffs = np.maximum(geometric_avg_price_by_path-self.K, 0)
        
        X = arithmetic_asian_call_payoffs
        Y = geometric_asian_call_payoffs
        
        beta = np.cov(X, Y)[0,1] / np.var(Y)
        Z = X - beta * (Y - exact_geometric_price*np.exp(self.rf*self.T))
    
        price, std_error = self.price_result(Z)
        return price, std_error, beta
    
    def arithmetic_asian_call_price_with_antithetic_variate(self, paths_pos, paths_neg):
        avg_price_by_path_pos = paths_pos.mean(axis=1)
        avg_price_by_path_neg = paths_neg.mean(axis=1)
        
        payoffs_pos = np.maximum(avg_price_by_path_pos - self.K, 0)
        payoffs_neg = np.maximum(avg_price_by_path_neg - self.K, 0)
        
        payoffs_avg = 0.5*(payoffs_pos+payoffs_neg)
        
        discounted_payoffs = payoffs_avg * np.exp(-self.rf * self.T)

        price = np.mean(discounted_payoffs)
        standard_error = np.std(discounted_payoffs) / np.sqrt(self.iterations//2)
        
        return price, standard_error
    
    def delta_using_pathwise_differentiation(self):
        paths = self.simulate_price_paths(2)
        ST = paths[:,-1]
        pathwise_samples = np.exp(-self.rf*self.T)*np.where(ST>self.K, ST/self.S0, 0)
        pathwise_delta = np.mean(pathwise_samples)
        std_error = np.std(pathwise_samples) / np.sqrt(self.iterations)
        return pathwise_delta, std_error
    
    def delta_using_likelihood_ratio(self):
        terminal, z = self.simulate_terminal_prices()
        payoffs = np.maximum(terminal - self.K, 0)
        likelihood_ratio_samples = (np.exp(-self.rf*self.T)*payoffs*z) / (self.S0 * self.sigma * np.sqrt(self.T))
        likelihood_ratio_delta = np.mean(likelihood_ratio_samples)
        std_error = np.std(likelihood_ratio_samples) / np.sqrt(self.iterations)
        return likelihood_ratio_delta, std_error
        
def bs_european_call_price(params: MarketParams):
    d1 = (np.log(params.S0/params.K) + (params.rf + 0.5 * params.sigma ** 2) * (params.T)) / (params.sigma * np.sqrt(params.T))
    d2 = d1 - params.sigma * np.sqrt(params.T)
    return params.S0*stats.norm.cdf(d1) - params.K*np.exp(-params.rf*(params.T))*stats.norm.cdf(d2)

def bs_european_put_price(params: MarketParams):
    d1 = (np.log(params.S0/params.K) + (params.rf + 0.5 * params.sigma ** 2) * (params.T)) / (params.sigma * np.sqrt(params.T))
    d2 = d1 - params.sigma * np.sqrt(params.T)
    return -params.S0*stats.norm.cdf(-d1) + params.K*np.exp(-params.rf*(params.T))*stats.norm.cdf(-d2)

def binomial_arithmetic_asian_call_price(params: MarketParams):
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

def bs_geometric_asian_call_price(params: MarketParams):
    dt = params.T/2
    m = (params.rf - 0.5*params.sigma**2)*dt
    s = params.sigma * np.sqrt(dt)
    
    mu_G = np.log(params.S0) + 1.5*m
    sigma_G = np.sqrt(1.25)*s
    
    d_2 = (mu_G - np.log(params.K))/sigma_G
    d_1 = d_2 + sigma_G
    
    E_G = np.exp(mu_G+0.5*sigma_G**2)

    return np.exp(-params.rf * params.T) * (E_G*stats.norm.cdf(d_1) - params.K*stats.norm.cdf(d_2))