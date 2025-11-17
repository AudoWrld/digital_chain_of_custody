"""Unit tests for rps_game.game"""
from rps_game import game


def test_decide_draw():
    assert game.decide_winner("rock", "rock") == "draw"
    assert game.decide_winner("paper", "paper") == "draw"


def test_decide_win_cases():
    assert game.decide_winner("rock", "scissors") == "win"
    assert game.decide_winner("paper", "rock") == "win"
    assert game.decide_winner("scissors", "paper") == "win"


def test_decide_lose_cases():
    assert game.decide_winner("rock", "paper") == "lose"
    assert game.decide_winner("paper", "scissors") == "lose"
    assert game.decide_winner("scissors", "rock") == "lose"


def test_play_round_invalid_move():
    try:
        game.play_round("lizard")
        assert False, "Expected ValueError for invalid move"
    except ValueError:
        pass


def test_random_move_valid():
    mv = game.random_move()
    assert mv in game.VALID_MOVES
