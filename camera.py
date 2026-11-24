"""Camera modes and right-drag look offsets for the follow camera."""

import math

from config import CAMERA_MODES


class Camera:
    def __init__(self):
        self.mode_index = 0
        self.position = [0.0, 2.1, -7.0]
        self.target = [0.0, 0.5, -1.3]
        self.look_yaw = 0.0
        self.look_pitch = 0.0
        self.look_dragging = False

    @property
    def mode(self):
        return CAMERA_MODES[self.mode_index]

    def cycle_mode(self):
        self.mode_index = (self.mode_index + 1) % len(CAMERA_MODES)
        if self.mode == "follow":
            self.look_yaw = 0.0
            self.look_pitch = 0.0

    def begin_look(self):
        if self.mode == "follow":
            self.look_dragging = True

    def end_look(self):
        self.look_dragging = False

    def look(self, dx: int, dy: int):
        if self.mode != "follow" or not self.look_dragging:
            return
        self.look_yaw = max(-1.35, min(1.35, self.look_yaw + dx * 0.003))
        self.look_pitch = max(-0.55, min(0.55, self.look_pitch - dy * 0.003))

    def update(self, ball, dt: float):
        if self.mode == "fixed":
            # Keep the overview sightline below the hanging score panel.
            desired = ([0.0, 3.0, -9.0], [0.0, 1.0, 3.4])
        elif self.mode == "result":
            desired = ([0.0, 4.2, 1.8], [0.0, 0.3, 3.4])
        elif self.mode == "scoreboard":
            desired = ([0.0, 4.45, -9.0], [0.0, 4.25, -5.72])
        else:  # orbit around a focus point just ahead of the ball
            if not self.look_dragging:
                recenter = min(1.0, dt * 2.5)
                self.look_yaw += (0.0 - self.look_yaw) * recenter
                self.look_pitch += (0.0 - self.look_pitch) * recenter
            focus = (ball.x * 0.68, 0.62, ball.z + 1.45)
            yaw = self.look_yaw
            pitch = max(-0.2, min(0.95, 0.38 + self.look_pitch))
            distance = 3.8
            horizontal = distance * math.cos(pitch)
            desired = ([focus[0] - math.sin(yaw) * horizontal,
                        focus[1] + math.sin(pitch) * distance,
                        focus[2] - math.cos(yaw) * horizontal],
                       [focus[0], focus[1], focus[2]])
        blend = min(1.0, dt * 3.5)
        for current, goal in zip((self.position, self.target), desired):
            for i in range(3):
                current[i] += (goal[i] - current[i]) * blend
