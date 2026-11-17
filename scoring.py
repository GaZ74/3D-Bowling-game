"""Scoring extension point for ten-pin bowling."""


class Scorecard:
    def __init__(self):
        self.frames = [[] for _ in range(10)]
        self.current_frame = 0

    def record_roll(self, pins_down: int) -> None:
        """Record a roll and advance the frame when appropriate.

        TODO: implement strike/spare rules, tenth-frame bonus rolls, and
        cumulative scoring. Keep this separate from rendering and physics.
        """
        raise NotImplementedError("Complete standard ten-pin scoring")

    def display_total(self) -> str:
        """Return a compact scoreboard string for the HUD."""
        return "Score: --"
