from app.models.match import Match
from app.app import db

class MatchManager:
    @staticmethod
    def create_match(player1_id):
        match = Match(player1_id=player1_id)
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
            match.status = 'in_progress'
            db.session.commit()
            return True
        return False

    @staticmethod
    def get_match(match_id):
        return Match.query.get(match_id)