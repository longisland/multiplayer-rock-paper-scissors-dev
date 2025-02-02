import time
from threading import Timer

class MatchStats:
    def __init__(self):
        self.rounds = 0
        self.creator_wins = 0
        self.joiner_wins = 0
        self.draws = 0

    def to_dict(self):
        return {
            'rounds': self.rounds,
            'creator_wins': self.creator_wins,
            'joiner_wins': self.joiner_wins,
            'draws': self.draws
        }

class Match:
    def __init__(self, match_id, creator_id, stake):
        self.id = match_id
        self.creator = creator_id
        self.joiner = None
        self.stake = stake
        self.moves = {}
        self.status = 'waiting'  # waiting, playing, finished
        self.timer = None
        self.start_time = None
        self.creator_ready = True  # Creator is automatically ready
        self.joiner_ready = False
        self.stats = MatchStats()
        self.result = None
        self.rematch_ready = set()

    def to_dict(self):
        return {
            'id': self.id,
            'creator': self.creator,
            'joiner': self.joiner,
            'stake': self.stake,
            'status': self.status,
            'stats': self.stats.to_dict(),
            'result': self.result
        }

    def is_player_in_match(self, player_id):
        return player_id in [self.creator, self.joiner]

    def get_player_role(self, player_id):
        if player_id == self.creator:
            return 'creator'
        elif player_id == self.joiner:
            return 'joiner'
        return None

    def start_timer(self, timeout, callback):
        if self.timer:
            self.timer.cancel()
        self.timer = Timer(timeout, callback, args=[self.id])
        self.timer.start()

    def cancel_timer(self):
        if self.timer:
            self.timer.cancel()
            self.timer = None

    def start_match(self):
        self.status = 'playing'
        self.start_time = time.time()
        self.moves = {}

    def make_move(self, player_id, move):
        if player_id not in [self.creator, self.joiner]:
            return False
        if player_id in self.moves:
            return False
        self.moves[player_id] = move
        return True

    def are_both_moves_made(self):
        return len(self.moves) == 2

    def set_result(self, result_data):
        if self.status == 'finished':
            return False  # Already processed
        self.result = result_data
        self.status = 'finished'
        self.rematch_ready = set()  # Reset rematch_ready when match finishes
        return True

    def add_rematch_ready(self, player_id):
        """Add a player to the rematch_ready set and return their role."""
        if player_id not in [self.creator, self.joiner]:
            return None
        self.rematch_ready.add(player_id)
        return 'creator' if player_id == self.creator else 'joiner'

    def is_rematch_ready(self):
        """Check if both players are ready for rematch."""
        return len(self.rematch_ready) == 2

    def get_other_player(self, player_id):
        """Get the other player's ID."""
        if player_id == self.creator:
            return self.joiner
        elif player_id == self.joiner:
            return self.creator
        return None

    def can_rematch(self, players):
        """Check if both players have enough coins for a rematch."""
        if not self.creator or not self.joiner:
            return False
        if self.creator not in players or self.joiner not in players:
            return False
        return (players[self.creator].has_enough_coins(self.stake) and 
                players[self.joiner].has_enough_coins(self.stake))