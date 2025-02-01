from app.models.models import db, Player, Match
from .game_logic import start_match_timer, calculate_and_emit_result

class MatchManager:
    @staticmethod
    def create_match(player1_id, stake):
        # Get player object
        player1 = Player.query.filter_by(session_id=player1_id).first()
        if not player1:
            return None

        # Check if player has enough coins
        if player1.coins < stake:
            return None

        # Deduct stake from player\"s balance
        player1.coins -= stake
        match = Match(creator_id=player1_id, status=\"waiting\", stake=stake)
        db.session.add(match)
        db.session.commit()
        return match

    @staticmethod
    def get_open_matches():
        return Match.query.filter_by(status=\"waiting\").all()

    @staticmethod
    def join_match(match_id, player2_id):
        match = Match.query.get(match_id)
        if not match or match.status != \"waiting\" or match.joiner_id:
            return False

        # Get player objects
        player2 = Player.query.filter_by(session_id=player2_id).first()
        if not player2:
            return False

        # Check if player has enough coins
        if player2.coins < match.stake:
            return False

        # Deduct stake from player\"s balance
        player2.coins -= match.stake
        match.joiner_id = player2_id
        match.status = \"playing\"  # Set status to playing immediately
        db.session.commit()

        # Start the match timer when second player joins
        start_match_timer(match_id)
        return True

    @staticmethod
    def get_match(match_id):
        return Match.query.get(match_id)

    @staticmethod
    def make_move(match_id, player_id, move):
        match = Match.query.get(match_id)
        if not match or match.status != \"playing\":
            return False

        # Record the move for the appropriate player
        if player_id == match.creator_id:
            match.creator_move = move
        elif player_id == match.joiner_id:
            match.joiner_move = move
        else:
            return False

        db.session.commit()

        # If both players have made their moves, calculate and emit the result
        if match.creator_move and match.joiner_move:
            calculate_and_emit_result(match_id)

        return True
