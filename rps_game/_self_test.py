"""Lightweight self-test runner for environments without pytest."""
from __future__ import annotations
from rps_game import game


def run():
    print("Running lightweight self-tests for rps_game...")
    assert game.decide_winner("rock", "rock") == "draw"
    assert game.decide_winner("paper", "paper") == "draw"
    assert game.decide_winner("rock", "scissors") == "win"
    assert game.decide_winner("paper", "rock") == "win"
    assert game.decide_winner("scissors", "paper") == "win"
    assert game.decide_winner("rock", "paper") == "lose"
    assert game.decide_winner("paper", "scissors") == "lose"
    assert game.decide_winner("scissors", "rock") == "lose"
    try:
        game.play_round("lizard")
        raise SystemExit("Expected ValueError for invalid move but none raised")
    except ValueError:
        pass
    mv = game.random_move()
    assert mv in game.VALID_MOVES
    print("All self-tests passed.")


if __name__ == "__main__":
    run()
