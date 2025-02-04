import pytest
from src.services.game_service import GameService
from src.models.match import Match
from src.models.player import Player
from src.models.database import User

def test_match_creation(match_service, db):
    # Test match creation with valid stake
    creator_id = "player1"
    stake = 50
    match = match_service.create_match(creator_id, stake)
    
    assert match is not None
    assert match.creator == creator_id
    assert match.stake == stake
    assert match.status == "waiting"
    assert match.joiner is None
    
    # Verify creator's coins were deducted
    creator = User.query.filter_by(username=creator_id).first()
    assert creator.coins == 50  # Initial 100 - stake 50

def test_match_joining(match_service, db):
    # Create initial match
    creator_id = "player1"
    joiner_id = "player2"
    stake = 50
    match = match_service.create_match(creator_id, stake)
    
    # Test joining the match
    joined_match = match_service.join_match(match.id, joiner_id)
    
    assert joined_match is not None
    assert joined_match.joiner == joiner_id
    assert joined_match.stake == stake
    
    # Verify joiner's coins were deducted
    joiner = User.query.filter_by(username=joiner_id).first()
    assert joiner.coins == 50  # Initial 100 - stake 50

def test_match_moves_and_result(match_service, db):
    # Setup match with two players
    creator_id = "player1"
    joiner_id = "player2"
    stake = 50
    match = match_service.create_match(creator_id, stake)
    match = match_service.join_match(match.id, joiner_id)
    
    # Make moves
    match.make_move(creator_id, "rock")
    match.make_move(joiner_id, "scissors")
    
    # Calculate result
    result_data = GameService.calculate_match_result(match, match_service.players)
    
    assert result_data is not None
    assert result_data["winner"] == "player1"
    assert result_data["creator_move"] == "rock"
    assert result_data["joiner_move"] == "scissors"
    
    # Verify coins distribution
    creator = User.query.filter_by(username=creator_id).first()
    joiner = User.query.filter_by(username=joiner_id).first()
    assert creator.coins == 150  # Initial 100 - stake 50 + win 100
    assert joiner.coins == 50  # Initial 100 - stake 50

def test_match_timeout(match_service, db):
    # Setup match with two players
    creator_id = "player1"
    joiner_id = "player2"
    stake = 50
    match = match_service.create_match(creator_id, stake)
    match = match_service.join_match(match.id, joiner_id)
    
    # Start the match
    match.creator_ready = True
    match.joiner_ready = True
    match.start_match()
    match.start_timer(30, match_service.handle_match_timeout)
    
    # Only creator makes a move
    match.make_move(creator_id, "rock")
    
    # Simulate timeout
    match = match_service.handle_match_timeout(match.id)
    
    assert match is not None
    assert match.moves[creator_id] == "rock"
    assert match.moves[joiner_id] in ["rock", "paper", "scissors"]
    assert match.status == "finished"

def test_rematch_request_and_accept(match_service, db):
    # Setup and complete initial match
    creator_id = "player1"
    joiner_id = "player2"
    stake = 50
    match = match_service.create_match(creator_id, stake)
    match = match_service.join_match(match.id, joiner_id)
    match.make_move(creator_id, "rock")
    match.make_move(joiner_id, "scissors")
    GameService.calculate_match_result(match, match_service.players)
    
    # Request rematch
    match.add_rematch_ready(creator_id)
    assert not match.is_rematch_ready()
    
    # Accept rematch
    match.add_rematch_ready(joiner_id)
    assert match.is_rematch_ready()
    
    # Create rematch
    rematch = match_service.create_rematch(match.id)
    
    assert rematch is not None
    assert rematch.creator == creator_id
    assert rematch.joiner == joiner_id
    assert rematch.stake == stake
    assert rematch.status == "playing"

def test_draw_result(match_service, db):
    # Setup match with two players
    creator_id = "player1"
    joiner_id = "player2"
    stake = 50
    match = match_service.create_match(creator_id, stake)
    match = match_service.join_match(match.id, joiner_id)
    
    # Both players choose rock
    match.make_move(creator_id, "rock")
    match.make_move(joiner_id, "rock")
    
    # Calculate result
    result_data = GameService.calculate_match_result(match, match_service.players)
    
    assert result_data is not None
    assert result_data["winner"] == "draw"
    
    # Verify coins are returned in case of draw
    creator = User.query.filter_by(username=creator_id).first()
    joiner = User.query.filter_by(username=joiner_id).first()
    assert creator.coins == 100  # Initial 100 - stake 50 + return 50
    assert joiner.coins == 100  # Initial 100 - stake 50 + return 50

def test_match_cancellation(match_service, db):
    # Create match
    creator_id = "player1"
    stake = 50
    match = match_service.create_match(creator_id, stake)
    
    # Cancel match
    result = match_service.cancel_match(match.id)
    
    assert result is True
    assert match.id not in match_service.matches
    
    # Verify creator's coins were refunded
    creator = User.query.filter_by(username=creator_id).first()
    assert creator.coins == 100  # Initial 100 - stake 50 + refund 50