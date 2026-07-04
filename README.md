# Monte Carlo Pricer with validation harness

This is the starting point of a larger pricing engine in the works.

Currently, terminal prices are simulated with Monte Carlo, and the price of European calls and puts is validated against Black Scholes.

In future versions, I plan to support exotics, and also migrate to AWS.

## The maths
Under risk-neutral measure, we model the stock as GBM $dS_t=r_fS_tdt+\sigma S_t dW_t$.

Where $W_t$ is a [Wiener Process](https://sites.me.ucsb.edu/~moehlis/APC591/tutorials/tutorial7/node2.html).

Applying [Itô's Lemma](https://math.nyu.edu/~goodman/teaching/StochCalc2018/notes/Lesson4.pdf) to $\ln S_t$ gives

$d(\ln S_t) = (r_f-\frac{1}{2}\sigma^2)d_t+\sigma dW_t$. Integrating this gives

$S_T=S_0\exp[(r_f-\frac{1}{2}\sigma^2)T+\sigma W_T]$

The arbitrage-free price is the discounted risk-neutral expectation: $C = e^{-r_fT}\mathbb{E}[(S_T-K)^+]$.

Monte Carlo estimates this by averaging over draws of the standard normal $Z~\sim N(0,1)$ since $W_T\sim N(0,T)$ and $Z\sim N(0,1)$ so $W_T=\sqrt{T}Z$

Black-Scholes calculates the same expectation, but analytically, so gives an exact value for us to validate MC against.

### Asian Options

Phase 2 of this project I plan to support Asian options. These are path-dependent, meaning their payoff depends on not just the terminal price $S(T)$, but on intermediate prices as well. In particular, the payoff is $(\frac{S(1)+S(2)}{2}-K, 0)^+$. This results in the tree to not be recombining anymore, so using the binomial model to price these options in discrete time becomes very costly ($2^n$ nodes at level $n$ instead of $n+1$ now), which is where MC will prove useful.

## Parameters

`S0` is the spot price of the underlying e.g. `S0=100`

`K` is the strike price e.g. `K=100`

`T` is the time to maturity in years e.g. `T=1`

`rf` is the risk-free rate e.g. `rf=0.05`

`sigma` is the volatility e.g. `sigma=0.2`

`iterations` is the number of paths to simulate e.g. `iterations=100000`

`n` is the number of steps to break each path into e.g. `n=252`

`rng_seed` is an optional seed for reproducible simulations e.g. `rng_seed=42`

## Simulating full path vs just terminal price

To simulate a full path (rather than just the terminal price), the SDE is discretised into `n` steps of size $dt = T/n$:

$$S_t = S_{t-1}\exp\left((r_f-\frac{1}{2}\sigma^2)dt+\sigma\sqrt{dt}\,z_{t-1}\right)$$

Taking logs and unrolling the recursion:

$$
\begin{aligned}
\ln S_t &= \ln S_{t-1} + (r_f-\frac{1}{2}\sigma^2)dt+\sigma\sqrt{dt}\,z_{t-1} \\
&= \dots \\
&= \ln S_0 + (r_f-\frac{1}{2}\sigma^2)T+\sigma\sqrt{dt}(z_0+\dots+z_{t-1})
\end{aligned}
$$

Since the sum of independent Normals is Normal, with variance equal to the sum of the variances, summing all the $\sqrt{dt}\,z_t$ terms gives $\sqrt{T}z$. This recovers the same closed form used for the terminal price:

$$S_t=S_0\exp\left((r_f-\frac{1}{2}\sigma^2)T+\sigma\sqrt{T}z\right)$$

confirming that simulating step-by-step and jumping straight to the terminal price are consistent.

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
