from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

class Player(db.Model):
    __tablename__ = "players"
    
    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.String(16), unique=True, nullable=False)
    coins = db.Column(db.Integer, default=100)
    current_match_id = db.Column(db.String(8), nullable=True)
    wins = db.Column(db.Integer, default=0)
    losses = db.Column(db.Integer, default=0)
    draws = db.Column(db.Integer, default=0)
    total_coins_won = db.Column(db.Integer, default=0)
    total_coins_lost = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_active = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "session_id": self.session_id,
            "coins": self.coins,
            "current_match_id": self.current_match_id,
            "wins": self.wins,
            "losses": self.losses,
            "draws": self.draws,
            "total_coins_won": self.total_coins_won,
            "total_coins_lost": self.total_coins_lost
        }

class Match(db.Model):
    __tablename__ = "matches"
    
    id = db.Column(db.String(8), primary_key=True)
    creator_id = db.Column(db.String(16), db.ForeignKey("players.session_id"), nullable=False)
    joiner_id = db.Column(db.String(16), db.ForeignKey("players.session_id"), nullable=True)
    stake = db.Column(db.Integer, nullable=False, default=1)
    status = db.Column(db.String(20), default="waiting")  # waiting, playing, finished
    creator_move = db.Column(db.String(10), nullable=True)
    joiner_move = db.Column(db.String(10), nullable=True)
    creator_ready = db.Column(db.Boolean, default=True)
    joiner_ready = db.Column(db.Boolean, default=False)
    winner = db.Column(db.String(16), nullable=True)
    result = db.Column(db.String(20), nullable=True)  # draw, player1, player2
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    started_at = db.Column(db.DateTime, nullable=True)
    finished_at = db.Column(db.DateTime, nullable=True)

    creator = db.relationship("Player", foreign_keys=[creator_id], backref="created_matches")
    joiner = db.relationship("Player", foreign_keys=[joiner_id], backref="joined_matches")

    def to_dict(self):
        return {
            "id": self.id,
            "creator_id": self.creator_id,
            "joiner_id": self.joiner_id,
            "stake": self.stake,
            "status": self.status,
            "creator_move": self.creator_move if self.status == "finished" else None,
            "joiner_move": self.joiner_move if self.status == "finished" else None,
            "creator_ready": self.creator_ready,
            "joiner_ready": self.joiner_ready,
            "winner": self.winner,
            "result": self.result,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "finished_at": self.finished_at.isoformat() if self.finished_at else None
        }
