from app.models.match import Match
from app.app import db
from .game_logic import start_match_timer, calculate_and_emit_result

class MatchManager:
    @staticmethod
    def create_match(player1_id):
        match = Match(player1_id=player1_id, status='waiting')
        db.session.add(match)
        db.session.commit()
        return match

    @staticmethod
    def get_open_matches():
        return Match.query.filter_by(status='waiting').all()

    @staticmethod
    def join_match(match_id, player2_id):
        match = Match.query.get(match_id)
        if match and match.status == 'waiting' and not match.player2_id:
            match.player2_id = player2_id
            match.status = 'playing'  # Set status to playing immediately
            db.session.commit()
            # Start the match timer when second player joins
            start_match_timer(match_id)
            return True
        return False

    @staticmethod
    def get_match(match_id):
        return Match.query.get(match_id)

    @staticmethod
    def make_move(match_id, player_id, move):
        match = Match.query.get(match_id)
        if not match or match.status != 'playing':
            return False

        # Record the move for the appropriate player
        if player_id == match.player1_id:
            match.creator_move = move
        elif player_id == match.player2_id:
            match.joiner_move = move
        else:
            return False

        db.session.commit()

        # If both players have made their moves, calculate and emit the result
        if match.creator_move and match.joiner_move:
            calculate_and_emit_result(match_id)

        return True
