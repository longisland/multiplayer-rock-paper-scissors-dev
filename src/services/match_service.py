import random
import secrets
from ..models.match import Match
from ..models.player import Player
from ..models.database import db, User, GameHistory
from ..config import Config
from datetime import datetime

class MatchService:
    def __init__(self):
        self.matches = {}
        self.players = {}

    def get_player(self, session_id):
        if session_id not in self.players:
            # Check if user exists in database
            user = User.query.filter_by(username=session_id).first()
            if not user:
                user = User(username=session_id, coins=Config.INITIAL_COINS)
                db.session.add(user)
                db.session.commit()
            
            # Create in-memory player
            self.players[session_id] = Player(session_id, user.coins)
            self.players[session_id].stats.wins = user.wins
            self.players[session_id].stats.losses = user.losses
            self.players[session_id].stats.draws = user.draws
            self.players[session_id].stats.total_games = user.total_games
        return self.players[session_id]

    def create_match(self, creator_id, stake):
        # Check if player has enough coins
        creator = self.players[creator_id]
        if not creator.has_enough_coins(stake):
            return None

        # Start database transaction
        db.session.begin_nested()
        try:
            # Get user from database with row locking
            creator_user = User.query.filter_by(username=creator_id).with_for_update().first()
            if not creator_user:
                db.session.rollback()
                return None

            # Deduct stake from creator
            creator_user.coins -= stake
            creator.add_coins(-stake)

            # Create match
            match_id = secrets.token_hex(4)
            match = Match(match_id, creator_id, stake)
            match.bets_placed.add(creator_id)  # Mark creator's bet as placed
            self.matches[match_id] = match
            self.players[creator_id].current_match = match_id

            # Commit transaction
            db.session.commit()
            return match

        except Exception as e:
            db.session.rollback()
            raise e

    def join_match(self, match_id, joiner_id):
        if match_id not in self.matches:
            return None

        match = self.matches[match_id]
        if match.status != 'waiting' or match.joiner is not None:
            return None

        # Check if joiner has enough coins
        joiner = self.players[joiner_id]
        if not joiner.has_enough_coins(match.stake):
            return None

        # Start database transaction
        db.session.begin_nested()
        try:
            # Get user from database with row locking
            joiner_user = User.query.filter_by(username=joiner_id).with_for_update().first()
            if not joiner_user:
                db.session.rollback()
                return None

            # Deduct stake from joiner
            joiner_user.coins -= match.stake
            joiner.add_coins(-match.stake)

            # Update match
            match.joiner = joiner_id
            match.bets_placed.add(joiner_id)  # Mark joiner's bet as placed
            self.players[joiner_id].current_match = match_id

            # Commit transaction
            db.session.commit()
            return match

        except Exception as e:
            db.session.rollback()
            raise e

    def get_match(self, match_id):
        return self.matches.get(match_id)

    def get_open_matches(self, player_id):
        open_matches = []
        for mid, match in self.matches.items():
            if (match.status == 'waiting' and 
                match.creator != player_id and 
                self.players[match.creator].has_enough_coins(match.stake) and
                self.players[player_id].has_enough_coins(match.stake)):
                open_matches.append({
                    'id': mid,
                    'stake': match.stake
                })
        return open_matches

    def handle_match_timeout(self, match_id):
        match = self.matches.get(match_id)
        if not match or match.status != 'playing':
            return

        # Assign random moves to players who haven't made a move
        if match.creator not in match.moves:
            match.moves[match.creator] = random.choice(['rock', 'paper', 'scissors'])

        if match.joiner not in match.moves:
            match.moves[match.joiner] = random.choice(['rock', 'paper', 'scissors'])

        # Calculate and set match result since both moves are now made
        from .game_service import GameService
        result_data = GameService.calculate_match_result(match, self.players)
        
        # Cancel the timer since we've handled the timeout
        match.cancel_timer()
        
        return match

    def create_rematch(self, old_match_id):
        old_match = self.matches.get(old_match_id)
        if not old_match:
            return None

        # Check if both players have enough coins
        if not old_match.can_rematch(self.players):
            return None

        # Check if both players have accepted rematch
        if not old_match.is_rematch_ready():
            return None

        # Randomly choose new creator and joiner
        new_creator = random.choice([old_match.creator, old_match.joiner])
        new_joiner = old_match.joiner if new_creator == old_match.creator else old_match.creator

        # Create new match
        match_id = secrets.token_hex(4)
        new_match = Match(match_id, new_creator, old_match.stake)
        new_match.joiner = new_joiner
        new_match.status = 'waiting'  # Start in waiting state
        new_match.creator_ready = True  # Both players need to ready up again
        new_match.joiner_ready = True

        # Update match and player states
        self.matches[match_id] = new_match
        self.players[new_creator].current_match = match_id
        self.players[new_joiner].current_match = match_id

        # Start the match
        new_match.start_match()
        new_match.start_timer(Config.MATCH_TIMEOUT, self.handle_match_timeout)

        return new_match

    def cleanup_match(self, match_id):
        if match_id in self.matches:
            match = self.matches[match_id]
            match.cancel_timer()

            # If match was not finished, return bets to players
            if match.status != 'finished':
                db.session.begin_nested()
                try:
                    # Return creator's bet if placed
                    if match.creator in match.bets_placed:
                        creator_user = User.query.filter_by(username=match.creator).with_for_update().first()
                        if creator_user and match.creator in self.players:
                            creator_user.coins += match.stake
                            self.players[match.creator].add_coins(match.stake)

                    # Return joiner's bet if placed
                    if match.joiner in match.bets_placed:
                        joiner_user = User.query.filter_by(username=match.joiner).with_for_update().first()
                        if joiner_user and match.joiner in self.players:
                            joiner_user.coins += match.stake
                            self.players[match.joiner].add_coins(match.stake)

                    db.session.commit()
                except Exception as e:
                    db.session.rollback()
                    raise e

            # Clear current match reference from players
            if match.creator in self.players:
                self.players[match.creator].current_match = None
            if match.joiner in self.players:
                self.players[match.joiner].current_match = None

            del self.matches[match_id]