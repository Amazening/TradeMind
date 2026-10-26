import pytest

from trademind.analysis.stats import (
    binomial_upper_tail,
    normal_upper_tail,
    two_proportion_p_value,
)


def test_normal_tail_known_values() -> None:
    assert normal_upper_tail(0) == pytest.approx(0.5)
    assert normal_upper_tail(1.6448536) == pytest.approx(0.05, abs=1e-6)
    assert normal_upper_tail(-1.6448536) == pytest.approx(0.95, abs=1e-6)


def test_two_proportions_equal_groups_give_one_half() -> None:
    assert two_proportion_p_value(10, 100, 10, 100) == pytest.approx(0.5)


def test_two_proportions_bigger_first_group_gives_a_small_p() -> None:
    p = two_proportion_p_value(40, 100, 10, 100)

    assert p is not None
    assert p < 0.0001


def test_two_proportions_smaller_first_group_gives_a_large_p() -> None:
    p = two_proportion_p_value(10, 100, 40, 100)

    assert p is not None
    assert p > 0.999


def test_two_proportions_cannot_run_without_data_or_variation() -> None:
    assert two_proportion_p_value(0, 0, 1, 5) is None
    assert two_proportion_p_value(0, 10, 0, 10) is None
    assert two_proportion_p_value(10, 10, 10, 10) is None


def test_binomial_tail_known_values() -> None:
    assert binomial_upper_tail(0, 10, 0.1) == 1.0
    assert binomial_upper_tail(1, 10, 0.1) == pytest.approx(1 - 0.9**10)
    assert binomial_upper_tail(10, 10, 0.1) == pytest.approx(1e-10)
    assert binomial_upper_tail(11, 10, 0.1) == 0.0


def test_binomial_tail_matches_a_hand_sum() -> None:
    # P(X >= 8) for 10 trials at p = 0.5 is (45 + 10 + 1) / 1024.
    assert binomial_upper_tail(8, 10, 0.5) == pytest.approx(56 / 1024)


def test_binomial_tail_handles_many_trials() -> None:
    p = binomial_upper_tail(300, 2000, 0.1)

    assert 0.0 <= p <= 1.0
    assert binomial_upper_tail(100, 2000, 0.1) == pytest.approx(1.0)
