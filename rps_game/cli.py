"""Command-line interface for the Rock-Paper-Scissors game."""
from __future__ import annotations
import argparse
import sys
from typing import Optional

from .game import VALID_MOVES, play_round, random_move


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(prog="rps", description="Play Rock-Paper-Scissors against the computer.")
    p.add_argument("rounds", type=int, nargs="?", default=1, help="Number of rounds to play (default: 1)")
    return p.parse_args(argv)


def interactive_rounds(rounds: int):
    print(f"Playing {rounds} round(s). Enter 'quit' to exit early.")
    score = {"win": 0, "lose": 0, "draw": 0}
    for i in range(1, rounds + 1):
        while True:
            user = input(f"Round {i} - your move (rock/paper/scissors): ").strip().lower()
            if user == "quit":
                print("Exiting early.")
                return score
            if user in VALID_MOVES:
                break
            print("Invalid move. Try again.")

        player, computer, result = play_round(user, None)
        print(f"You: {player}  Computer: {computer} -> {result.upper()}")
        score[result] += 1

    return score


def main(argv: Optional[list[str]] = None) -> int:
    args = parse_args(argv)
    rounds = args.rounds
    score = interactive_rounds(rounds)
    print("\nFinal score:")
    print(f"Wins: {score['win']}, Losses: {score['lose']}, Draws: {score['draw']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
