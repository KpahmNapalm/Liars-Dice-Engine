"""
Multi-player game state management.

Wires the GameState into the probability/decision engines so the
engine always reasons about the REAL table - correct dice totals,
correct wild status, correct turn order - rather than manually
specified numbers.
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict
import random

from decision_engine import (
    Bid, BidType, ActionType, Action,
    evaluate_actions, query_bid_odds, OddsReport,
)


@dataclass
class Player:
    id: int
    name: str
    dice: List[int] = field(default_factory=list)
    num_dice: int = 5
    profile: Dict = field(default_factory=dict)

    @property
    def is_eliminated(self) -> bool:
        return self.num_dice <= 0


@dataclass
class GameState:
    players: List[Player]
    current_player_idx: int
    current_bid: Optional[Bid] = None
    bid_history: List[tuple] = field(default_factory=list)
    round_number: int = 1

    @property
    def active_players(self) -> List[Player]:
        return [p for p in self.players if not p.is_eliminated]

    @property
    def total_dice_in_play(self) -> int:
        return sum(p.num_dice for p in self.active_players)

    @property
    def one_rule_active(self) -> bool:
        return any(p.num_dice == 1 for p in self.active_players)

    @property
    def ones_are_wild(self) -> bool:
        return not self.one_rule_active

    @property
    def current_player(self) -> Player:
        return self.players[self.current_player_idx]

    @property
    def is_game_over(self) -> bool:
        return len(self.active_players) <= 1

    @property
    def winner(self) -> Optional[Player]:
        active = self.active_players
        return active[0] if len(active) == 1 else None

    def roll_all_dice(self):
        for p in self.active_players:
            p.dice = [random.randint(1, 6) for _ in range(p.num_dice)]

    def next_player_idx(self, from_idx: int) -> int:
        n = len(self.players)
        idx = (from_idx + 1) % n
        while self.players[idx].is_eliminated:
            idx = (idx + 1) % n
        return idx

    def advance_turn(self):
        self.current_player_idx = self.next_player_idx(self.current_player_idx)

    def resolve_liar(self, challenger: Player, bid_owner: Player, bid_was_true: bool):
        if bid_was_true:
            challenger.num_dice = max(0, challenger.num_dice - 1)
            next_starter = challenger
        else:
            bid_owner.num_dice = max(0, bid_owner.num_dice - 1)
            next_starter = bid_owner
        self._start_new_round(next_starter)

    def resolve_exact(self, caller: Player, was_exact: bool):
        if was_exact:
            caller.num_dice = min(6, caller.num_dice + 1)
        else:
            caller.num_dice = max(0, caller.num_dice - 1)
        self._start_new_round(caller)

    def _start_new_round(self, starting_player: Player):
        self.round_number += 1
        self.current_bid = None
        self.bid_history = []
        if starting_player.is_eliminated:
            self.current_player_idx = self.next_player_idx(
                self.players.index(starting_player)
            )
        else:
            self.current_player_idx = self.players.index(starting_player)
        self.roll_all_dice()

    def get_recommended_actions(self, min_raise_probability: float = 0.05) -> List[Action]:
        player = self.current_player
        return evaluate_actions(
            own_dice=player.dice,
            current_bid=self.current_bid,
            total_dice_in_play=self.total_dice_in_play,
            ones_are_wild=self.ones_are_wild,
            min_raise_probability=min_raise_probability,
        )

    def query_odds(self, face: int, quantity: int, bid_type: BidType) -> OddsReport:
        player = self.current_player
        return query_bid_odds(
            own_dice=player.dice,
            face=face,
            quantity=quantity,
            bid_type=bid_type,
            total_dice_in_play=self.total_dice_in_play,
            ones_are_wild=self.ones_are_wild,
            current_bid=self.current_bid,
        )
