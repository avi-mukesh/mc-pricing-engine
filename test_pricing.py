import pricing


params = pricing.MarketParams(100, 120, 1, 0.02, 0.03)


mc_pricer = pricing.MonteCarloPricer()
bs_pricer = pricing.MonteCarloPricer()