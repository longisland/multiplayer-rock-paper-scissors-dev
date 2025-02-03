import unittest
from src.services.game_service import GameService
from src.models.match import Match
from src.models.player import Player
from src.models.database import db, User, GameHistory

class TestGameLogic(unittest.TestCase):
    def setUp(self):
        # Create test match
        self.match = Match('test_match', 'creator', 10)
        self.match.joiner = 'joiner'
        self.match.start_match()

        # Create test players
        self.players = {
            'creator': Player('creator', 100),
            'joiner': Player('joiner', 100)
        }

    def test_calculate_winner(self):
        # Test all possible combinations
        test_cases = [
            ('rock', 'rock', 'draw'),
            ('rock', 'paper', 'player2'),
            ('rock', 'scissors', 'player1'),
            ('paper', 'rock', 'player1'),
            ('paper', 'paper', 'draw'),
            ('paper', 'scissors', 'player2'),
            ('scissors', 'rock', 'player2'),
            ('scissors', 'paper', 'player1'),
            ('scissors', 'scissors', 'draw')
        ]

        for move1, move2, expected in test_cases:
            result = GameService.calculate_winner(move1, move2)
            self.assertEqual(result, expected, f"Failed for {move1} vs {move2}")

    def test_auto_move_draw(self):
        # Test draw with auto-selected moves
        self.match.moves['creator'] = 'rock'
        self.match.moves['joiner'] = 'rock'
        self.match.auto_moves.add('creator')  # Creator's move was auto-selected
        self.match.auto_moves.add('joiner')   # Joiner's move was auto-selected

        # Initial coins
        creator_coins = self.players['creator'].coins
        joiner_coins = self.players['joiner'].coins
        stake = self.match.stake

        # Calculate result
        result = GameService.calculate_match_result(self.match, self.players)

        # Verify draw result
        self.assertEqual(result['winner'], 'draw')
        
        # Verify coins are returned correctly (no double return)
        self.assertEqual(self.players['creator'].coins, creator_coins)
        self.assertEqual(self.players['joiner'].coins, joiner_coins)

    def test_auto_move_win(self):
        # Test win with auto-selected move
        self.match.moves['creator'] = 'rock'
        self.match.moves['joiner'] = 'scissors'
        self.match.auto_moves.add('creator')  # Creator's move was auto-selected

        # Initial coins
        creator_coins = self.players['creator'].coins
        joiner_coins = self.players['joiner'].coins
        stake = self.match.stake

        # Calculate result
        result = GameService.calculate_match_result(self.match, self.players)

        # Verify creator wins
        self.assertEqual(result['winner'], 'player1')
        
        # Verify coins are awarded correctly (no multiplier)
        self.assertEqual(self.players['creator'].coins, creator_coins + stake)
        self.assertEqual(self.players['joiner'].coins, joiner_coins - stake)

    def test_normal_move_win(self):
        # Test win with normal moves
        self.match.moves['creator'] = 'rock'
        self.match.moves['joiner'] = 'scissors'

        # Initial coins
        creator_coins = self.players['creator'].coins
        joiner_coins = self.players['joiner'].coins
        stake = self.match.stake

        # Calculate result
        result = GameService.calculate_match_result(self.match, self.players)

        # Verify creator wins
        self.assertEqual(result['winner'], 'player1')
        
        # Verify coins are awarded correctly
        self.assertEqual(self.players['creator'].coins, creator_coins + stake)
        self.assertEqual(self.players['joiner'].coins, joiner_coins - stake)

if __name__ == '__main__':
    unittest.main()