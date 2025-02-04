import unittest
from unittest.mock import patch, MagicMock
from src.services.game_service import GameService
from src.services.match_service import MatchService
from src.models.match import Match
from src.models.player import Player
from src.models.database import User, db

class TestGameMechanics(unittest.TestCase):
    def setUp(self):
        from flask import Flask
        from src.config import TestConfig
        from src.models.database import db

        self.app = Flask(__name__)
        self.app.config.from_object(TestConfig)
        db.init_app(self.app)

        self.app_context = self.app.app_context()
        self.app_context.push()

        db.create_all()

        self.game_service = GameService()
        self.match_service = MatchService()
        self.initial_coins = 100

        # Test players
        self.player1_id = 'test_player1'
        self.player2_id = 'test_player2'

        # Initialize players
        self.match_service.players[self.player1_id] = Player(self.player1_id, self.initial_coins)
        self.match_service.players[self.player2_id] = Player(self.player2_id, self.initial_coins)

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def test_move_validation(self):
        # Create and join match
        match = self.match_service.create_match(self.player1_id, 50)
        self.match_service.join_match(match.id, self.player2_id)
        match.start_match()

        # Test invalid move
        with self.assertRaises(ValueError):
            match.make_move(self.player1_id, 'invalid_move')

        # Test valid move
        match.make_move(self.player1_id, 'rock')
        self.assertEqual(match.moves[self.player1_id], 'rock')

        # Test making move twice
        with self.assertRaises(ValueError):
            match.make_move(self.player1_id, 'paper')

    def test_auto_selection_mechanics(self):
        match = self.match_service.create_match(self.player1_id, 50)
        self.match_service.join_match(match.id, self.player2_id)
        match.start_match()

        # Only player1 makes a move
        match.make_move(self.player1_id, 'rock')

        # Handle timeout
        result_match = self.match_service.handle_match_timeout(match.id)

        # Verify auto-selection for player2
        self.assertIn(result_match.moves[self.player2_id], ['rock', 'paper', 'scissors'])

    def test_rematch_mechanics(self):
        # Create initial match
        match = self.match_service.create_match(self.player1_id, 50)
        self.match_service.join_match(match.id, self.player2_id)
        match.start_match()

        # Complete match
        match.make_move(self.player1_id, 'rock')
        match.make_move(self.player2_id, 'scissors')
        self.game_service.calculate_match_result(match, self.match_service.players)

        # Request rematch
        rematch = self.match_service.request_rematch(match.id, self.player1_id)
        self.assertIsNotNone(rematch)
        self.assertTrue(rematch.creator_rematch)
        self.assertFalse(rematch.joiner_rematch)

        # Accept rematch
        accepted_rematch = self.match_service.accept_rematch(match.id, self.player2_id)
        self.assertIsNotNone(accepted_rematch)
        self.assertEqual(accepted_rematch.stake, match.stake)
        self.assertEqual(accepted_rematch.creator, self.player1_id)
        self.assertEqual(accepted_rematch.joiner, self.player2_id)
        self.assertEqual(accepted_rematch.status, 'playing')

        # Verify old match is cleaned up
        self.assertNotIn(match.id, self.match_service.matches)

    def test_game_result_calculation(self):
        test_cases = [
            ('rock', 'scissors', self.player1_id),
            ('scissors', 'paper', self.player1_id),
            ('paper', 'rock', self.player1_id),
            ('scissors', 'rock', self.player2_id),
            ('paper', 'scissors', self.player2_id),
            ('rock', 'paper', self.player2_id),
            ('rock', 'rock', 'draw'),
            ('paper', 'paper', 'draw'),
            ('scissors', 'scissors', 'draw')
        ]

        for p1_move, p2_move, expected_winner in test_cases:
            # Reset player coins for each test case
            self.match_service.players[self.player1_id].coins = self.initial_coins
            self.match_service.players[self.player2_id].coins = self.initial_coins

            # Create and setup match
            match = self.match_service.create_match(self.player1_id, 50)
            self.match_service.join_match(match.id, self.player2_id)
            match.start_match()

            # Make moves
            match.make_move(self.player1_id, p1_move)
            match.make_move(self.player2_id, p2_move)

            # Calculate result
            result = self.game_service.calculate_match_result(match, self.match_service.players)
            self.assertIsNotNone(result)
            self.assertEqual(result['winner'], expected_winner)

    def test_match_timer_mechanics(self):
        match = self.match_service.create_match(self.player1_id, 50)
        self.match_service.join_match(match.id, self.player2_id)
        
        # Record start time
        start_time = match.start_match()
        self.assertIsNotNone(start_time)

        # Verify match is in progress
        self.assertEqual(match.status, 'playing')

        # Handle timeout
        result_match = self.match_service.handle_match_timeout(match.id)
        self.assertEqual(result_match.status, 'finished')

if __name__ == '__main__':
    unittest.main()