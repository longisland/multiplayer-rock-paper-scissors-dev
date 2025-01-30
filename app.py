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
            return jsonify({'error': 'Not your match'}), 400
        
        # Check if player already made a move
        if (session_id == match.creator_id and match.creator_move) or \
           (session_id == match.joiner_id and match.joiner_move):
            logger.error(f"Player {session_id} already made a move in match {match.id}")
            return jsonify({'error': 'Move already made'}), 400
        
        # Record the move
        try:
            # Record the move
            if session_id == match.creator_id:
                match.creator_move = move
            else:
                match.joiner_move = move
            
            # Cancel the timer if both players have moved
            if match.creator_move and match.joiner_move:
                if match.id in match_timers and match_timers[match.id]:
                    match_timers[match.id].cancel()
                    match_timers.pop(match.id)
            
            db.session.commit()
            
            logger.info(f"Player {session_id} made move {move} in match {match.id}")
            
            # Notify others that a move was made (without revealing the move)
            socketio.emit('move_made', {
                'player': 'creator' if session_id == match.creator_id else 'joiner',
                'auto': False
            }, room=match.id)
            
            # If both players have moved, calculate result
            if match.creator_move and match.joiner_move:
                calculate_and_emit_result(match.id)
            
            return jsonify({'success': True})
        except Exception as e:
            db.session.rollback()
            logger.exception(f"Error recording move for match {match.id}")
            return jsonify({'error': 'Failed to record move. Please try again.'}), 500
    except Exception as e:
        logger.exception("Error making move")
        return jsonify({'error': 'Internal server error'}), 500

def calculate_and_emit_result(match_id):
    match = get_match(match_id)
    if not match:
        logger.error(f"Match {match_id} not found in calculate_and_emit_result")
        return
    
    creator = Player.query.filter_by(session_id=match.creator_id).first()
    joiner = Player.query.filter_by(session_id=match.joiner_id).first()
    
    if not creator or not joiner:
        logger.error(f"Players not found for match {match_id}")
        return
    
    result = calculate_winner(match.creator_move, match.joiner_move)
    
    # Cancel timer if exists
    if match_id in match_timers and match_timers[match_id]:
        match_timers[match_id].cancel()
        match_timers.pop(match_id)
    
    # Store stake for potential rematch
    stake = match.stake
    
    # Update player stats and coins
    if result == 'draw':
        creator.draws += 1
        joiner.draws += 1
    elif result == 'player1':  # Creator wins
        creator.wins += 1
        creator.total_coins_won += stake
        joiner.losses += 1
        joiner.total_coins_lost += stake
        creator.coins += stake
        joiner.coins -= stake
        match.winner = creator.session_id
    else:  # Joiner wins
        joiner.wins += 1
        joiner.total_coins_won += stake
        creator.losses += 1
        creator.total_coins_lost += stake
        creator.coins -= stake
        joiner.coins += stake
        match.winner = joiner.session_id
    
    match.status = 'finished'
    match.finished_at = datetime.now(UTC)
    match.creator_ready = False  # Reset ready states for rematch
    match.joiner_ready = False
    
    # Keep match references for rematch
    creator.current_match_id = match_id
    joiner.current_match_id = match_id
    
    # Commit all changes
    db.session.commit()
    
    # Prepare result object
    result_data = {
        'winner': result,
        'creator_move': match.creator_move,
        'joiner_move': match.joiner_move,
        'creator_stats': {
            'wins': creator.wins,
            'losses': creator.losses,
            'draws': creator.draws,
            'total_coins_won': creator.total_coins_won,
            'total_coins_lost': creator.total_coins_lost
        },
        'joiner_stats': {
            'wins': joiner.wins,
            'losses': joiner.losses,
            'draws': joiner.draws,
            'total_coins_won': joiner.total_coins_won,
            'total_coins_lost': joiner.total_coins_lost
        },
        'stake': stake,
        'can_rematch': (creator.coins >= stake and joiner.coins >= stake)
    }
    
    # Notify both players
    socketio.emit('match_result', result_data, room=match_id)

@socketio.on('connect')
def handle_connect():
    try:
        session_id = session.get('session_id')
        if session_id:
            player = Player.query.filter_by(session_id=session_id).first()
            if player:
                join_room(session_id)
                logger.info(f"Socket connected for session {session_id}")
                
                # If player is in a match, join that room too
                if player.current_match_id:
                    match = get_match(player.current_match_id)
                    if match:
                        join_room(match.id)
                        logger.info(f"Player {session_id} joined match room {match.id}")
    except Exception as e:
        logger.exception("Error in socket connect handler")

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
            logger.error(f"Match {match_id} not found")
            return
        
        if match.status != 'waiting':
            logger.error(f"Match {match_id} not in waiting state. Status: {match.status}")
            return
        
        join_room(match_id)
        logger.info(f"Player {session_id} joined match room {match_id} via socket")
    except Exception as e:
        logger.exception("Error in join_match_room handler")

@socketio.on('ready_for_match')
def on_ready_for_match(data):
    try:
        session_id = session.get('session_id')
        match_id = data.get('match_id')
        
        if not session_id or not match_id:
            logger.error(f"Invalid session or match ID in ready_for_match: {session_id}, {match_id}")
            return
            
        match = get_match(match_id)
        if not match:
            logger.error(f"Match {match_id} not found")
            return
        
        # Join the match room if not already in it
        join_room(match_id)
        
        # For rematch, the match will already be in playing state
        if match.status not in ['waiting', 'playing']:
            logger.error(f"Match {match_id} in invalid state. Status: {match.status}")
            return
        
        if session_id == match.creator_id:
            match.creator_ready = True
            logger.info(f"Creator {session_id} ready in match {match_id}")
        elif session_id == match.joiner_id:
            match.joiner_ready = True
            logger.info(f"Joiner {session_id} ready in match {match_id}")
        else:
            logger.error(f"Player {session_id} not part of match {match_id}")
            return
        
        db.session.commit()
        
        # If both players are ready, start the match
        if match.creator_ready and match.joiner_ready:
            if match.status == 'waiting':
                match.status = 'playing'
                match.started_at = datetime.now(UTC)
                match.creator_move = None
                match.joiner_move = None
                db.session.commit()
            
            # Set up timer for move timeout
            def handle_timeout():
                with app.app_context():
                    try:
                        handle_match_timeout(match_id)
                    except Exception as e:
                        logger.exception(f"Error in match timeout handler for match {match_id}")
            
            # Cancel any existing timer
            if match_id in match_timers and match_timers[match_id]:
                match_timers[match_id].cancel()
            
            # Start new timer
            match_timers[match_id] = Timer(10, handle_timeout)  # 10 seconds for move timeout
            match_timers[match_id].start()
            
            logger.info(f"Match {match_id} started")
            socketio.emit('match_started', {
                'match_id': match_id,
                'start_time': match.started_at.isoformat(),
                'creator_id': match.creator_id,
                'joiner_id': match.joiner_id,
                'stake': match.stake,
                'rematch': True
            }, room=match_id)
    except Exception as e:
        logger.exception("Error in ready_for_match handler")

@socketio.on('rematch_request')
def on_rematch_request(data):
    try:
        session_id = session.get('session_id')
        match_id = data.get('match_id')
        
        if not session_id or not match_id:
            logger.error(f"Invalid session or match ID in rematch_request: {session_id}, {match_id}")
            return
        
        # Lock the match for update
        match = Match.query.filter_by(id=match_id).with_for_update().first()
        if not match:
            logger.error(f"Match {match_id} not found")
            return
        
        # Check if match is in finished state
        if match.status != 'finished':
            logger.error(f"Match {match_id} not in finished state")
            return
        
        # Check if both players have enough coins
        creator = Player.query.filter_by(session_id=match.creator_id).first()
        joiner = Player.query.filter_by(session_id=match.joiner_id).first()
        
        if not creator or not joiner:
            logger.error(f"Players not found for match {match_id}")
            return
        
        if creator.coins < match.stake or joiner.coins < match.stake:
            logger.error(f"Insufficient coins for rematch in match {match_id}")
            socketio.emit('rematch_declined', {
                'error': 'Insufficient coins'
            }, room=match_id)
            return
        
        # Check if player already accepted rematch
        if (session_id == match.creator_id and match.creator_ready) or \
           (session_id == match.joiner_id and match.joiner_ready):
            logger.error(f"Player {session_id} already accepted rematch")
            return
        
        # Update player ready state in the current match
        if session_id == match.creator_id:
            match.creator_ready = True
            logger.info(f"Creator {session_id} ready for rematch in match {match_id}")
        else:
            match.joiner_ready = True
            logger.info(f"Joiner {session_id} ready for rematch in match {match_id}")
        db.session.commit()
        
        # Notify others that a player accepted rematch
        socketio.emit('rematch_accepted_by_player', {
            'player': 'creator' if session_id == match.creator_id else 'joiner',
            'match_id': match_id,
            'creator_ready': match.creator_ready,
            'joiner_ready': match.joiner_ready
        }, room=match_id)
        
        # Start a new match only if both players have accepted
        if match.creator_ready and match.joiner_ready:
            logger.info(f"Both players ready for rematch in match {match_id}")
            
            # Create new match with same stake but random creator
            new_creator_id = random.choice([match.creator_id, match.joiner_id])
            new_joiner_id = match.joiner_id if new_creator_id == match.creator_id else match.creator_id
            
            new_match_id = secrets.token_hex(4)
            new_match = Match(
                id=new_match_id,
                creator_id=new_creator_id,
                joiner_id=new_joiner_id,
                stake=match.stake,
                status='playing',  # Start in playing state
                creator_ready=True,  # Both players are ready
                joiner_ready=True,
                started_at=datetime.now(UTC)  # Set start time
            )
            
            # Update player references
            new_creator = Player.query.filter_by(session_id=new_creator_id).first()
            new_joiner = Player.query.filter_by(session_id=new_joiner_id).first()
            new_creator.current_match_id = new_match_id
            new_joiner.current_match_id = new_match_id
            
            db.session.add(new_match)
            db.session.commit()
            
            # Join both players to the new match room
            join_room(new_match_id)
            
            # Set up timer for move timeout
            def handle_timeout():
                with app.app_context():
                    try:
                        handle_match_timeout(new_match_id)
                    except Exception as e:
                        logger.exception(f"Error in match timeout handler for match {new_match_id}")
            
            # Start new timer
            match_timers[new_match_id] = Timer(10, handle_timeout)  # 10 seconds for move timeout
            match_timers[new_match_id].start()
            
            logger.info(f"Rematch started: {new_match_id}")
            
            # Notify both players about the new match
            socketio.emit('match_started', {
                'match_id': new_match_id,
                'start_time': new_match.started_at.isoformat(),
                'rematch': True,
                'creator_id': new_creator_id,
                'joiner_id': new_joiner_id,
                'stake': new_match.stake
            }, room=match_id)  # Send to old match room
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
            logger.error(f"Match {match_id} not found")
            return
        
        socketio.emit('rematch_declined', {}, room=match_id)
        logger.info(f"Rematch declined for match {match_id} by {session_id}")
    except Exception as e:
        logger.exception("Error in rematch_declined handler")

# Start cleanup thread
def cleanup_thread_func():
    with app.app_context():
        while True:
            try:
                cleanup_stale_matches()
            except Exception as e:
                logger.exception("Error in cleanup thread")
            time.sleep(10)  # Run every 10 seconds

cleanup_thread = threading.Thread(target=cleanup_thread_func, daemon=True)
cleanup_thread.start()

@socketio.on('rematch_accepted')
def on_rematch_accepted(data):
    try:
        session_id = session.get('session_id')
        match_id = data.get('match_id')
        
        if not session_id or not match_id:
            logger.error(f"Invalid session or match ID in rematch_accepted: {session_id}, {match_id}")
            return
        
        match = get_match(match_id)
        if not match:
            logger.error(f"Match {match_id} not found")
            return
        
        # Create new match with same stake but random creator
        new_creator_id = random.choice([match.creator_id, match.joiner_id])
        new_joiner_id = match.joiner_id if new_creator_id == match.creator_id else match.creator_id
        
        new_match_id = secrets.token_hex(4)
        new_match = Match(
            id=new_match_id,
            creator_id=new_creator_id,
            joiner_id=new_joiner_id,
            stake=match.stake,
            status='waiting',
            creator_ready=False,
            joiner_ready=False
        )
        
        # Update player references
        new_creator = Player.query.filter_by(session_id=new_creator_id).first()
        new_joiner = Player.query.filter_by(session_id=new_joiner_id).first()
        new_creator.current_match_id = new_match_id
        new_joiner.current_match_id = new_match_id
        
        db.session.add(new_match)
        db.session.commit()
        
        # Join both players to the new match room
        join_room(new_match_id)
        
        # Update player ready state
        if session_id == new_creator_id:
            new_match.creator_ready = True
        else:
            new_match.joiner_ready = True
        db.session.commit()
        
        # Notify others that a player accepted rematch
        socketio.emit('rematch_accepted_by_player', {
            'player': 'creator' if session_id == new_creator_id else 'joiner',
            'match_id': new_match_id
        }, room=match_id)  # Send to old match room
        
        # Start the match if both players have accepted
        if new_match.creator_ready and new_match.joiner_ready:
            new_match.status = 'playing'
            new_match.started_at = datetime.now(UTC)
            new_match.creator_move = None
            new_match.joiner_move = None
            db.session.commit()
            
            # Set up timer for move timeout
            def handle_timeout():
                with app.app_context():
                    try:
                        handle_match_timeout(new_match_id)
                    except Exception as e:
                        logger.exception(f"Error in match timeout handler for match {new_match_id}")
            
            # Cancel any existing timer
            if new_match_id in match_timers and match_timers[new_match_id]:
                match_timers[new_match_id].cancel()
            
            # Start new timer
            match_timers[new_match_id] = Timer(10, handle_timeout)  # 10 seconds for move timeout
            match_timers[new_match_id].start()
            
            logger.info(f"Rematch started: {new_match_id}")
            
            # Notify both players about the new match
            socketio.emit('rematch_started', {
                'match_id': new_match_id,
                'creator_id': new_creator_id,
                'joiner_id': new_joiner_id,
                'stake': new_match.stake
            }, room=match_id)  # Send to old match room
            
            # Then start the match
            socketio.emit('match_started', {
                'match_id': new_match_id,
                'start_time': new_match.started_at.isoformat(),
                'rematch': True
            }, room=new_match_id)  # Send to new match room
    except Exception as e:
        logger.exception("Error in rematch_accepted handler")

@socketio.on('rematch_request')
def on_rematch_request(data):
    try:
        session_id = session.get('session_id')
        match_id = data.get('match_id')
        
        if not session_id or not match_id:
            logger.error(f"Invalid session or match ID in rematch_request: {session_id}, {match_id}")
            return
        
        # Lock the match for update
        match = Match.query.filter_by(id=match_id).with_for_update().first()
        if not match:
            logger.error(f"Match {match_id} not found")
            return
        
        # Check if match is in finished state
        if match.status != 'finished':
            logger.error(f"Match {match_id} not in finished state")
            return
        
        # Check if both players have enough coins
        creator = Player.query.filter_by(session_id=match.creator_id).first()
        joiner = Player.query.filter_by(session_id=match.joiner_id).first()
        
        if not creator or not joiner:
            logger.error(f"Players not found for match {match_id}")
            return
        
        if creator.coins < match.stake or joiner.coins < match.stake:
            logger.error(f"Insufficient coins for rematch in match {match_id}")
            socketio.emit('rematch_declined', {
                'error': 'Insufficient coins'
            }, room=match_id)
            return
        
        # Update player ready state in the current match
        if session_id == match.creator_id:
            match.creator_ready = True
            logger.info(f"Creator {session_id} ready for rematch in match {match_id}")
        else:
            match.joiner_ready = True
            logger.info(f"Joiner {session_id} ready for rematch in match {match_id}")
        db.session.commit()
        
        # Notify others that a player accepted rematch
        socketio.emit('rematch_accepted_by_player', {
            'player': 'creator' if session_id == match.creator_id else 'joiner',
            'match_id': match_id
        }, room=match_id)
        
        # Start a new match only if both players have accepted
        if match.creator_ready and match.joiner_ready:
            logger.info(f"Both players ready for rematch in match {match_id}")
            
            # Create new match with same stake but random creator
            new_creator_id = random.choice([match.creator_id, match.joiner_id])
            new_joiner_id = match.joiner_id if new_creator_id == match.creator_id else match.creator_id
            
            new_match_id = secrets.token_hex(4)
            new_match = Match(
                id=new_match_id,
                creator_id=new_creator_id,
                joiner_id=new_joiner_id,
                stake=match.stake,
                status='playing',  # Start in playing state
                creator_ready=False,  # Reset ready states
                joiner_ready=False,
                started_at=datetime.now(UTC)  # Set start time
            )
            
            # Update player references
            new_creator = Player.query.filter_by(session_id=new_creator_id).first()
            new_joiner = Player.query.filter_by(session_id=new_joiner_id).first()
            new_creator.current_match_id = new_match_id
            new_joiner.current_match_id = new_match_id
            
            db.session.add(new_match)
            db.session.commit()
            
            # Join both players to the new match room
            join_room(new_match_id)
            
            # Set up timer for move timeout
            def handle_timeout():
                with app.app_context():
                    try:
                        handle_match_timeout(new_match_id)
                    except Exception as e:
                        logger.exception(f"Error in match timeout handler for match {new_match_id}")
            
            # Start new timer
            match_timers[new_match_id] = Timer(10, handle_timeout)  # 10 seconds for move timeout
            match_timers[new_match_id].start()
            
            logger.info(f"Rematch started: {new_match_id}")
            
            # First notify about the rematch being accepted
            socketio.emit('rematch_accepted', {
                'match_id': new_match_id,
                'creator_id': new_creator_id,
                'joiner_id': new_joiner_id,
                'stake': new_match.stake
            }, room=match_id)  # Send to old match room
            
            # Then notify about the match starting
            socketio.emit('ready_for_match', {
                'match_id': new_match_id,
                'creator_id': new_creator_id,
                'joiner_id': new_joiner_id,
                'stake': new_match.stake
            }, room=match_id)  # Send to old match room
            
            # Finally start the match
            socketio.emit('match_started', {
                'match_id': new_match_id,
                'start_time': new_match.started_at.isoformat(),
                'rematch': True,
                'creator_id': new_creator_id,
                'joiner_id': new_joiner_id,
                'stake': new_match.stake
            }, room=new_match_id)  # Send to new match room
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
            logger.error(f"Match {match_id} not found")
            return
        
        # Notify others that a player declined rematch
        socketio.emit('rematch_declined', {}, room=match_id)
        logger.info(f"Rematch declined for match {match_id} by {session_id}")
    except Exception as e:
        logger.exception("Error in rematch_declined handler")

@socketio.on('disconnect')
def on_disconnect():
    try:
        session_id = session.get('session_id')
        if not session_id:
            return
        
        player = Player.query.filter_by(session_id=session_id).first()
        if not player or not player.current_match_id:
            return
        
        match = get_match(player.current_match_id)
        if not match:
            return
        
        # If match is in waiting state, clean it up
        if match.status == 'waiting':
            logger.info(f"Player {session_id} disconnected from waiting match {match.id}")
            try:
                if match.creator_id:
                    creator = Player.query.filter_by(session_id=match.creator_id).first()
                    if creator:
                        creator.current_match_id = None
                if match.joiner_id:
                    joiner = Player.query.filter_by(session_id=match.joiner_id).first()
                    if joiner:
                        joiner.current_match_id = None
                db.session.delete(match)
                db.session.commit()
                logger.info(f"Cleaned up match {match.id} after player disconnect")
            except Exception as e:
                logger.exception(f"Error cleaning up match {match.id} after disconnect")
                db.session.rollback()
        
        # If match is in playing state, handle timeout
        elif match.status == 'playing':
            logger.info(f"Player {session_id} disconnected from playing match {match.id}")
            handle_match_timeout(match.id)
    except Exception as e:
        logger.exception("Error handling disconnect")

if __name__ == '__main__':
    socketio.run(app,
                host='0.0.0.0',
                port=int(os.getenv('PORT', 5000)),
                allow_unsafe_werkzeug=True,  # Allow WebSocket connections
                log_output=True,  # Enable logging
                debug=app.config['DEBUG'])