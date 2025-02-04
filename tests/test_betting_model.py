import unittest
from unittest.mock import patch, MagicMock
from src.services.game_service import GameService
from src.services.match_service import MatchService
from src.models.match import Match
from src.models.player import Player
from src.models.database import User, db

class TestBettingModel(unittest.TestCase):
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

    def test_stake_validation(self):
        # Test minimum stake
        with self.assertRaises(ValueError):
            self.match_service.create_match(self.player1_id, 0)

        # Test negative stake
        with self.assertRaises(ValueError):
            self.match_service.create_match(self.player1_id, -10)

        # Test stake greater than player's coins
        with self.assertRaises(ValueError):
            self.match_service.create_match(self.player1_id, self.initial_coins + 1)

        # Test valid stake
        match = self.match_service.create_match(self.player1_id, self.initial_coins)
        self.assertIsNotNone(match)
        self.assertEqual(match.stake, self.initial_coins)

    def test_win_reward_distribution(self):
        stake = 50
        match = self.match_service.create_match(self.player1_id, stake)
        self.match_service.join_match(match.id, self.player2_id)
        match.start_match()

        # Initial balance check
        self.assertEqual(self.match_service.players[self.player1_id].coins, self.initial_coins - stake)
        self.assertEqual(self.match_service.players[self.player2_id].coins, self.initial_coins - stake)

        # Player 1 wins
        match.make_move(self.player1_id, 'rock')
        match.make_move(self.player2_id, 'scissors')
        result = self.game_service.calculate_match_result(match, self.match_service.players)

        # Verify winner gets both stakes
        self.assertEqual(self.match_service.players[self.player1_id].coins, self.initial_coins + stake)
        self.assertEqual(self.match_service.players[self.player2_id].coins, self.initial_coins - stake)

    def test_draw_stake_return(self):
        stake = 50
        match = self.match_service.create_match(self.player1_id, stake)
        self.match_service.join_match(match.id, self.player2_id)
        match.start_match()

        # Initial balance check
        self.assertEqual(self.match_service.players[self.player1_id].coins, self.initial_coins - stake)
        self.assertEqual(self.match_service.players[self.player2_id].coins, self.initial_coins - stake)

        # Force draw
        match.make_move(self.player1_id, 'rock')
        match.make_move(self.player2_id, 'rock')
        result = self.game_service.calculate_match_result(match, self.match_service.players)

        # Verify stakes are returned
        self.assertEqual(self.match_service.players[self.player1_id].coins, self.initial_coins)
        self.assertEqual(self.match_service.players[self.player2_id].coins, self.initial_coins)

    def test_rematch_stake_handling(self):
        stake = 50
        # Initial match
        match = self.match_service.create_match(self.player1_id, stake)
        self.match_service.join_match(match.id, self.player2_id)
        match.start_match()

        # Complete match
        match.make_move(self.player1_id, 'rock')
        match.make_move(self.player2_id, 'scissors')
        self.game_service.calculate_match_result(match, self.match_service.players)

        # Request rematch
        rematch = self.match_service.request_rematch(match.id, self.player1_id)
        
        # Verify stake is deducted again
        self.assertEqual(self.match_service.players[self.player1_id].coins, 
                        self.initial_coins + stake - stake)  # Won previous + new stake deducted

        # Accept rematch
        accepted_rematch = self.match_service.accept_rematch(rematch.id, self.player2_id)
        
        # Verify stake is deducted from second player
        self.assertEqual(self.match_service.players[self.player2_id].coins, 
                        self.initial_coins - stake - stake)  # Lost previous + new stake deducted

    def test_disconnection_stake_return(self):
        stake = 50
        match = self.match_service.create_match(self.player1_id, stake)
        self.match_service.join_match(match.id, self.player2_id)
        match.start_match()

        # Initial balance check
        self.assertEqual(self.match_service.players[self.player1_id].coins, self.initial_coins - stake)
        self.assertEqual(self.match_service.players[self.player2_id].coins, self.initial_coins - stake)

        # Simulate disconnection
        self.match_service.handle_disconnect(self.player1_id)

        # Verify stakes are returned
        self.assertEqual(self.match_service.players[self.player1_id].coins, self.initial_coins)
        self.assertEqual(self.match_service.players[self.player2_id].coins, self.initial_coins)

if __name__ == '__main__':
    unittest.main()