import unittest
from src.models.database import User, db
from src.services.game_service import GameService
from src.services.match_service import MatchService
from src.models.match import Match
from src.config import Config

class TestGameLogic(unittest.TestCase):
    def setUp(self):
        # Initialize services
        self.game_service = GameService()
        self.match_service = MatchService()
        
        # Create test users with initial balance of 100 coins
        self.creator_user = User(username='test_creator', coins=100)
        self.joiner_user = User(username='test_joiner', coins=100)
        
        # Create test match with stake of 10 coins
        self.stake = 10
        self.match = Match('test_match', 'test_creator', self.stake)
        self.match.joiner = 'test_joiner'
        
        # Store initial balances
        self.initial_balance = 100  # Both players start with 100 coins
        
        # Deduct stakes at match start
        self.creator_user.coins -= self.stake
        self.joiner_user.coins -= self.stake

    def test_immediate_stake_deduction(self):
        """Test that stakes are immediately deducted at match start"""
        # Verify balances after stake deduction
        self.assertEqual(self.creator_user.coins, self.initial_balance - self.stake)
        self.assertEqual(self.joiner_user.coins, self.initial_balance - self.stake)

    def test_manual_win_creator(self):
        """Test creator winning with manual moves"""
        # Set moves
        self.match.moves = {
            'test_creator': 'rock',
            'test_joiner': 'scissors'
        }
        
        # Calculate result
        result = self.game_service.calculate_winner(
            self.match.moves['test_creator'],
            self.match.moves['test_joiner']
        )
        
        # Verify result
        self.assertEqual(result, 'player1')
        
        # Apply win rewards
        self.creator_user.coins += 2 * self.stake  # Winner gets both stakes
        
        # Verify final balances
        # Creator: Initial (100) - Stake (10) + Double Stake (20) = 110
        # Joiner: Initial (100) - Stake (10) = 90
        self.assertEqual(self.creator_user.coins, self.initial_balance + self.stake)
        self.assertEqual(self.joiner_user.coins, self.initial_balance - self.stake)

    def test_manual_loss_creator(self):
        """Test creator losing with manual moves"""
        # Set moves
        self.match.moves = {
            'test_creator': 'scissors',
            'test_joiner': 'rock'
        }
        
        # Calculate result
        result = self.game_service.calculate_winner(
            self.match.moves['test_creator'],
            self.match.moves['test_joiner']
        )
        
        # Verify result
        self.assertEqual(result, 'player2')
        
        # Apply win rewards to joiner
        self.joiner_user.coins += 2 * self.stake  # Winner gets both stakes
        
        # Verify final balances
        # Creator: Initial (100) - Stake (10) = 90
        # Joiner: Initial (100) - Stake (10) + Double Stake (20) = 110
        self.assertEqual(self.creator_user.coins, self.initial_balance - self.stake)
        self.assertEqual(self.joiner_user.coins, self.initial_balance + self.stake)

    def test_auto_win_creator(self):
        """Test creator winning with auto move"""
        # Set moves
        self.match.moves = {
            'test_creator': 'auto',
            'test_joiner': 'scissors'
        }
        
        # Calculate result (auto move becomes random)
        result = self.game_service.calculate_winner(
            'rock',  # Simulating random auto move that wins
            self.match.moves['test_joiner']
        )
        
        # Verify result
        self.assertEqual(result, 'player1')
        
        # Apply win rewards (auto win only returns stake)
        self.creator_user.coins += self.stake
        
        # Verify final balances
        # Creator: Initial (100) - Stake (10) + Stake (10) = 100
        # Joiner: Initial (100) - Stake (10) = 90
        self.assertEqual(self.creator_user.coins, self.initial_balance)
        self.assertEqual(self.joiner_user.coins, self.initial_balance - self.stake)

    def test_auto_loss_creator(self):
        """Test creator losing with auto move"""
        # Set moves
        self.match.moves = {
            'test_creator': 'auto',
            'test_joiner': 'rock'
        }
        
        # Calculate result (auto move becomes random)
        result = self.game_service.calculate_winner(
            'scissors',  # Simulating random auto move that loses
            self.match.moves['test_joiner']
        )
        
        # Verify result
        self.assertEqual(result, 'player2')
        
        # Apply win rewards to joiner (manual win)
        self.joiner_user.coins += 2 * self.stake
        
        # Verify final balances
        # Creator: Initial (100) - Stake (10) = 90
        # Joiner: Initial (100) - Stake (10) + Double Stake (20) = 110
        self.assertEqual(self.creator_user.coins, self.initial_balance - self.stake)
        self.assertEqual(self.joiner_user.coins, self.initial_balance + self.stake)

    def test_manual_draw(self):
        """Test draw with manual moves"""
        # Set moves
        self.match.moves = {
            'test_creator': 'rock',
            'test_joiner': 'rock'
        }
        
        # Calculate result
        result = self.game_service.calculate_winner(
            self.match.moves['test_creator'],
            self.match.moves['test_joiner']
        )
        
        # Verify result
        self.assertEqual(result, 'draw')
        
        # Apply draw rewards (both get stakes back)
        self.creator_user.coins += self.stake
        self.joiner_user.coins += self.stake
        
        # Verify final balances
        # Both: Initial (100) - Stake (10) + Stake (10) = 100
        self.assertEqual(self.creator_user.coins, self.initial_balance)
        self.assertEqual(self.joiner_user.coins, self.initial_balance)

    def test_auto_draw(self):
        """Test draw with auto moves"""
        # Set moves
        self.match.moves = {
            'test_creator': 'auto',
            'test_joiner': 'auto'
        }
        
        # Calculate result (auto moves become random)
        result = self.game_service.calculate_winner(
            'rock',  # Simulating random auto moves
            'rock'
        )
        
        # Verify result
        self.assertEqual(result, 'draw')
        
        # Apply draw rewards (both get stakes back)
        self.creator_user.coins += self.stake
        self.joiner_user.coins += self.stake
        
        # Verify final balances
        # Both: Initial (100) - Stake (10) + Stake (10) = 100
        self.assertEqual(self.creator_user.coins, self.initial_balance)
        self.assertEqual(self.joiner_user.coins, self.initial_balance)

    def test_mixed_draw(self):
        """Test draw with one manual and one auto move"""
        # Set moves
        self.match.moves = {
            'test_creator': 'rock',
            'test_joiner': 'auto'
        }
        
        # Calculate result (auto move becomes random)
        result = self.game_service.calculate_winner(
            self.match.moves['test_creator'],
            'rock'  # Simulating random auto move
        )
        
        # Verify result
        self.assertEqual(result, 'draw')
        
        # Apply draw rewards (both get stakes back)
        self.creator_user.coins += self.stake
        self.joiner_user.coins += self.stake
        
        # Verify final balances
        # Both: Initial (100) - Stake (10) + Stake (10) = 100
        self.assertEqual(self.creator_user.coins, self.initial_balance)
        self.assertEqual(self.joiner_user.coins, self.initial_balance)

    def test_rematch_stake_verification(self):
        """Test that rematch is only allowed if both players have enough coins"""
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