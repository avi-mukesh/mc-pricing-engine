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

Asian options are path-dependent, meaning their payoff depends on not just the terminal price $S(T)$, but on intermediate prices as well. In particular, the payoff is $\left(\frac{S(1)+\dots+S(N)}{N}-K\right)^+$. This results in the tree to not be recombining anymore, so using the binomial model to price these options in discrete time becomes very costly ($2^n$ distinct paths to track at level $n$ instead of $n+1$ now), which is where MC will prove useful.

For validating the Asian option pricer, I use the two-step binomial model in the case we only have $N=2$ timesteps. The binomial model takes $u$, $d$ as inputs (two possible simple returns e.g. 3% and -5%), rather than $\sigma$.

To make the translation, let $M$ be a two-point random variable, representing the log return, taking values $\ln(1+u)$ and $\ln(1+d)$ with probabilities $p$ and $1-p$ respectively. The log return over one step in GBM is $$\ln\left(\frac{S_{t+dt}}{S_t}\right) = \left(r-\frac{1}{2}\sigma^2\right)dt+\sigma\sqrt{dt}z$$

which is $N\left(\left(r-\frac{1}{2}\sigma^2\right)dt, \sigma^2dt\right)$. So equate $\mathrm{Var}(M) = \sigma^2dt$ and simplify to get $$p(1-p)(\ln(1+u)-\ln(1+d))^2=\sigma^2dt$$

Also set up an equation relating the mean. We equate the expected growth factor from one step of the binomial model to the expected growth factor over $dt$ in GBM. Expected growth factor from one step of the binomial model is $$p(1+u)+(1-p)(1+d)$$ and expected growth factor over $dt$ in GBM is $\mathbb{E}[\frac{S_{t+dt}}{S_t}]=\mathbb{E}\left[\exp\left(\left(r-\frac{1}{2}\sigma^2\right)dt+\sigma\sqrt{dt}z\right)\right]$ which can be calculated (noting that it is the [M.G.F](https://www.le.ac.uk/users/dsgp1/COURSES/MATHSTAT/6normgf.pdf) of a Normal distribution evaluated at $t=1$) to give $$\exp\left(\left(r+\frac{1}{2}\sigma^2\right)dt+\frac{1}{2}\sigma^2dt\right) = e^{rdt}$$ Equating the two expected growth factors gives $$p(1+u)+(1-p)(1+d)=e^{rdt}$$ So far we only have 2 equations but 3 unknowns ($u, d, p$) so we need to impose a third condition. We can choose this freely because it won't matter for convergence in the limit, so let's constrain $$(1+u)(1+d)=1 \implies \ln(1+u)=-\ln(1+d)$$ as this recombines the tree symmetrically. Substitute this into first equation to get $$4p(1-p)(\ln(1+u))^2=\sigma^2dt$$

CRR defines $\ln(1+u)=\sigma\sqrt{dt}$ so $u=e^{\sigma\sqrt{dt}}-1$, and $d=e^{-\sigma\sqrt{dt}}-1$. This means the variance equation is no longer solved exactly. The mean equation forces $p=\frac{1}{2}+O(\sqrt{dt})$ so $4p(1-p)=1-O(dt)$ and the variance is matched only up to an $O(dt^2)$ error per step. Over $N=T/dt$ steps these errors total $O(dt)$, which vanishes in the limit.

With $(u,d,p)$ calibrated to $\sigma$, both models share the same per-step mean and variance. But they do **not** sample the same distribution: MC draws the exact lognormal step, whereas the tree replaces it with a two-point approximation. So at $n=2$ the tree also carries discretation error and is not an exact anchor.

I confirmed this directly by pricing a vanilla European on the same 2-step tree to get $\approx 9.541$ against a Black–Scholes value of $10.451$, which is a significant gap on an option that has already been validated. The tree is therefore a *convergent* check only. As its step count increases (averaging still at the two monitoring dates), its Asian price should converge to the MC value. In next section, we look at geometric Asians, for which there is an exact closed-form anchor we can derive and use.

### Geometric Asian
Setting $m=(r-\frac{1}{2}\sigma^2)dt$ and $s=\sigma\sqrt{dt}$.

Writing the log-prices in terms of the independent shocks $Z_1$ and $Z_2$ we get
$$\ln (S(1)) = \ln(S_0) + m + sZ_1$$
$$\ln (S(2)) = \ln(S_0) + 2m + sZ_1+sZ_2$$

Geometric average is $G=\sqrt{S(1)S(2)}$. So

$$
\begin{aligned}
\ln(G) &= \tfrac{1}{2}\big(\ln(S(1))+\ln(S(2))\big) \\
&= \tfrac{1}{2}\big(\ln(S_0) + m + sZ_1+\ln(S_0) + 2m + sZ_1+sZ_2\big) \\
&= \ln(S_0)+\tfrac{3}{2}m+sZ_1+\tfrac{1}{2}sZ_2
\end{aligned}
$$

So $\ln(G)$ is Normal with

$$\mu_G = \mathbb{E}[\ln(G)]=\ln(S_0)+\frac{3}{2}m$$

$$\sigma_G^2 = Var[\ln(G)]=s^2+\left(\frac{1}{2}s\right)^2=\frac{5}{4}s^2$$

After a bit of algebra (like calculating M.G.F at t=1) we get

$$\mathbb{E}[G]=\mathbb{E}[e^{\ln(G)}] = \dots = S_0e^{\left(\frac{3}{2}r-\frac{1}{8}\sigma^2\right)dt}$$

Notice the drift here is $\frac{3}{2}rdt$, not $rdt$. $G$ is not a tradeable asset, so no-arbitrage does not force it to grow at the risk-free rate. It's drift is simply what the averaging produces. This is why we cannot use BS with an effective volatility, and must instead evaluate

$$\mathbb{E}[e^{-rT}(G-K)^+]$$

directly, with $G$'s actual mean and variance both plugged in.

To evaluate this

$$
\begin{aligned}
\mathbb{E}[(G-K)^+] &= \int_{\ln(K)}^\infty (e^x-K)\,\phi(x; \mu_G, \sigma_G^2)\,dx \\
&= \int_{\ln(K)}^\infty e^x\phi(x; \mu_G, \sigma_G^2)\,dx \;-\; K\int_{\ln(K)}^\infty \phi(x; \mu_G, \sigma_G^2)\,dx
\end{aligned}
$$

**Second term**: $-KP[X>\ln(K)]$ where $X\sim N(\mu_G, \sigma_G^2)$.

Standardise $Z=\frac{X-\mu_G}{\sigma_G}\sim N(0,1)$, so

$$
\begin{aligned}
P[X>\ln(K)] &= P\left[Z>\tfrac{\ln(K)-\mu_G}{\sigma_G}\right] \\
&= 1-N\left(\tfrac{\ln(K)-\mu_G}{\sigma_G}\right) \\
&= N\left(\tfrac{\mu_G - \ln(K)}{\sigma_G}\right)
\end{aligned}
$$

Define $d_2 = \frac{\mu_G - \ln(K)}{\sigma_G}$, so the second term is $-KN(d_2)$.

**First term**: Writing the Normal pdf $e^x\phi(x;\mu_G, \sigma_G^2) = \frac{1}{\sqrt{2\pi\sigma_G^2}} e^{x-\frac{1}{2}(\frac{x-\mu_G}{\sigma_G})^2}$

In the exponent, expanding and then completing the square gives $-\frac{(x-(\mu_G+\sigma_G^2))^2}{2\sigma_G^2}+\frac{1}{2}\sigma_G^2+\mu_G$

So

$$
\begin{aligned}
e^x\phi(x;\mu_G, \sigma_G^2) &=\frac{1}{\sqrt{2\pi\sigma_G^2}}\exp\left(\mu_G+\frac{1}{2}\sigma_G^2-\frac{(x-(\mu_G+\sigma_G^2))^2}{2\sigma_G^2}\right) \\
&= e^{\mu_G+\frac{1}{2}\sigma_G^2}\phi(x;\mu_G+\sigma_G^2, \sigma_G^2)
\end{aligned}
$$

Also notice that $e^{\mu_G+\frac{1}{2}\sigma_G^2}=\mathbb{E}[G]$

So

$$
\begin{aligned}
\int_{\ln(K)}^\infty e^x\phi(x; \mu_G, \sigma_G^2)\,dx &= \int_{\ln(K)}^\infty \mathbb{E}[G]\phi(x; \mu_G+\sigma_G^2, \sigma_G^2)\,dx \\
&= \mathbb{E}[G]P[X'>\ln(K)] 
\end{aligned}
$$

Where $X'\sim N(\mu_G+\sigma_G^2, \sigma_G^2)$.

Standardising $X'$ as before, this probability becomes

$$
\begin{aligned}
P\left[Z>\frac{\ln(K)-(\mu_G+\sigma_G^2)}{\sigma_G}\right] &= 1 - N\left(\frac{\ln(K)-(\mu_G+\sigma_G^2)}{\sigma_G}\right) \\
&= N\left(\frac{(\mu_G+\sigma_G^2)-\ln(K)}{\sigma_G}\right)
\end{aligned}
$$

Define $d_1 = \frac{(\mu_G+\sigma_G^2)-\ln(K)}{\sigma_G}$, which conveniently equals $d_2+\sigma_G$ so first term is $\mathbb{E}[G]N(d_1)$

Overall, for $n=2$ we finally have the price formula

$$e^{-rT}(\mathbb{E}[G]N(d_1)-KN(d_2))$$

### Control Variate

A control variate needs two properties: its expectation must be known exactly, and it must be strongly correlated with the target. We know the price of the geometric option exactly (derived above) and since both the arithmetic Asian and geometric Asian use the same price path, their prices are correlated. This lets us build a lower variance estimator for the arithmetic Asian.

If $X$ and $Y$ are random variables representing payoffs of the arithmetic and geometric Asian, respectively, then let $Z = X - \beta(Y-\mathbb{E}[Y])$. Then this is an unbiased estimator (as $\mathbb{E}[Z] = \mathbb{E}[X]$) for any $\beta$. We choose $\beta$ that minimises $\mathrm{Var}(Z) = \mathrm{Var}(X)-2\beta \mathrm{Cov}(X,Y)+\beta^2\mathrm{Var}(Y)$. Minimising gives $\beta=\frac{\mathrm{Cov}(X,Y)}{\mathrm{Var}(Y)}$, which gives $\mathrm{Var}(Z) = \mathrm{Var}(X)(1-\rho^2)$. The standard error from the Monte Carlo estimate for Asian price was 0.0359. In the code, we measure $\rho=0.9996$, giving $1-\rho^2 \approx 0.0008$. So the standard error in the estimate from the control variate will be $\approx \sqrt{0.0008} \approx 0.0283 \approx \frac{1}{35}$ times the standard error, which it is - the standard error in this estimate is $\approx 0.0010$. The price of the arithmetic Asian using the Monte Carlo simulation gives 8.107, whereas the price using the control variate gives 8.112. We have $\bar{X} - \bar{Z} = \beta(\bar{Y}-\mathbb{E}[Y])$, so the two estimators differ by exactly $\beta$ times the control's own sampling error.

### Antithetic Variate

Antithetic variates exploit the symmetry of the Normal distribution. If $Z$ is a valid draw, then so is $-Z$. Rather than simulating $N$ independent paths, we simulate $\frac{N}{2}$ and pair each with its mirror, averaging the two payoffs. Unlike the control variate, where we needed the price of a geometric Asian, this requires no outside knowledge. We only need the fact that the Normal distribution is symmetric.

Let $f$ represent the arithmetic call payoff as a function of the shocks $Z$. Since $f(Z)$ and $f(-Z)$ have the same distribution

$$
\begin{aligned}
\mathrm{Var}(\frac{1}{2}(f(Z)+f(-Z))) &= \frac{1}{4}\mathrm{Var}(f(Z))+\frac{1}{4}\mathrm{Var}(f(-Z))+\frac{1}{2}\mathrm{Cov}(f(Z), f(-Z)) \\
&= \frac{1}{2}\mathrm{Var}(f(Z)) + \frac{1}{2}\rho \mathrm{Var}(f(Z)) \\
&= \frac{1}{2}\mathrm{Var}(f(Z))(1+\rho)
\end{aligned}
$$

Where $\rho = \mathrm{corr}(f(Z), f(-Z))$.

This is the variance of a single pair-average, not of the estimator. To compare estimators fairly, hold the total number payoff evaluations fixed at $N$. The plain estimator averages $N$ independent draws, whereas the antithetic one averages $\frac{N}{2}$ independent pairs. So, writing $\mathrm{Var}(f)$ for $\mathrm{Var}(f(Z))$, $$\frac{SE_{\text{antithetic}}}{SE_{\text{plain}}} = \frac{\frac{\sqrt{\frac{1}{2}\mathrm{Var}(f)(1+\rho)}}{\sqrt{\frac{N}{2}}}}{\frac{\sqrt{\mathrm{Var}(f)}}{\sqrt{N}}} = \sqrt{\frac{\frac{1}{2}\mathrm{Var}(f)(1+\rho)}{\mathrm{Var}(f)}}\cdot\sqrt{2} = \sqrt{1+\rho}$$

So $\rho<0$ reduces the error, $\rho=0$ does nothing, and $\rho>0$ makes it worse.

We measure $\rho=-0.5173$, predicting $SE_{antithetic} = 0.0356\sqrt{1-0.5173} \approx 0.0247$. The simulation gives $0.0248$, a reduction by factor of $\approx 1.44$, which is modest compared to the variance reduction obtained from the control variate previously.

### Summary of results for arithmetic Asian

| Estimator | Price | Standard error | Reduction |
|---|---|---|---|
| Plain MC | 8.107 | 0.0356 | - |
| Control Variate | 8.112 | 0.0010 | 35x |
| Antithetic Variate | 8.107 | 0.0248 | 1.44x |

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

$$S_t = S_{t-1}\exp\left(\left(r_f-\frac{1}{2}\sigma^2\right)dt+\sigma\sqrt{dt}\,z_{t-1}\right)$$

Taking logs and unrolling the recursion:

$$
\begin{aligned}
\ln S_t &= \ln S_{t-1} + \left(r_f-\frac{1}{2}\sigma^2\right)dt+\sigma\sqrt{dt}\,z_{t-1} \\
&= \dots \\
&= \ln S_0 + \left(r_f-\frac{1}{2}\sigma^2\right)T+\sigma\sqrt{dt}(z_0+\dots+z_{t-1})
\end{aligned}
$$

Since the sum of independent Normals is Normal, with variance equal to the sum of the variances, summing all the $\sqrt{dt}\,z_t$ terms gives $\sqrt{T}z$. This recovers the same closed form used for the terminal price:

$$S_t=S_0\exp\left(\left(r_f-\frac{1}{2}\sigma^2\right)T+\sigma\sqrt{T}z\right)$$

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
C-P &= \frac{1}{N}\sum_{i=1}^N\left(e^{-r_fT}(S_i-K)^+\right) - \frac{1}{N}\sum_{i=1}^N\left(e^{-r_fT}(K-S_i)^+\right) \\
&= e^{-r_fT}\frac{1}{N}\sum_{i=1}^N\left((S_i-K)^+-(K-S_i)^+\right) && \text{(because same paths)} \\
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

## Convergence
Let $\sigma_{\text{payoffs}}$ represent the standard deviation of the discounted payoffs. Since $SE_{\text{payoffs}} = \frac{\sigma_{\text{payoffs}}}{\sqrt{N}}$, taking logs gives $\log(SE_{\text{payoffs}})=\log(\sigma_{\text{payoffs}})-0.5\log(N)$. So plotting log of the standard errors against log of the number of simulations, we get a straight line with gradient $-0.5$ and intercept $\log(\sigma_{\text{payoffs}})$. Plotting for $N=10^3, 10^4, 10^5, 10^6$ simulations, we get a gradient of -0.4959, and an estimate for $\sigma_{\text{payoffs}}$ of 13.9374.

The downside of Monte Carlo simulations is the slow convergence. Halving the error requires quadrupling the number of iterations. This is why variance reduction matters. The control variate's 35x improvement would have required 1225x more simulations to achieve by brute force.


![Plot of log(SE) against log(N)](/convergence.png)

## Greeks

### Finding delta analytically

Delta measures the rate of change of the price of the option with respect to a move in the underlying asset.
$$\Delta = \frac{\partial C}{\partial S_0}$$

From Black-Scholes $C=S_0N(d_1)-Ke^{-rT}N(d_2)$, analytically we have as an anchor $\Delta = N(d_1)$. To verify this, write

$$\frac{\partial C}{\partial S_0} = N(d_1) + S_0N'(d_1)\frac{\partial d_1}{\partial S_0} - Ke^{-rT}N'(d_2)\frac{\partial d_2}{\partial S_0}$$

Since we have

$$d_1 = \frac{\log\left(\frac{S_0}{K}\right)+(r_f+0.5\sigma^2)T}{\sigma\sqrt{T}}
\qquad \text{and} \qquad d_2 = d_1 - \sigma\sqrt{T}$$

the two partials are equal $\frac{\partial d_1}{\partial S_0} = \frac{\partial d_2}{\partial S_0}$. So just need to ensure that $S_0N'(d_1) = Ke^{-rT}N'(d_2)$. We have $N'(x) = \frac{1}{\sqrt{2\pi}}e^{-\frac{1}{2}x^2}$ so

$$
\begin{aligned}
Ke^{-r_fT}N'(d_2) &= Ke^{-r_fT}N'(d_1-\sigma\sqrt{T}) \\
&= Ke^{-r_fT}\frac{1}{\sqrt{2\pi}}e^{-\frac{1}{2}(d_1-\sigma\sqrt{T})^2} \\
&= \frac{K}{\sqrt{2\pi}}e^{-\frac{1}{2}d_1^2+d_1\sigma\sqrt{T}-\frac{1}{2}\sigma^2T-r_fT} \\
&= S_0\frac{1}{\sqrt{2\pi}}e^{-\frac{1}{2}d_1^2}\cdot \frac{K}{S_0}e^{d_1\sigma\sqrt{T}-\frac{1}{2}\sigma^2T-r_fT} \\
&= S_0N(d_1)\exp\left(\ln\left(\frac{K}{S_0}\right)+d_1\sigma\sqrt{T}-\frac{1}{2}\sigma^2T-r_fT\right)
\end{aligned}
$$

Substituting in for $d_1$, the expression in the exponent becomes

$$\ln\left(\frac{K}{S_0}\right)+\left(\frac{\log\left(\frac{S_0}{K}\right)+\left(r_f+\frac{1}{2}\sigma^2\right)T}{\sigma\sqrt{T}}\right)\sigma\sqrt{T}-\frac{1}{2}\sigma^2T-r_fT = 0.$$

Hence $S_0N'(d_1) = Ke^{-rT}N'(d_2)$, so the last two terms in the expansion of $\frac{\partial C}{\partial S_0}$ above cancel, and $\Delta = N(d_1)$.

### Finding delta numerically

We can estimate $\Delta$ numerically using a finite difference approach, by pricing the option at $S_0$ and at $S_0+h$, then

$$\Delta \approx \frac{C(S_0+h)-C(S_0)}{h}$$

This is the definition of the derivative, with the limit stopped short. The choice of $h$ is a tradeoff as shown in the below table. By common random numbers (CRN), we mean the same $Z$ shocks have been used to simulate both $C(S_0)$ and $C(S_0+h)$ so that the two price estimates share their Monte Carlo noise and it largely cancels in the subtraction. Without CRN, each price carries independent noise of size $SE\approx 0.046$, so their difference has standard deviation $SE\sqrt{2}\approx 0.065$. This is then divided by $h$, amplifying delta without bound as $h\to 0$.

**With common random numbers:**

| $h$ | $C(S_0+h)-C(S_0)$ | $\Delta$ |
|---|---|---|
| 0.1 | 0.0637 | 0.6368 |
| 0.01 | 0.0064 | 0.6359 |
| 0.001 | 0.0006 | 0.6358 |
| 0.0001 | 0.0001 | 0.6358 |

**With independent random numbers:**

| $h$ | $C(S_0+h)-C(S_0)$ | $\Delta$ |
|---|---|---|
| 0.1 | 0.2127 | 2.1271 |
| 0.01 | 0.1550 | 15.4961 |
| 0.001 | 0.1492 | 149.1929 |
| 0.0001 | 0.1486 | 1486.1619 |

Exact value: $\Delta = N(d_1) = 0.6368$. All runs at $N = 100{,}000$ paths, $C(S_0) = 10.4363$.

The numerator column $C(S_0+h)-C(S_0)$ shows that under CRN, the price difference shrinks with $h$, as a genuine derivative should, and the ratio stays near $0.636$ throughout. Under independent draws the difference instead converges to a constant $\approx 0.149$ - the fixed discrepancy between what the two seeds happen to price. As $h \to 0$ the real signal vanishes but that constant does not, so the estimate grows by a factor of ten each time $h$ decreases by a factor of ten.

Measuring this directly: over 50 independent seed pairs at $h = 0.01$, the estimated $\Delta$ has standard deviation $6.63$, against a predicted standard deviation of $\frac{SE\sqrt{2}}{h} \approx 6.5$. The estimator is roughly ten times noisier than the quantity it estimates.

The small drift under CRN from $0.6368$ to $0.6358$ is the forward-difference bias vanishing as $h \to 0$; the residual gap to the exact value is Monte Carlo error in the price *level*, which CRN cannot remove (the MC price 10.4363 isn't the true 10.4506) — it cancels noise in the *difference*, not in either price individually.

So the trade-off is asymmetric. Too large an $h$ introduces $O(h)$ bias; too small an $h$ amplifies noise. With CRN, bias dominates and small $h$ is safe. Without CRN, variance dominates and there is a floor below which $h$ cannot usefully go. Common random numbers are not an optimisation here — they are what makes finite-difference Greeks viable at all.

### Pathwise Greeks
From the definition of call price $C=e^{-rT}\mathbb{E}[\text{payoff}]$ so from the definition of delta,

$$\Delta = e^{-rT}\mathbb{E}\left[\frac{\partial}{\partial S_0}\text{payoff}\right]$$

By the chain rule, $$\frac{\partial}{\partial S_0}\text{payoff} = \frac{\partial}{\partial S_T}\text{payoff}\cdot\frac{\partial S_T}{\partial S_0}$$

$\frac{\partial S_T}{\partial S_0}$ is simply $\exp\left((r_f-\frac{1}{2}\sigma^2)T+\sigma W_T\right) = \frac{S_T}{S_0}$ and since payoff is $\max(S_T-K, 0)$, we have

$$
\frac{\partial}{\partial S_T}\text{payoff} = \begin{cases}
			1, & \text{if $S_T>K$}\\
            0, & \text{if $S_T<K$}
		 \end{cases}
$$

So 

$$
\frac{\partial}{\partial S_0}\text{payoff} = \begin{cases}
			\frac{S_T}{S_0}, & \text{if $S_T>K$}\\
            0, & \text{if $S_T<K$}
		 \end{cases}
$$

So

$$
\mathbb{E}\left[\frac{\partial}{\partial S_0}\text{payoff}\right] = \mathbb{E}\left[\frac{S_T}{S_0}1_{\{S_T>K\}}\right]
$$

So $$\Delta = e^{-rT}\mathbb{E}\left[\frac{S_T}{S_0}1_{\{S_T>K\}}\right]$$

Using this method to estimate $\Delta$ we obtain 0.6358, which is close to the exact 0.6358.

The biggest downside of this method is that for a digital payoff, $\frac{\partial}{\partial S_0}\text{payoff} = 0$, so this estimator concludes $\Delta=0$ which is completely incorrect. In the case of a call option, the derivative is undefined at $S_T=K$, which is a measure-zero set, so there is no harm there. But for a digital option, the discontinuity is where the sensitivity of the option to $S_0$ lives, so it can't be ignored. 

Note that this rederives the BS delta

Letting $X=\ln(S_T)$, so that $X$ is Normal with mean $\mu=\ln(S_0)+\left(r-\frac{1}{2}\sigma^2\right)T$ and variance $\nu=\sigma^2 T$ the expectation is 

$$\int_{\ln(K)}^{\infty}e^x\phi(x;\mu,\nu)\,dx$$

This is exactly the integral we evaluated in the section Geometric Asian, just with different parameters. The result is

$$e^{\mu+\frac{1}{2}\nu}N\left(\frac{(\mu+\nu)-\ln(K)}{\sqrt{\nu}}\right)$$

Substituting back in $\mu$ and $\nu$ we get 

$$e^{\ln(S_0)+\left(r-\frac{1}{2}\sigma^2\right)T+\frac{1}{2}\sigma^2 T}N\left(\frac{\ln(S_0)+\left(r-\frac{1}{2}\sigma^2\right)T+\sigma^2 T-\ln(K)}{\sigma\sqrt{T}}\right)$$

$$ = e^{\ln(S_0)+rT}N\left(\frac{\ln(S_0)+\left(r+\frac{1}{2}\sigma^2\right)T -\ln(K)}{\sigma\sqrt{T}}\right)$$

$$ = S_0e^{rT}N\left(\frac{\ln\left(\frac{S_0}{K}\right)+\left(r+\frac{1}{2}\sigma^2\right)T}{\sigma\sqrt{T}}\right)$$

So $$\frac{e^{-rT}}{S_0}\mathbb{E}[S_T1_{S_T>K}] = N\left(\frac{\ln\left(\frac{S_0}{K}\right)+\left(r+\frac{1}{2}\sigma^2\right)T}{\sigma\sqrt{T}}\right) = N(d_1)$$ as required.

Next up: likelihood ratio