import pytest
from src.models.database import User, GameHistory

def test_match_creation(test_app, match_service):
    # Create session and get initial state
    with test_app.session_transaction() as sess:
        sess['session_id'] = 'player1'
    
    response = test_app.get('/api/state')
    assert response.status_code == 200
    data = response.get_json()
    initial_coins = data['coins']
    
    # Create match
    response = test_app.post('/api/create_match', json={'stake': 10})
    assert response.status_code == 200
    data = response.get_json()
    assert 'match_id' in data
    assert data['coins'] == initial_coins - 10  # Stake deducted
    
    # Verify match exists
    response = test_app.get('/api/state')
    data = response.get_json()
    assert data['current_match'] is not None
    assert data['current_match']['stake'] == 10

def test_join_match(test_app, match_service):
    # Create two players
    with test_app.session_transaction() as sess:
        sess['session_id'] = 'player1'
    
    # Create match
    response = test_app.post('/api/create_match', json={'stake': 10})
    match_id = response.get_json()['match_id']
    
    # Switch to player2
    with test_app.session_transaction() as sess:
        sess['session_id'] = 'player2'
    
    # Join match
    response = test_app.post('/api/join_match', json={'match_id': match_id})
    assert response.status_code == 200
    
    # Verify both players in match
    response = test_app.get('/api/state')
    data = response.get_json()
    assert data['current_match']['id'] == match_id

def test_match_moves_and_result(test_app, socket_client, match_service):
    # Create match with player1
    with test_app.session_transaction() as sess:
        sess['session_id'] = 'player1'
    response = test_app.post('/api/create_match', json={'stake': 10})
    match_id = response.get_json()['match_id']
    
    # Join with player2
    with test_app.session_transaction() as sess:
        sess['session_id'] = 'player2'
    test_app.post('/api/join_match', json={'match_id': match_id})
    
    # Connect both players to socket
    socket_client1 = socket_client
    socket_client2 = socket_client
    
    # Signal ready for both players
    socket_client1.emit('ready_for_match', {'match_id': match_id})
    socket_client2.emit('ready_for_match', {'match_id': match_id})
    
    # Make moves
    with test_app.session_transaction() as sess:
        sess['session_id'] = 'player1'
    response = test_app.post('/api/move', json={'move': 'rock'})
    assert response.status_code == 200
    
    with test_app.session_transaction() as sess:
        sess['session_id'] = 'player2'
    response = test_app.post('/api/move', json={'move': 'scissors'})
    assert response.status_code == 200
    
    # Verify match result
    match = match_service.get_match(match_id)
    assert match.moves['player1'] == 'rock'
    assert match.moves['player2'] == 'scissors'

def test_match_timeout(test_app, socket_client, match_service):
    # Create match with player1
    with test_app.session_transaction() as sess:
        sess['session_id'] = 'player1'
    response = test_app.post('/api/create_match', json={'stake': 10})
    match_id = response.get_json()['match_id']
    
    # Join with player2
    with test_app.session_transaction() as sess:
        sess['session_id'] = 'player2'
    test_app.post('/api/join_match', json={'match_id': match_id})
    
    # Connect both players and start match
    socket_client1 = socket_client
    socket_client2 = socket_client
    socket_client1.emit('ready_for_match', {'match_id': match_id})
    socket_client2.emit('ready_for_match', {'match_id': match_id})
    
    # Only player1 makes a move
    with test_app.session_transaction() as sess:
        sess['session_id'] = 'player1'
    test_app.post('/api/move', json={'move': 'rock'})
    
    # Simulate timeout
    match = match_service.get_match(match_id)
    match_service.handle_match_timeout(match_id)
    
    # Verify auto-selection for player2
    match = match_service.get_match(match_id)
    assert match.moves['player1'] == 'rock'
    assert match.moves['player2'] is not None  # Auto-selected move

def test_rematch_system(test_app, socket_client, match_service):
    # Create and complete a match first
    with test_app.session_transaction() as sess:
        sess['session_id'] = 'player1'
    response = test_app.post('/api/create_match', json={'stake': 10})
    match_id = response.get_json()['match_id']
    
    with test_app.session_transaction() as sess:
        sess['session_id'] = 'player2'
    test_app.post('/api/join_match', json={'match_id': match_id})
    
    # Connect both players and start match
    socket_client1 = socket_client
    socket_client2 = socket_client
    socket_client1.emit('ready_for_match', {'match_id': match_id})
    socket_client2.emit('ready_for_match', {'match_id': match_id})
    
    # Complete the match
    with test_app.session_transaction() as sess:
        sess['session_id'] = 'player1'
    test_app.post('/api/move', json={'move': 'rock'})
    
    with test_app.session_transaction() as sess:
        sess['session_id'] = 'player2'
    test_app.post('/api/move', json={'move': 'scissors'})
    
    # Request rematch
    socket_client1.emit('rematch_accepted', {'match_id': match_id})
    socket_client2.emit('rematch_accepted', {'match_id': match_id})
    
    # Verify new match created
    match = match_service.get_match(match_id)
    assert match is None  # Old match cleaned up
    
    # Get state for both players to verify new match
    with test_app.session_transaction() as sess:
        sess['session_id'] = 'player1'
    response = test_app.get('/api/state')
    data = response.get_json()
    assert data['current_match'] is not None
    new_match_id = data['current_match']['id']
    
    with test_app.session_transaction() as sess:
        sess['session_id'] = 'player2'
    response = test_app.get('/api/state')
    data = response.get_json()
    assert data['current_match']['id'] == new_match_id