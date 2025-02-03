import pytest
from ..models.database import db, User, GameHistory
from ..services.game_service import GameService
from ..services.match_service import MatchService
from ..models.match import Match
from datetime import datetime

class TestGameMechanics:
    @pytest.fixture(autouse=True)
    def setup(self, app):
        self.match_service = MatchService()
        self.player1_id = "test_player1"
        self.player2_id = "test_player2"
        self.stake = 10

    def test_bet_deduction(self, app):
        with app.app_context():
            # Create players
            player1 = self.match_service.get_player(self.player1_id)
            player2 = self.match_service.get_player(self.player2_id)
            initial_coins = player1.coins

            # Create match
            match = self.match_service.create_match(self.player1_id, self.stake)
            assert player1.coins == initial_coins  # No deduction yet

            # Join match
            match = self.match_service.join_match(match.id, self.player2_id)
            assert player1.coins == initial_coins - self.stake  # Deducted at join
            assert player2.coins == initial_coins - self.stake  # Deducted at join

    def test_auto_selection(self, app):
        with app.app_context():
            # Create players
            player1 = self.match_service.get_player(self.player1_id)
            player2 = self.match_service.get_player(self.player2_id)

            # Create match
            match = self.match_service.create_match(self.player1_id, self.stake)
            match = self.match_service.join_match(match.id, self.player2_id)
            match.start_time = datetime.utcnow().timestamp() - 11  # Past timeout

            # Auto-select moves
            match = self.match_service.handle_match_timeout(match.id)
            
            # Verify moves were auto-selected
            assert len(match.moves) == 2
            assert match.moves[self.player1_id] in ['rock', 'paper', 'scissors']
            assert match.moves[self.player2_id] in ['rock', 'paper', 'scissors']
            assert match.is_auto_selected()

    def test_draw_case(self, app):
        with app.app_context():
            # Create players
            player1 = self.match_service.get_player(self.player1_id)
            player2 = self.match_service.get_player(self.player2_id)
            initial_coins = player1.coins

            # Create match
            match = self.match_service.create_match(self.player1_id, self.stake)
            match = self.match_service.join_match(match.id, self.player2_id)
            initial_coins = player1.coins + self.stake  # Account for initial deduction
            match.make_move(self.player1_id, 'rock')
            match.make_move(self.player2_id, 'rock')

            # Calculate result
            result = GameService.calculate_match_result(match, {
                self.player1_id: player1,
                self.player2_id: player2
            })

            # Verify draw
            assert result['winner'] == 'draw'
            assert player1.coins == initial_coins  # Got stake back
            assert player2.coins == initial_coins  # Got stake back

    def test_win_lose_case(self, app):
        with app.app_context():
            # Create players
            player1 = self.match_service.get_player(self.player1_id)
            player2 = self.match_service.get_player(self.player2_id)
            initial_coins = player1.coins

            # Create match
            match = self.match_service.create_match(self.player1_id, self.stake)
            match = self.match_service.join_match(match.id, self.player2_id)
            initial_coins = player1.coins + self.stake  # Account for initial deduction
            match.make_move(self.player1_id, 'rock')     # Winner
            match.make_move(self.player2_id, 'scissors')  # Loser

            # Calculate result
            result = GameService.calculate_match_result(match, {
                self.player1_id: player1,
                self.player2_id: player2
            })

            # Verify win/lose
            assert result['winner'] == 'player1'
            assert player1.coins == initial_coins + self.stake  # Got double stake
            assert player2.coins == initial_coins - self.stake  # Lost stake