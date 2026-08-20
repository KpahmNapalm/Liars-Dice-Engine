"""
Liar's Dice Engine - Web App (Streamlit)

Web version of cli.py. Same underlying engine (decision_engine.py,
game_state.py, opponent_model.py, strategies.py) - only the
input/output layer changed from terminal prompts to a web UI.

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

st.title("🎲 Liar's Dice Engine")
st.caption("Live table assistant - powered by the combined (lookahead + opponent modeling) strategy")

# ---------------- SETUP ----------------
if not st.session_state.setup_done:
    st.subheader("Table setup")
    num_players = st.number_input("How many players (including you)?", min_value=2, max_value=8, value=4)

    dice_counts = []
    cols = st.columns(min(num_players, 4))
    for i in range(num_players):
        with cols[i % 4]:
            label = f"Player {i+1}" + (" (you)" if i == 0 else "")
            d = st.number_input(label, min_value=0, max_value=6, value=5, key=f"setup_dice_{i}")
            dice_counts.append(d)

    if st.button("Start game", type="primary"):
        st.session_state.dice_counts = dice_counts
        st.session_state.num_players = num_players
        players = [Player(id=i, name=f"Player {i+1}") for i in range(num_players)]
        st.session_state.game = GameState(players=players, current_player_idx=0)
        st.session_state.setup_done = True
        st.rerun()

# ---------------- MAIN GAME UI ----------------
else:
    dice_counts = st.session_state.dice_counts
    num_players = st.session_state.num_players
    total_dice = sum(dice_counts)
    ones_wild = not any(c == 1 for c in dice_counts if c > 0)

    # --- Status bar ---
    c1, c2, c3 = st.columns(3)
    c1.metric("Total dice in play", total_dice)
    c2.metric("One Rule active", "Yes" if not ones_wild else "No")
    c3.metric("Your dice", str(st.session_state.own_dice) if st.session_state.own_dice else "not set")

    bid_owner_str = f" (Player {st.session_state.current_bid_owner+1})" if st.session_state.current_bid_owner is not None else ""
    st.info(f"**Current bid:** {format_bid(st.session_state.current_bid)}{bid_owner_str}")

    st.write("**Dice counts:**", {f"P{i+1}": c for i, c in enumerate(dice_counts)})

    tabs = st.tabs(["🎲 Your dice", "🧠 Recommendation", "🔍 Check odds",
                     "📝 Record bid", "⚖️ Record challenge", "✏️ Edit dice count"])

    # --- Tab: set your dice ---
    with tabs[0]:
        st.write("Enter your dice for this round:")
        raw = st.text_input("Comma-separated (e.g. 3,4,1,6,2)", key="dice_input")
        if st.button("Set dice / start new round"):
            try:
                values = [int(x.strip()) for x in raw.split(",") if x.strip()]
                if not values or any(v < 1 or v > 6 for v in values):
                    st.error("Enter 1-6 comma-separated numbers.")
                else:
                    st.session_state.own_dice = values
                    if len(values) != dice_counts[0]:
                        st.warning(f"You entered {len(values)} dice but tracked count was {dice_counts[0]} - updating.")
                        dice_counts[0] = len(values)
                    st.session_state.current_bid = None
                    st.session_state.current_bid_owner = None
                    st.success("New round started.")
                    st.rerun()
            except ValueError:
                st.error("Could not parse - use comma-separated numbers like 3,4,1,6,2")

    # --- Tab: get recommendation ---
    with tabs[1]:
        if not st.session_state.own_dice:
            st.warning("Set your dice first (first tab).")
        elif total_dice == 0:
            st.warning("No dice in play - game should be over.")
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
                    st.error(f"Could not compute a recommendation: {e}")

    # --- Tab: check odds on a hypothetical bid ---
    with tabs[2]:
        if not st.session_state.own_dice:
            st.warning("Set your dice first (first tab).")
        else:
            face = st.number_input("Face value (1-6)", min_value=1, max_value=6, value=4, key="odds_face")
            qty = st.number_input("Quantity", min_value=1, value=3, key="odds_qty")
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
        face = st.number_input("Face bid (1-6)", min_value=1, max_value=6, value=4, key="rec_face")
        qty = st.number_input("Quantity bid", min_value=1, value=3, key="rec_qty")
        owner = st.number_input("Which player made this bid?", min_value=1, max_value=num_players,
                                 value=2, key="rec_owner")
        if st.button("Record bid"):
            bt = BidType.ONES if face == 1 else BidType.REGULAR
            st.session_state.current_bid = Bid(quantity=qty, face=face, bid_type=bt)
            st.session_state.current_bid_owner = owner - 1
            st.success(f"Current bid updated to {qty}x face {face} (Player {owner})")
            st.rerun()

    # --- Tab: record a challenge outcome ---
    with tabs[4]:
        if st.session_state.current_bid is None:
            st.warning("No current bid to challenge - record one in the 'Record bid' tab first.")
        else:
            outcome = st.radio("Call type", ["Liar", "Exact"], key="challenge_type")
            caller = st.number_input("Which player made the call?", min_value=1, max_value=num_players,
                                      value=1, key="challenge_caller")
            actual = st.number_input(
                f"How many dice actually showed face {st.session_state.current_bid.face} (incl. wilds)?",
                min_value=0, max_value=total_dice, key="challenge_actual"
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
                st.rerun()

    # --- Tab: manually edit a dice count ---
    with tabs[5]:
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
