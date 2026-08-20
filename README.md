---

editor_options: 
  markdown: 
    wrap: 72
---

# Liar's Dice Probability & Decision Engine

A probability calculator and decision-support engine for a custom Liar's Dice variant, including a "switch to/from ones" bidding mechanic, an Exact call, and a One Rule that disables wildcards when any player is down to their last die.

## Quick start

``` bash
python3 cli.py
```

Walks you through table setup (players, dice counts), then gives you a menu each turn: get a recommended move, check the odds on any hypothetical bid, or record what actually happened at the table.

Requires Python 3.8+ and no external dependencies (standard library only).

## Files

| File | Purpose |
|------------------------------------|------------------------------------|
| `dice_probability.py` | Core combinatorial math - probability that a given bid is true or exactly true |
| `decision_engine.py` | Enumerates legal moves (raise, switch to/from ones, call liar/exact) and scores them |
| `game_state.py` | Multiplayer game state: turn order, elimination, One Rule detection |
| `opponent_model.py` | Tracks each player's bid-honesty track record and adjusts trust accordingly |
| `strategies.py` | Several bot strategies (safety_max, pressure, lookahead, opponent_aware, combined, bluffer, random) for simulation and comparison |
| `simulation.py` | Monte Carlo simulation engine - plays out full games to test strategies against each other |
| `cli.py` | Interactive live-play assistant, uses the `combined` strategy |
| `test_engine.py` | Regression test suite - run with `python3 -m unittest test_engine.py -v` |

## The rules this engine implements

- Each player starts with 5 dice (max 6), rolled secretly each round
- Bids claim a quantity of a face value across ALL dice in play
- On your turn: raise the bid, switch to ones (halve quantity, round up), switch from ones (double quantity + 1), call Liar, or call Exact
- 1s are wild for regular-face bids, and count as themselves when bid on directly
- **One Rule**: when any player is on their last die, 1s lose wildcard status for that entire round
- Call Liar: bidder loses a die if wrong, challenger loses a die if the bid was actually true
- Call Exact: caller gains a die (capped at 6) if exactly right, loses a die if wrong
- Last player standing wins

## How the recommendation works

The `combined` strategy (used by the CLi) blends three things:

1.  **Raw probability** (`dice_probability.py`) - the objective odds a bid is true, given your dice and the total dice in play
2.  **2-ply lookahead** (`strategies.py: strategy_lookahead`) - not just "is my bid safe," but "if the opponent counters with their most likely safe move, how well-positioned am I after that"
3.  **Opponent modeling** (`opponent_model.py`) - tracks each specific player's history of challenged bids, and discounts trust in players who have a track record of bluffing

## Validated results (see simulation.py)

Strategies were compared head-to-head over hundreds to thousands of simulated games:

- A pure "maximize safety" strategy is beatable by simple bluffing (loses \~41% vs bluffers)
- Adding opponent modeling flips that matchup to a winning record (\~51%)
- Adding 2-ply lookahead on top adds a further modest edge, especially against more sophisticated (non-bluffing) opponents
- The opponent model's trust-shrinkage parameter matters a lot: too reactive to small samples actively hurts performance against honest players (an issue found and fixed during development - see `test_established_pattern_has_larger_effect` and `test_single_data_point_has_small_effect` in `test_engine.py`)

## Known limitations

- Opponent modeling only learns from bids that get **challenged** - bids nobody questions leave no signal, so a cautious bluffer who rarely gets challenged stays under the radar longer than a careless one
- Lookahead is currently 2-ply (your move -\> their likely response -\> your response to that) - deeper lookahead is possible but gets computationally expensive quickly
- The `combined` strategy is tuned against the specific bot opponents in this codebase (bluffer, pressure, safety_max) - it hasn't been validated against real human play
