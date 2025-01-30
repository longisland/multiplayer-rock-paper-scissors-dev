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
    """Clean up matches that have been stuck in 'playing' state for too long."""
    try:
        with app.app_context():
            # Find matches that have been in 'playing' state for more than 30 seconds
            stale_matches = Match.query.filter_by(status='playing').filter(
                Match.started_at < datetime.now(UTC) - timedelta(seconds=30)
            ).all()
            
            for match in stale_matches:
                logger.info(f"Cleaning up stale match {match.id}")
                handle_match_timeout(match.id)
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
        
        match = get_match(player.current_match_id)
        if not match:
            logger.error(f"No active match for player {session_id}")
            return jsonify({'error': 'No active match'}), 400
        
        # Check if match is too old (more than 10 seconds)
        if match.started_at and match.started_at < datetime.now(UTC) - timedelta(seconds=10):
            logger.error(f"Match {match.id} has timed out")
            handle_match_timeout(match.id)
            return jsonify({'error': 'Match has timed out. Random moves were assigned.'}), 400
        
        if match.status != 'playing':
            logger.error(f"Match {match.id} not in playing state. Status: {match.status}")
            return jsonify({'error': 'Match not in playing state'}), 400
        
        # Check if player already made a move
        if (session_id == match.creator_id and match.creator_move) or \
           (session_id == match.joiner_id and match.joiner_move):
            logger.error(f"Player {session_id} already made a move in match {match.id}")
            return jsonify({'error': 'Move already made'}), 400
        
        # Record the move
        try:
            # Lock the match for update
            match = Match.query.filter_by(id=match.id).with_for_update().first()
            if not match:
                logger.error(f"Match {match.id} disappeared during move")
                return jsonify({'error': 'Match not found'}), 400
            
            # Check match state again after lock
            if match.status != 'playing':
                logger.error(f"Match {match.id} not in playing state after lock. Status: {match.status}")
                return jsonify({'error': 'Match not in playing state'}), 400
            
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
    
    # Clear current match references
    creator.current_match_id = None
    joiner.current_match_id = None
    
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
        
        if match.status != 'waiting':
            logger.error(f"Match {match_id} not in waiting state. Status: {match.status}")
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
                'start_time': match.started_at.isoformat()
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
        
        match = get_match(match_id)
        if not match:
            logger.error(f"Match {match_id} not found")
            return
        
        creator = Player.query.filter_by(session_id=match.creator_id).first()
        joiner = Player.query.filter_by(session_id=match.joiner_id).first()
        
        if not creator or not joiner:
            logger.error(f"Players not found for match {match_id}")
            return
        
        # Check if both players have enough coins
        if creator.coins < match.stake or joiner.coins < match.stake:
            logger.error(f"Insufficient coins for rematch in match {match_id}")
            socketio.emit('rematch_declined', {
                'error': 'Insufficient coins'
            }, room=match_id)
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
            creator_ready=True  # Creator is automatically ready
        )
        
        # Update player references
        new_creator = Player.query.filter_by(session_id=new_creator_id).first()
        new_joiner = Player.query.filter_by(session_id=new_joiner_id).first()
        new_creator.current_match_id = new_match_id
        new_joiner.current_match_id = new_match_id
        
        db.session.add(new_match)
        db.session.commit()
        
        # Notify players about the new match
        socketio.emit('rematch_created', {
            'match_id': new_match_id,
            'creator_id': new_creator_id
        }, room=match_id)
        
        logger.info(f"Rematch created: {new_match_id} from match {match_id}")
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

if __name__ == '__main__':
    socketio.run(app,
                host='0.0.0.0',
                port=int(os.getenv('PORT', 5000)),
                allow_unsafe_werkzeug=True,  # Allow WebSocket connections
                log_output=True,  # Enable logging
                debug=app.config['DEBUG'])