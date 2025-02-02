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
        match_id = secrets.token_hex(4)
        match = Match(match_id, creator_id, stake)
        self.matches[match_id] = match
        self.players[creator_id].current_match = match_id
        return match

    def join_match(self, match_id, joiner_id):
        import logging
        logger = logging.getLogger('rps_game')

        if match_id not in self.matches:
            logger.error(f"Match {match_id} not found")
            return None

        match = self.matches[match_id]
        if match.status != 'waiting':
            logger.error(f"Match {match_id} not in waiting state (status: {match.status})")
            return None

        if match.joiner is not None:
            logger.error(f"Match {match_id} already has a joiner")
            return None

        if match.creator == joiner_id:
            logger.error(f"Cannot join own match: {match_id}")
            return None

        # Check if both players have enough coins
        if not self.players[match.creator].has_enough_coins(match.stake):
            logger.error(f"Creator has insufficient coins. Has: {self.players[match.creator].coins}, Needs: {match.stake}")
            return None

        if not self.players[joiner_id].has_enough_coins(match.stake):
            logger.error(f"Joiner has insufficient coins. Has: {self.players[joiner_id].coins}, Needs: {match.stake}")
            return None

        match.joiner = joiner_id
        match.joiner_ready = False  # Reset joiner ready state
        self.players[joiner_id].current_match = match_id
        logger.info(f"Player {joiner_id} joined match {match_id}")
        return match

    def get_match(self, match_id):
        return self.matches.get(match_id)

    def get_open_matches(self, player_id):
        import logging
        logger = logging.getLogger('rps_game')

        open_matches = []
        for mid, match in list(self.matches.items()):  # Use list() to avoid modification during iteration
            try:
                if match.status != 'waiting':
                    logger.debug(f"Match {mid} not in waiting state (status: {match.status})")
                    continue

                if match.creator == player_id:
                    logger.debug(f"Match {mid} created by player {player_id}")
                    continue

                if match.joiner is not None:
                    logger.debug(f"Match {mid} already has joiner {match.joiner}")
                    continue

                # Check if creator still exists and is connected
                creator = self.players.get(match.creator)
                if not creator or creator.current_match != mid:
                    logger.warning(f"Creator {match.creator} not connected to match {mid}")
                    self.cleanup_match(mid)
                    continue

                # Check if player exists and is not in another match
                player = self.players.get(player_id)
                if not player:
                    logger.warning(f"Player {player_id} not found")
                    continue

                if player.current_match:
                    logger.debug(f"Player {player_id} already in match {player.current_match}")
                    continue

                # Check if both players have enough coins
                if not creator.has_enough_coins(match.stake):
                    logger.warning(f"Creator {match.creator} has insufficient coins for match {mid}")
                    self.cleanup_match(mid)
                    continue

                if not player.has_enough_coins(match.stake):
                    logger.debug(f"Player {player_id} has insufficient coins for match {mid}")
                    continue

                open_matches.append({
                    'id': mid,
                    'stake': match.stake
                })
                logger.info(f"Found open match {mid} for player {player_id}")
            except Exception as e:
                logger.exception(f"Error processing match {mid}")
                continue

        return open_matches

    def handle_match_timeout(self, match_id):
        from flask import current_app
        from .game_service import GameService
        import logging

        logger = logging.getLogger('rps_game')
        logger.info(f"Match timeout handler called for match {match_id}")

        match = self.matches.get(match_id)
        if not match:
            logger.warning(f"Match {match_id} not found")
            return
        if match.status != 'playing':
            logger.warning(f"Match {match_id} not in playing state (status: {match.status})")
            return

        # Track which moves were auto-generated
        auto_moves = []

        # Assign random moves to players who haven't made a move
        if match.creator not in match.moves:
            match.moves[match.creator] = random.choice(['rock', 'paper', 'scissors'])
            auto_moves.append('creator')
            logger.info(f"Auto-move for creator in match {match_id}: {match.moves[match.creator]}")

        if match.joiner not in match.moves:
            match.moves[match.joiner] = random.choice(['rock', 'paper', 'scissors'])
            auto_moves.append('joiner')
            logger.info(f"Auto-move for joiner in match {match_id}: {match.moves[match.joiner]}")

        # Get the socketio instance from the app
        socketio = current_app.extensions['socketio']

        # Notify about auto moves
        for role in auto_moves:
            logger.info(f"Emitting auto-move for {role} in match {match_id}")
            socketio.emit('move_made', {
                'player': role,
                'auto': True
            }, room=match.id)

        # Calculate match result if both moves are now made
        if match.are_both_moves_made():
            logger.info(f"Both moves made in match {match_id}, calculating result")
            result = GameService.calculate_match_result(match, self.players)
            socketio.emit('match_result', result, room=match.id)
            logger.info(f"Match {match_id} result: {result}")

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
            
            # Clear current match reference from players
            if match.creator in self.players:
                self.players[match.creator].current_match = None
            if match.joiner in self.players:
                self.players[match.joiner].current_match = None
            
            del self.matches[match_id]