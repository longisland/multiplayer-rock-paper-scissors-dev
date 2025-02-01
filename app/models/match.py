from datetime import datetime
from app.app import db

class Match(db.Model):
    __tablename__ = 'matches'

    id = db.Column(db.Integer, primary_key=True)
    player1_id = db.Column(db.String(50), nullable=False)
    player2_id = db.Column(db.String(50), nullable=True)
    status = db.Column(db.String(20), default='waiting')  # waiting, playing, finished
    creator_move = db.Column(db.String(10), nullable=True)  # rock, paper, scissors
    joiner_move = db.Column(db.String(10), nullable=True)  # rock, paper, scissors
    result = db.Column(db.String(10), nullable=True)  # player1, player2, draw
    stake = db.Column(db.Integer, nullable=False, default=10)  # Default stake is 10 coins
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    started_at = db.Column(db.DateTime, nullable=True)
    finished_at = db.Column(db.DateTime, nullable=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'player1_id': self.player1_id,
            'player2_id': self.player2_id,
            'status': self.status,
            'creator_move': self.creator_move,
            'joiner_move': self.joiner_move,
            'result': self.result,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'finished_at': self.finished_at.isoformat() if self.finished_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'stake': self.stake
        }