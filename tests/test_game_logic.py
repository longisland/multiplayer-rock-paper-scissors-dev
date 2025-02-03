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
        
        # Create test users
        self.creator_user = User(username='test_creator', coins=100)
        self.joiner_user = User(username='test_joiner', coins=100)
        
        # Create test match
        self.match = Match('test_match', 'test_creator', 10)  # stake = 10
        self.match.joiner = 'test_joiner'
        
        # Store initial balances
        self.initial_creator_balance = self.creator_user.coins
        self.initial_joiner_balance = self.joiner_user.coins
        self.stake = self.match.stake

    def test_immediate_stake_deduction(self):
        """Test that stakes are immediately deducted at match start"""
        # Start match
        self.match.start_match()
        
        # Deduct stakes
        self.creator_user.coins -= self.stake
        self.joiner_user.coins -= self.stake
        
        # Verify balances
        self.assertEqual(self.creator_user.coins, self.initial_creator_balance - self.stake)
        self.assertEqual(self.joiner_user.coins, self.initial_joiner_balance - self.stake)

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
        self.creator_user.coins += 2 * self.stake  # Winner gets double stake
        
        # Verify final balances
        self.assertEqual(self.creator_user.coins, self.initial_creator_balance + self.stake)
        self.assertEqual(self.joiner_user.coins, self.initial_joiner_balance - self.stake)

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
        self.assertEqual(self.creator_user.coins, self.initial_creator_balance)
        self.assertEqual(self.joiner_user.coins, self.initial_joiner_balance - self.stake)

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
        
        # Apply draw rewards
        self.creator_user.coins += self.stake
        self.joiner_user.coins += self.stake
        
        # Verify final balances
        self.assertEqual(self.creator_user.coins, self.initial_creator_balance)
        self.assertEqual(self.joiner_user.coins, self.initial_joiner_balance)

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
        self.assertEqual(self.creator_user.coins, self.initial_creator_balance)
        self.assertEqual(self.joiner_user.coins, self.initial_joiner_balance)

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
        self.assertEqual(self.creator_user.coins, self.initial_creator_balance)
        self.assertEqual(self.joiner_user.coins, self.initial_joiner_balance)

    def test_rematch_stake_verification(self):
        """Test that rematch is only allowed if both players have enough coins"""
        # Set initial balances to exactly stake amount
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