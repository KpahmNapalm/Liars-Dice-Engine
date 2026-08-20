"""
Regression tests for the Liar's Dice engine.

Run with: python3 -m unittest test_engine.py -v

These lock in known-correct values so future changes to the engine
(tuning weights, refactoring, adding features) can't silently break
the underlying math or rules.
"""

import unittest
from dice_probability import bid_probability, bid_probability_exact
from decision_engine import (
    Bid, BidType, is_valid_raise, enumerate_raises,
    switch_to_ones, switch_from_ones, evaluate_actions,
)
from game_state import GameState, Player
from opponent_model import OpponentModel


class TestDiceProbability(unittest.TestCase):

    def test_basic_probability_bounds(self):
        """Probabilities must always be in [0, 1]."""
        own = [3, 4, 1, 6, 2]
        for face in range(1, 7):
            for qty in range(1, 15):
                p = bid_probability(own, face, qty, 15, ones_are_wild=True)
                self.assertGreaterEqual(p, 0.0)
                self.assertLessEqual(p, 1.0)

    def test_impossible_bid_is_zero(self):
        """Bidding more than total dice in play must be impossible."""
        own = [3, 4, 1, 6, 2]
        p = bid_probability(own, face=4, quantity=100, total_dice_in_play=15, ones_are_wild=True)
        self.assertEqual(p, 0.0)

    def test_own_dice_guarantee_bid(self):
        """If you personally hold enough matching dice, the bid must be P=1.0."""
        own = [4, 4, 4, 4, 4]  # five 4s in your own hand
        p = bid_probability(own, face=4, quantity=5, total_dice_in_play=20, ones_are_wild=True)
        self.assertAlmostEqual(p, 1.0)

    def test_wilds_increase_probability(self):
        """Ones-are-wild should never make a regular-face bid LESS likely."""
        own = [3, 4, 1, 6, 2]
        p_wild = bid_probability(own, face=4, quantity=3, total_dice_in_play=10, ones_are_wild=True)
        p_no_wild = bid_probability(own, face=4, quantity=3, total_dice_in_play=10, ones_are_wild=False)
        self.assertGreaterEqual(p_wild, p_no_wild)

    def test_exact_probability_bounds(self):
        own = [3, 4, 1, 6, 2]
        p_at_least = bid_probability(own, 4, 3, 10, True)
        p_exact = bid_probability_exact(own, 4, 3, 10, True)
        self.assertLessEqual(p_exact, p_at_least)  # exact is a subset of "at least"
        self.assertGreaterEqual(p_exact, 0.0)

    def test_ones_bid_ignores_wild_flag_for_target(self):
        """Bidding ON ones should give the same per-die match prob (1/6)
        regardless of the wild flag, since 1 IS the target face either way."""
        own = [2, 3, 4, 5, 6]  # no natural 1s in hand
        p1 = bid_probability(own, face=1, quantity=2, total_dice_in_play=10, ones_are_wild=True)
        p2 = bid_probability(own, face=1, quantity=2, total_dice_in_play=10, ones_are_wild=False)
        self.assertAlmostEqual(p1, p2)


class TestBidLegality(unittest.TestCase):

    def test_opening_bid_always_legal(self):
        candidate = Bid(quantity=1, face=2, bid_type=BidType.REGULAR)
        self.assertTrue(is_valid_raise(None, candidate))

    def test_same_face_must_increase_quantity(self):
        current = Bid(quantity=3, face=4, bid_type=BidType.REGULAR)
        self.assertTrue(is_valid_raise(current, Bid(4, 4, BidType.REGULAR)))
        self.assertFalse(is_valid_raise(current, Bid(3, 4, BidType.REGULAR)))
        self.assertFalse(is_valid_raise(current, Bid(2, 4, BidType.REGULAR)))

    def test_higher_face_can_keep_quantity(self):
        current = Bid(quantity=3, face=4, bid_type=BidType.REGULAR)
        self.assertTrue(is_valid_raise(current, Bid(3, 5, BidType.REGULAR)))

    def test_cannot_cross_bid_types_via_raise(self):
        """A REGULAR bid can't be 'raised' directly into a ONES bid -
        that has to go through switch_to_ones instead."""
        current = Bid(quantity=3, face=4, bid_type=BidType.REGULAR)
        self.assertFalse(is_valid_raise(current, Bid(2, 1, BidType.ONES)))

    def test_switch_to_ones_rounds_up(self):
        current = Bid(quantity=5, face=4, bid_type=BidType.REGULAR)
        switched = switch_to_ones(current)
        self.assertEqual(switched.quantity, 3)  # ceil(5/2) = 3
        self.assertEqual(switched.face, 1)
        self.assertEqual(switched.bid_type, BidType.ONES)

    def test_switch_to_ones_exact_half(self):
        current = Bid(quantity=6, face=4, bid_type=BidType.REGULAR)
        switched = switch_to_ones(current)
        self.assertEqual(switched.quantity, 3)  # ceil(6/2) = 3, no rounding needed

    def test_switch_from_ones_doubles_plus_one(self):
        current = Bid(quantity=3, face=1, bid_type=BidType.ONES)
        options = switch_from_ones(current)
        self.assertEqual(len(options), 5)  # one per face 2-6
        for opt in options:
            self.assertEqual(opt.quantity, 7)  # 3*2 + 1 = 7
            self.assertEqual(opt.bid_type, BidType.REGULAR)

    def test_switch_functions_reject_wrong_type(self):
        regular = Bid(3, 4, BidType.REGULAR)
        ones = Bid(3, 1, BidType.ONES)
        self.assertIsNone(switch_from_ones(regular))  # can't switch-from-ones on a regular bid
        self.assertIsNone(switch_to_ones(ones))        # can't switch-to-ones on a ones bid


class TestGameState(unittest.TestCase):

    def make_game(self, dice_counts):
        players = [Player(id=i, name=f"P{i}", num_dice=d) for i, d in enumerate(dice_counts)]
        return GameState(players=players, current_player_idx=0)

    def test_total_dice_sums_active_players_only(self):
        game = self.make_game([5, 5, 0, 3])  # player 2 already eliminated
        self.assertEqual(game.total_dice_in_play, 13)
        self.assertEqual(len(game.active_players), 3)

    def test_one_rule_triggers_correctly(self):
        game = self.make_game([5, 1, 5, 5])
        self.assertTrue(game.one_rule_active)
        self.assertFalse(game.ones_are_wild)

    def test_one_rule_inactive_when_no_one_on_last_die(self):
        game = self.make_game([5, 2, 5, 5])
        self.assertFalse(game.one_rule_active)
        self.assertTrue(game.ones_are_wild)

    def test_game_over_detection(self):
        game = self.make_game([5, 0, 0, 0])
        self.assertTrue(game.is_game_over)
        self.assertEqual(game.winner.id, 0)

    def test_game_not_over_with_two_active(self):
        game = self.make_game([5, 3, 0, 0])
        self.assertFalse(game.is_game_over)
        self.assertIsNone(game.winner)

    def test_exact_gain_capped_at_six(self):
        game = self.make_game([6, 5, 5, 5])
        game.roll_all_dice()
        game.resolve_exact(caller=game.players[0], was_exact=True)
        self.assertEqual(game.players[0].num_dice, 6)  # capped, not 7

    def test_next_player_idx_skips_eliminated(self):
        game = self.make_game([5, 0, 5, 5])  # player 1 eliminated
        nxt = game.next_player_idx(0)
        self.assertEqual(nxt, 2)  # skips player 1


class TestOpponentModel(unittest.TestCase):

    def test_no_data_returns_raw_probability_unchanged(self):
        model = OpponentModel()
        raw_p = 0.75
        adjusted = model.adjusted_probability(player_id=1, face=4, raw_p=raw_p)
        self.assertAlmostEqual(adjusted, raw_p)  # zero samples -> zero weight on empirical rate

    def test_single_data_point_has_small_effect(self):
        """Regression guard for the over-reaction bug found in Task 11:
        one unlucky result should NOT swing trust drastically."""
        model = OpponentModel(min_samples_for_confidence=15)
        model.record_resolution(player_id=1, face=4, was_true=False)
        adjusted = model.adjusted_probability(player_id=1, face=4, raw_p=0.85)
        # Should move toward 0 but not collapse - within a bounded range
        self.assertGreater(adjusted, 0.7)
        self.assertLess(adjusted, 0.85)

    def test_established_pattern_has_larger_effect(self):
        """Many consistent observations SHOULD meaningfully shift trust."""
        model = OpponentModel(min_samples_for_confidence=15)
        for _ in range(20):
            model.record_resolution(player_id=1, face=4, was_true=False)
        adjusted = model.adjusted_probability(player_id=1, face=4, raw_p=0.85)
        # With n=20 samples at threshold 15, weight = 20/35 ≈ 0.57, so
        # adjusted ≈ 0.43*0.85 ≈ 0.36 - a large, meaningful drop from 0.85,
        # even though it hasn't fully converged to the empirical 0.
        self.assertLess(adjusted, 0.5)


if __name__ == "__main__":
    unittest.main(verbosity=2)
