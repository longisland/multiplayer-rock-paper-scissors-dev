import unittest
from unittest.mock import patch, MagicMock
from src.services.game_service import GameService
from src.services.match_service import MatchService
from src.models.match import Match
from src.models.player import Player
from src.models.database import User, db

class TestGameLogic(unittest.TestCase):
    def setUp(self):
        from flask import Flask
        from src.config import TestConfig
        from src.models.database import db

        # Create a new Flask app with test config
        self.app = Flask(__name__)
        self.app.config.from_object(TestConfig)
        db.init_app(self.app)

        self.app_context = self.app.app_context()
        self.app_context.push()

        # Initialize database
        db.create_all()

        self.match_service = MatchService()
        self.game_service = GameService()
        self.creator_id = 'player1'
        self.joiner_id = 'player2'
        self.stake = 10
        self.initial_coins = 100

        # Initialize players in memory
        self.match_service.players[self.creator_id] = Player(self.creator_id, self.initial_coins)
        self.match_service.players[self.joiner_id] = Player(self.joiner_id, self.initial_coins)

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def test_match_creation_deducts_stake(self):
        # Create match
        match = self.match_service.create_match(self.creator_id, self.stake)

        # Verify stake was deducted
        creator_user = User.query.filter_by(username=self.creator_id).first()
        self.assertEqual(creator_user.coins, self.initial_coins - self.stake)
        self.assertEqual(self.match_service.players[self.creator_id].coins, self.initial_coins - self.stake)
        self.assertIsNotNone(match)
        self.assertEqual(match.creator, self.creator_id)
        self.assertEqual(match.stake, self.stake)

    def test_match_joining_deducts_stake(self):
        # Create match first
        match = self.match_service.create_match(self.creator_id, self.stake)
        self.assertIsNotNone(match)
        
        creator_user = User.query.filter_by(username=self.creator_id).first()
        self.assertEqual(creator_user.coins, self.initial_coins - self.stake)
        
        # Join match
        joined_match = self.match_service.join_match(match.id, self.joiner_id)
        self.assertIsNotNone(joined_match)

        # Verify stake was deducted from joiner
        joiner_user = User.query.filter_by(username=self.joiner_id).first()
        self.assertEqual(joiner_user.coins, self.initial_coins - self.stake)
        self.assertEqual(self.match_service.players[self.joiner_id].coins, self.initial_coins - self.stake)
        self.assertEqual(joined_match.joiner, self.joiner_id)

    def test_auto_selection_result_calculation(self):
        # Create and join match
        match = self.match_service.create_match(self.creator_id, self.stake)
        self.assertIsNotNone(match)
        
        creator_user = User.query.filter_by(username=self.creator_id).first()
        self.assertEqual(creator_user.coins, self.initial_coins - self.stake)

        joined_match = self.match_service.join_match(match.id, self.joiner_id)
        self.assertIsNotNone(joined_match)
        
        joiner_user = User.query.filter_by(username=self.joiner_id).first()
        self.assertEqual(joiner_user.coins, self.initial_coins - self.stake)

        # Start match
        match.start_match()

        # Handle timeout (auto-selection)
        result_match = self.match_service.handle_match_timeout(match.id)
        self.assertIsNotNone(result_match)

        # Verify both moves were made
        self.assertTrue(match.creator in match.moves)
        self.assertTrue(match.joiner in match.moves)
        self.assertIn(match.moves[match.creator], ['rock', 'paper', 'scissors'])
        self.assertIn(match.moves[match.joiner], ['rock', 'paper', 'scissors'])

        # Verify match was finished
        self.assertEqual(match.status, 'finished')

    def test_draw_result_returns_stakes(self):
        # Create and join match
        match = self.match_service.create_match(self.creator_id, self.stake)
        self.assertIsNotNone(match)
        
        creator_user = User.query.filter_by(username=self.creator_id).first()
        self.assertEqual(creator_user.coins, self.initial_coins - self.stake)

        joined_match = self.match_service.join_match(match.id, self.joiner_id)
        self.assertIsNotNone(joined_match)
        
        joiner_user = User.query.filter_by(username=self.joiner_id).first()
        self.assertEqual(joiner_user.coins, self.initial_coins - self.stake)

        # Start match and make same moves (force draw)
        match.start_match()
        match.make_move(self.creator_id, 'rock')
        match.make_move(self.joiner_id, 'rock')

        # Calculate result
        result = self.game_service.calculate_match_result(match, self.match_service.players)

        # Verify stakes were returned in draw
        creator_user = User.query.filter_by(username=self.creator_id).first()
        joiner_user = User.query.filter_by(username=self.joiner_id).first()
        self.assertEqual(creator_user.coins, self.initial_coins)
        self.assertEqual(joiner_user.coins, self.initial_coins)
        self.assertEqual(result['winner'], 'draw')

if __name__ == '__main__':
    unittest.main()