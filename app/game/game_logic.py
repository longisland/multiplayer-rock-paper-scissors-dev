import random
from datetime import datetime, UTC, timedelta
from threading import Timer
import logging
from flask_socketio import SocketIO
from ..models.models import db, Player, Match

logger = logging.getLogger(__name__)

# Match timers storage
match_timers = {}

# Initialize SocketIO instance
socketio = SocketIO()

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

def start_match_timer(match_id):
    """Start a timer for the match."""
    logger.info(f"Starting timer for match {match_id}")
    match = get_match(match_id)
    if not match:
        logger.error(f"Match {match_id} not found when starting timer")
        return

    match.started_at = datetime.now(UTC)
    db.session.commit()

    # Create a timer for 30 seconds
    timer = Timer(30.0, handle_match_timeout, args=[match_id])
    timer.start()
    match_timers[match_id] = timer

    # Notify clients that the match has started with match details
    socketio.emit('match_started', {
        'match_id': match_id,
        'time_limit': 30,
        'player1_id': match.player1_id,
        'player2_id': match.player2_id,
        'status': match.status
    }, room=str(match_id))

def calculate_and_emit_result(match_id):
    """Calculate and emit the match result."""
    match = get_match(match_id)
    if not match:
        logger.error(f"Match {match_id} not found when calculating result")
        return

    if match.creator_move and match.joiner_move:
        result = calculate_winner(match.creator_move, match.joiner_move)
        match.result = result
        match.status = 'finished'
        match.finished_at = datetime.now(UTC)
        db.session.commit()

        # Clean up the timer if it exists
        if match_id in match_timers:
            match_timers[match_id].cancel()
            del match_timers[match_id]

        # Emit the result to all players in the match
        socketio.emit('match_result', {
            'result': result,
            'creator_move': match.creator_move,
            'joiner_move': match.joiner_move
        }, room=match_id)

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

def cleanup_stale_matches(app):
    """Clean up matches that have been stuck in 'playing' or 'waiting' state for too long."""
    try:
        with app.app_context():
            # Find matches that have been in 'playing' state for more than 30 seconds
            playing_cutoff = datetime.now(UTC) - timedelta(seconds=30)
            waiting_cutoff = datetime.now(UTC) - timedelta(minutes=5)

            # Clean up stale playing matches
            stale_playing = Match.query.filter(
                Match.status == 'playing',
                Match.started_at < playing_cutoff
            ).all()

            # Clean up stale waiting matches
            stale_waiting = Match.query.filter(
                Match.status == 'waiting',
                Match.created_at < waiting_cutoff
            ).all()

            # Handle stale playing matches
            for match in stale_playing:
                logger.info(f"Cleaning up stale playing match {match.id}")
                handle_match_timeout(match.id)

            # Handle stale waiting matches
            for match in stale_waiting:
                logger.info(f"Cleaning up stale waiting match {match.id}")
                try:
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
                    # Notify clients about the match being cancelled
                    socketio.emit('match_cancelled', {
                        'match_id': match.id,
                        'reason': 'timeout'
                    }, room=str(match.id))
                    logger.info(f"Cleaned up waiting match {match.id}")
                except Exception as e:
                    logger.exception(f"Error cleaning up waiting match {match.id}")
                    db.session.rollback()

    except Exception as e:
        logger.exception("Error cleaning up stale matches")
