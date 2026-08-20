"""
Opponent modeling (Phase 2).

Tracks each player's track record of bid honesty, learned only from
bids that actually get challenged (Liar/Exact calls) - unverified
bids leave no signal. This is a real limitation: the model is biased
toward a player's riskier bids, since safe bids rarely get challenged
and so rarely get checked. Treat this as informative, not complete.

The adjustment: blend the raw combinatorial P(bid true) from
dice_probability.py with the bidder's empirical true-rate, using a
shrinkage weight that grows as more data accumulates on that player.
"""

from dataclasses import dataclass, field
from typing import Dict


@dataclass
class PlayerProfile:
    player_id: int
    bids_resolved: int = 0
    bids_true: int = 0
    per_face_resolved: Dict[int, int] = field(default_factory=dict)
    per_face_true: Dict[int, int] = field(default_factory=dict)

    def record(self, face: int, was_true: bool):
        self.bids_resolved += 1
        self.per_face_resolved[face] = self.per_face_resolved.get(face, 0) + 1
        if was_true:
            self.bids_true += 1
            self.per_face_true[face] = self.per_face_true.get(face, 0) + 1

    @property
    def empirical_true_rate(self) -> float:
        if self.bids_resolved == 0:
            return 0.5  # no data - neutral
        return self.bids_true / self.bids_resolved

    def face_true_rate(self, face: int) -> float:
        resolved = self.per_face_resolved.get(face, 0)
        if resolved == 0:
            return self.empirical_true_rate  # fall back to overall rate
        return self.per_face_true.get(face, 0) / resolved


class OpponentModel:
    """
    Container for all players' profiles over the course of a game.
    Reset this per-game (a fresh set of opponents shouldn't carry
    over another game's read on them, unless you deliberately want
    persistent cross-game player tracking - that would be a further
    extension).
    """

    def __init__(self, min_samples_for_confidence: int = 15):
        self.profiles: Dict[int, PlayerProfile] = {}
        self.min_samples_for_confidence = min_samples_for_confidence

    def get_profile(self, player_id: int) -> PlayerProfile:
        if player_id not in self.profiles:
            self.profiles[player_id] = PlayerProfile(player_id=player_id)
        return self.profiles[player_id]

    def record_resolution(self, player_id: int, face: int, was_true: bool):
        self.get_profile(player_id).record(face, was_true)

    def adjusted_probability(self, player_id: int, face: int, raw_p: float) -> float:
        """
        Blend the raw combinatorial probability with this player's
        track record. Shrinkage weight grows with sample size, so a
        handful of observations won't overwhelm the math, but a
        well-established pattern will.
        """
        profile = self.get_profile(player_id)
        n = profile.per_face_resolved.get(face, 0)
        # Shrinkage: weight approaches 1 as n grows past min_samples_for_confidence
        weight = n / (n + self.min_samples_for_confidence)
        empirical = profile.face_true_rate(face)
        return (1 - weight) * raw_p + weight * empirical
