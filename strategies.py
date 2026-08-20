"""
Alternative bot strategies for head-to-head Monte Carlo comparison.

Each strategy is a function: (game_state) -> Action
This lets us empirically test which raise-scoring philosophy actually
wins more often, rather than guessing.
"""

import random
from decision_engine import (
    ActionType, Action,
    enumerate_raises, bid_probability,
)


def strategy_safety_max(game, min_raise_probability: float = 0.05) -> Action:
    """
    Always pick the action with highest P(true). 'Play it as safe as possible.'
    """
    actions = game.get_recommended_actions(min_raise_probability=min_raise_probability)
    if not actions:
        actions = game.get_recommended_actions(min_raise_probability=0.0)
    return actions[0]


def strategy_random_legal(game, min_raise_probability: float = 0.0) -> Action:
    """
    Baseline: pick uniformly at random among all legal actions.
    """
    actions = game.get_recommended_actions(min_raise_probability=min_raise_probability)
    if not actions:
        actions = game.get_recommended_actions(min_raise_probability=0.0)
    return random.choice(actions)


def strategy_pressure(game, min_raise_probability: float = 0.05,
                       safety_weight: float = 0.5) -> Action:
    """
    Balances safety against 'pressure': how much does this bid limit
    the NEXT player's own best safe option? Estimated with no info
    about their hand (empty own_dice - a neutral "outside view").
    """
    total_dice = game.total_dice_in_play
    wild = game.ones_are_wild

    actions = game.get_recommended_actions(min_raise_probability=min_raise_probability)
    if not actions:
        actions = game.get_recommended_actions(min_raise_probability=0.0)

    scored = []
    for a in actions:
        if a.action_type in (ActionType.CALL_LIAR, ActionType.CALL_EXACT):
            scored.append((a, a.expected_value))
            continue

        candidate_bid = a.resulting_bid
        next_options = enumerate_raises(candidate_bid, total_dice)
        if next_options:
            best_next_p = max(
                bid_probability([], c.face, c.quantity, total_dice, wild)
                for c in next_options
            )
        else:
            best_next_p = 0.0

        pressure = 1 - best_next_p
        combined = safety_weight * a.probability + (1 - safety_weight) * pressure
        scored.append((a, combined))

    scored.sort(key=lambda x: x[1], reverse=True)
    return scored[0][0]


def strategy_opponent_aware(game, opponent_model, min_raise_probability: float = 0.05,
                              safety_weight: float = 0.9) -> Action:
    """
    Same as strategy_pressure, EXCEPT when scoring Call Liar / Call
    Exact: uses the bidder's opponent_model track record to adjust
    the probability estimate, rather than trusting pure combinatorics.
    """
    total_dice = game.total_dice_in_play
    wild = game.ones_are_wild

    actions = game.get_recommended_actions(min_raise_probability=min_raise_probability)
    if not actions:
        actions = game.get_recommended_actions(min_raise_probability=0.0)

    # Who placed the current bid? Needed to look up their profile.
    bidder_id = game.bid_history[-1][0] if game.bid_history else None

    scored = []
    for a in actions:
        if a.action_type in (ActionType.CALL_LIAR, ActionType.CALL_EXACT) and bidder_id is not None:
            bid = game.current_bid
            raw_p_true = bid_probability(game.current_player.dice, bid.face, bid.quantity,
                                          total_dice, wild)
            adj_p_true = opponent_model.adjusted_probability(bidder_id, bid.face, raw_p_true)

            if a.action_type == ActionType.CALL_LIAR:
                p_false = 1 - adj_p_true
                ev = p_false * 1 + adj_p_true * -1
            else:  # CALL_EXACT - approximate using the same adjustment on the "at least" probability
                # Shift the exact-probability estimate by the same relative adjustment
                shift = adj_p_true - raw_p_true
                adj_p_exact = max(0.0, min(1.0, a.probability + shift))
                ev = adj_p_exact * 1.5 + (1 - adj_p_exact) * -1
            scored.append((a, ev))
            continue

        if a.action_type in (ActionType.CALL_LIAR, ActionType.CALL_EXACT):
            scored.append((a, a.expected_value))
            continue

        candidate_bid = a.resulting_bid
        next_options = enumerate_raises(candidate_bid, total_dice)
        if next_options:
            best_next_p = max(
                bid_probability([], c.face, c.quantity, total_dice, wild)
                for c in next_options
            )
        else:
            best_next_p = 0.0
        pressure = 1 - best_next_p
        combined = safety_weight * a.probability + (1 - safety_weight) * pressure
        scored.append((a, combined))

    scored.sort(key=lambda x: x[1], reverse=True)
    return scored[0][0]


def strategy_bluffer(game, min_raise_probability: float = 0.0, bluff_rate: float = 0.35) -> Action:
    """
    A test opponent: most of the time plays safely (like safety_max),
    but bluff_rate of the time deliberately picks a risky bid (one
    with roughly 25-45% true probability) instead of a safe one, to
    simulate a player who bluffs. Used to validate whether
    opponent-aware modeling can actually detect and punish this
    pattern better than strategies with no memory.
    """
    actions = game.get_recommended_actions(min_raise_probability=min_raise_probability)
    if not actions:
        actions = game.get_recommended_actions(min_raise_probability=0.0)

    if random.random() < bluff_rate:
        raises = [a for a in actions if a.action_type == ActionType.RAISE]
        risky = [a for a in raises if 0.20 <= a.probability <= 0.50]
        if risky:
            return random.choice(risky)
        # No mid-risk raise available - fall back to safest

    return actions[0]


def strategy_lookahead(game, min_raise_probability: float = 0.05,
                        safety_weight: float = 0.9) -> Action:
    """
    2-ply lookahead: for each candidate bid, considers not just its
    own safety, but (a) how much room the opponent has to safely
    counter it, and (b) NEW - if the opponent makes their most likely
    safe counter, how well-positioned are WE to respond after that.

    Opponent moves are evaluated from a no-info outside view (we don't
    know their dice). Our own projected future move DOES use our real
    dice, since those don't change between now and our next turn -
    this is the part that makes it genuine lookahead rather than just
    another one-step heuristic.
    """
    total_dice = game.total_dice_in_play
    wild = game.ones_are_wild
    own_dice = game.current_player.dice

    actions = game.get_recommended_actions(min_raise_probability=min_raise_probability)
    if not actions:
        actions = game.get_recommended_actions(min_raise_probability=0.0)

    scored = []
    for a in actions:
        if a.action_type in (ActionType.CALL_LIAR, ActionType.CALL_EXACT):
            scored.append((a, a.expected_value))
            continue

        candidate_bid = a.resulting_bid

        # Ply 1: opponent's best safe continuation (no-info view)
        opp_options = enumerate_raises(candidate_bid, total_dice)
        if opp_options:
            opp_best = max(opp_options, key=lambda c: bid_probability([], c.face, c.quantity, total_dice, wild))
            opp_best_p = bid_probability([], opp_best.face, opp_best.quantity, total_dice, wild)
        else:
            opp_best = None
            opp_best_p = 0.0  # no safe continuation for them at all - very good for us
        pressure_now = 1 - opp_best_p

        # Ply 2: if opponent plays that likely bid, how safe is OUR best
        # response using our REAL dice?
        if opp_best is not None:
            our_next_options = enumerate_raises(opp_best, total_dice)
            if our_next_options:
                our_future_safety = max(
                    bid_probability(own_dice, c.face, c.quantity, total_dice, wild)
                    for c in our_next_options
                )
            else:
                our_future_safety = 0.0  # we'd be cornered two moves out
        else:
            our_future_safety = 1.0  # opponent already has no room - moot point

        lookahead_component = 0.5 * pressure_now + 0.5 * our_future_safety
        score = safety_weight * a.probability + (1 - safety_weight) * lookahead_component
        scored.append((a, score))

    scored.sort(key=lambda x: x[1], reverse=True)
    return scored[0][0]


def strategy_combined(game, opponent_model, min_raise_probability: float = 0.05,
                       safety_weight: float = 0.9) -> Action:
    """
    The full strategy: 2-ply lookahead for RAISE/switch decisions
    (from strategy_lookahead), combined with opponent-model-adjusted
    probabilities for CALL_LIAR/CALL_EXACT decisions (from
    strategy_opponent_aware). Targets two different weaknesses at
    once - shallow reasoning and exploitable trust in "objective" math.
    """
    total_dice = game.total_dice_in_play
    wild = game.ones_are_wild
    own_dice = game.current_player.dice
    bidder_id = game.bid_history[-1][0] if game.bid_history else None

    actions = game.get_recommended_actions(min_raise_probability=min_raise_probability)
    if not actions:
        actions = game.get_recommended_actions(min_raise_probability=0.0)

    scored = []
    for a in actions:
        if a.action_type in (ActionType.CALL_LIAR, ActionType.CALL_EXACT):
            if bidder_id is not None:
                bid = game.current_bid
                raw_p_true = bid_probability(own_dice, bid.face, bid.quantity, total_dice, wild)
                adj_p_true = opponent_model.adjusted_probability(bidder_id, bid.face, raw_p_true)
                if a.action_type == ActionType.CALL_LIAR:
                    p_false = 1 - adj_p_true
                    ev = p_false * 1 + adj_p_true * -1
                else:
                    shift = adj_p_true - raw_p_true
                    adj_p_exact = max(0.0, min(1.0, a.probability + shift))
                    ev = adj_p_exact * 1.5 + (1 - adj_p_exact) * -1
                scored.append((a, ev))
            else:
                scored.append((a, a.expected_value))
            continue

        # RAISE / switch: 2-ply lookahead, same as strategy_lookahead
        candidate_bid = a.resulting_bid
        opp_options = enumerate_raises(candidate_bid, total_dice)
        if opp_options:
            opp_best = max(opp_options, key=lambda c: bid_probability([], c.face, c.quantity, total_dice, wild))
            opp_best_p = bid_probability([], opp_best.face, opp_best.quantity, total_dice, wild)
        else:
            opp_best = None
            opp_best_p = 0.0
        pressure_now = 1 - opp_best_p

        if opp_best is not None:
            our_next_options = enumerate_raises(opp_best, total_dice)
            if our_next_options:
                our_future_safety = max(
                    bid_probability(own_dice, c.face, c.quantity, total_dice, wild)
                    for c in our_next_options
                )
            else:
                our_future_safety = 0.0
        else:
            our_future_safety = 1.0

        lookahead_component = 0.5 * pressure_now + 0.5 * our_future_safety
        score = safety_weight * a.probability + (1 - safety_weight) * lookahead_component
        scored.append((a, score))

    scored.sort(key=lambda x: x[1], reverse=True)
    return scored[0][0]


STRATEGIES = {
    "safety_max": strategy_safety_max,
    "random_legal": strategy_random_legal,
    "pressure": strategy_pressure,
    "bluffer": strategy_bluffer,
    "lookahead": strategy_lookahead,
    # "opponent_aware" is intentionally excluded here since it needs an
    # extra opponent_model argument - wired in separately in simulation.
}
