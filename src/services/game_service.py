import random

class GameService:
    @staticmethod
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

    @staticmethod
    def random_move():
        return random.choice(['rock', 'paper', 'scissors'])

    @staticmethod
    def calculate_match_result(match, players):
        creator_move = match.moves[match.creator]
        joiner_move = match.moves[match.joiner]
        result = GameService.calculate_winner(creator_move, joiner_move)

        # Update match stats
        match.stats.rounds += 1
        if result == 'draw':
            match.stats.draws += 1
            players[match.creator].record_draw()
            players[match.joiner].record_draw()
        elif result == 'player1':
            match.stats.creator_wins += 1
            players[match.creator].record_win()
            players[match.creator].add_coins(match.stake)
            players[match.joiner].record_loss()
            players[match.joiner].add_coins(-match.stake)
        else:
            match.stats.joiner_wins += 1
            players[match.joiner].record_win()
            players[match.joiner].add_coins(match.stake)
            players[match.creator].record_loss()
            players[match.creator].add_coins(-match.stake)

        # Prepare result data
        result_data = {
            'winner': result,
            'creator_move': creator_move,
            'joiner_move': joiner_move,
            'match_stats': match.stats.to_dict(),
            'creator_stats': players[match.creator].stats.to_dict(),
            'joiner_stats': players[match.joiner].stats.to_dict(),
            'stake': match.stake,
            'can_rematch': (players[match.creator].has_enough_coins(match.stake) and 
                          players[match.joiner].has_enough_coins(match.stake))
        }

        match.set_result(result_data)
        return result_data