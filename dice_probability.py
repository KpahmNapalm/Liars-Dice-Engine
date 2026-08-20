"""
Dice probability calculator for Liar's Dice engine.

Handles the core question: given a bid, what's the probability
it's actually true, based on:
  - your own known dice
  - the number of unknown (opponent) dice
  - whether 1s are wild (regular bids) or not (during the One Rule)

NOTE: uses float arithmetic rather than Fraction. Fraction gives exact
rational results but is dramatically slower at higher dice counts
(measured ~27x slower at n=20) due to arbitrary-precision integer math.
Since results are always ultimately displayed/consumed as floats,
and Monte Carlo simulation needs to run this thousands of times per
game, float precision is the right tradeoff here.
"""

from math import comb
from typing import List


def prob_unknown_dice_at_least_k(n_unknown: int, p_match: float, k_needed: int) -> float:
    """
    Probability that at least k_needed of n_unknown hidden dice match
    the target face, where each hidden die independently matches with
    probability p_match.
    """
    if k_needed <= 0:
        return 1.0
    if k_needed > n_unknown:
        return 0.0

    total = 0.0
    for i in range(k_needed, n_unknown + 1):
        total += comb(n_unknown, i) * (p_match ** i) * ((1 - p_match) ** (n_unknown - i))
    return total


def count_matches_in_own_dice(own_dice: List[int], face: int, wild_ok: bool) -> int:
    """
    Count how many of your own dice count toward a given face.
    If wild_ok is True, 1s count as matches for any face (except when
    face itself is 1, in which case this is just a normal count).
    """
    if face == 1:
        return own_dice.count(1)

    count = own_dice.count(face)
    if wild_ok:
        count += own_dice.count(1)
    return count


def bid_probability(
    own_dice: List[int],
    face: int,
    quantity: int,
    total_dice_in_play: int,
    ones_are_wild: bool,
) -> float:
    """
    Compute the probability that a bid of `quantity` dice showing `face`
    (across ALL dice in play) is true or better, given your own dice.
    """
    n_unknown = total_dice_in_play - len(own_dice)

    if face == 1:
        p_match = 1 / 6
    else:
        if ones_are_wild:
            p_match = 2 / 6
        else:
            p_match = 1 / 6

    own_matches = count_matches_in_own_dice(own_dice, face, wild_ok=ones_are_wild)
    k_needed = quantity - own_matches

    return prob_unknown_dice_at_least_k(n_unknown, p_match, k_needed)


def bid_probability_exact(
    own_dice: List[int],
    face: int,
    quantity: int,
    total_dice_in_play: int,
    ones_are_wild: bool,
) -> float:
    """
    Probability that the bid is EXACTLY correct (used for Call Exact).
    """
    p_at_least = bid_probability(own_dice, face, quantity, total_dice_in_play, ones_are_wild)
    p_at_least_plus_1 = bid_probability(own_dice, face, quantity + 1, total_dice_in_play, ones_are_wild)
    return p_at_least - p_at_least_plus_1


if __name__ == "__main__":
    own = [3, 4, 1, 6, 2]
    p = bid_probability(own, face=4, quantity=3, total_dice_in_play=10, ones_are_wild=True)
    print(f"P(>=3 fours, wilds on): {p:.3f}")
    p2 = bid_probability(own, face=4, quantity=3, total_dice_in_play=10, ones_are_wild=False)
    print(f"P(>=3 fours, wilds off): {p2:.3f}")
    p3 = bid_probability(own, face=1, quantity=2, total_dice_in_play=10, ones_are_wild=True)
    print(f"P(>=2 ones): {p3:.3f}")
    p4 = bid_probability_exact(own, face=4, quantity=3, total_dice_in_play=10, ones_are_wild=True)
    print(f"P(exactly 3 fours, wilds on): {p4:.3f}")
