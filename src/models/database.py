from datetime import datetime
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

class User(db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, db.Sequence('user_id_seq'), primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    coins = db.Column(db.Integer, default=100)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_seen = db.Column(db.DateTime, default=datetime.utcnow)
    total_games = db.Column(db.Integer, default=0)
    wins = db.Column(db.Integer, default=0)
    losses = db.Column(db.Integer, default=0)
    draws = db.Column(db.Integer, default=0)
    total_coins_won = db.Column(db.Integer, default=0)
    total_coins_lost = db.Column(db.Integer, default=0)

    def to_dict(self):
        return {
            'id': self.id,
            'username': self.username,
            'coins': self.coins,
            'total_games': self.total_games,
            'wins': self.wins,
            'losses': self.losses,
            'draws': self.draws,
            'total_coins_won': self.total_coins_won,
            'total_coins_lost': self.total_coins_lost
        }

class GameHistory(db.Model):
    __tablename__ = 'game_history'

    id = db.Column(db.Integer, db.Sequence('game_history_id_seq'), primary_key=True)
    player1_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    player2_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    player1_choice = db.Column(db.String(10), nullable=False)
    player2_choice = db.Column(db.String(10), nullable=False)
    winner_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    played_at = db.Column(db.DateTime, default=datetime.utcnow)
    bet_amount = db.Column(db.Integer, default=0)

    player1 = db.relationship('User', foreign_keys=[player1_id])
    player2 = db.relationship('User', foreign_keys=[player2_id])
    winner = db.relationship('User', foreign_keys=[winner_id])