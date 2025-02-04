import unittest
from unittest.mock import patch, MagicMock
from src.services.match_service import MatchService
from src.models.match import Match
from src.models.player import Player
from src.models.database import User, db

class TestMatchmaking(unittest.TestCase):
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

        self.match_service = MatchService()
        self.initial_coins = 100

        # Test players
        self.player1_id = 'test_player1'
        self.player2_id = 'test_player2'
        self.player3_id = 'test_player3'

        # Initialize players
        self.match_service.players[self.player1_id] = Player(self.player1_id, self.initial_coins)
        self.match_service.players[self.player2_id] = Player(self.player2_id, self.initial_coins)
        self.match_service.players[self.player3_id] = Player(self.player3_id, self.initial_coins)

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def test_match_creation_validation(self):
        # Test invalid stake
        with self.assertRaises(ValueError):
            self.match_service.create_match(self.player1_id, -10)

        with self.assertRaises(ValueError):
            self.match_service.create_match(self.player1_id, self.initial_coins + 10)

        # Test valid stake
        match = self.match_service.create_match(self.player1_id, 50)
        self.assertIsNotNone(match)
        self.assertEqual(match.creator, self.player1_id)
        self.assertEqual(match.stake, 50)

    def test_match_joining_validation(self):
        # Create a match
        match = self.match_service.create_match(self.player1_id, 50)
        match_id = match.id

        # Test joining non-existent match
        with self.assertRaises(ValueError):
            self.match_service.join_match("invalid_id", self.player2_id)

        # Test joining own match
        with self.assertRaises(ValueError):
            self.match_service.join_match(match_id, self.player1_id)

        # Test valid join
        joined_match = self.match_service.join_match(match_id, self.player2_id)
        self.assertIsNotNone(joined_match)
        self.assertEqual(joined_match.joiner, self.player2_id)

        # Test joining full match
        with self.assertRaises(ValueError):
            self.match_service.join_match(match_id, self.player3_id)

    def test_match_cleanup(self):
        # Create a match
        match = self.match_service.create_match(self.player1_id, 50)
        match_id = match.id

        # Simulate disconnection and get returned coins
        returned_coins = self.match_service.handle_disconnect(self.player1_id)

        # Verify match was cleaned up
        self.assertNotIn(match_id, self.match_service.matches)
        
        # Verify stake was returned
        self.assertEqual(returned_coins, self.initial_coins)

    def test_match_timeout_handling(self):
        # Create and join match
        match = self.match_service.create_match(self.player1_id, 50)
        match_id = match.id
        self.match_service.join_match(match_id, self.player2_id)

        # Start match
        match.start_match()

        # Handle timeout
        result_match = self.match_service.handle_match_timeout(match_id)

        # Verify timeout was handled
        self.assertIsNotNone(result_match)
        self.assertEqual(result_match.status, 'finished')
        self.assertTrue(all(player in result_match.moves for player in [self.player1_id, self.player2_id]))

if __name__ == '__main__':
    unittest.main()