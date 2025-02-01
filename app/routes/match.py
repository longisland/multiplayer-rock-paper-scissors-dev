from flask import Blueprint, jsonify, request, render_template, redirect, url_for
from flask_socketio import emit, join_room, leave_room
from app.game.match_manager import MatchManager
import uuid

match_bp = Blueprint('match', __name__)

@match_bp.route('/create-match', methods=['POST'])
def create_match():
    player_id = request.cookies.get('player_id')
    if not player_id:
        player_id = str(uuid.uuid4())
    
    match = MatchManager.create_match(player_id)
    response = jsonify({'match_id': match.id})
    response.set_cookie('player_id', player_id)
    return response

@match_bp.route('/open-matches', methods=['GET'])
def get_open_matches():
    matches = MatchManager.get_open_matches()
    return jsonify([match.to_dict() for match in matches])

@match_bp.route('/join-match/<int:match_id>', methods=['POST'])
def join_match(match_id):
    player_id = request.cookies.get('player_id')
    if not player_id:
        player_id = str(uuid.uuid4())
    
    success = MatchManager.join_match(match_id, player_id)
    response = jsonify({'success': success})
    response.set_cookie('player_id', player_id)
    return response

@match_bp.route('/match/<int:match_id>', methods=['GET'])
def get_match_status(match_id):
    match = MatchManager.get_match(match_id)
    if not match:
        return jsonify({'error': 'Match not found'}), 404
    return jsonify(match.to_dict())

def register_socket_events(socketio):
    @socketio.on('join')
    def on_join(data):
        match_id = data.get('match_id')
        if match_id:
            join_room(str(match_id))
            emit('user_joined', {'match_id': match_id}, room=str(match_id))

    @socketio.on('leave')
    def on_leave(data):
        match_id = data.get('match_id')
        if match_id:
            leave_room(str(match_id))
            emit('user_left', {'match_id': match_id}, room=str(match_id))

    @socketio.on('make_move')
    def on_move(data):
        match_id = data.get('match_id')
        player_id = data.get('player_id')
        move = data.get('move')
        
        if match_id and player_id and move:
            success = MatchManager.make_move(match_id, player_id, move)
            if success:
                emit('move_made', {'player_id': player_id}, room=str(match_id))
