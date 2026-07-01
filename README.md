# Monte Carlo Pricer with validation harness

This is the starting point of a larger pricing engine in the works.

Currently, terminal prices are simulated with Monte Carlo, and the price of European calls and puts is validated against Black Scholes.

In future versions, I plan to support exotics, and also migrate to AWS.

## Validation

The main assertion is that Monte Carlo prices are within 2SE of that output Black Scholes (the true price).

By the CLT, the MC estimator converge to a Normal distribution with standard deviation $\sigma/\sqrt{N}$ where $\sigma$ is the std deviation of the individual discounted payoffs. Roughly 95% of runs land within 2SE of the true price.

## Checking put-call parity holds

Put-call parity is this identity $C - P = S_0 -Ke^{-r_fT}$.
It holds exactly for Black-Scholes (deterministic), but for MC it holds up to the sampling error in $mean(S_i)$:

$C$ and $P$ are means of discounted payoffs over the same paths.

$$
\begin{aligned}
C-P &= \frac{1}{N}\sum_{i=1}^N(e^{-r_fT}(S_i-K)^+) - \frac{1}{N}\sum_{i=1}^N(e^{-r_fT}(K-S_i)^+) \\
&= e^{-r_fT}\frac{1}{N}\sum_{i=1}^N((S_i-K)^+-(K-S_i)^+) && \text{( because same paths)} \\
&= e^{-r_fT}\frac{1}{N}\sum_{i=1}^N(S_i-K) \\
&= e^{-r_fT}\frac{1}{N}\sum_{i=1}^N S_i-Ke^{-r_fT}
\end{aligned}
$$

Hence

$$
\begin{aligned}
C-P-S_0+Ke^{-r_fT} &= e^{-r_fT}\frac{1}{N}\sum_{i=1}^N S_i-Ke^{-r_fT} - S_0 + Ke^{-r_fT} \\
&= e^{-r_fT}\frac{1}{N}\sum_{i=1}^N S_i - S_0
\end{aligned}
$$

So the put-call parity in this case is basically checking how close $e^{-r_fT}\frac{1}{N}\sum_{i=1}^N S_i$, the discounted mean, gets to $S_0$

This is why we use standard error of the discounted final prices in the put-call parity assertion.
