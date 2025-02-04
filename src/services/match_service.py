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
        try:
            # Start transaction
            db.session.begin_nested()

            # Get creator from database with row locking
            creator_user = User.query.filter_by(username=creator_id).with_for_update().first()
            if not creator_user or creator_user.coins < stake:
                db.session.rollback()
                return None

            # Deduct stake from creator
            creator_user.coins -= stake

            # Create match
            match_id = secrets.token_hex(4)
            match = Match(match_id, creator_id, stake)
            self.matches[match_id] = match
            self.players[creator_id].current_match = match_id
            
            # Update in-memory state
            self.players[creator_id].coins = creator_user.coins

            # Commit transaction
            db.session.commit()
            return match

        except Exception as e:
            db.session.rollback()
            return None

    def join_match(self, match_id, joiner_id):
        if match_id not in self.matches:
            return None

        match = self.matches[match_id]
        if match.status != 'waiting' or match.joiner is not None:
            return None

        try:
            # Start transaction
            db.session.begin_nested()

            # Get joiner from database with row locking
            joiner_user = User.query.filter_by(username=joiner_id).with_for_update().first()
            if not joiner_user or joiner_user.coins < match.stake:
                db.session.rollback()
                return None

            # Deduct stake from joiner
            joiner_user.coins -= match.stake

            # Update match state
            match.joiner = joiner_id
            self.players[joiner_id].current_match = match_id
            
            # Update in-memory state
            self.players[joiner_id].coins = joiner_user.coins

            # Commit transaction
            db.session.commit()
            return match

        except Exception as e:
            db.session.rollback()
            return None

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

        try:
            # Start transaction
            db.session.begin_nested()

            # Get both players from database with row locking
            creator_user = User.query.filter_by(username=match.creator).with_for_update().first()
            joiner_user = User.query.filter_by(username=match.joiner).with_for_update().first()

            if not creator_user or not joiner_user:
                db.session.rollback()
                return None

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

            # Commit transaction
            db.session.commit()
            
            return match

        except Exception as e:
            db.session.rollback()
            return None

    def create_rematch(self, old_match_id):
        old_match = self.matches.get(old_match_id)
        if not old_match:
            return None

        # Check if both players have accepted rematch
        if not old_match.is_rematch_ready():
            return None

        try:
            # Start transaction
            db.session.begin_nested()

            # Get users from database with row locking
            creator_user = User.query.filter_by(username=old_match.creator).with_for_update().first()
            joiner_user = User.query.filter_by(username=old_match.joiner).with_for_update().first()

            if not creator_user or not joiner_user:
                db.session.rollback()
                return None

            # Verify coins again within transaction
            if creator_user.coins < old_match.stake or joiner_user.coins < old_match.stake:
                db.session.rollback()
                return None

            # Deduct stakes from both players
            creator_user.coins -= old_match.stake
            joiner_user.coins -= old_match.stake

            # Create new match
            match_id = secrets.token_hex(4)
            new_match = Match(match_id, old_match.creator, old_match.stake)
            new_match.joiner = old_match.joiner
            new_match.status = 'playing'  # Start in playing state
            new_match.creator_ready = True
            new_match.joiner_ready = True

            # Update match and player states
            self.matches[match_id] = new_match
            self.players[old_match.creator].current_match = match_id
            self.players[old_match.joiner].current_match = match_id

            # Update in-memory state and commit transaction
            db.session.commit()

            # Refresh player states
            self.players[old_match.creator]._refresh_user()
            self.players[old_match.joiner]._refresh_user()

            # Clean up old match
            self.cleanup_match(old_match_id)

            # Start the match timer
            new_match.start_match()
            new_match.start_timer(Config.MATCH_TIMEOUT, self.handle_match_timeout)

            return new_match

        except Exception as e:
            db.session.rollback()
            return None

    def cancel_match(self, match_id):
        """Cancel a match and refund the stake to the creator."""
        try:
            match = self.matches.get(match_id)
            if not match or match.status != 'waiting':
                return None

            # Start transaction
            db.session.begin_nested()

            # Get creator from database with row locking
            creator_user = User.query.filter_by(username=match.creator).with_for_update().first()
            if not creator_user:
                db.session.rollback()
                return None

            # Refund stake to creator
            creator_user.coins += match.stake
            
            # Update in-memory state
            self.players[match.creator].coins = creator_user.coins

            # Commit transaction
            db.session.commit()

            # Clean up the match
            self.cleanup_match(match_id)
            return True

        except Exception as e:
            db.session.rollback()
            return None

    def cleanup_match(self, match_id):
        """Clean up match resources without handling refunds."""
        if match_id in self.matches:
            match = self.matches[match_id]
            match.cancel_timer()
            
            # Clear current match reference from players
            if match.creator in self.players:
                self.players[match.creator].current_match = None
            if match.joiner in self.players:
                self.players[match.joiner].current_match = None
            
            del self.matches[match_id]