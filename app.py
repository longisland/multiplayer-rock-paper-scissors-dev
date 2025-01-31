from flask import Flask, render_template, request, jsonify, session
from flask_socketio import SocketIO, emit, join_room, leave_room
import secrets
import os
import random
import time
from datetime import datetime, UTC, timedelta
from threading import Timer
import logging
from models import db, Player, Match
from config import Config
import threading

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

app = Flask(__name__, static_url_path='/static')
app.config.from_object(Config)

# Initialize database
db.init_app(app)

# Create tables
with app.app_context():
    db.create_all()

# Configure Flask-SocketIO
socketio = SocketIO(
    app,
    async_mode='gevent',  # Use gevent for WebSocket support
    cors_allowed_origins='*',  # Allow all origins in development
    logger=True,
    engineio_logger=True,
    ping_timeout=60,
    ping_interval=25,
    max_http_buffer_size=1000000,
    manage_session=False  # Let Flask manage the sessions
)

# Match timers storage
match_timers = {}

def get_match(match_id):
    """Get a match by ID using the new SQLAlchemy API."""
    return db.session.get(Match, match_id)

def random_move():
    return random.choice(['rock', 'paper', 'scissors'])

def cleanup_stale_matches():
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

def generate_session_id():
    return secrets.token_hex(8)

@app.route('/')
def index():
    if 'session_id' not in session:
        session_id = generate_session_id()
        session['session_id'] = session_id
        new_player = Player(session_id=session_id)
        db.session.add(new_player)
        db.session.commit()
        logger.info(f"Created new session: {session_id}")
    return render_template('index.html')

@app.route('/api/state')
def get_state():
    try:
        session_id = session.get('session_id')
        if not session_id:
            # Create new session if none exists
            session_id = generate_session_id()
            session['session_id'] = session_id
            new_player = Player(session_id=session_id)
            db.session.add(new_player)
            db.session.commit()
            logger.info(f"Created new session: {session_id}")
        
        player = Player.query.filter_by(session_id=session_id).first()
        if not player:
            # Reinitialize player if not found
            player = Player(session_id=session_id)
            db.session.add(player)
            db.session.commit()
            logger.info(f"Reinitialized player: {session_id}")
        
        # Update last active timestamp
        player.last_active = datetime.now(UTC)
        db.session.commit()
        
        # Get open matches that:
        # 1. Are in waiting state
        # 2. Are not created by current player
        # 3. Have a creator with enough coins
        # 4. Current player has enough coins to join
        open_matches = []
        available_matches = Match.query.filter_by(status='waiting').all()
        
        for match in available_matches:
            if (match.creator_id != session_id and 
                match.creator.coins >= match.stake and
                player.coins >= match.stake):
                open_matches.append({
                    'id': match.id,
                    'stake': match.stake
                })
        
        # Get current match details if in a match
        current_match = None
        if player.current_match_id:
            match = get_match(player.current_match_id)
            if match:
                # Check if match is stale
                if match.started_at:
                    cutoff_time = datetime.now(UTC) - timedelta(seconds=30)
                    match_time = match.started_at.replace(tzinfo=UTC) if match.started_at.tzinfo is None else match.started_at
                    if match_time < cutoff_time:
                        # Clean up stale match
                        if match.status == 'playing':
                            handle_match_timeout(match.id)
                        else:
                            player.current_match_id = None
                            db.session.delete(match)
                            db.session.commit()
                        match = None
                
                if match:
                    current_match = {
                        'id': match.id,
                        'status': match.status,
                        'stake': match.stake,
                        'is_creator': session_id == match.creator_id
                    }
        
        logger.debug(f"State for {session_id}: coins={player.coins}, current_match={current_match}")
        return jsonify({
            'coins': player.coins,
            'stats': {
                'wins': player.wins,
                'losses': player.losses,
                'draws': player.draws,
                'total_coins_won': player.total_coins_won,
                'total_coins_lost': player.total_coins_lost
            },
            'open_matches': open_matches,
            'current_match': current_match
        })
    except Exception as e:
        logger.exception("Error getting state")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/api/create_match', methods=['POST'])
def create_match():
    try:
        session_id = session.get('session_id')
        player = Player.query.filter_by(session_id=session_id).first()
        if not player:
            logger.error(f"Invalid session: {session_id}")
            return jsonify({'error': 'Invalid session'}), 400
        
        stake = request.json.get('stake', 0)
        if not isinstance(stake, int) or stake <= 0:
            logger.error(f"Invalid stake: {stake}")
            return jsonify({'error': 'Invalid stake'}), 400
        
        if player.coins < stake:
            logger.error(f"Insufficient coins. Has: {player.coins}, Needs: {stake}")
            return jsonify({'error': 'Insufficient coins'}), 400
        
        # Clear any existing match
        if player.current_match_id:
            current_match = get_match(player.current_match_id)
            if current_match:
                logger.info(f"Cleaning up existing match: {current_match.id}")
                if current_match.id in match_timers and match_timers[current_match.id]:
                    match_timers[current_match.id].cancel()
                    match_timers.pop(current_match.id)
                db.session.delete(current_match)
            player.current_match_id = None
        
        match_id = secrets.token_hex(4)
        new_match = Match(
            id=match_id,
            creator_id=session_id,
            stake=stake,
            status='waiting',
            creator_ready=True  # Creator is automatically ready
        )
        
        db.session.add(new_match)
        player.current_match_id = match_id
        db.session.commit()
        
        logger.info(f"Match created: {match_id} by {session_id}")
        logger.info(f"Creator {session_id} ready in match {match_id}")
        return jsonify({'match_id': match_id})
    except Exception as e:
        logger.exception("Error creating match")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/api/join_match', methods=['POST'])
def join_match():
    try:
        session_id = session.get('session_id')
        player = Player.query.filter_by(session_id=session_id).first()
        if not player:
            logger.error(f"Invalid session: {session_id}")
            return jsonify({'error': 'Invalid session'}), 400
        
        match_id = request.json.get('match_id')
        match = get_match(match_id)
        if not match:
            logger.error(f"Invalid match: {match_id}")
            return jsonify({'error': 'Invalid match'}), 400
        
        if match.status != 'waiting':
            logger.error(f"Match not available. Status: {match.status}")
            return jsonify({'error': 'Match not available'}), 400
        
        if player.coins < match.stake:
            logger.error(f"Insufficient coins. Has: {player.coins}, Needs: {match.stake}")
            return jsonify({'error': 'Insufficient coins'}), 400
        
        # Clear any existing match for the joining player
        if player.current_match_id and player.current_match_id != match_id:
            current_match = get_match(player.current_match_id)
            if current_match:
                logger.info(f"Cleaning up existing match: {current_match.id}")
                if current_match.id in match_timers and match_timers[current_match.id]:
                    match_timers[current_match.id].cancel()
                    match_timers.pop(current_match.id)
                db.session.delete(current_match)
            player.current_match_id = None
        
        # Update match and player state
        match.joiner_id = session_id
        player.current_match_id = match_id
        db.session.commit()
        
        logger.info(f"Player {session_id} joined match {match_id}")
        return jsonify({'success': True})
    except Exception as e:
        logger.exception("Error joining match")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/api/move', methods=['POST'])
def make_move():
    try:
        session_id = session.get('session_id')
        player = Player.query.filter_by(session_id=session_id).first()
        if not player:
            logger.error(f"Invalid session: {session_id}")
            return jsonify({'error': 'Invalid session'}), 400
        
        move = request.json.get('move')
        if move not in ['rock', 'paper', 'scissors']:
            logger.error(f"Invalid move: {move}")
            return jsonify({'error': 'Invalid move'}), 400
        
        # Lock the player for update to get the latest state
        player = Player.query.filter_by(session_id=session_id).with_for_update().first()
        if not player:
            logger.error(f"Player {session_id} disappeared")
            return jsonify({'error': 'Player not found'}), 400
        
        if not player.current_match_id:
            logger.error(f"No active match for player {session_id}")
            return jsonify({'error': 'No active match'}), 400
        
        # Lock the match for update
        match = Match.query.filter_by(id=player.current_match_id).with_for_update().first()
        if not match:
            logger.error(f"Match {player.current_match_id} not found")
            return jsonify({'error': 'Match not found'}), 400
        
        # Check if match is too old (more than 10 seconds)
        if match.started_at:
            # Convert naive datetime to UTC
            if match.started_at.tzinfo is None:
                match_start = match.started_at.replace(tzinfo=UTC)
            else:
                match_start = match.started_at
            
            if match_start < datetime.now(UTC) - timedelta(seconds=10):
                logger.error(f"Match {match.id} has timed out")
                handle_match_timeout(match.id)
                return jsonify({'error': 'Match has timed out. Random moves were assigned.'}), 400
        
        if match.status != 'playing':
            logger.error(f"Match {match.id} not in playing state. Status: {match.status}")
            return jsonify({'error': 'Match not in playing state'}), 400
        
        # Check if player is part of the match
        if session_id not in [match.creator_id, match.joiner_id]:
            logger.error(f"Player {session_id} not part of match {match.id}")
            return jsonify({'error': 'Not part of match'}), 400
        
        # Check if player already made a move
        if (session_id == match.creator_id and match.creator_move) or \
           (session_id == match.joiner_id and match.joiner_move):
            logger.error(f"Player {session_id} already made a move in match {match.id}")
            return jsonify({'error': 'Already made a move'}), 400
        
        # Record the move
        if session_id == match.creator_id:
            match.creator_move = move
            logger.info(f"Creator {session_id} made move {move} in match {match.id}")
            socketio.emit('move_made', {'player': 'creator'}, room=match.id)
        else:
            match.joiner_move = move
            logger.info(f"Joiner {session_id} made move {move} in match {match.id}")
            socketio.emit('move_made', {'player': 'joiner'}, room=match.id)
        
        db.session.commit()
        
        # If both players have moved, calculate result
        if match.creator_move and match.joiner_move:
            calculate_and_emit_result(match.id)
        
        return jsonify({'success': True})
    except Exception as e:
        logger.exception("Error making move")
        return jsonify({'error': 'Internal server error'}), 500

def calculate_and_emit_result(match_id):
    try:
        match = get_match(match_id)
        if not match:
            logger.error(f"Match {match_id} not found in result calculation")
            return
        
        # Get both players
        creator = Player.query.filter_by(session_id=match.creator_id).first()
        joiner = Player.query.filter_by(session_id=match.joiner_id).first()
        
        if not creator or not joiner:
            logger.error(f"Players not found for match {match_id}")
            return
        
        # Store stake for potential rematch
        stake = match.stake
        
        # Calculate winner
        result = calculate_winner(match.creator_move, match.joiner_move)
        
        # Update match state
        match.status = 'finished'
        match.finished_at = datetime.now(UTC)
        match.creator_ready = False  # Reset ready states for rematch
        match.joiner_ready = False
        
        # Keep match references for rematch
        creator.current_match_id = match.id
        joiner.current_match_id = match.id
        
        # Update player stats and coins
        if result == 'draw':
            creator.draws += 1
            joiner.draws += 1
            creator.coins += stake
            joiner.coins += stake
            winner_id = None
        elif result == 'player1':  # Creator wins
            creator.wins += 1
            joiner.losses += 1
            creator.coins += stake * 2
            creator.total_coins_won += stake
            joiner.total_coins_lost += stake
            winner_id = creator.session_id
        else:  # Joiner wins
            joiner.wins += 1
            creator.losses += 1
            joiner.coins += stake * 2
            joiner.total_coins_won += stake
            creator.total_coins_lost += stake
            winner_id = joiner.session_id
        
        match.winner_id = winner_id
        db.session.commit()
        
        # Emit result to both players
        socketio.emit('match_result', {
            'creator_move': match.creator_move,
            'joiner_move': match.joiner_move,
            'winner_id': winner_id,
            'stake': stake,
            'can_rematch': (creator.coins >= stake and joiner.coins >= stake)
        }, room=match.id)
        
    except Exception as e:
        logger.exception(f"Error calculating result for match {match_id}")

@socketio.on('join_match_room')
def on_join_match_room(data):
    try:
        session_id = session.get('session_id')
        match_id = data.get('match_id')
        
        if not session_id or not match_id:
            logger.error(f"Invalid session or match ID in join_match_room: {session_id}, {match_id}")
            return
        
        match = get_match(match_id)
        if not match:
            return
        
        # Only allow players who are part of the match
        if session_id not in [match.creator_id, match.joiner_id]:
            logger.error(f"Player {session_id} not part of match {match_id}")
            return
        
        join_room(match_id)
        logger.info(f"Player {session_id} joined match room {match_id}")
        
        # For rematch, the match will already be in playing state
        if match.status == 'playing':
            # Start match timer
            if match_id not in match_timers or not match_timers[match_id].is_alive():
                timer = Timer(10, handle_match_timeout, args=[match_id])
                match_timers[match_id] = timer
                timer.start()
            
            # Notify player about current match state
            emit('match_started', {
                'match_id': match_id,
                'stake': match.stake,
                'creator_id': match.creator_id,
                'joiner_id': match.joiner_id,
                'rematch': True
            })
            
            # If moves have been made, notify the player
            if match.creator_move:
                emit('move_made', {'player': 'creator'})
            if match.joiner_move:
                emit('move_made', {'player': 'joiner'})
        elif match.status == 'waiting':
            # If this is the joiner, start the match
            if session_id == match.joiner_id:
                # Deduct stakes
                creator = Player.query.filter_by(session_id=match.creator_id).first()
                joiner = Player.query.filter_by(session_id=match.joiner_id).first()
                
                if not creator or not joiner:
                    logger.error(f"Players not found for match {match_id}")
                    return
                
                creator.coins -= match.stake
                joiner.coins -= match.stake
                
                # Update match state
                match.status = 'playing'
                match.started_at = datetime.now(UTC)
                db.session.commit()
                
                # Start match timer
                timer = Timer(10, handle_match_timeout, args=[match_id])
                match_timers[match_id] = timer
                timer.start()
                
                # Notify both players
                socketio.emit('match_started', {
                    'match_id': match_id,
                    'stake': match.stake,
                    'creator_id': match.creator_id,
                    'joiner_id': match.joiner_id,
                    'rematch': True
                }, room=match_id)
        
    except Exception as e:
        logger.exception("Error in join_match_room handler")

@socketio.on('rematch_request')
def on_rematch_request(data):
    try:
        session_id = session.get('session_id')
        match_id = data.get('match_id')
        
        if not session_id or not match_id:
            logger.error(f"Invalid session or match ID in rematch_request: {session_id}, {match_id}")
            return
        
        match = get_match(match_id)
        if not match:
            return
        
        # Get both players
        creator = Player.query.filter_by(session_id=match.creator_id).first()
        joiner = Player.query.filter_by(session_id=match.joiner_id).first()
        
        if not creator or not joiner:
            return
        
        # Check if both players have enough coins for rematch
        stake = match.stake
        if creator.coins < stake or joiner.coins < stake:
            logger.error(f"Insufficient coins for rematch in match {match_id}")
            socketio.emit('rematch_declined', {
                'reason': 'insufficient_coins'
            }, room=match_id)
            return
        
        # Check if player already accepted rematch
        if (session_id == match.creator_id and match.creator_ready) or \
           (session_id == match.joiner_id and match.joiner_ready):
            logger.error(f"Player {session_id} already accepted rematch")
            return
        
        # Update ready state
        if session_id == match.creator_id:
            match.creator_ready = True
            logger.info(f"Creator {session_id} ready for rematch in match {match_id}")
        elif session_id == match.joiner_id:
            match.joiner_ready = True
            logger.info(f"Joiner {session_id} ready for rematch in match {match_id}")
        
        db.session.commit()
        
        # Notify others that a player accepted rematch
        socketio.emit('rematch_accepted_by_player', {
            'player_type': 'creator' if session_id == match.creator_id else 'joiner'
        }, room=match_id)
        
        # If both players are ready, start new match
        if match.creator_ready and match.joiner_ready:
            logger.info(f"Both players ready for rematch in match {match_id}")
            
            # Deduct stakes
            creator.coins -= stake
            joiner.coins -= stake
            
            # Reset match state
            match.status = 'playing'
            match.started_at = datetime.now(UTC)
            match.creator_move = None
            match.joiner_move = None
            match.winner_id = None
            match.finished_at = None
            
            # Reset ready states
            match.creator_ready = False
            match.joiner_ready = False
            
            db.session.commit()
            
            # First notify about the rematch being accepted
            socketio.emit('rematch_accepted', {
                'match_id': match_id,
                'stake': stake
            }, room=match_id)
            
            # Give clients time to process the rematch acceptance
            time.sleep(1)
            
            # Start match timer
            timer = Timer(10, handle_match_timeout, args=[match_id])
            match_timers[match_id] = timer
            timer.start()
            
            # Notify players to start playing
            socketio.emit('match_started', {
                'match_id': match_id,
                'stake': stake,
                'rematch': True,
                'creator_id': match.creator_id,
                'joiner_id': match.joiner_id
            }, room=match_id)
            
    except Exception as e:
        logger.exception("Error in rematch_request handler")

@socketio.on('rematch_declined')
def on_rematch_declined(data):
    try:
        session_id = session.get('session_id')
        match_id = data.get('match_id')
        
        if not session_id or not match_id:
            logger.error(f"Invalid session or match ID in rematch_declined: {session_id}, {match_id}")
            return
        
        match = get_match(match_id)
        if not match:
            return
        
        # Reset ready states when a player declines
        match.creator_ready = False
        match.joiner_ready = False
        db.session.commit()
        
        # Notify others that a player declined rematch
        socketio.emit('rematch_declined', {}, room=match_id)
        
    except Exception as e:
        logger.exception("Error in rematch_declined handler")