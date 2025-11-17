"""Core game logic for Rock-Paper-Scissors."""
from __future__ import annotations
import random
from typing import Literal, Tuple

Move = Literal["rock", "paper", "scissors"]
VALID_MOVES = ("rock", "paper", "scissors")


def random_move() -> Move:
    """Return a random valid move for the computer."""
    return random.choice(VALID_MOVES)  # type: ignore[return-value]


def decide_winner(player: Move, opponent: Move) -> str:
    """Decide the winner for a single round.

    Returns:
      'win' if player beats opponent,
      'lose' if player loses to opponent,
      'draw' if same move.
    """
    player = player.lower()
    opponent = opponent.lower()
    if player == opponent:
        return "draw"

    wins = {
        "rock": "scissors",
        "paper": "rock",
        "scissors": "paper",
    }

    if wins.get(player) == opponent:
        return "win"
    return "lose"


def play_round(player_move: str, opponent_move: str | None = None) -> Tuple[str, str, str]:
    """Play a single round.

    Args:
      player_move: player's move (case-insensitive string)
      opponent_move: if None, the computer will pick a random move.

    Returns a tuple: (player_move, opponent_move, result) where result is 'win'|'lose'|'draw'.
    """
    pm = player_move.lower()
    if pm not in VALID_MOVES:
        raise ValueError(f"invalid move: {player_move!r}. valid moves: {VALID_MOVES}")

    om = opponent_move.lower() if opponent_move is not None else random_move()
    if om not in VALID_MOVES:
        raise ValueError(f"invalid opponent move: {opponent_move!r}. valid: {VALID_MOVES}")

    result = decide_winner(pm, om)
    return pm, om, result


if __name__ == "__main__":
    print("Run the CLI with `python -m rps_game.cli` or import rps_game.game")
