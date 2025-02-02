from flask import Flask, render_template, request, jsonify, session
from flask_socketio import SocketIO, emit, join_room, leave_room
import secrets
from datetime import datetime

from .config import Config
from .services.match_service import MatchService
from .services.game_service import GameService
from .utils.logger import setup_logger
from .models.database import db, User, GameHistory

# Configure logging
logger = setup_logger()

# Initialize Flask app
app = Flask(__name__)
app.config.from_object(Config)

# Initialize database
db.init_app(app)
with app.app_context():
    try:
        db.create_all()
    except Exception as e:
        print(f"Error creating database tables: {e}")
        # Wait for PostgreSQL to be ready
        import time
        time.sleep(10)
        db.create_all()

# Configure Flask-SocketIO
socketio = SocketIO(
    app,
    async_mode='gevent',
    cors_allowed_origins='*',
    logger=True,
    engineio_logger=True,
    ping_timeout=60,
    ping_interval=25,
    max_http_buffer_size=1000000,
    manage_session=False  # Let Flask manage the sessions
)

# Initialize services
match_service = MatchService()
game_service = GameService()

@app.route('/')
def index():
    if 'session_id' not in session:
        session_id = secrets.token_hex(8)
        session['session_id'] = session_id
        match_service.get_player(session_id)  # Initialize player
        logger.info(f"Created new session: {session_id}")
    return render_template('index.html')

@app.route('/api/state')
def get_state():
    try:
        session_id = session.get('session_id')
        if not session_id:
            session_id = secrets.token_hex(8)
            session['session_id'] = session_id
            logger.info(f"Created new session: {session_id}")

        player = match_service.get_player(session_id)
        open_matches = match_service.get_open_matches(session_id)

        # Get current match details if in a match
        current_match = None
        if player.current_match:
            match = match_service.get_match(player.current_match)
            if match:
                current_match = {
                    'id': player.current_match,
                    'status': match.status,
                    'stake': match.stake,
                    'is_creator': session_id == match.creator
                }

        return jsonify({
            'coins': player.coins,
            'stats': player.stats.to_dict(),
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
        if not session_id:
            logger.error(f"Invalid session: {session_id}")
            return jsonify({'error': 'Invalid session'}), 400

        stake = request.json.get('stake', 0)
        if not isinstance(stake, int) or stake <= 0:
            logger.error(f"Invalid stake: {stake}")
            return jsonify({'error': 'Invalid stake'}), 400

        player = match_service.get_player(session_id)
        if not player.has_enough_coins(stake):
            logger.error(f"Insufficient coins. Has: {player.coins}, Needs: {stake}")
            return jsonify({'error': 'Insufficient coins'}), 400

        # Clear any existing match
        if player.current_match:
            match_service.cleanup_match(player.current_match)

        match = match_service.create_match(session_id, stake)
        logger.info(f"Match created: {match.id} by {session_id}")
        return jsonify({'match_id': match.id})
    except Exception as e:
        logger.exception("Error creating match")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/api/join_match', methods=['POST'])
def join_match():
    try:
        session_id = session.get('session_id')
        if not session_id:
            logger.error(f"Invalid session: {session_id}")
            return jsonify({'error': 'Invalid session'}), 400

        match_id = request.json.get('match_id')
        if not match_id:
            logger.error("No match_id provided")
            return jsonify({'error': 'Match ID required'}), 400

        match = match_service.get_match(match_id)
        if not match:
            logger.error(f"Match not found: {match_id}")
            return jsonify({'error': 'Match not found'}), 400

        if match.status != 'waiting':
            logger.error(f"Match not in waiting state: {match_id} (status: {match.status})")
            return jsonify({'error': 'Match not available'}), 400

        if match.joiner is not None:
            logger.error(f"Match already has a joiner: {match_id}")
            return jsonify({'error': 'Match already has a joiner'}), 400

        if match.creator == session_id:
            logger.error(f"Cannot join own match: {match_id}")
            return jsonify({'error': 'Cannot join own match'}), 400

        player = match_service.get_player(session_id)
        if not player.has_enough_coins(match.stake):
            logger.error(f"Insufficient coins. Has: {player.coins}, Needs: {match.stake}")
            return jsonify({'error': 'Insufficient coins'}), 400

        # Check if creator still has enough coins
        creator = match_service.get_player(match.creator)
        if not creator.has_enough_coins(match.stake):
            logger.error(f"Creator has insufficient coins. Has: {creator.coins}, Needs: {match.stake}")
            return jsonify({'error': 'Creator has insufficient coins'}), 400

        # Clear any existing match
        if player.current_match and player.current_match != match_id:
            match_service.cleanup_match(player.current_match)

        match = match_service.join_match(match_id, session_id)
        if not match:
            logger.error(f"Failed to join match: {match_id}")
            return jsonify({'error': 'Failed to join match'}), 400

        logger.info(f"Player {session_id} joined match {match_id}")
        return jsonify({'success': True})
    except Exception as e:
        logger.exception("Error joining match")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/api/move', methods=['POST'])
def make_move():
    try:
        session_id = session.get('session_id')
        if not session_id:
            logger.error(f"Invalid session: {session_id}")
            return jsonify({'error': 'Invalid session'}), 400

        move = request.json.get('move')
        if move not in ['rock', 'paper', 'scissors']:
            logger.error(f"Invalid move: {move}")
            return jsonify({'error': 'Invalid move'}), 400

        player = match_service.get_player(session_id)
        if not player.current_match:
            logger.error(f"No active match for player {session_id}")
            return jsonify({'error': 'No active match'}), 400

        match = match_service.get_match(player.current_match)
        if not match or match.status != 'playing':
            logger.error(f"Match not in playing state")
            return jsonify({'error': 'Match not in playing state'}), 400

        if not match.make_move(session_id, move):
            logger.error(f"Move already made or invalid player")
            return jsonify({'error': 'Invalid move'}), 400

        # Notify others that a move was made (without revealing the move)
        socketio.emit('move_made', {
            'player': match.get_player_role(session_id),
            'auto': False
        }, room=match.id)

        if match.are_both_moves_made():
            result = game_service.calculate_match_result(match, match_service.players)
            socketio.emit('match_result', result, room=match.id)

        return jsonify({'success': True})
    except Exception as e:
        logger.exception("Error making move")
        return jsonify({'error': 'Internal server error'}), 500

@socketio.on('connect')
def handle_connect():
    try:
        session_id = session.get('session_id')
        if not session_id:
            logger.error("No session ID found")
            return

        join_room(session_id)
        logger.info(f"Socket connected for session {session_id}")

        player = match_service.get_player(session_id)
        if player.current_match:
            match = match_service.get_match(player.current_match)
            if match:
                # Check if the match is still valid for this player
                if match.creator == session_id or match.joiner == session_id:
                    join_room(match.id)
                    logger.info(f"Player {session_id} joined match room {match.id}")
                else:
                    # Clear invalid match reference
                    player.current_match = None
                    logger.warning(f"Cleared invalid match reference for player {session_id}")
    except Exception as e:
        logger.exception("Error in socket connect handler")

@socketio.on('join_match_room')
def on_join_match_room(data):
    try:
        session_id = session.get('session_id')
        match_id = data.get('match_id')

        if not session_id or not match_id:
            logger.error(f"Invalid session or match ID in join_match_room")
            return

        match = match_service.get_match(match_id)
        if not match:
            logger.error(f"Match {match_id} not found")
            return

        if match.status != 'waiting':
            logger.error(f"Match {match_id} not in waiting state (status: {match.status})")
            return

        if match.joiner is not None and match.joiner != session_id:
            logger.error(f"Match {match_id} already has a joiner")
            return

        if match.creator != session_id and match.joiner != session_id:
            logger.error(f"Player {session_id} not part of match {match_id}")
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
            logger.error(f"Invalid session or match ID in ready_for_match")
            return

        match = match_service.get_match(match_id)
        if not match:
            logger.error(f"Match {match_id} not found")
            return

        if match.status != 'waiting':
            logger.error(f"Match {match_id} not in waiting state (status: {match.status})")
            return

        # Check if player is part of the match
        if session_id != match.creator and session_id != match.joiner:
            logger.error(f"Player {session_id} not part of match {match_id}")
            return

        # Check if both players are still connected
        creator = match_service.get_player(match.creator)
        if not creator or creator.current_match != match_id:
            logger.error(f"Creator {match.creator} not connected to match {match_id}")
            return

        joiner = match_service.get_player(match.joiner) if match.joiner else None
        if match.joiner and (not joiner or joiner.current_match != match_id):
            logger.error(f"Joiner {match.joiner} not connected to match {match_id}")
            return

        # Check if both players have enough coins
        if not creator.has_enough_coins(match.stake):
            logger.error(f"Creator has insufficient coins. Has: {creator.coins}, Needs: {match.stake}")
            socketio.emit('match_error', {
                'error': 'Creator has insufficient coins'
            }, room=match_id)
            return

        if joiner and not joiner.has_enough_coins(match.stake):
            logger.error(f"Joiner has insufficient coins. Has: {joiner.coins}, Needs: {match.stake}")
            socketio.emit('match_error', {
                'error': 'Joiner has insufficient coins'
            }, room=match_id)
            return

        # Mark player as ready
        if session_id == match.creator:
            match.creator_ready = True
            logger.info(f"Creator {session_id} ready in match {match_id}")
        elif session_id == match.joiner:
            match.joiner_ready = True
            logger.info(f"Joiner {session_id} ready in match {match_id}")

        # Start match if both players are ready
        if match.creator_ready and match.joiner_ready:
            match.start_match()
            def timeout_handler(match_id):
                with app.app_context():
                    match_service.handle_match_timeout(match_id)
            match.start_timer(Config.MATCH_TIMEOUT, timeout_handler)

            socketio.emit('match_started', {
                'match_id': match_id,
                'start_time': match.start_time
            }, room=match_id)

            logger.info(f"Match {match_id} started")
    except Exception as e:
        logger.exception("Error in ready_for_match handler")

@socketio.on('rematch_accepted')
def on_rematch_accepted(data):
    try:
        session_id = session.get('session_id')
        match_id = data.get('match_id')

        if not session_id or not match_id:
            logger.error(f"Invalid session or match ID in rematch_accepted")
            return

        match = match_service.get_match(match_id)
        if not match:
            logger.error(f"Match {match_id} not found")
            return

        # Check if both players have enough coins
        creator = match_service.get_player(match.creator)
        joiner = match_service.get_player(match.joiner)
        if not creator.has_enough_coins(match.stake) or not joiner.has_enough_coins(match.stake):
            logger.error(f"Insufficient coins for rematch in match {match_id}")
            socketio.emit('rematch_declined', {
                'error': 'Insufficient coins'
            }, room=match_id)
            return

        # Initialize rematch_ready if not exists
        if not hasattr(match, 'rematch_ready'):
            match.rematch_ready = set()

        # Add this player to ready set
        match.rematch_ready.add(session_id)

        # Get player role and notify other player
        player_role = 'creator' if session_id == match.creator else 'joiner'
        other_player_id = match.joiner if session_id == match.creator else match.creator
        
        socketio.emit('rematch_accepted_by_player', {
            'player': player_role
        }, room=other_player_id)

        # Only proceed if both players have accepted
        if len(match.rematch_ready) == 2:
            # Create new match with same stake but keep original creator
            new_match = match_service.create_match(match.creator, match.stake)
            if new_match:
                # Update joiner
                match_service.join_match(new_match.id, match.joiner)

                # Notify both players
                socketio.emit('rematch_started', {
                    'match_id': new_match.id,
                    'is_creator': True,
                    'stake': new_match.stake
                }, room=match.creator)

                socketio.emit('rematch_started', {
                    'match_id': new_match.id,
                    'is_creator': False,
                    'stake': new_match.stake
                }, room=match.joiner)

                logger.info(f"Rematch started: {new_match.id} (original: {match_id})")

                # Join both players to the new match room
                join_room(new_match.id, sid=match.creator)
                join_room(new_match.id, sid=match.joiner)

                # Signal ready for both players
                new_match.creator_ready = True
                new_match.joiner_ready = True

                # Start the match
                new_match.start_match()
                def timeout_handler(match_id):
                    with app.app_context():
                        match_service.handle_match_timeout(match_id)
                new_match.start_timer(Config.MATCH_TIMEOUT, timeout_handler)

                # Notify both players that the match has started
                socketio.emit('match_started', {
                    'match_id': new_match.id,
                    'start_time': new_match.start_time
                }, room=new_match.id)

                # Cleanup old match after everything is set up
                match_service.cleanup_match(match_id)
    except Exception as e:
        logger.exception("Error in rematch_accepted handler")

@socketio.on('rematch_declined')
def on_rematch_declined(data):
    try:
        session_id = session.get('session_id')
        match_id = data.get('match_id')

        if not session_id or not match_id:
            logger.error(f"Invalid session or match ID in rematch_declined")
            return

        match = match_service.get_match(match_id)
        if match:
            socketio.emit('rematch_declined', {}, room=match_id)
            logger.info(f"Rematch declined for match {match_id} by {session_id}")
    except Exception as e:
        logger.exception("Error in rematch_declined handler")

if __name__ == '__main__':
    socketio.run(app, 
                host=Config.HOST,
                port=Config.PORT,
                debug=Config.DEBUG,
                allow_unsafe_werkzeug=True)