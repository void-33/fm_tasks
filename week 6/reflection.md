# Reflection: Bayesian vs. MLE Decision Making

## One Concrete Example Where the Fully Bayesian Answer Changed a Decision I Would Have Made Using Only the MLE

In Part 2 (Q6), I analyzed whether the overall churn rate exceeded 0.25 — a business threshold the VP uses to trigger a retention campaign.

The MLE approach relies on a frequentist one-proportion z-test, which the notebook computes requires **n = 6,304 observations** before the result reaches statistical significance. For the first 6,303 customers, a frequentist analyst has no formal basis for action.

The sequential Bayesian update told a dramatically different story. Starting from a `Beta(2, 8)` prior encoding the historical belief that churn is typically below 30%, I updated the posterior one customer at a time using `update_posterior()`. I then computed P(θ > 0.25) at each step via Monte Carlo sampling from the current posterior. The posterior probability crossed the 90% decision threshold at **n = 17** — after only 17 observations, and **6,287 observations earlier** than the frequentist approach required.

The mechanism behind this difference is **sequential evidence incorporation with explicit uncertainty quantification**. Rather than waiting until a fixed sample size is reached, the Bayesian framework allows the decision threshold to be crossed as soon as the posterior probability — a direct, interpretable statement of belief — reaches 90%. There is no need for a p-value or a pre-committed sample size. The prior acts as a calibrated starting point that the data progressively overrides, compressing the evidence requirement by orders of magnitude.

The decision this changed: under MLE, I would have told the VP *"we don't have enough data yet"* for the first 6,303 customers. Under the Bayesian framework, I could have recommended triggering the retention campaign after just 17 observations, acting on real evidence rather than waiting for a sample size that may never be reached in a new customer segment — precisely the situation the VP described with the 40-customer contract tier.
