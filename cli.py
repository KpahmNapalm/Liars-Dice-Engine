"""
Liar's Dice Engine - Interactive CLI (hardened, v2)

Real table assistant: enter what's actually happening, get odds and
a recommended move back. Uses the 'combined' strategy (2-ply
lookahead + opponent modeling), validated as the strongest performer
in simulation testing (Tasks 7-11).

All user input is validated - bad input re-prompts instead of crashing.
"""

from typing import List, Optional
from decision_engine import Bid, BidType, ActionType, query_bid_odds
from opponent_model import OpponentModel
from strategies import strategy_combined
from game_state import GameState, Player


def input_int(prompt: str, min_val: Optional[int] = None, max_val: Optional[int] = None,
              default: Optional[int] = None) -> int:
    """Keep asking until a valid integer (optionally within range) is entered."""
    while True:
        raw = input(prompt).strip()
        if raw == "" and default is not None:
            return default
        try:
            value = int(raw)
        except ValueError:
            print("  Please enter a whole number.")
            continue
        if min_val is not None and value < min_val:
            print(f"  Must be at least {min_val}.")
            continue
        if max_val is not None and value > max_val:
            print(f"  Must be at most {max_val}.")
            continue
        return value


def input_dice_list(prompt: str) -> List[int]:
    """Keep asking until a valid comma-separated list of dice (1-6) is entered."""
    while True:
        raw = input(prompt).strip()
        if not raw:
            print("  Please enter at least one die value.")
            continue
        parts = [p.strip() for p in raw.split(",") if p.strip()]
        try:
            values = [int(p) for p in parts]
        except ValueError:
            print("  Could not parse that - use comma-separated numbers, e.g. 3,4,1,6,2")
            continue
        if not values:
            print("  Please enter at least one die value.")
            continue
        if any(v < 1 or v > 6 for v in values):
            print("  All dice must be between 1 and 6.")
            continue
        return values


def input_choice(prompt: str, valid_choices: List[str]) -> str:
    """Keep asking until one of the valid choices (case-insensitive) is entered."""
    lowered = [c.lower() for c in valid_choices]
    while True:
        raw = input(prompt).strip().lower()
        if raw in lowered:
            return raw
        print(f"  Please enter one of: {', '.join(valid_choices)}")


def format_bid(bid: Optional[Bid]) -> str:
    if bid is None:
        return "(no bid yet)"
    return f"{bid.quantity} x face {bid.face} ({bid.bid_type.value})"


def main():
    print("=" * 60)
    print("  LIAR'S DICE ENGINE - live table assistant (v2)")
    print("=" * 60)

    num_players = input_int("How many players (including you, 2-8)? ", min_val=2, max_val=8)
    dice_counts = []
    for i in range(num_players):
        d = input_int(f"  Dice count for player {i+1}{' (you)' if i == 0 else ''} [5]: ",
                       min_val=0, max_val=6, default=5)
        dice_counts.append(d)

    YOUR_SEAT = 0
    current_bid: Optional[Bid] = None
    current_bid_owner: Optional[int] = None
    own_dice: List[int] = []
    opponent_model = OpponentModel()

    players = [Player(id=i, name=f"Player {i+1}") for i in range(num_players)]
    game = GameState(players=players, current_player_idx=YOUR_SEAT)

    def sync_game_state():
        for i, p in enumerate(players):
            p.num_dice = dice_counts[i]
        players[YOUR_SEAT].dice = own_dice
        game.current_bid = current_bid
        game.bid_history = [(current_bid_owner, current_bid)] if current_bid_owner is not None and current_bid else []
        game.current_player_idx = YOUR_SEAT

    while True:
        total_dice = sum(dice_counts)
        ones_wild = not any(c == 1 for c in dice_counts if c > 0)

        print("\n" + "-" * 60)
        print(f"Total dice in play: {total_dice}   |   One Rule active: {not ones_wild}")
        print(f"Current bid: {format_bid(current_bid)}" +
              (f"  (by Player {current_bid_owner+1})" if current_bid_owner is not None else ""))
        print(f"Your dice: {own_dice if own_dice else '(not set)'}")
        print(f"Dice counts: {dice_counts}")
        print("-" * 60)
        print("1) Set/update your dice (new round)")
        print("2) Get recommended move")
        print("3) Check odds on a specific hypothetical bid")
        print("4) Record someone else's bid (update current bid)")
        print("5) Record a challenge result (Liar/Exact) + update dice counts")
        print("6) Update a player's dice count directly")
        print("7) Quit")
        choice = input_choice("> ", ["1", "2", "3", "4", "5", "6", "7"])

        if choice == "1":
            own_dice = input_dice_list("Enter your dice, comma-separated (e.g. 3,4,1,6,2): ")
            if len(own_dice) != dice_counts[YOUR_SEAT]:
                print(f"  Note: you entered {len(own_dice)} dice but your tracked count is "
                      f"{dice_counts[YOUR_SEAT]}. Using what you entered.")
                dice_counts[YOUR_SEAT] = len(own_dice)
            current_bid = None
            current_bid_owner = None
            print("New round started, current bid cleared.")

        elif choice == "2":
            if not own_dice:
                print("Set your dice first (option 1).")
                continue
            if total_dice == 0:
                print("No dice in play - game should be over.")
                continue
            sync_game_state()
            try:
                action = strategy_combined(game, opponent_model=opponent_model)
            except Exception as e:
                print(f"  Could not compute a recommendation ({e}). "
                      f"Check that dice counts and the current bid make sense together.")
                continue
            bid_str = format_bid(action.resulting_bid) if action.resulting_bid else "-"
            print(f"\nRecommended: {action.action_type.value}")
            print(f"  Bid: {bid_str}")
            print(f"  P(true): {action.probability:.1%}")

        elif choice == "3":
            if not own_dice:
                print("Set your dice first (option 1).")
                continue
            face = input_int("Face value to check (1-6): ", min_val=1, max_val=6)
            qty = input_int("Quantity to check (at least 1): ", min_val=1)
            if qty > total_dice:
                print(f"  Note: {qty} exceeds total dice in play ({total_dice}) - probability will be 0.")
            bt = BidType.ONES if face == 1 else BidType.REGULAR
            report = query_bid_odds(own_dice, face, qty, bt, total_dice, ones_wild, current_bid)
            print()
            print(report.summary())

        elif choice == "4":
            face = input_int("Face bid (1-6): ", min_val=1, max_val=6)
            qty = input_int("Quantity bid (at least 1): ", min_val=1)
            owner = input_int(f"Which player made this bid? (1-{num_players}): ",
                               min_val=1, max_val=num_players) - 1
            bt = BidType.ONES if face == 1 else BidType.REGULAR
            current_bid = Bid(quantity=qty, face=face, bid_type=bt)
            current_bid_owner = owner
            print(f"Current bid updated to: {format_bid(current_bid)} (Player {owner+1})")

        elif choice == "5":
            if current_bid is None:
                print("No current bid to challenge - use option 4 first.")
                continue
            outcome = input_choice("Was it a (L)iar call or (E)xact call? ", ["l", "e"])
            caller = input_int(f"Which player made the call? (1-{num_players}): ",
                                min_val=1, max_val=num_players) - 1

            actual_count = input_int(
                f"How many total dice actually showed face {current_bid.face} "
                f"(counting wilds if applicable)? ", min_val=0, max_val=total_dice
            )

            if outcome == "l":
                bid_was_true = actual_count >= current_bid.quantity
                if current_bid_owner is not None:
                    opponent_model.record_resolution(current_bid_owner, current_bid.face, bid_was_true)
                if bid_was_true:
                    dice_counts[caller] = max(0, dice_counts[caller] - 1)
                    print(f"Bid was TRUE. Player {caller+1} (challenger) loses a die -> {dice_counts[caller]} left")
                else:
                    if current_bid_owner is not None:
                        dice_counts[current_bid_owner] = max(0, dice_counts[current_bid_owner] - 1)
                        print(f"Bid was FALSE. Player {current_bid_owner+1} loses a die "
                              f"-> {dice_counts[current_bid_owner]} left")
            else:
                was_exact = actual_count == current_bid.quantity
                if current_bid_owner is not None:
                    opponent_model.record_resolution(current_bid_owner, current_bid.face, was_exact)
                if was_exact:
                    dice_counts[caller] = min(6, dice_counts[caller] + 1)
                    print(f"EXACT! Player {caller+1} gains a die -> {dice_counts[caller]}")
                else:
                    dice_counts[caller] = max(0, dice_counts[caller] - 1)
                    print(f"Not exact. Player {caller+1} loses a die -> {dice_counts[caller]}")

            eliminated = [i+1 for i, c in enumerate(dice_counts) if c == 0]
            if eliminated:
                print(f"Eliminated: Player(s) {eliminated}")
            remaining = [i for i, c in enumerate(dice_counts) if c > 0]
            if len(remaining) <= 1:
                winner = remaining[0] + 1 if remaining else None
                print(f"\nGame over! Winner: Player {winner}" if winner else "\nGame over - no players remain.")

            current_bid = None
            current_bid_owner = None
            own_dice = []
            print("Round over - remember to set your new dice (option 1) after everyone re-rolls.")

        elif choice == "6":
            pn = input_int(f"Which player? (1-{num_players}): ", min_val=1, max_val=num_players) - 1
            new_count = input_int(f"New dice count for player {pn+1} (0-6): ", min_val=0, max_val=6)
            dice_counts[pn] = new_count

        elif choice == "7":
            print("Good luck out there.")
            break


if __name__ == "__main__":
    main()
