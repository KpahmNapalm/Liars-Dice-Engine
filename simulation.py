"""
Monte Carlo simulation engine for Liar's Dice.

Plays out full games automatically using bot strategies, resolving
challenges against REAL dice rolls (not just probability estimates).
Supports assigning DIFFERENT strategies to different players so we
can empirically test which one wins more often.
"""

import random
from typing import Dict, Callable
from collections import Counter
from functools import partial

from decision_engine import BidType, ActionType
from game_state import GameState, Player
from strategies import STRATEGIES, strategy_safety_max, strategy_opponent_aware, strategy_combined
from opponent_model import OpponentModel


def true_count(game: GameState, face: int, bid_type: BidType) -> int:
    total = 0
    for p in game.active_players:
        if bid_type == BidType.ONES or face == 1:
            total += p.dice.count(1)
        else:
            total += p.dice.count(face)
            if game.ones_are_wild:
                total += p.dice.count(1)
    return total


def play_one_turn(game: GameState, player_strategies: Dict[int, Callable],
                   opponent_model: OpponentModel = None) -> str:
    player = game.current_player
    strategy_fn = player_strategies.get(player.id, strategy_safety_max)
    action = strategy_fn(game)

    if action.action_type == ActionType.CALL_LIAR:
        bid = game.current_bid
        owner_id = game.bid_history[-1][0] if game.bid_history else None
        bid_owner = next((p for p in game.players if p.id == owner_id), player)
        actual = true_count(game, bid.face, bid.bid_type)
        was_true = actual >= bid.quantity
        if opponent_model is not None and owner_id is not None:
            opponent_model.record_resolution(owner_id, bid.face, was_true)
        game.resolve_liar(challenger=player, bid_owner=bid_owner, bid_was_true=was_true)
        return f"{player.name} calls LIAR on {bid.quantity}x{bid.face} (actual={actual})"

    elif action.action_type == ActionType.CALL_EXACT:
        bid = game.current_bid
        owner_id = game.bid_history[-1][0] if game.bid_history else None
        actual = true_count(game, bid.face, bid.bid_type)
        was_exact = actual == bid.quantity
        if opponent_model is not None and owner_id is not None:
            opponent_model.record_resolution(owner_id, bid.face, was_exact)
        game.resolve_exact(caller=player, was_exact=was_exact)
        return f"{player.name} calls EXACT on {bid.quantity}x{bid.face} (actual={actual})"

    else:
        game.current_bid = action.resulting_bid
        game.bid_history.append((player.id, action.resulting_bid))
        game.advance_turn()
        return f"{player.name} bids {action.resulting_bid.quantity}x{action.resulting_bid.face} ({action.action_type.value})"


def simulate_game(player_strategy_names: list, verbose: bool = False, max_turns: int = 500) -> Dict:
    """
    Play one full game. player_strategy_names[i] is the strategy name
    (key into STRATEGIES) used by the player in seat i.
    """
    num_players = len(player_strategy_names)
    players = [Player(id=i, name=f"P{i}({player_strategy_names[i]})") for i in range(num_players)]
    player_strategies = {i: STRATEGIES[player_strategy_names[i]] for i in range(num_players)}

    game = GameState(players=players, current_player_idx=0)
    game.roll_all_dice()

    turn_count = 0
    while not game.is_game_over and turn_count < max_turns:
        result = play_one_turn(game, player_strategies)
        turn_count += 1
        if verbose:
            print(f"  [{turn_count}] {result}")

    winner = game.winner
    winner_strategy = player_strategy_names[winner.id] if winner else None
    return {
        "winner_id": winner.id if winner else None,
        "winner_strategy": winner_strategy,
        "total_turns": turn_count,
        "total_rounds": game.round_number,
        "completed": game.is_game_over,
    }


MODEL_BASED_STRATEGIES = {
    "opponent_aware": strategy_opponent_aware,
    "combined": strategy_combined,
}


def simulate_game_with_opponent_model(player_strategy_names: list, opponent_aware_seat: int,
                                       verbose: bool = False, max_turns: int = 500,
                                       model_strategy_name: str = "opponent_aware") -> Dict:
    """
    Like simulate_game, but seat `opponent_aware_seat` uses a
    model-based strategy (opponent_aware or combined) backed by a
    fresh OpponentModel that accumulates data over the course of
    THIS game only.
    """
    num_players = len(player_strategy_names)
    players = [Player(id=i, name=f"P{i}({player_strategy_names[i]})") for i in range(num_players)]

    opponent_model = OpponentModel()
    model_strategy_fn = MODEL_BASED_STRATEGIES[model_strategy_name]
    player_strategies = {}
    for i in range(num_players):
        if i == opponent_aware_seat:
            player_strategies[i] = partial(model_strategy_fn, opponent_model=opponent_model)
        else:
            player_strategies[i] = STRATEGIES[player_strategy_names[i]]

    game = GameState(players=players, current_player_idx=0)
    game.roll_all_dice()

    turn_count = 0
    while not game.is_game_over and turn_count < max_turns:
        result = play_one_turn(game, player_strategies, opponent_model=opponent_model)
        turn_count += 1
        if verbose:
            print(f"  [{turn_count}] {result}")

    winner = game.winner
    names = list(player_strategy_names)
    names[opponent_aware_seat] = model_strategy_name
    winner_strategy = names[winner.id] if winner else None
    return {
        "winner_id": winner.id if winner else None,
        "winner_strategy": winner_strategy,
        "total_turns": turn_count,
        "completed": game.is_game_over,
    }


def run_head_to_head(strategy_names: list, num_games: int = 500) -> Dict:
    """
    Run many games with a FIXED strategy assignment per seat, then
    also rotate seat assignments across games to cancel out any
    seat-position bias.
    """
    win_counts_by_strategy = Counter()
    incomplete = 0
    n = len(strategy_names)

    for g in range(num_games):
        # Rotate which strategy sits in which seat each game
        rotation = g % n
        rotated = strategy_names[rotation:] + strategy_names[:rotation]
        result = simulate_game(rotated, verbose=False)
        if result["winner_strategy"] is not None:
            win_counts_by_strategy[result["winner_strategy"]] += 1
        else:
            incomplete += 1

    return {
        "num_games": num_games,
        "win_counts": dict(win_counts_by_strategy),
        "win_rates": {s: c / num_games for s, c in win_counts_by_strategy.items()},
        "incomplete": incomplete,
    }


def run_opponent_aware_test(bluffer_seats: int = 3, num_games: int = 500) -> Dict:
    """
    Test whether opponent-aware modeling actually pays off: one seat
    uses opponent_aware, the rest are bluffers. Rotates the aware
    seat across games to control for position bias.
    """
    win_counts = Counter()
    incomplete = 0
    total_seats = bluffer_seats + 1

    for g in range(num_games):
        aware_seat = g % total_seats
        names = ["bluffer"] * total_seats
        result = simulate_game_with_opponent_model(names, opponent_aware_seat=aware_seat)
        if result["winner_strategy"] is not None:
            win_counts[result["winner_strategy"]] += 1
        else:
            incomplete += 1

    return {
        "num_games": num_games,
        "win_counts": dict(win_counts),
        "win_rates": {s: c / num_games for s, c in win_counts.items()},
        "incomplete": incomplete,
    }


if __name__ == "__main__":
    print("=== Head-to-head: safety_max vs pressure vs random_legal vs safety_max ===\n")
    random.seed(42)
    results = run_head_to_head(
        strategy_names=["safety_max", "pressure", "random_legal", "safety_max"],
        num_games=500,
    )
    print(f"Games completed: {results['num_games'] - results['incomplete']} / {results['num_games']}")
    print(f"Win rates by strategy: {results['win_rates']}")
