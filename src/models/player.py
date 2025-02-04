from .database import db, User

class Player:
    def __init__(self, session_id, initial_coins=100):
        self.session_id = session_id
        self.current_match = None
        self._user = None
        self._ensure_user_exists(initial_coins)

    def _ensure_user_exists(self, initial_coins):
        """Ensure user exists in database and create if not"""
        if not self._user:
            self._user = User.query.filter_by(username=self.session_id).first()
            if not self._user:
                self._user = User(username=self.session_id, coins=initial_coins)
                db.session.add(self._user)
                db.session.commit()

    def _refresh_user(self):
        """Refresh user data from database"""
        if self._user:
            db.session.expire_all()
            self._user = User.query.filter_by(username=self.session_id).first()

    @property
    def coins(self):
        self._refresh_user()
        return self._user.coins

    @coins.setter
    def coins(self, value):
        self._refresh_user()
        self._user.coins = value
        db.session.commit()

    @property
    def stats(self):
        """Return a PlayerStats-like object for compatibility"""
        return self.to_stats_dict()

    def to_dict(self):
        self._refresh_user()
        return {
            'coins': self._user.coins,
            'current_match': self.current_match,
            'stats': self.stats.to_dict()
        }

    def has_enough_coins(self, amount):
        self._refresh_user()
        return self._user.coins >= amount

    def record_win(self):
        self._refresh_user()
        self._user.wins += 1
        self._user.total_games += 1
        db.session.commit()

    def record_loss(self):
        self._refresh_user()
        self._user.losses += 1
        self._user.total_games += 1
        db.session.commit()

    def record_draw(self):
        self._refresh_user()
        self._user.draws += 1
        self._user.total_games += 1
        db.session.commit()

    def to_stats_dict(self):
        """Return a dictionary with stats that matches the old PlayerStats interface"""
        self._refresh_user()
        return type('PlayerStats', (), {
            'wins': self._user.wins,
            'losses': self._user.losses,
            'draws': self._user.draws,
            'total_games': self._user.total_games,
            'total_coins_won': self._user.total_coins_won or 0,
            'total_coins_lost': self._user.total_coins_lost or 0,
            'to_dict': lambda: {
                'wins': self._user.wins,
                'losses': self._user.losses,
                'draws': self._user.draws,
                'total_games': self._user.total_games,
                'total_coins_won': self._user.total_coins_won or 0,
                'total_coins_lost': self._user.total_coins_lost or 0
            }
        })