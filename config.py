WINDOW_WIDTH = 1100
WINDOW_HEIGHT = 720
WINDOW_TITLE = "3D Bowling Game"
USE_CLUB_ROOM_MODEL = True

# Source-space anchors in bowling_club.glb. The model faces toward decreasing X.
CLUB_BALL_SOURCE_X = 22.5
CLUB_HOLDER_SOURCE_X = 22.2
CLUB_HOLDER_SOURCE_Z = -27.34
CLUB_PIN_HEAD_SOURCE_X = -5.6
CLUB_PIN_CENTER_SOURCE_Z = -26.11
CLUB_LANE_START_SOURCE_X = 30.0
CLUB_FLOOR_SOURCE_Y = -0.02
CLUB_CEILING_Y = 3.55  # bowling_club.glb ceiling top in scene coordinates

# Scene coordinates: X is lane width, Y is height, and Z runs toward the pins.
BALL_START_Z = -4.0
BALL_HOLDER_X = CLUB_HOLDER_SOURCE_Z - CLUB_PIN_CENTER_SOURCE_Z
BALL_HOLDER_Z = BALL_START_Z + CLUB_BALL_SOURCE_X - CLUB_HOLDER_SOURCE_X
LANE_HALF_WIDTH = 1.25
LANE_START_Z = BALL_START_Z - (CLUB_LANE_START_SOURCE_X - CLUB_BALL_SOURCE_X)
PIN_DECK_Z = BALL_START_Z + (CLUB_BALL_SOURCE_X - CLUB_PIN_HEAD_SOURCE_X)
FOLLOW_STOP_FRACTION = 2.0 / 3.0
FOLLOW_STOP_Z = BALL_START_Z + (PIN_DECK_Z - BALL_START_Z) * FOLLOW_STOP_FRACTION
SCOREBOARD_LEFT_ANGLE = 38.0
BALL_RADIUS = 0.22
PIN_SPACING = 0.25
PIN_ROW_DEPTH = 0.19
PIN_ROWS = 4
PIN_RADIUS = 0.11

# Pins crossing these playable-area bounds count as fallen. The lateral limit
# marks the inner gutter edge; the far limit follows the
# physical reset line rather than the curved ball-return guide.
PIN_FALL_X_LIMIT = LANE_HALF_WIDTH - 0.20  # inner gutter edge
PIN_FALL_MIN_Z = LANE_START_Z - PIN_RADIUS
PIN_FALL_MAX_Z = PIN_DECK_Z + 2.0 + PIN_RADIUS

# Fixed-step motion keeps collisions stable even if rendering slows briefly.
PHYSICS_HZ = 120
MAX_PHYSICS_STEPS = 12
BALL_PIN_IMPULSE = 0.58
PIN_PIN_RESTITUTION = 0.35
PIN_LINEAR_DAMPING = 1.7
PIN_ANGULAR_DAMPING = 2.2
PIN_UPRIGHT_STIFFNESS = 1.1
PIN_FALL_ANGLE = 0.92
PIN_MAX_TILT = 1.50
PIN_STOP_SPEED = 0.045

# A wide shot follows the outside guide around the pin deck to a reset pocket.
LANE_BALL_CENTER_LIMIT = LANE_HALF_WIDTH - BALL_RADIUS - 0.20  # extra visual clearance from the model gutter
GUIDE_CENTER_X = LANE_BALL_CENTER_LIMIT  # keep the guided ball center inside this lane
GUIDE_TURN_RADIUS = BALL_RADIUS
PIN_BACK_Z = PIN_DECK_Z + (PIN_ROWS - 1) * PIN_ROW_DEPTH + PIN_RADIUS
GUIDE_TURN_START_Z = PIN_BACK_Z + BALL_RADIUS + 0.25
GUIDE_RESET_X = GUIDE_CENTER_X - GUIDE_TURN_RADIUS
RESET_ZONE_Z = GUIDE_TURN_START_Z + GUIDE_TURN_RADIUS + 0.95
BALL_STOP_Z = RESET_ZONE_Z + 0.35
GUIDE_ALIGNMENT_LENGTH = 0.85
GUIDE_PATH_SAMPLES = 96

FPS = 60
BALL_SPEED_MIN = 5.0
BALL_SPEED_MAX = 12.0
BALL_SPEED_DEFAULT = 8.0
BALL_SPEED_STEP = 0.5
MAX_AIM_ANGLE = 0.65  # radians
MAX_START_X = 0.65
START_X_STEP = 0.12
MAX_BALL_TIME = 2.2

CAMERA_MODES = ("follow", "fixed", "result", "scoreboard")









