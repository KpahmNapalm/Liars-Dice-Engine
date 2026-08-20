"""
Liar's Dice Engine - Web App (Streamlit)

Web version of cli.py. Same underlying engine (decision_engine.py,
game_state.py, opponent_model.py, strategies.py) - only the
input/output layer changed from terminal prompts to a web UI.

This version has a custom visual design system: real pip-layout dice
tiles (with the number always shown too, since Unicode die glyphs
render inconsistently across systems), card-based sections, a
consistent color/typography system, and custom gradient probability
bars, in place of Streamlit's raw defaults.

Run locally with: streamlit run app.py
Deploy free at: https://share.streamlit.io
"""

import streamlit as st
from decision_engine import Bid, BidType, ActionType, query_bid_odds
from opponent_model import OpponentModel
from strategies import strategy_combined
from game_state import GameState, Player

st.set_page_config(page_title="Liar's Dice Engine", page_icon="🎲", layout="centered")

# ======================================================================
# DESIGN SYSTEM - custom CSS
# ======================================================================
PRIMARY = "#1e3a5f"       # deep navy - headers, primary buttons
PRIMARY_DARK = "#152a45"
ACCENT = "#c9932e"        # warm gold - highlights, current-bid emphasis
BG = "#f6f7fb"
CARD_BG = "#ffffff"
BORDER = "#e6e8ef"
TEXT_MUTED = "#6b7280"
GREEN = "#16a34a"
AMBER = "#d97706"
RED = "#dc2626"

st.markdown(f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

html, body, [class*="css"] {{
    font-family: 'Inter', -apple-system, sans-serif;
}}

.stApp {{
    background-color: {BG};
}}

/* ---- Header ---- */
.app-header {{
    padding: 8px 0 4px 0;
}}
.app-title {{
    font-size: 30px;
    font-weight: 800;
    color: {PRIMARY};
    letter-spacing: -0.5px;
    margin-bottom: 2px;
}}
.app-subtitle {{
    color: {TEXT_MUTED};
    font-size: 14px;
    font-weight: 500;
}}

/* ---- Cards ---- */
.card {{
    background: {CARD_BG};
    border: 1px solid {BORDER};
    border-radius: 16px;
    padding: 18px 22px;
    margin-bottom: 16px;
    box-shadow: 0 1px 2px rgba(16, 24, 40, 0.04);
}}
.card-label {{
    font-size: 12px;
    font-weight: 700;
    color: {TEXT_MUTED};
    text-transform: uppercase;
    letter-spacing: 0.6px;
    margin-bottom: 6px;
}}

/* ---- Dice tiles ---- */
.dice-row {{
    display: flex;
    gap: 10px;
    flex-wrap: wrap;
    align-items: center;
}}
.die-tile {{
    position: relative;
    width: 52px;
    height: 52px;
    background: linear-gradient(150deg, #ffffff, #eef1f6);
    border: 1px solid {BORDER};
    border-radius: 12px;
    box-shadow: 0 2px 4px rgba(16, 24, 40, 0.10), inset 0 1px 0 rgba(255,255,255,0.7);
    flex-shrink: 0;
}}
.die-pips {{
    position: absolute;
    inset: 8px;
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    grid-template-rows: repeat(3, 1fr);
}}
.pip {{
    width: 7px;
    height: 7px;
    border-radius: 50%;
    background: {PRIMARY};
    justify-self: center;
    align-self: center;
}}
.die-number {{
    position: absolute;
    bottom: -7px;
    right: -7px;
    background: {PRIMARY};
    color: white;
    font-size: 11px;
    font-weight: 700;
    width: 19px;
    height: 19px;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    box-shadow: 0 1px 3px rgba(0,0,0,0.35);
    border: 1.5px solid white;
}}
.die-tile-ghost {{
    background: {BORDER};
    box-shadow: none;
    border: 1px dashed #c7cbd6;
}}
.die-tile-sm {{
    width: 30px;
    height: 30px;
    border-radius: 8px;
}}
.die-tile-sm .die-pips {{ inset: 5px; }}
.die-tile-sm .pip {{ width: 4px; height: 4px; }}

/* ---- Bid display ---- */
.bid-display {{
    display: flex;
    align-items: center;
    gap: 14px;
    padding: 4px 0;
}}
.bid-qty {{
    font-size: 30px;
    font-weight: 800;
    color: {PRIMARY};
}}
.bid-times {{
    font-size: 20px;
    color: {TEXT_MUTED};
}}
.bid-meta {{
    color: {TEXT_MUTED};
    font-size: 13px;
    font-weight: 600;
}}
.bid-owner {{
    color: {ACCENT};
    font-weight: 700;
}}

/* ---- Probability bars ---- */
.prob-row {{ margin: 12px 0; }}
.prob-label-row {{
    display: flex;
    justify-content: space-between;
    align-items: baseline;
    margin-bottom: 5px;
}}
.prob-label {{ font-weight: 600; font-size: 14px; color: #374151; }}
.prob-value {{ font-weight: 800; font-size: 15px; }}
.prob-track {{
    background: #eceef2;
    border-radius: 999px;
    height: 10px;
    overflow: hidden;
}}
.prob-fill {{
    height: 100%;
    border-radius: 999px;
}}

/* ---- Buttons ---- */
.stButton > button {{
    border-radius: 10px;
    font-weight: 600;
    border: 1px solid {BORDER};
}}
.stButton > button[kind="primary"] {{
    background: {PRIMARY};
    border: none;
}}
.stButton > button[kind="primary"]:hover {{
    background: {PRIMARY_DARK};
}}

/* ---- Tabs ---- */
.stTabs [data-baseweb="tab-list"] {{
    gap: 4px;
}}
.stTabs [data-baseweb="tab"] {{
    border-radius: 8px 8px 0 0;
    font-weight: 600;
}}

/* ---- Recommendation banner ---- */
.rec-banner {{
    background: linear-gradient(135deg, {PRIMARY}, {PRIMARY_DARK});
    color: white;
    border-radius: 14px;
    padding: 18px 22px;
    margin: 10px 0;
}}
.rec-banner .rec-label {{
    font-size: 12px;
    text-transform: uppercase;
    letter-spacing: 0.6px;
    opacity: 0.75;
    font-weight: 700;
}}
.rec-banner .rec-action {{
    font-size: 22px;
    font-weight: 800;
    margin-top: 2px;
}}

/* ---- Player chip (eliminated / dice remaining) ---- */
.player-chip-label {{
    font-size: 12px;
    font-weight: 700;
    color: {TEXT_MUTED};
    margin-bottom: 4px;
}}
.eliminated-tag {{
    color: {RED};
    font-weight: 700;
    font-size: 13px;
}}
</style>
""", unsafe_allow_html=True)


# ======================================================================
# VISUAL COMPONENTS
# ======================================================================
PIP_LAYOUTS = {
    1: [(2, 2)],
    2: [(1, 1), (3, 3)],
    3: [(1, 1), (2, 2), (3, 3)],
    4: [(1, 1), (1, 3), (3, 1), (3, 3)],
    5: [(1, 1), (1, 3), (2, 2), (3, 1), (3, 3)],
    6: [(1, 1), (1, 3), (2, 1), (2, 3), (3, 1), (3, 3)],
}


def _die_tile_html(value, small=False, ghost=False):
    size_class = " die-tile-sm" if small else ""
    ghost_class = " die-tile-ghost" if ghost else ""
    if ghost:
        return f'<div class="die-tile{size_class}{ghost_class}"></div>'
    pips = "".join(
        f'<div class="pip" style="grid-row:{r};grid-column:{c};"></div>'
        for r, c in PIP_LAYOUTS.get(value, [])
    )
    number_badge = "" if small else f'<div class="die-number">{value}</div>'
    return (
        f'<div class="die-tile{size_class}{ghost_class}">'
        f'<div class="die-pips">{pips}</div>{number_badge}</div>'
    )


def dice_row(values, small=False):
    """Render a row of real dice (known face values) as pip tiles with number badges."""
    if not values:
        st.caption("No dice set yet.")
        return
    tiles = "".join(_die_tile_html(v, small=small) for v in values)
    st.markdown(f'<div class="dice-row">{tiles}</div>', unsafe_allow_html=True)


def ghost_dice_row(count, small=True):
    """Render N face-down/unknown dice - used for opponents' remaining count."""
    if count <= 0:
        st.markdown('<span class="eliminated-tag">✕ Eliminated</span>', unsafe_allow_html=True)
        return
    tiles = "".join(_die_tile_html(0, small=small, ghost=True) for _ in range(count))
    st.markdown(f'<div class="dice-row">{tiles}</div>', unsafe_allow_html=True)


def probability_bar(label, p):
    """Custom gradient probability bar, color-coded by favorability."""
    p = min(max(p, 0.0), 1.0)
    if p >= 0.70:
        color = GREEN
    elif p >= 0.40:
        color = AMBER
    else:
        color = RED
    st.markdown(f"""
    <div class="prob-row">
      <div class="prob-label-row">
        <span class="prob-label">{label}</span>
        <span class="prob-value" style="color:{color};">{p:.1%}</span>
      </div>
      <div class="prob-track"><div class="prob-fill" style="width:{p*100:.1f}%; background:{color};"></div></div>
    </div>
    """, unsafe_allow_html=True)


def bid_display(bid, owner=None):
    """Large, clear display of a bid: quantity, a die-face icon for the value, and type."""
    if bid is None:
        st.markdown('<span style="color:#9ca3af; font-weight:600;">No bid yet this round</span>',
                    unsafe_allow_html=True)
        return
    owner_html = f'<span class="bid-owner">Player {owner+1}</span>' if owner is not None else ""
    type_tag = "ones bid" if bid.bid_type == BidType.ONES else "regular bid"
    tile = _die_tile_html(bid.face, small=False)
    st.markdown(f"""
    <div class="bid-display">
      <div class="bid-qty">{bid.quantity}</div>
      <div class="bid-times">×</div>
      {tile}
      <div class="bid-meta">{type_tag}{'<br>' + owner_html if owner is not None else ''}</div>
    </div>
    """, unsafe_allow_html=True)


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
# SIDEBAR - persistent rules & help
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
        5. **Resolve challenge** - log the outcome when someone calls Liar or Exact

        The engine learns each opponent's honesty over the course of
        the game (Resolve challenge is what feeds that), and reasons
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

st.markdown("""
<div class="app-header">
  <div class="app-title">🎲 Liar's Dice Engine</div>
  <div class="app-subtitle">Live table assistant · lookahead + opponent-modeling strategy</div>
</div>
""", unsafe_allow_html=True)

# ==================================================================
# SETUP
# ==================================================================
if not st.session_state.setup_done:
    with st.container(border=True):
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

    # --- Status card ---
    with st.container(border=True):
        c1, c2, c3 = st.columns(3)
        c1.metric("Total dice in play", total_dice)
        c2.metric("One Rule active", "Yes" if not ones_wild else "No",
                  help="Automatically true the moment ANY player is down to exactly 1 die.")
        c3.metric("Your dice", "set" if st.session_state.own_dice else "not set")
        if st.session_state.own_dice:
            st.caption("Your current roll:")
            dice_row(st.session_state.own_dice)

    # --- Current bid card ---
    with st.container(border=True):
        st.markdown('<div class="card-label">Current bid</div>', unsafe_allow_html=True)
        bid_display(st.session_state.current_bid, st.session_state.current_bid_owner)

    # --- Dice remaining card ---
    with st.container(border=True):
        st.markdown('<div class="card-label">Dice remaining</div>', unsafe_allow_html=True)
        dc_cols = st.columns(min(num_players, 4))
        for i, c in enumerate(dice_counts):
            with dc_cols[i % 4]:
                you_tag = " (you)" if i == 0 else ""
                st.markdown(f'<div class="player-chip-label">Player {i+1}{you_tag}</div>',
                            unsafe_allow_html=True)
                ghost_dice_row(c)

    tabs = st.tabs(["1️⃣ Your dice", "2️⃣ Recommendation", "🔍 Check odds",
                     "📝 Record bid", "⚖️ Resolve challenge", "✏️ Edit count"])

    # --- On-page quick start guide (sidebar can be missed, esp. on mobile) ---
    if "quickstart_dismissed" not in st.session_state:
        st.session_state.quickstart_dismissed = False
    if not st.session_state.quickstart_dismissed:
        with st.container(border=True):
            st.markdown("**🚀 Quick start — the loop you'll repeat each round:**")
            qs1, qs2, qs3, qs4, qs5 = st.columns(5)
            qs1.markdown("**1. Your dice**\nEnter your roll")
            qs2.markdown("**2. Recommend**\nGet the best move")
            qs3.markdown("**📝 Record bid**\nLog opponents' bids")
            qs4.markdown("**⚖️ Resolve**\nLog challenge results")
            qs5.markdown("**🔁 Repeat**\nNew round, new roll")
            if st.button("Got it, hide this"):
                st.session_state.quickstart_dismissed = True
                st.rerun()

    # --- Tab: set your dice ---
    with tabs[0]:
        st.caption("Do this first at the start of every round - it also clears the current bid, "
                   "since a fresh roll means a fresh round.")
        raw = st.text_input(
            "Your dice, comma-separated", key="dice_input", placeholder="e.g. 3,4,1,6,2",
            help="Enter every die you rolled, separated by commas. Each value must be 1-6."
        )
        if raw.strip():
            try:
                preview_values = [int(x.strip()) for x in raw.split(",") if x.strip()]
                if preview_values and all(1 <= v <= 6 for v in preview_values):
                    st.caption("Preview:")
                    dice_row(preview_values)
            except ValueError:
                pass
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
                    elif not values:
                        st.error("Enter at least one die value.")
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
                    action_label = action.action_type.value.replace("_", " ").title()
                    st.markdown(f"""
                    <div class="rec-banner">
                      <div class="rec-label">Recommended move</div>
                      <div class="rec-action">{action_label}</div>
                    </div>
                    """, unsafe_allow_html=True)
                    if action.resulting_bid:
                        bid_display(action.resulting_bid)
                    probability_bar("P(true)", action.probability)
                    st.caption("How likely this bid/challenge is to hold up if checked.")
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
                bid_display(Bid(qty, face, bt))
                probability_bar("P(true / safe)", report.p_true)
                probability_bar("P(false / vulnerable to Liar)", report.p_false)
                probability_bar("P(exactly this / Exact-callable)", report.p_exact)
                st.write(f"**Legal raise right now?** {'✅ Yes' if report.is_valid_raise else '❌ No'}")

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
        preview_bt = BidType.ONES if face == 1 else BidType.REGULAR
        st.caption("Preview:")
        bid_display(Bid(qty, face, preview_bt))
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
    col_a, col_b = st.columns(2)
    with col_a:
        if st.button("🔄 Reset entire game"):
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.rerun()
    with col_b:
        if st.session_state.quickstart_dismissed and st.button("💡 Show quick start again"):
            st.session_state.quickstart_dismissed = False
            st.rerun()
