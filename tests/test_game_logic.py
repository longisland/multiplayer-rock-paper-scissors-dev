import unittest
from unittest.mock import MagicMock, patch
from flask import Flask
from src.services.game_service import GameService
from src.models.match import Match
from src.models.player import Player
from src.models.database import db, User, GameHistory

class TestGameLogic(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Create Flask app for testing
        cls.app = Flask(__name__)
        cls.app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
        cls.app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
        db.init_app(cls.app)
        
        # Create database tables
        with cls.app.app_context():
            db.create_all()

    def setUp(self):
        # Create application context
        self.ctx = self.app.app_context()
        self.ctx.push()

        # Create test users with extra coins to account for initial stake deduction
        self.user1 = User(username='player1', coins=110)
        self.user2 = User(username='player2', coins=110)
        db.session.add(self.user1)
        db.session.add(self.user2)
        db.session.commit()

        self.game_service = GameService()
        self.match = Match('test_match', 'player1', 10)
        self.match.joiner = 'player2'

        # Create players and deduct initial stakes
        self.players = {
            'player1': Player('player1', 100),
            'player2': Player('player2', 100)
        }
        
        # Deduct stakes from both players
        self.user1.coins -= self.match.stake
        self.user2.coins -= self.match.stake
        self.players['player1'].coins = self.user1.coins
        self.players['player2'].coins = self.user2.coins
        db.session.commit()

    def tearDown(self):
        # Clear database
        db.session.remove()
        db.drop_all()
        db.create_all()
        self.ctx.pop()

    def test_normal_moves(self):
        """Test all possible normal move combinations"""
        test_cases = [
            # (player1_move, player2_move, expected_result)
            ('rock', 'scissors', 'player1'),
            ('rock', 'paper', 'player2'),
            ('rock', 'rock', 'draw'),
            ('paper', 'rock', 'player1'),
            ('paper', 'scissors', 'player2'),
            ('paper', 'paper', 'draw'),
            ('scissors', 'paper', 'player1'),
            ('scissors', 'rock', 'player2'),
            ('scissors', 'scissors', 'draw')
        ]

        for p1_move, p2_move, expected in test_cases:
            self.match.moves = {
                'player1': p1_move,
                'player2': p2_move
            }
            result = self.game_service.calculate_winner(p1_move, p2_move)
            self.assertEqual(result, expected,
                f"Failed with moves: player1={p1_move}, player2={p2_move}")

    def test_auto_selected_moves(self):
        """Test that auto-selected moves follow the same rules"""
        # Test all combinations with auto-selected moves
        moves = ['rock', 'paper', 'scissors']
        for p1_move in moves:
            for p2_move in moves:
                # Normal move vs auto-selected
                self.match.moves = {
                    'player1': p1_move,
                    'player2': p2_move  # Simulating auto-selected
                }
                result1 = self.game_service.calculate_winner(p1_move, p2_move)
                
                # Auto-selected vs normal move
                self.match.moves = {
                    'player1': p1_move,  # Simulating auto-selected
                    'player2': p2_move
                }
                result2 = self.game_service.calculate_winner(p1_move, p2_move)
                
                # Results should be the same regardless of auto-selection
                self.assertEqual(result1, result2,
                    f"Auto-selected moves gave different results: {p1_move} vs {p2_move}")

    def test_stake_handling(self):
        """Test proper stake handling in different scenarios"""
        initial_balance = 90  # 100 - 10 (initial stake)
        stake = 10

        test_cases = [
            # (p1_move, p2_move, p1_expected_balance, p2_expected_balance)
            ('rock', 'scissors', initial_balance + 2*stake, initial_balance),  # P1 wins
            ('rock', 'paper', initial_balance, initial_balance + 2*stake),    # P2 wins
            ('rock', 'rock', initial_balance + stake, initial_balance + stake),  # Draw
        ]

        for p1_move, p2_move, p1_balance, p2_balance in test_cases:
            # Reset balances and match state
            self.user1.coins = initial_balance
            self.user2.coins = initial_balance
            self.players['player1'].coins = initial_balance
            self.players['player2'].coins = initial_balance
            db.session.commit()

            # Reset match state
            self.match.moves = {}
            self.match.status = 'playing'
            self.match.result = None

            # Set moves
            self.match.moves = {
                'player1': p1_move,
                'player2': p2_move
            }

            # Calculate result
            result = self.game_service.calculate_match_result(self.match, self.players)

            # Verify balances
            self.assertEqual(self.players['player1'].coins, p1_balance,
                f"Player 1 balance incorrect for {p1_move} vs {p2_move}")
            self.assertEqual(self.players['player2'].coins, p2_balance,
                f"Player 2 balance incorrect for {p1_move} vs {p2_move}")

    def test_auto_select_stake_handling(self):
        """Test that auto-selected moves handle stakes correctly"""
        initial_balance = 90  # 100 - 10 (initial stake)
        stake = 10

        # Test auto-selected moves with stakes
        moves = ['rock', 'paper', 'scissors']
        for p1_move in moves:
            for p2_move in moves:
                # Reset balances and match state
                self.user1.coins = initial_balance
                self.user2.coins = initial_balance
                self.players['player1'].coins = initial_balance
                self.players['player2'].coins = initial_balance
                db.session.commit()

                # Reset match state
                self.match.moves = {}
                self.match.status = 'playing'
                self.match.result = None

                # Set moves (one auto-selected)
                self.match.moves = {
                    'player1': p1_move,
                    'player2': p2_move  # Simulating auto-selected
                }

                # Calculate result
                result = self.game_service.calculate_match_result(self.match, self.players)

                # Calculate expected balances
                winner = self.game_service.calculate_winner(p1_move, p2_move)
                if winner == 'draw':
                    expected_p1_balance = initial_balance + stake
                    expected_p2_balance = initial_balance + stake
                elif winner == 'player1':
                    expected_p1_balance = initial_balance + 2*stake
                    expected_p2_balance = initial_balance
                else:  # player2 wins
                    expected_p1_balance = initial_balance
                    expected_p2_balance = initial_balance + 2*stake

                # Verify balances
                self.assertEqual(self.players['player1'].coins, expected_p1_balance,
                    f"Auto-select: Player 1 balance incorrect for {p1_move} vs {p2_move}")
                self.assertEqual(self.players['player2'].coins, expected_p2_balance,
                    f"Auto-select: Player 2 balance incorrect for {p1_move} vs {p2_move}")

if __name__ == '__main__':
    unittest.main()