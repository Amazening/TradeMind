"""The two statistical tests the patterns use, written with the standard library only."""

import math


def normal_upper_tail(z: float) -> float:
    """P(Z >= z) for a standard normal Z."""
    return 0.5 * math.erfc(z / math.sqrt(2))


def two_proportion_p_value(hits_a: int, total_a: int, hits_b: int, total_b: int) -> float | None:
    """One-sided p-value that proportion A is greater than proportion B (z-test, pooled).

    None if the test cannot be run, for example when no one in either group has the outcome.
    """
    if total_a == 0 or total_b == 0:
        return None
    pooled = (hits_a + hits_b) / (total_a + total_b)
    spread = math.sqrt(pooled * (1 - pooled) * (1 / total_a + 1 / total_b))
    if spread == 0:
        return None
    z = (hits_a / total_a - hits_b / total_b) / spread
    return normal_upper_tail(z)


def binomial_upper_tail(hits: int, trials: int, p: float) -> float:
    """P(X >= hits) for X ~ Binomial(trials, p), exact.

    Uses log-probabilities so large trial counts do not overflow.
    """
    if hits <= 0:
        return 1.0
    if hits > trials:
        return 0.0
    log_p, log_q = math.log(p), math.log(1 - p)
    log_n = math.lgamma(trials + 1)
    total = 0.0
    for k in range(hits, trials + 1):
        log_pmf = log_n - math.lgamma(k + 1) - math.lgamma(trials - k + 1)
        total += math.exp(log_pmf + k * log_p + (trials - k) * log_q)
    return min(total, 1.0)
