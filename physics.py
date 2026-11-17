"""Starter motion and trajectory helpers (world units, seconds, radians)."""

import math

from config import BALL_START_Z, MAX_BALL_TIME, PIN_DECK_Z


def predict_trajectory(aim_angle: float, speed: float, start_x: float = 0.0,
                       samples: int = 36):
    """Return a list of (x, y, z) points for the preview line.

    The starter uses a straight, constant-speed path. Add spin/curve only if
    there is time after the required features are complete.
    """
    points = []
    duration = min(MAX_BALL_TIME, (PIN_DECK_Z - BALL_START_Z) / max(speed, 0.1))
    for index in range(samples + 1):
        t = duration * index / samples
        points.append((start_x + math.sin(aim_angle) * speed * t, 0.08,
                       BALL_START_Z + math.cos(aim_angle) * speed * t))
    return points


def advance_ball(ball, dt: float) -> bool:
    """Advance a thrown ball; return True when it reaches the pin deck."""
    ball.x += ball.vx * dt
    ball.z += ball.vz * dt
    return ball.z >= PIN_DECK_Z


def apply_starter_pin_hits(ball, pins) -> int:
    """Mark pins near the ball's path as down; replace with better collision tests."""
    knocked = 0
    for pin in pins:
        if not pin.down and abs(pin.x - ball.x) < 0.36 and abs(pin.z - ball.z) < 0.52:
            pin.down = True
            knocked += 1
    return knocked
