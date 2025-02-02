from ..models.database import db, User

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

    @property
    def coins(self):
        self._ensure_user_exists(100)
        return self._user.coins

    @coins.setter
    def coins(self, value):
        self._ensure_user_exists(100)
        self._user.coins = value
        db.session.commit()

    def to_dict(self):
        self._ensure_user_exists(100)
        return {
            'coins': self._user.coins,
            'current_match': self.current_match,
            'stats': {
                'wins': self._user.wins,
                'losses': self._user.losses,
                'draws': self._user.draws,
                'total_games': self._user.total_games,
                'total_coins_won': self._user.total_coins_won or 0,
                'total_coins_lost': self._user.total_coins_lost or 0
            }
        }

    def has_enough_coins(self, amount):
        self._ensure_user_exists(100)
        return self._user.coins >= amount

    def record_win(self):
        self._ensure_user_exists(100)
        self._user.wins += 1
        self._user.total_games += 1
        db.session.commit()

    def record_loss(self):
        self._ensure_user_exists(100)
        self._user.losses += 1
        self._user.total_games += 1
        db.session.commit()

    def record_draw(self):
        self._ensure_user_exists(100)
        self._user.draws += 1
        self._user.total_games += 1
        db.session.commit()