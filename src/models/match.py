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
        self.creator_rematch = False
        self.joiner_rematch = False

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
        self.timer.daemon = True  # Make timer daemon to prevent blocking on program exit
        self.timer.start()
        return self.timer

    def cancel_timer(self):
        if self.timer:
            self.timer.cancel()
            self.timer = None

    def start_match(self):
        if self.status != 'waiting':
            raise ValueError("Match must be in waiting state to start")
        if not self.creator or not self.joiner:
            raise ValueError("Both players must be present to start match")
        if not self.creator_ready or not self.joiner_ready:
            raise ValueError("Both players must be ready to start match")

        self.status = 'playing'
        self.start_time = time.time()
        self.moves = {}
        return self.start_time

    def make_move(self, player_id, move):
        if self.status != 'playing':
            raise ValueError("Match is not in playing state")
        if player_id not in [self.creator, self.joiner]:
            raise ValueError("Player is not in this match")
        if player_id in self.moves:
            raise ValueError("Player has already made a move")
        if move not in ['rock', 'paper', 'scissors']:
            raise ValueError("Invalid move. Must be 'rock', 'paper', or 'scissors'")
        self.moves[player_id] = move
        return True

    def are_both_moves_made(self):
        return len(self.moves) == 2

    def set_result(self, result_data):
        if self.status == 'finished':
            return False  # Already processed
        self.result = result_data
        self.status = 'finished'
        self.creator_rematch = False  # Reset rematch flags when match finishes
        self.joiner_rematch = False
        return True

    def is_rematch_ready(self):
        """Check if both players are ready for rematch."""
        from ..utils.logger import setup_logger
        logger = setup_logger()
        
        logger.info(f"Checking rematch readiness: creator={self.creator_rematch}, joiner={self.joiner_rematch}")
        return self.creator_rematch and self.joiner_rematch

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