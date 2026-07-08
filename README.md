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

Asian options are path-dependent, meaning their payoff depends on not just the terminal price $S(T)$, but on intermediate prices as well. In particular, the payoff is $(\frac{S(1)+\dots+S(N)}{N}-K)^+$. This results in the tree to not be recombining anymore, so using the binomial model to price these options in discrete time becomes very costly ($2^n$ distinct paths to track at level $n$ instead of $n+1$ now), which is where MC will prove useful.

For validating the Asian option pricer, I use the two-step binomial model in the case we only have $N=2$ timesteps. The binomial model takes $u$, $d$ as inputs (two possible simple returns e.g. 3% and -5%), rather than $\sigma$.

To make the translation, let $M$ be a two-point random variable, representing the log return, taking values $\ln(1+u)$ and $\ln(1+d)$ with probabilities $p$ and $1-p$ respectively. The log return over one step in GBM is $$\ln(\frac{S_{t+dt}}{S_t}) = (r-\frac{1}{2}\sigma^2)dt+\sigma\sqrt{dt}z$$

which is $N((r-\frac{1}{2}\sigma^2)dt, \sigma^2dt)$. So equate $Var(M) = \sigma^2dt$ and simplify to get $$p(1-p)(\ln(1+u)-\ln(1+d))^2=\sigma^2dt$$

Also set up an equation relating the mean. We equate the expected growth factor from one step of the binomial model to the expected growth factor over $dt$ in GBM. Expected growth factor from one step of the binomial model is $$p(1+u)+(1-p)(1+d)$$ and expected growth factor over $dt$ in GBM is $\mathbb{E}[\frac{S_{t+dt}}{S_t}]=\mathbb{E}[\exp((r-\frac{1}{2}\sigma^2)dt+\sigma\sqrt{dt}z)]$ which can be calculated (noting that it is the [M.G.F](https://www.le.ac.uk/users/dsgp1/COURSES/MATHSTAT/6normgf.pdf) of a Normal distribution evaluated at $t=1$) to give $$\exp((r-\frac{1}{2}\sigma^2)dt+\frac{1}{2}\sigma^2dt) = e^{rdt}$$ Equating the two expected growth factors gives $$p(1+u)+(1-p)(1+d)=e^{rdt}$$ So far we only have 2 equations but 3 unknowns ($u, d, p$) so we need to impose a third condition. We can choose this freely because it won't matter for convergence in the limit, so let's constrain $$(1+u)(1+d)=1 \implies \ln(1+u)=-\ln(1+d)$$ as this recombines the tree symmetrically. Substitute this into first equation to get $$4p(1-p)(\ln(1+u))^2=\sigma^2dt$$

CRR defines $\ln(1+u)=\sigma\sqrt{dt}$ so $u=e^{\sigma\sqrt{dt}}-1$, and $d=e^{-\sigma\sqrt{dt}}-1$. This means the variance equation is no longer solved exactly. The mean equation forces $p=\frac{1}{2}+O(\sqrt{dt})$ so $4p(1-p)=1-O(dt)$ and the variance is matched only up to an $O(dt^2)$ error per step. Over $N=T/dt$ steps these errors total $O(dt)$, which vanishes in the limit.

With $(u,d,p)$ calibrated to $\sigma$, both models share the same per-step mean and variance. But they do **not** sample the same distribution: MC draws the exact lognormal step, whereas the tree replaces it with a two-point approximation. So at $n=2$ the tree also carries discretation error and is not an exact anchor.

I confirmed this directly by pricing a vanilla European on the same 2-step tree to get $\approx 9.5$ against a Black–Scholes value of $10.451$, which is a significant gap on an option that has already been validated. The tree is therefore a *convergent* check only. As its step count increases (averaging still at the two monitoring dates), its Asian price should converge to the MC value. For an exact anchor I instead use the geometric-average Asian, whose closed form is derived below.


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
