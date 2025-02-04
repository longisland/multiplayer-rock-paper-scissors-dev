import pytest
from src.services.game_service import GameService
from src.models.database import User

def test_betting_distribution_win(match_service, db):
    # Setup match with two players
    creator_id = "player1"
    joiner_id = "player2"
    stake = 50
    
    # Create match and join
    match = match_service.create_match(creator_id, stake)
    match = match_service.join_match(match.id, joiner_id)
    
    # Start the match
    match.creator_ready = True
    match.joiner_ready = True
    match.start_match()
    
    # Make moves where creator wins
    match.make_move(creator_id, "rock")
    match.make_move(joiner_id, "scissors")
    
    # Calculate result
    result_data = GameService.calculate_match_result(match, match_service.players)
    
    # Verify final coin distribution
    creator = User.query.filter_by(username=creator_id).first()
    joiner = User.query.filter_by(username=joiner_id).first()
    
    assert creator.coins == 150  # Initial 100 - stake 50 + win 100
    assert joiner.coins == 50  # Initial 100 - stake 50
    assert creator.total_coins_won == stake
    assert joiner.total_coins_lost == stake

def test_betting_distribution_draw(match_service, db):
    # Setup match with two players
    creator_id = "player1"
    joiner_id = "player2"
    stake = 50
    
    # Create match and join
    match = match_service.create_match(creator_id, stake)
    match = match_service.join_match(match.id, joiner_id)
    
    # Start the match
    match.creator_ready = True
    match.joiner_ready = True
    match.start_match()
    
    # Make moves for a draw
    match.make_move(creator_id, "rock")
    match.make_move(joiner_id, "rock")
    
    # Calculate result
    result_data = GameService.calculate_match_result(match, match_service.players)
    
    # Verify coins are returned in draw
    creator = User.query.filter_by(username=creator_id).first()
    joiner = User.query.filter_by(username=joiner_id).first()
    
    assert creator.coins == 100  # Initial 100 - stake 50 + return 50
    assert joiner.coins == 100  # Initial 100 - stake 50 + return 50
    assert creator.total_coins_won == 0
    assert joiner.total_coins_won == 0

def test_betting_limits(match_service, db):
    creator_id = "player1"
    
    # Test minimum bet
    min_stake = 1
    match = match_service.create_match(creator_id, min_stake)
    assert match is not None
    
    # Test maximum bet (should be limited by player's coins)
    creator = User.query.filter_by(username=creator_id).first()
    max_stake = creator.coins + 1
    match = match_service.create_match(creator_id, max_stake)
    assert match is None  # Should fail as stake exceeds available coins

def test_consecutive_matches_betting(match_service, db):
    creator_id = "player1"
    joiner_id = "player2"
    stake = 50
    
    # First match
    match1 = match_service.create_match(creator_id, stake)
    match1 = match_service.join_match(match1.id, joiner_id)
    match1.make_move(creator_id, "rock")
    match1.make_move(joiner_id, "scissors")
    GameService.calculate_match_result(match1, match_service.players)
    
    # Record intermediate coins
    creator_mid = User.query.filter_by(username=creator_id).first().coins
    joiner_mid = User.query.filter_by(username=joiner_id).first().coins
    
    # Second match with same stake
    match2 = match_service.create_match(creator_id, stake)
    match2 = match_service.join_match(match2.id, joiner_id)
    match2.make_move(creator_id, "paper")
    match2.make_move(joiner_id, "rock")
    GameService.calculate_match_result(match2, match_service.players)
    
    # Verify final coins
    creator = User.query.filter_by(username=creator_id).first()
    joiner = User.query.filter_by(username=joiner_id).first()
    
    # Creator won both matches
    assert creator.coins == creator_mid + stake
    assert joiner.coins == joiner_mid - stake
    assert creator.total_coins_won == stake * 2
    assert joiner.total_coins_lost == stake * 2

def test_rematch_betting(match_service, db):
    creator_id = "player1"
    joiner_id = "player2"
    stake = 50
    
    # Initial match
    match = match_service.create_match(creator_id, stake)
    match = match_service.join_match(match.id, joiner_id)
    match.make_move(creator_id, "rock")
    match.make_move(joiner_id, "scissors")
    GameService.calculate_match_result(match, match_service.players)
    
    # Request and accept rematch
    match.add_rematch_ready(creator_id)
    match.add_rematch_ready(joiner_id)
    
    # Create rematch
    rematch = match_service.create_rematch(match.id)
    
    # Verify stakes are correctly deducted for rematch
    creator = User.query.filter_by(username=creator_id).first()
    joiner = User.query.filter_by(username=joiner_id).first()
    
    assert creator.coins == 150 - stake  # Won first match (150) - new stake
    assert joiner.coins == 50 - stake  # Lost first match (50) - new stake