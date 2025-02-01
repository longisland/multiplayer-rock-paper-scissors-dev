from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

class Player(db.Model):
    __tablename__ = 'players'
    
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

class Match(db.Model):
    __tablename__ = 'matches'
    
    id = db.Column(db.String(8), primary_key=True)
    creator_id = db.Column(db.String(16), db.ForeignKey('players.session_id'), nullable=False)
    joiner_id = db.Column(db.String(16), db.ForeignKey('players.session_id'), nullable=True)
    stake = db.Column(db.Integer, nullable=False)
    status = db.Column(db.String(20), default='waiting')  # waiting, playing, finished
    creator_move = db.Column(db.String(10), nullable=True)
    joiner_move = db.Column(db.String(10), nullable=True)
    creator_ready = db.Column(db.Boolean, default=True)
    joiner_ready = db.Column(db.Boolean, default=False)
    winner = db.Column(db.String(16), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    started_at = db.Column(db.DateTime, nullable=True)
    finished_at = db.Column(db.DateTime, nullable=True)

    creator = db.relationship('Player', foreign_keys=[creator_id], backref='created_matches')
    joiner = db.relationship('Player', foreign_keys=[joiner_id], backref='joined_matches')