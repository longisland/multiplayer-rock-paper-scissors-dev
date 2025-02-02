class PlayerStats:
    def __init__(self):
        self.wins = 0
        self.losses = 0
        self.draws = 0
        self.total_coins_won = 0
        self.total_coins_lost = 0

    def to_dict(self):
        return {
            'wins': self.wins,
            'losses': self.losses,
            'draws': self.draws,
            'total_coins_won': self.total_coins_won,
            'total_coins_lost': self.total_coins_lost
        }

class Player:
    def __init__(self, session_id, initial_coins=100):
        self.session_id = session_id
        self.coins = initial_coins
        self.current_match = None
        self.stats = PlayerStats()

    def to_dict(self):
        return {
            'coins': self.coins,
            'current_match': self.current_match,
            'stats': self.stats.to_dict()
        }

    def has_enough_coins(self, amount):
        return self.coins >= amount

    def add_coins(self, amount):
        """Deprecated: Use direct coin assignment and stats update instead"""
        pass

    def record_win(self):
        self.stats.wins += 1

    def record_loss(self):
        self.stats.losses += 1

    def record_draw(self):
        self.stats.draws += 1