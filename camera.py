"""Simple camera mode selection and smooth position interpolation."""

from config import CAMERA_MODES


class Camera:
    def __init__(self):
        self.mode_index = 0
        self.position = [0.0, 4.0, -7.5]
        self.target = [0.0, 0.5, 1.0]

    @property
    def mode(self):
        return CAMERA_MODES[self.mode_index]

    def cycle_mode(self):
        self.mode_index = (self.mode_index + 1) % len(CAMERA_MODES)

    def update(self, ball, dt: float):
        if self.mode == "fixed":
            desired = ([0.0, 5.5, -8.0], [0.0, 0.4, 1.8])
        elif self.mode == "result":
            desired = ([0.0, 4.2, 1.8], [0.0, 0.3, 3.4])
        else:  # follow view keeps the moving ball in frame
            desired = ([ball.x * 0.45, 3.8, ball.z - 4.3],
                       [ball.x * 0.7, 0.35, ball.z + 1.4])
        blend = min(1.0, dt * 3.5)
        for current, goal in zip((self.position, self.target), desired):
            for i in range(3):
                current[i] += (goal[i] - current[i]) * blend
