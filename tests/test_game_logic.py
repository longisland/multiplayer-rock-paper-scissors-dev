import os
import unittest
from flask import Flask
from src.models.database import User, db
from src.services.game_service import GameService
from src.services.match_service import MatchService
from src.models.match import Match
from src.config import Config

class TestConfig(Config):
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    TESTING = True

class TestGameLogic(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Create Flask app
        cls.app = Flask(__name__)
        cls.app.config.from_object(TestConfig)
        
        # Initialize database
        db.init_app(cls.app)
        
        # Create application context
        cls.app_context = cls.app.app_context()
        cls.app_context.push()
        
        # Create tables
        db.create_all()

    @classmethod
    def tearDownClass(cls):
        # Drop tables
        db.drop_all()
        
        # Remove application context
        cls.app_context.pop()

    def setUp(self):
        # Initialize services
        self.game_service = GameService()
        self.match_service = MatchService()
        
        # Create test users with initial balance of 100 coins
        self.creator_user = User(username='test_creator', coins=100)
        self.joiner_user = User(username='test_joiner', coins=100)
        
        # Add users to database
        db.session.add(self.creator_user)
        db.session.add(self.joiner_user)
        db.session.commit()
        
        # Create test match with stake of 10 coins
        self.stake = 10
        self.match = Match('test_match', 'test_creator', self.stake)
        self.match.joiner = 'test_joiner'
        
        # Store initial balances
        self.initial_balance = 100  # Both players start with 100 coins
        
        # Deduct stakes at match start
        self.creator_user.coins -= self.stake  # Now 90
        self.joiner_user.coins -= self.stake   # Now 90
        db.session.commit()
        
        # Initialize auto_selected set
        self.match.auto_selected = set()
        
        # Create player objects for stats
        self.players = {
            'test_creator': self.creator_user,
            'test_joiner': self.joiner_user
        }

    def tearDown(self):
        # Clean up database
        db.session.remove()
        db.drop_all()
        db.create_all()

    def test_immediate_stake_deduction(self):
        """Test that stakes are immediately deducted at match start"""
        # Verify balances after stake deduction (90 coins each)
        self.assertEqual(self.creator_user.coins, self.initial_balance - self.stake)
        self.assertEqual(self.joiner_user.coins, self.initial_balance - self.stake)

    def test_manual_vs_manual_win(self):
        """Test manual vs manual win scenario"""
        # Set moves
        self.match.moves = {
            'test_creator': 'rock',
            'test_joiner': 'scissors'
        }
        
        # Process result
        result_data = self.game_service.calculate_match_result(self.match, self.players)
        
        # Verify final balances
        # Creator: 90 + 20 = 110 (initial - stake + double stake)
        # Joiner: 90 + 0 = 90 (initial - stake)
        self.assertEqual(self.creator_user.coins, self.initial_balance + self.stake)
        self.assertEqual(self.joiner_user.coins, self.initial_balance - self.stake)

    def test_auto_vs_manual_win(self):
        """Test auto vs manual win scenario"""
        # Set moves and mark as auto
        self.match.moves = {
            'test_creator': 'rock',
            'test_joiner': 'scissors'
        }
        self.match.auto_selected.add('test_creator')
        
        # Process result
        result_data = self.game_service.calculate_match_result(self.match, self.players)
        
        # Verify final balances
        # Creator: 90 + 20 = 110 (initial - stake + double stake)
        # Joiner: 90 + 0 = 90 (initial - stake)
        self.assertEqual(self.creator_user.coins, self.initial_balance + self.stake)
        self.assertEqual(self.joiner_user.coins, self.initial_balance - self.stake)

    def test_manual_vs_auto_win(self):
        """Test manual vs auto win scenario"""
        # Set moves and mark as auto
        self.match.moves = {
            'test_creator': 'rock',
            'test_joiner': 'scissors'
        }
        self.match.auto_selected.add('test_joiner')
        
        # Process result
        result_data = self.game_service.calculate_match_result(self.match, self.players)
        
        # Verify final balances
        # Creator: 90 + 20 = 110 (initial - stake + double stake)
        # Joiner: 90 + 0 = 90 (initial - stake)
        self.assertEqual(self.creator_user.coins, self.initial_balance + self.stake)
        self.assertEqual(self.joiner_user.coins, self.initial_balance - self.stake)

    def test_auto_vs_auto_win(self):
        """Test auto vs auto win scenario"""
        # Set moves and mark both as auto
        self.match.moves = {
            'test_creator': 'rock',
            'test_joiner': 'scissors'
        }
        self.match.auto_selected.add('test_creator')
        self.match.auto_selected.add('test_joiner')
        
        # Process result
        result_data = self.game_service.calculate_match_result(self.match, self.players)
        
        # Verify final balances
        # Creator: 90 + 20 = 110 (initial - stake + double stake)
        # Joiner: 90 + 0 = 90 (initial - stake)
        self.assertEqual(self.creator_user.coins, self.initial_balance + self.stake)
        self.assertEqual(self.joiner_user.coins, self.initial_balance - self.stake)

    def test_manual_vs_manual_draw(self):
        """Test manual vs manual draw scenario"""
        # Set moves
        self.match.moves = {
            'test_creator': 'rock',
            'test_joiner': 'rock'
        }
        
        # Process result
        result_data = self.game_service.calculate_match_result(self.match, self.players)
        
        # Verify final balances
        # Both: 90 + 10 = 100 (initial - stake + stake back)
        self.assertEqual(self.creator_user.coins, self.initial_balance)
        self.assertEqual(self.joiner_user.coins, self.initial_balance)

    def test_auto_vs_manual_draw(self):
        """Test auto vs manual draw scenario"""
        # Set moves and mark one as auto
        self.match.moves = {
            'test_creator': 'rock',
            'test_joiner': 'rock'
        }
        self.match.auto_selected.add('test_creator')
        
        # Process result
        result_data = self.game_service.calculate_match_result(self.match, self.players)
        
        # Verify final balances
        # Both: 90 + 10 = 100 (initial - stake + stake back)
        self.assertEqual(self.creator_user.coins, self.initial_balance)
        self.assertEqual(self.joiner_user.coins, self.initial_balance)

    def test_auto_vs_auto_draw(self):
        """Test auto vs auto draw scenario"""
        # Set moves and mark both as auto
        self.match.moves = {
            'test_creator': 'rock',
            'test_joiner': 'rock'
        }
        self.match.auto_selected.add('test_creator')
        self.match.auto_selected.add('test_joiner')
        
        # Process result
        result_data = self.game_service.calculate_match_result(self.match, self.players)
        
        # Verify final balances
        # Both: 90 + 10 = 100 (initial - stake + stake back)
        self.assertEqual(self.creator_user.coins, self.initial_balance)
        self.assertEqual(self.joiner_user.coins, self.initial_balance)

    def test_rematch_stake_verification(self):
        """Test rematch stake verification"""
        # Set balances to exactly stake amount
        self.creator_user.coins = self.stake
        self.joiner_user.coins = self.stake
        
        # Verify both players can afford the rematch
        can_rematch = (
            self.creator_user.coins >= self.stake and 
            self.joiner_user.coins >= self.stake
        )
        self.assertTrue(can_rematch)
        
        # Reduce one player's balance below stake
        self.creator_user.coins = self.stake - 1
        
        # Verify rematch is not allowed
        can_rematch = (
            self.creator_user.coins >= self.stake and 
            self.joiner_user.coins >= self.stake
        )
        self.assertFalse(can_rematch)

if __name__ == '__main__':
    unittest.main()