from flask import Flask, render_template, request, jsonify, session
from flask_socketio import SocketIO, emit, join_room, leave_room
import secrets
import os
import random
import time
from datetime import datetime, timezone, timedelta
UTC = timezone.utc
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

# Start periodic cleanup task
def start_cleanup_task():
    """Start a periodic task to clean up stale matches."""
    def run_cleanup():
        while True:
            time.sleep(30)  # Run every 30 seconds
            cleanup_stale_matches()
    
    cleanup_thread = threading.Thread(target=run_cleanup, daemon=True)
    cleanup_thread.start()

# Start the cleanup task
start_cleanup_task()

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
            
            # Find all matches that might be stale
            stale_matches = Match.query.filter(
                Match.status.in_(['playing', 'waiting'])
            ).all()
            
            # Also find matches where one player is missing or inactive
            all_matches = Match.query.all()
            for match in all_matches:
                creator = Player.query.filter_by(session_id=match.creator_id).first()
                joiner = Player.query.filter_by(session_id=match.joiner_id).first() if match.joiner_id else None
                
                # Add to stale matches if:
                # 1. Creator is missing or inactive
                # 2. Joiner is missing or inactive (if match has a joiner)
                # 3. Match is in an inconsistent state
                if (not creator or 
                    (match.joiner_id and not joiner) or
                    (match.status == 'waiting' and match.joiner_id) or
                    (match.status == 'playing' and not match.joiner_id)):
                    if match not in stale_matches:
                        stale_matches.append(match)
            
            # Process each stale match
            for match in stale_matches:
                logger.info(f"Cleaning up stale match {match.id} (status: {match.status})")
                
                try:
                    # For playing matches, handle timeout
                    if match.status == 'playing' and match.started_at:
                        match_time = match.started_at.replace(tzinfo=UTC) if match.started_at.tzinfo is None else match.started_at
                        if match_time < cutoff_time:
                            handle_match_timeout(match.id)
                            continue
                    
                    # For all other cases, clean up the match
                    if match.creator_id:
                        creator = Player.query.filter_by(session_id=match.creator_id).first()
                        if creator and creator.current_match_id == match.id:
                            creator.current_match_id = None
                    
                    if match.joiner_id:
                        joiner = Player.query.filter_by(session_id=match.joiner_id).first()
                        if joiner and joiner.current_match_id == match.id:
                            joiner.current_match_id = None
                    
                    # Delete the match
                    db.session.delete(match)
                    db.session.commit()
                    logger.info(f"Cleaned up match {match.id}")
                    
                except Exception as e:
                    logger.exception(f"Error cleaning up match {match.id}")
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
        
        # Clean up any stale matches
        cleanup_stale_matches()
        
        # Get open matches that:
        # 1. Are in waiting state
        # 2. Are not created by current player
        # 3. Have a creator with enough coins
        # 4. Current player has enough coins to join
        # 5. Creator is still active
        open_matches = []
        available_matches = Match.query.filter_by(status='waiting').all()
        
        for match in available_matches:
            creator = Player.query.filter_by(session_id=match.creator_id).first()
            if (match.creator_id != session_id and 
                creator and creator.coins >= match.stake and
                player.coins >= match.stake and
                not match.joiner_id):  # Ensure no joiner is assigned
                open_matches.append({
                    'id': match.id,
                    'stake': match.stake
                })
        
        # Get current match details if in a match
        current_match = None
        if player.current_match_id:
            match = get_match(player.current_match_id)
            if match:
                # Verify match is valid
                creator = Player.query.filter_by(session_id=match.creator_id).first()
                joiner = Player.query.filter_by(session_id=match.joiner_id).first() if match.joiner_id else None
                
                # Clean up match if it's invalid
                if not creator or (match.joiner_id and not joiner):
                    player.current_match_id = None
                    db.session.delete(match)
                    db.session.commit()
                    match = None
                else:
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
        else:
            match.joiner_move = move
            logger.info(f"Joiner {session_id} made move {move} in match {match.id}")
        
        db.session.commit()
        
        # Notify others that a move was made
        socketio.emit('move_made', {
            'player': 'creator' if session_id == match.creator_id else 'joiner'
        }, room=match.id)
        
        # If both players have moved, calculate and emit result
        if match.creator_move and match.joiner_move:
            calculate_and_emit_result(match.id)
        
        return jsonify({'success': True})
    except Exception as e:
        logger.exception("Error making move")
        return jsonify({'error': 'Internal server error'}), 500

def calculate_and_emit_result(match_id):
    try:
        # Lock the match for update
        match = Match.query.filter_by(id=match_id).with_for_update().first()
        if not match:
            logger.error(f"Match {match_id} not found in result calculation")
            return
        
        # Get player objects
        creator = Player.query.filter_by(session_id=match.creator_id).first()
        joiner = Player.query.filter_by(session_id=match.joiner_id).first()
        
        if not creator or not joiner:
            logger.error(f"Players not found for match {match_id}")
            return
        
        # Store stake for potential rematch
        stake = match.stake
        
        # Calculate winner
        result = calculate_winner(match.creator_move, match.joiner_move)
        
        # Update match status
        match.status = 'finished'
        match.finished_at = datetime.now(UTC)
        match.creator_ready = False  # Reset ready states for rematch
        match.joiner_ready = False
        
        # Keep match references for rematch
        creator.current_match_id = match_id
        joiner.current_match_id = match_id
        
        # Update player stats and coins
        if result == 'draw':
            creator.draws += 1
            joiner.draws += 1
            creator.coins += stake
            joiner.coins += stake
        elif result == 'player1':  # Creator wins
            creator.wins += 1
            joiner.losses += 1
            creator.coins += stake * 2
            creator.total_coins_won += stake
            joiner.total_coins_lost += stake
        else:  # Joiner wins
            creator.losses += 1
            joiner.wins += 1
            joiner.coins += stake * 2
            joiner.total_coins_won += stake
            creator.total_coins_lost += stake
        
        db.session.commit()
        
        # Emit result to both players
        socketio.emit('match_result', {
            'creator_move': match.creator_move,
            'joiner_move': match.joiner_move,
            'result': result,
            'can_rematch': (creator.coins >= stake and joiner.coins >= stake)
        }, room=match_id)
        
        logger.info(f"Match {match_id} finished. Result: {result}")
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
            logger.error(f"Match {match_id} not found")
            return
        
        # Only allow players who are part of the match
        if session_id not in [match.creator_id, match.joiner_id]:
            logger.error(f"Player {session_id} not part of match {match_id}")
            return
        
        join_room(match_id)
        logger.info(f"Player {session_id} joined match room {match_id}")
        
        # If this is a joiner joining a waiting match, start the match
        if match.status == 'waiting' and match.joiner_id == session_id:
            # Start the match
            match.status = 'playing'
            match.started_at = datetime.now(UTC)
            
            # Deduct stakes
            creator = Player.query.filter_by(session_id=match.creator_id).first()
            joiner = Player.query.filter_by(session_id=match.joiner_id).first()
            
            if not creator or not joiner:
                logger.error(f"Players not found for match {match_id}")
                return
            
            creator.coins -= match.stake
            joiner.coins -= match.stake
            db.session.commit()
            
            # Start match timer
            timer = Timer(10, handle_match_timeout, args=[match_id])
            match_timers[match_id] = timer
            timer.start()
            
            # Notify players about match start
            socketio.emit('match_started', {
                'match_id': match_id,
                'start_time': match.started_at.isoformat(),
                'creator_id': match.creator_id,
                'joiner_id': match.joiner_id,
                'stake': match.stake,
                'time_limit': 10
            }, room=match_id)
            
            logger.info(f"Match {match_id} started")
        
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
                creator_ready=False,  # Reset ready states for new match
                joiner_ready=False,
                started_at=datetime.now(UTC)  # Set start time
            )
            
            # Update player references
            new_creator = Player.query.filter_by(session_id=new_creator_id).first()
            new_joiner = Player.query.filter_by(session_id=new_joiner_id).first()
            new_creator.current_match_id = new_match_id
            new_joiner.current_match_id = new_match_id
            
            # Deduct stakes
            new_creator.coins -= match.stake
            new_joiner.coins -= match.stake
            
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
            socketio.emit('match_started', {
                'match_id': new_match_id,
                'creator_id': new_creator_id,
                'joiner_id': new_joiner_id,
                'stake': new_match.stake,
                'rematch': True,
                'time_limit': 10
            }, room=match_id)  # Send to old match room

            # Join both players to the new match room
            socket_id = request.sid
            leave_room(match_id)
            join_room(new_match_id)

            # Notify about match start in the new room
            socketio.emit('match_started', {
                'match_id': new_match_id,
                'creator_id': new_creator_id,
                'joiner_id': new_joiner_id,
                'stake': new_match.stake,
                'rematch': True,
                'time_limit': 10
            }, room=new_match_id)
            
            # Clean up old match
            db.session.delete(match)
            db.session.commit()
            
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
        
        # Reset ready states
        match.creator_ready = False
        match.joiner_ready = False
        db.session.commit()
        
        # Notify others that a player declined rematch
        socketio.emit('rematch_declined', {}, room=match_id)
        logger.info(f"Rematch declined for match {match_id} by {session_id}")
    except Exception as e:
        logger.exception("Error in rematch_declined handler")

@socketio.on('disconnect')
def on_disconnect():
    try:
        session_id = session.get('session_id')
        if session_id:
            # Find any matches this player is part of
            player = Player.query.filter_by(session_id=session_id).first()
            if player and player.current_match_id:
                match = get_match(player.current_match_id)
                if match:
                    # If match is in waiting state, clean it up
                    if match.status == 'waiting':
                        db.session.delete(match)
                    # If match is playing, handle timeout
                    elif match.status == 'playing':
                        handle_match_timeout(match.id)
                    # Reset player's match reference
                    player.current_match_id = None
                    db.session.commit()
        
        logger.info(f"Client disconnected: {session_id}")
    except Exception as e:
        logger.exception("Error handling disconnect")

if __name__ == '__main__':
    socketio.run(app, debug=True, host='0.0.0.0', port=5000)