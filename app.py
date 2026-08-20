"""
Liar's Dice Engine - Web App (Streamlit)

Web version of cli.py. Same underlying engine (decision_engine.py,
game_state.py, opponent_model.py, strategies.py) - only the
input/output layer changed from terminal prompts to a web UI.

This version adds first-time-user polish: a persistent rules/help
sidebar, tooltips on every input, per-tab explanations, and clearer
error messages.

Run locally with: streamlit run app.py
Deploy free at: https://share.streamlit.io
"""

import streamlit as st
from decision_engine import Bid, BidType, ActionType, query_bid_odds
from opponent_model import OpponentModel
from strategies import strategy_combined
from game_state import GameState, Player

st.set_page_config(page_title="Liar's Dice Engine", page_icon="🎲", layout="centered")


def format_bid(bid):
    if bid is None:
        return "(no bid yet)"
    return f"{bid.quantity} x face {bid.face} ({bid.bid_type.value})"


def init_state():
    if "setup_done" not in st.session_state:
        st.session_state.setup_done = False
        st.session_state.dice_counts = []
        st.session_state.own_dice = []
        st.session_state.current_bid = None
        st.session_state.current_bid_owner = None
        st.session_state.opponent_model = OpponentModel()
        st.session_state.log = []


init_state()

# ==================================================================
# SIDEBAR - persistent rules & help, visible on every screen
# ==================================================================
with st.sidebar:
    st.header("📖 Help")

    with st.expander("How to use this app", expanded=not st.session_state.setup_done):
        st.markdown("""
        **Set up once, then loop through each round:**
        1. **Your dice** - enter what you rolled at the start of each round
        2. **Recommendation** - get the engine's suggested move on your turn
        3. **Check odds** - sanity-check any specific bid before you commit to it
        4. **Record bid** - log what an opponent bid, so the engine tracks the table state
        5. **Record challenge** - log the outcome when someone calls Liar or Exact

        The engine learns each opponent's honesty over the course of
        the game (Record challenge is what feeds that), and reasons
        a couple of moves ahead when recommending a bid.
        """)

    with st.expander("Game rules"):
        st.markdown("""
        - Each player starts with up to 5 dice (max 6), rolled secretly each round
        - A **bid** claims a quantity of a face value across ALL dice at the table
        - On your turn you can: **raise** the bid, **switch to ones**
          (halve the quantity, round up), **switch from ones** (double
          the quantity + 1), or **challenge** it
        - **1s are wild** for regular bids, and count only as themselves
          when bid on directly
        - **One Rule:** the moment any player is down to their last die,
          1s stop being wild for that entire round
        - **Call Liar:** if the bid was false, the bidder loses a die;
          if it was actually true, the challenger loses a die instead
        - **Call Exact:** guess the count exactly right and you *gain*
          a die (capped at 6); guess wrong and you lose one
        - Last player with dice left wins
        """)

    st.divider()
    st.caption("Powered by dice combinatorics + 2-ply lookahead + opponent modeling, "
               "validated by simulating thousands of games (see simulation.py).")

st.title("🎲 Liar's Dice Engine")
st.caption("Live table assistant - powered by the combined (lookahead + opponent modeling) strategy")

# ==================================================================
# SETUP
# ==================================================================
if not st.session_state.setup_done:
    st.subheader("Table setup")
    st.caption("New here? Check **How to use this app** in the sidebar for a quick walkthrough.")

    num_players = st.number_input(
        "How many players (including you)?", min_value=2, max_value=8, value=4,
        help="Count everyone at the table, including yourself. You'll always be Player 1."
    )

    st.write("Starting dice count for each player (usually 5 each):")
    dice_counts = []
    cols = st.columns(min(num_players, 4))
    for i in range(num_players):
        with cols[i % 4]:
            label = f"Player {i+1}" + (" (you)" if i == 0 else "")
            d = st.number_input(
                label, min_value=0, max_value=6, value=5, key=f"setup_dice_{i}",
                help="How many dice this player has right now. Use 5 for a fresh game."
            )
            dice_counts.append(d)

    if st.button("Start game", type="primary"):
        st.session_state.dice_counts = dice_counts
        st.session_state.num_players = num_players
        players = [Player(id=i, name=f"Player {i+1}") for i in range(num_players)]
        st.session_state.game = GameState(players=players, current_player_idx=0)
        st.session_state.setup_done = True
        st.rerun()

# ==================================================================
# MAIN GAME UI
# ==================================================================
else:
    dice_counts = st.session_state.dice_counts
    num_players = st.session_state.num_players
    total_dice = sum(dice_counts)
    ones_wild = not any(c == 1 for c in dice_counts if c > 0)

    # --- Status bar ---
    c1, c2, c3 = st.columns(3)
    c1.metric("Total dice in play", total_dice)
    c2.metric("One Rule active", "Yes" if not ones_wild else "No",
              help="Automatically true the moment ANY player is down to exactly 1 die.")
    c3.metric("Your dice", str(st.session_state.own_dice) if st.session_state.own_dice else "not set")

    bid_owner_str = f" (Player {st.session_state.current_bid_owner+1})" if st.session_state.current_bid_owner is not None else ""
    st.info(f"**Current bid:** {format_bid(st.session_state.current_bid)}{bid_owner_str}")

    st.write("**Dice counts:**", {f"P{i+1}": c for i, c in enumerate(dice_counts)})

    tabs = st.tabs(["🎲 Your dice", "🧠 Recommendation", "🔍 Check odds",
                     "📝 Record bid", "⚖️ Record challenge", "✏️ Edit dice count"])

    # --- Tab: set your dice ---
    with tabs[0]:
        st.caption("Do this first at the start of every round - it also clears the current bid, "
                   "since a fresh roll means a fresh round.")
        raw = st.text_input(
            "Your dice, comma-separated", key="dice_input", placeholder="e.g. 3,4,1,6,2",
            help="Enter every die you rolled, separated by commas. Each value must be 1-6."
        )
        if st.button("Set dice / start new round"):
            if not raw.strip():
                st.error("Enter your dice first - e.g. type 3,4,1,6,2 into the box above.")
            else:
                try:
                    values = [int(x.strip()) for x in raw.split(",") if x.strip()]
                except ValueError:
                    st.error("Couldn't read that as numbers. Use commas between digits only, "
                             "like 3,4,1,6,2 - no letters or extra symbols.")
                    values = None

                if values is not None:
                    bad = [v for v in values if v < 1 or v > 6]
                    if bad:
                        st.error(f"Dice can only show 1-6. These values don't make sense: {bad}")
                    else:
                        st.session_state.own_dice = values
                        if len(values) != dice_counts[0]:
                            st.warning(f"You entered {len(values)} dice but your tracked count was "
                                       f"{dice_counts[0]} - updating your count to match.")
                            dice_counts[0] = len(values)
                        st.session_state.current_bid = None
                        st.session_state.current_bid_owner = None
                        st.success("New round started.")
                        st.rerun()

    # --- Tab: get recommendation ---
    with tabs[1]:
        st.caption("Uses your real dice plus everything logged so far (bids, challenges, dice counts) "
                   "to suggest the strongest move available to you right now.")
        if not st.session_state.own_dice:
            st.warning("Set your dice first in the **Your dice** tab before asking for a recommendation.")
        elif total_dice == 0:
            st.warning("No dice are left in play - the game should already be over.")
        else:
            if st.button("Get recommended move", type="primary"):
                game = st.session_state.game
                for i, p in enumerate(game.players):
                    p.num_dice = dice_counts[i]
                game.players[0].dice = st.session_state.own_dice
                game.current_bid = st.session_state.current_bid
                game.bid_history = (
                    [(st.session_state.current_bid_owner, st.session_state.current_bid)]
                    if st.session_state.current_bid_owner is not None and st.session_state.current_bid
                    else []
                )
                game.current_player_idx = 0
                try:
                    action = strategy_combined(game, opponent_model=st.session_state.opponent_model)
                    bid_str = format_bid(action.resulting_bid) if action.resulting_bid else "-"
                    st.success(f"**Recommended: {action.action_type.value}**")
                    st.write(f"Bid: {bid_str}")
                    st.write(f"P(true): {action.probability:.1%}")
                except Exception as e:
                    st.error(f"Something about the current setup doesn't add up, so a recommendation "
                             f"couldn't be computed ({e}). Double-check your dice count and the "
                             f"current bid look right, then try again.")

    # --- Tab: check odds on a hypothetical bid ---
    with tabs[2]:
        st.caption("Curious about a bid before you commit to it? Check its odds here - "
                   "this works for ANY bid, not just the one currently on the table.")
        if not st.session_state.own_dice:
            st.warning("Set your dice first in the **Your dice** tab.")
        else:
            face = st.number_input(
                "Face value (1-6)", min_value=1, max_value=6, value=4, key="odds_face",
                help="The face you're considering bidding on. Face 1 is scored as a 'ones' bid."
            )
            qty = st.number_input(
                "Quantity", min_value=1, value=3, key="odds_qty",
                help="How many of that face you'd be claiming exist across ALL dice at the table."
            )
            if st.button("Check odds"):
                bt = BidType.ONES if face == 1 else BidType.REGULAR
                report = query_bid_odds(st.session_state.own_dice, face, qty, bt,
                                         total_dice, ones_wild, st.session_state.current_bid)
                st.write(f"**P(true / safe):** {report.p_true:.1%}")
                st.write(f"**P(false / vulnerable to Liar):** {report.p_false:.1%}")
                st.write(f"**P(exactly this / Exact-callable):** {report.p_exact:.1%}")
                st.write(f"**Legal raise right now?** {'Yes' if report.is_valid_raise else 'No'}")

    # --- Tab: record someone else's bid ---
    with tabs[3]:
        st.caption("Whenever an opponent bids, log it here so the engine's picture of the table "
                   "stays accurate for your next recommendation.")
        face = st.number_input("Face bid (1-6)", min_value=1, max_value=6, value=4, key="rec_face")
        qty = st.number_input("Quantity bid", min_value=1, value=3, key="rec_qty")
        owner = st.number_input(
            "Which player made this bid?", min_value=1, max_value=num_players, value=2, key="rec_owner",
            help="Player numbers match the table setup order - you are always Player 1."
        )
        if st.button("Record bid"):
            bt = BidType.ONES if face == 1 else BidType.REGULAR
            st.session_state.current_bid = Bid(quantity=qty, face=face, bid_type=bt)
            st.session_state.current_bid_owner = owner - 1
            st.success(f"Current bid updated to {qty}x face {face} (Player {owner})")
            st.rerun()

    # --- Tab: record a challenge outcome ---
    with tabs[4]:
        st.caption("Log what happened when someone calls Liar or Exact. This is also what feeds "
                   "the opponent-tracking model, so it's worth keeping up to date.")
        if st.session_state.current_bid is None:
            st.warning("There's no current bid to challenge yet - log one first in the "
                       "**Record bid** tab.")
        else:
            outcome = st.radio(
                "Call type", ["Liar", "Exact"], key="challenge_type",
                help="Liar: challenger thinks the bid is too high. Exact: caller thinks the count is exactly right."
            )
            caller = st.number_input("Which player made the call?", min_value=1, max_value=num_players,
                                      value=1, key="challenge_caller")
            actual = st.number_input(
                f"How many dice actually showed face {st.session_state.current_bid.face} "
                f"(counting wilds if they're active)?",
                min_value=0, max_value=total_dice, key="challenge_actual",
                help="Count this up from all revealed dice at the table."
            )
            if st.button("Resolve challenge", type="primary"):
                bid = st.session_state.current_bid
                owner_id = st.session_state.current_bid_owner
                caller_idx = caller - 1
                msg = ""

                if outcome == "Liar":
                    was_true = actual >= bid.quantity
                    if owner_id is not None:
                        st.session_state.opponent_model.record_resolution(owner_id, bid.face, was_true)
                    if was_true:
                        dice_counts[caller_idx] = max(0, dice_counts[caller_idx] - 1)
                        msg = f"Bid was TRUE. Player {caller} loses a die."
                    elif owner_id is not None:
                        dice_counts[owner_id] = max(0, dice_counts[owner_id] - 1)
                        msg = f"Bid was FALSE. Player {owner_id+1} loses a die."
                else:
                    was_exact = actual == bid.quantity
                    if owner_id is not None:
                        st.session_state.opponent_model.record_resolution(owner_id, bid.face, was_exact)
                    if was_exact:
                        dice_counts[caller_idx] = min(6, dice_counts[caller_idx] + 1)
                        msg = f"EXACT! Player {caller} gains a die."
                    else:
                        dice_counts[caller_idx] = max(0, dice_counts[caller_idx] - 1)
                        msg = f"Not exact. Player {caller} loses a die."

                st.session_state.dice_counts = dice_counts
                st.session_state.current_bid = None
                st.session_state.current_bid_owner = None
                st.session_state.own_dice = []

                remaining = [i for i, c in enumerate(dice_counts) if c > 0]
                if len(remaining) <= 1:
                    winner = remaining[0] + 1 if remaining else None
                    st.balloons()
                    msg += f"  🏆 Game over! Winner: Player {winner}" if winner else "  Game over."

                st.success(msg)
                st.info("Round over - head to **Your dice** once everyone's re-rolled.")
                st.rerun()

    # --- Tab: manually edit a dice count ---
    with tabs[5]:
        st.caption("For manual corrections - e.g. fixing a mis-entered count without "
                   "going through a full challenge resolution.")
        pn = st.number_input("Which player?", min_value=1, max_value=num_players, value=1, key="edit_pn")
        new_count = st.number_input("New dice count", min_value=0, max_value=6, value=5, key="edit_count")
        if st.button("Update dice count"):
            dice_counts[pn - 1] = new_count
            st.session_state.dice_counts = dice_counts
            st.success(f"Player {pn} now has {new_count} dice.")
            st.rerun()

    st.divider()
    if st.button("🔄 Reset entire game"):
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.rerun()
