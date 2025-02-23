import pytest
from src.services.game_service import GameService
from src.models.database import User

def test_win_calculation(game_service, db_session):
    # Create test users
    player1 = User(session_id='player1', coins=100)
    player2 = User(session_id='player2', coins=100)
    db_session.add(player1)
    db_session.add(player2)
    db_session.commit()
    
    # Test all winning combinations
    test_cases = [
        ('rock', 'scissors', 'player1'),
        ('scissors', 'paper', 'player1'),
        ('paper', 'rock', 'player1'),
        ('scissors', 'rock', 'player2'),
        ('paper', 'scissors', 'player2'),
        ('rock', 'paper', 'player2'),
        ('rock', 'rock', None),
        ('paper', 'paper', None),
        ('scissors', 'scissors', None)
    ]
    
    for p1_move, p2_move, expected_winner in test_cases:
        class MockMatch:
            def __init__(self):
                self.creator = 'player1'
                self.joiner = 'player2'
                self.stake = 10
                self.moves = {'player1': p1_move, 'player2': p2_move}
        
        mock_match = MockMatch()
        players = {'player1': player1, 'player2': player2}
        
        result = game_service.calculate_match_result(mock_match, players)
        
        if expected_winner:
            assert result['winner'] == expected_winner
        else:
            assert result['winner'] is None  # Draw

def test_auto_selection(game_service, db_session):
    # Create test users
    player1 = User(session_id='player1', coins=100)
    player2 = User(session_id='player2', coins=100)
    db_session.add(player1)
    db_session.add(player2)
    db_session.commit()
    
    class MockMatch:
        def __init__(self):
            self.creator = 'player1'
            self.joiner = 'player2'
            self.stake = 10
            self.moves = {'player1': 'rock', 'player2': None}
            
        def make_move(self, player_id, move):
            self.moves[player_id] = move
            return True
    
    mock_match = MockMatch()
    players = {'player1': player1, 'player2': player2}
    
    # Test auto-selection for player2
    game_service.handle_timeout(mock_match, players)
    assert mock_match.moves['player2'] is not None
    
def test_rematch_stake_handling(game_service, db_session):
    # Create test users with initial coins
    player1 = User(session_id='player1', coins=100)
    player2 = User(session_id='player2', coins=100)
    db_session.add(player1)
    db_session.add(player2)
    db_session.commit()
    
    class MockMatch:
        def __init__(self):
            self.creator = 'player1'
            self.joiner = 'player2'
            self.stake = 10
            self.moves = {'player1': 'rock', 'player2': 'scissors'}
    
    mock_match = MockMatch()
    players = {'player1': player1, 'player2': player2}
    
    # Calculate initial match result
    result = game_service.calculate_match_result(mock_match, players)
    
    # Verify coins updated correctly
    assert player1.coins == 110  # Won the stake
    assert player2.coins == 90   # Lost the stake
    
    # Verify both players can still afford rematch
    assert player1.coins >= mock_match.stake
    assert player2.coins >= mock_match.stake