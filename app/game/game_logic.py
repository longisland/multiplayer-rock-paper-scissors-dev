import random
from datetime import datetime, UTC, timedelta
from threading import Timer
import logging
from ..models.models import db, Player, Match

logger = logging.getLogger(__name__)

# Match timers storage
match_timers = {}

def get_match(match_id):
    """Get a match by ID using the new SQLAlchemy API."""
    return db.session.get(Match, match_id)

def random_move():
    return random.choice(['rock', 'paper', 'scissors'])

def calculate_winner(move1, move2):
    if move1 == move2:
        return 'draw'
    if (
        (move1 == 'rock' and move2 == 'scissors') or
        (move1 == 'paper' and move2 == 'rock') or
        (move1 == 'scissors' and move2 == 'paper')
    ):
        return 'player1'
    return 'player2'

def cleanup_stale_matches(app):
    """Clean up matches that have been stuck in 'playing' or 'waiting' state for too long."""
    try:
        with app.app_context():
            # Find matches that have been in 'playing' state for more than 30 seconds
            cutoff_time = datetime.now(UTC) - timedelta(seconds=30)
            stale_matches = Match.query.filter(
                Match.status.in_(['playing', 'waiting'])
            ).all()
            
            # Filter matches manually to handle naive datetimes
            stale_matches = [
                match for match in stale_matches
                if match.started_at and (
                    match.started_at.replace(tzinfo=UTC) if match.started_at.tzinfo is None
                    else match.started_at
                ) < cutoff_time
            ]
            
            for match in stale_matches:
                logger.info(f"Cleaning up stale match {match.id}")
                if match.status == 'playing':
                    handle_match_timeout(match.id)
                else:
                    # For waiting matches, just clean up and reset player states
                    try:
                        if match.creator_id:
                            creator = Player.query.filter_by(session_id=match.creator_id).first()
                            if creator and creator.current_match_id == match.id:
                                creator.current_match_id = None
                        if match.joiner_id:
                            joiner = Player.query.filter_by(session_id=match.joiner_id).first()
                            if joiner and joiner.current_match_id == match.id:
                                joiner.current_match_id = None
                        db.session.delete(match)
                        db.session.commit()
                        logger.info(f"Cleaned up waiting match {match.id}")
                    except Exception as e:
                        logger.exception(f"Error cleaning up waiting match {match.id}")
                        db.session.rollback()
    except Exception as e:
        logger.exception("Error cleaning up stale matches")

def handle_match_timeout(match_id):
    try:
        match = get_match(match_id)
        if not match:
            logger.error(f"Match {match_id} not found in timeout handler")
            return
        
        if match.status != 'playing':
            logger.error(f"Match {match_id} not in playing state in timeout handler")
            return
        
        logger.info(f"Match {match_id} timed out. Processing...")
        
        # Assign random moves to players who haven't made a move
        if not match.creator_move:
            move = random_move()
            match.creator_move = move
            logger.info(f"Assigned random move {move} to creator in match {match_id}")
            socketio.emit('move_made', {'player': 'creator', 'auto': True}, room=match_id)
        
        if not match.joiner_move:
            move = random_move()
            match.joiner_move = move
            logger.info(f"Assigned random move {move} to joiner in match {match_id}")
            socketio.emit('move_made', {'player': 'joiner', 'auto': True}, room=match_id)
        
        db.session.commit()
        
        # Calculate and emit result
        calculate_and_emit_result(match_id)
    except Exception as e:
        logger.exception(f"Error in match timeout handler for match {match_id}")
        # Try to clean up the match in case of error
        try:
            match = get_match(match_id)
            if match:
                match.status = 'finished'
                match.finished_at = datetime.now(UTC)
                if match.creator_id:
                    creator = Player.query.filter_by(session_id=match.creator_id).first()
                    if creator:
                        creator.current_match_id = None
                if match.joiner_id:
                    joiner = Player.query.filter_by(session_id=match.joiner_id).first()
                    if joiner:
                        joiner.current_match_id = None
                db.session.commit()
        except Exception as cleanup_error:
            logger.exception(f"Error cleaning up match {match_id} after timeout error")