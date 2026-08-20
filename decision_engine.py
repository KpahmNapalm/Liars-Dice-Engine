"""
1-ply decision engine for Liar's Dice.

Given a game state, enumerates all legal actions and scores each
using expected value, based purely on the probability calculator
(no opponent modeling yet - that's Phase 2).
"""

from dataclasses import dataclass
from typing import List, Optional
from enum import Enum

from dice_probability import bid_probability, bid_probability_exact


class BidType(Enum):
    REGULAR = "regular"
    ONES = "ones"


class ActionType(Enum):
    RAISE = "raise"
    SWITCH_TO_ONES = "switch_to_ones"
    SWITCH_FROM_ONES = "switch_from_ones"
    CALL_LIAR = "call_liar"
    CALL_EXACT = "call_exact"


@dataclass(frozen=True)
class Bid:
    quantity: int
    face: int
    bid_type: BidType


@dataclass
class Action:
    action_type: ActionType
    resulting_bid: Optional[Bid]
    probability: float
    expected_value: float


def is_valid_raise(current: Optional[Bid], candidate: Bid) -> bool:
    """A raise must be on the same bid_type and strictly higher."""
    if current is None:
        return True
    if candidate.bid_type != current.bid_type:
        return False
    if candidate.face == current.face:
        return candidate.quantity > current.quantity
    return candidate.face > current.face and candidate.quantity >= current.quantity


def enumerate_raises(current: Optional[Bid], max_quantity: int) -> List[Bid]:
    """All legal raise bids given the current bid, within a quantity ceiling."""
    bid_type = current.bid_type if current else BidType.REGULAR
    faces = [1] if bid_type == BidType.ONES else range(2, 7)
    candidates = []
    for face in faces:
        for qty in range(1, max_quantity + 1):
            candidate = Bid(quantity=qty, face=face, bid_type=bid_type)
            if is_valid_raise(current, candidate):
                candidates.append(candidate)
    return candidates


def switch_to_ones(current: Bid) -> Optional[Bid]:
    if current.bid_type != BidType.REGULAR:
        return None
    new_qty = -(-current.quantity // 2)  # ceiling division = round up
    return Bid(quantity=new_qty, face=1, bid_type=BidType.ONES)


def switch_from_ones(current: Bid):
    if current.bid_type != BidType.ONES:
        return None
    new_qty = current.quantity * 2 + 1
    return [Bid(quantity=new_qty, face=f, bid_type=BidType.REGULAR) for f in range(2, 7)]


def evaluate_actions(
    own_dice: List[int],
    current_bid: Optional[Bid],
    total_dice_in_play: int,
    ones_are_wild: bool,
    max_quantity: Optional[int] = None,
    min_raise_probability: float = 0.05,
) -> List[Action]:
    """
    Enumerate all legal actions from this position and score each one.
    Returns a list of Actions sorted best-first.

    NOTE ON RAISE SCORING: raises are currently scored purely by
    P(bid is true) - i.e. "maximize safety." This is a provisional
    placeholder strategy, now being compared against alternatives
    (see strategies.py) via Monte Carlo simulation.

    min_raise_probability: raises below this true-probability are
    filtered out entirely as "absurd" bids not worth recommending.
    """
    if max_quantity is None:
        max_quantity = total_dice_in_play

    actions: List[Action] = []

    if current_bid is not None:
        p_true = bid_probability(
            own_dice, current_bid.face, current_bid.quantity,
            total_dice_in_play, ones_are_wild
        )
        p_false = 1 - p_true
        liar_ev = p_false * 1 + p_true * -1
        actions.append(Action(ActionType.CALL_LIAR, None, p_false, liar_ev))

        p_exact = bid_probability_exact(
            own_dice, current_bid.face, current_bid.quantity,
            total_dice_in_play, ones_are_wild
        )
        p_not_exact = 1 - p_exact
        exact_ev = p_exact * 1.5 + p_not_exact * -1
        actions.append(Action(ActionType.CALL_EXACT, None, p_exact, exact_ev))

    for candidate in enumerate_raises(current_bid, max_quantity):
        p_true = bid_probability(own_dice, candidate.face, candidate.quantity,
                                   total_dice_in_play, ones_are_wild)
        if p_true < min_raise_probability:
            continue
        actions.append(Action(ActionType.RAISE, candidate, p_true, p_true))

    if current_bid is not None:
        switched = switch_to_ones(current_bid)
        if switched is not None:
            p_true = bid_probability(own_dice, switched.face, switched.quantity,
                                       total_dice_in_play, ones_are_wild)
            if p_true >= min_raise_probability:
                actions.append(Action(ActionType.SWITCH_TO_ONES, switched, p_true, p_true))

        switched_out_options = switch_from_ones(current_bid)
        if switched_out_options:
            for opt in switched_out_options:
                p_true = bid_probability(own_dice, opt.face, opt.quantity,
                                           total_dice_in_play, ones_are_wild)
                if p_true >= min_raise_probability:
                    actions.append(Action(ActionType.SWITCH_FROM_ONES, opt, p_true, p_true))

    actions.sort(key=lambda a: a.expected_value, reverse=True)
    return actions


@dataclass
class OddsReport:
    bid: Bid
    p_true: float
    p_false: float
    p_exact: float
    is_valid_raise: bool

    def summary(self) -> str:
        bt = self.bid.bid_type.value
        lines = [
            f"Bid: {self.bid.quantity} x face {self.bid.face} ({bt})",
            f"  P(true / safe if you bid this)   : {self.p_true:.1%}",
            f"  P(false / vulnerable to Liar)     : {self.p_false:.1%}",
            f"  P(exactly this / Exact-callable)  : {self.p_exact:.1%}",
            f"  Legal raise right now?            : {'yes' if self.is_valid_raise else 'no'}",
        ]
        return "\n".join(lines)


def query_bid_odds(
    own_dice: List[int],
    face: int,
    quantity: int,
    bid_type: BidType,
    total_dice_in_play: int,
    ones_are_wild: bool,
    current_bid: Optional[Bid] = None,
) -> OddsReport:
    hypothetical = Bid(quantity=quantity, face=face, bid_type=bid_type)
    p_true = bid_probability(own_dice, face, quantity, total_dice_in_play, ones_are_wild)
    p_exact = bid_probability_exact(own_dice, face, quantity, total_dice_in_play, ones_are_wild)
    p_false = 1 - p_true
    legal = is_valid_raise(current_bid, hypothetical)

    return OddsReport(
        bid=hypothetical,
        p_true=p_true,
        p_false=p_false,
        p_exact=p_exact,
        is_valid_raise=legal,
    )
