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
        # Validate stake
        if stake <= 0:
            raise ValueError("Stake must be positive")
        if stake > self.players[creator_id].coins:
            raise ValueError("Insufficient coins for stake")

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
            raise ValueError("Match does not exist")

        match = self.matches[match_id]
        if match.status != 'waiting':
            raise ValueError("Match is not in waiting state")
        if match.joiner is not None:
            raise ValueError("Match is already full")
        if match.creator == joiner_id:
            raise ValueError("Cannot join your own match")
        if not self.players[joiner_id].has_enough_coins(match.stake):
            raise ValueError("Insufficient coins for stake")

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
            match.joiner_ready = True  # Set joiner as ready
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

    def request_rematch(self, match_id, player_id):
        match = self.matches.get(match_id)
        if not match:
            raise ValueError("Match does not exist")

        if match.status != 'finished':
            raise ValueError("Match is not finished")

        if player_id not in [match.creator, match.joiner]:
            raise ValueError("Player is not part of this match")

        if not self.players[player_id].has_enough_coins(match.stake):
            raise ValueError("Insufficient coins for rematch")

        # Set rematch flag for the requesting player
        if player_id == match.creator:
            match.creator_rematch = True
        else:
            match.joiner_rematch = True

        # If both players have accepted, create the rematch
        if match.creator_rematch and match.joiner_rematch:
            return self.create_rematch(match_id)

        return match

    def accept_rematch(self, match_id, player_id):
        from ..utils.logger import setup_logger
        logger = setup_logger()

        match = self.matches.get(match_id)
        if not match:
            logger.error(f"Match {match_id} does not exist")
            raise ValueError("Match does not exist")

        if match.status != 'finished':
            logger.error(f"Match {match_id} is not finished (status: {match.status})")
            raise ValueError("Match is not finished")

        if player_id not in [match.creator, match.joiner]:
            logger.error(f"Player {player_id} is not part of match {match_id}")
            raise ValueError("Player is not part of this match")

        if not self.players[player_id].has_enough_coins(match.stake):
            logger.error(f"Player {player_id} has insufficient coins for rematch")
            raise ValueError("Insufficient coins for rematch")

        # Set rematch flag for the accepting player
        if player_id == match.creator:
            match.creator_rematch = True
            logger.info(f"Creator {player_id} accepted rematch")
        else:
            match.joiner_rematch = True
            logger.info(f"Joiner {player_id} accepted rematch")

        # If both players have accepted, create the rematch
        if match.is_rematch_ready():
            logger.info(f"Both players accepted rematch, creating new match")
            return self.create_rematch(match_id)

        logger.info(f"Waiting for other player to accept rematch")
        return match

    def create_rematch(self, old_match_id):
        from ..utils.logger import setup_logger
        logger = setup_logger()

        old_match = self.matches.get(old_match_id)
        if not old_match:
            logger.error(f"Match {old_match_id} does not exist")
            return None

        # Check if both players have enough coins
        if not old_match.can_rematch(self.players):
            logger.error(f"Players do not have enough coins for rematch")
            return None

        # Check if both players have accepted rematch
        if not old_match.is_rematch_ready():
            logger.error(f"Not all players have accepted rematch")
            return None

        try:
            # Start transaction
            db.session.begin_nested()

            # Get users from database with row locking
            creator_user = User.query.filter_by(username=old_match.creator).with_for_update().first()
            joiner_user = User.query.filter_by(username=old_match.joiner).with_for_update().first()

            if not creator_user or not joiner_user:
                logger.error(f"Could not find users in database")
                db.session.rollback()
                return None

            # Verify coins again within transaction
            if creator_user.coins < old_match.stake or joiner_user.coins < old_match.stake:
                logger.error(f"Players do not have enough coins in database")
                db.session.rollback()
                return None

            # Deduct stakes from both players
            creator_user.coins -= old_match.stake
            joiner_user.coins -= old_match.stake

            # Create new match
            match_id = secrets.token_hex(4)
            new_match = Match(match_id, old_match.creator, old_match.stake)
            new_match.joiner = old_match.joiner
            new_match.creator_ready = True
            new_match.joiner_ready = True

            # Update match and player states
            self.matches[match_id] = new_match
            self.players[old_match.creator].current_match = match_id
            self.players[old_match.joiner].current_match = match_id

            # Update in-memory state
            self.players[old_match.creator].coins = creator_user.coins
            self.players[old_match.joiner].coins = joiner_user.coins

            # Commit transaction
            db.session.commit()

            # Start the match timer
            logger.info(f"Starting new match {match_id}")
            new_match.start_match()  # This will set status to 'playing'
            new_match.start_timer(Config.MATCH_TIMEOUT, self.handle_match_timeout)

            # Remove old match from memory
            if old_match_id in self.matches:
                logger.info(f"Cleaning up old match {old_match_id}")
                del self.matches[old_match_id]

            return new_match

        except Exception as e:
            logger.error(f"Error creating rematch: {e}")
            db.session.rollback()
            return None

    def handle_disconnect(self, player_id):
        # Get initial coins from config
        initial_coins = Config.INITIAL_COINS

        try:
            # Start transaction
            db.session.begin_nested()

            # Get user from database with row locking
            user = User.query.filter_by(username=player_id).with_for_update().first()
            if not user:
                db.session.rollback()
                return initial_coins

            # Find any match this player is in
            for match_id, match in list(self.matches.items()):
                if player_id in [match.creator, match.joiner]:
                    # Return stakes if match is not finished
                    if match.status != 'finished':
                        # Return stake to both players
                        creator_user = User.query.filter_by(username=match.creator).with_for_update().first()
                        joiner_user = User.query.filter_by(username=match.joiner).with_for_update().first()

                        if creator_user:
                            creator_user.coins += match.stake
                            if match.creator in self.players:
                                self.players[match.creator].coins = creator_user.coins

                        if joiner_user:
                            joiner_user.coins += match.stake
                            if match.joiner in self.players:
                                self.players[match.joiner].coins = joiner_user.coins

                    # Clean up the match
                    self.cleanup_match(match_id)

            # Commit transaction
            db.session.commit()

            # Remove player from memory
            if player_id in self.players:
                del self.players[player_id]

            # Return initial coins for testing purposes
            return initial_coins

        except Exception as e:
            db.session.rollback()
            return initial_coins

    def cleanup_match(self, match_id):
        if match_id in self.matches:
            match = self.matches[match_id]
            match.cancel_timer()
            
            # Clear current match reference from players
            if match.creator in self.players:
                self.players[match.creator].current_match = None
            if match.joiner in self.players:
                self.players[match.joiner].current_match = None
            
            del self.matches[match_id]