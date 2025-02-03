import unittest
from src.services.game_service import GameService
from src.services.match_service import MatchService
from src.models.match import Match
from src.models.player import Player
from src.models.database import db, User, GameHistory
from src.app import app
from src.config import TestConfig

class TestGameLogic(unittest.TestCase):
    def setUp(self):
        app.config.from_object(TestConfig)
        self.app = app.test_client()
        self.app_context = app.app_context()
        self.app_context.push()
        db.create_all()
        self.match_service = MatchService()
        self.game_service = GameService()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def test_win_calculation(self):
        # Test all winning combinations
        self.assertEqual(self.game_service.calculate_winner('rock', 'scissors'), 'player1')
        self.assertEqual(self.game_service.calculate_winner('paper', 'rock'), 'player1')
        self.assertEqual(self.game_service.calculate_winner('scissors', 'paper'), 'player1')
        self.assertEqual(self.game_service.calculate_winner('scissors', 'rock'), 'player2')
        self.assertEqual(self.game_service.calculate_winner('rock', 'paper'), 'player2')
        self.assertEqual(self.game_service.calculate_winner('paper', 'scissors'), 'player2')

    def test_draw_calculation(self):
        # Test all draw combinations
        self.assertEqual(self.game_service.calculate_winner('rock', 'rock'), 'draw')
        self.assertEqual(self.game_service.calculate_winner('paper', 'paper'), 'draw')
        self.assertEqual(self.game_service.calculate_winner('scissors', 'scissors'), 'draw')

    def test_balance_deduction(self):
        # Create test users
        creator = User(username='creator', coins=100)
        joiner = User(username='joiner', coins=100)
        db.session.add(creator)
        db.session.add(joiner)
        db.session.commit()

        # Initialize players in match service
        self.match_service.get_player('creator')
        self.match_service.get_player('joiner')

        # Create match
        match = self.match_service.create_match('creator', 10)
        
        # Join match should deduct balance immediately
        self.match_service.join_match(match.id, 'joiner')

        # Verify balances were deducted
        creator = User.query.filter_by(username='creator').first()
        joiner = User.query.filter_by(username='joiner').first()
        self.assertEqual(creator.coins, 90)
        self.assertEqual(joiner.coins, 90)

    def test_auto_selection_calculation(self):
        # Create test users
        creator = User(username='creator', coins=100)
        joiner = User(username='joiner', coins=100)
        db.session.add(creator)
        db.session.add(joiner)
        db.session.commit()

        # Initialize players in match service
        self.match_service.get_player('creator')
        self.match_service.get_player('joiner')

        # Create and start match
        match = self.match_service.create_match('creator', 10)
        self.match_service.join_match(match.id, 'joiner')
        match.start_match()

        # Handle timeout (auto-selection)
        self.match_service.handle_match_timeout(match.id)

        # Verify moves were made
        self.assertIn(match.creator, match.moves)
        self.assertIn(match.joiner, match.moves)
        self.assertIn(match.moves[match.creator], ['rock', 'paper', 'scissors'])
        self.assertIn(match.moves[match.joiner], ['rock', 'paper', 'scissors'])

        # Verify result was calculated
        self.assertIsNotNone(match.result)

    def test_rematch_functionality(self):
        # Create test users
        creator = User(username='creator', coins=100)
        joiner = User(username='joiner', coins=100)
        db.session.add(creator)
        db.session.add(joiner)
        db.session.commit()

        # Initialize players in match service
        self.match_service.get_player('creator')
        self.match_service.get_player('joiner')

        # Create and play first match
        match = self.match_service.create_match('creator', 10)
        self.match_service.join_match(match.id, 'joiner')
        match.start_match()
        match.make_move('creator', 'rock')
        match.make_move('joiner', 'scissors')
        self.game_service.calculate_match_result(match, self.match_service.players)

        # Both players accept rematch
        match.rematch_ready.add('creator')
        match.rematch_ready.add('joiner')

        # Create rematch
        new_match = self.match_service.create_rematch(match.id)
        self.assertIsNotNone(new_match)
        self.assertEqual(new_match.stake, 10)
        self.assertEqual(new_match.creator, 'creator')
        self.assertEqual(new_match.joiner, 'joiner')

if __name__ == '__main__':
    unittest.main()