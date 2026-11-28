"""PyOpenGL/GLUT application entry point."""

import time
from pathlib import Path

from OpenGL.GL import *
from OpenGL.GLU import gluPerspective
from OpenGL.GLUT import *

from camera import Camera
from config import (BALL_SPEED_MAX, BALL_SPEED_MIN, MAX_AIM_ANGLE, WINDOW_HEIGHT,
                    CAMERA_MODES, USE_CLUB_ROOM_MODEL, WINDOW_TITLE, WINDOW_WIDTH)
from game import BowlingGame
from renderer import (BULB_LIGHT_POSITIONS, GRAFFITI_LIGHT_POSITIONS,
                      draw_scene)

from model_loader import Model

ASSETS = Path(__file__).parent / "assets"

ball_model = Model(ASSETS / "bowling_ball.glb", target_size=0.44)
pin_model = Model(ASSETS / "bowling_pin.glb", target_size=0.52, anchor="bottom")
room_model = None
if USE_CLUB_ROOM_MODEL:
    try:
        room_model = Model(ASSETS / "bowling_club.glb", target_size=1.0,
                                                    use_materials=True,
                           exclude_name_tokens=("Bowling_pin",))
    except Exception as exc:
        print(f"Club room model unavailable; using procedural room: {exc}")

game = BowlingGame()
camera = Camera()
last_time = time.perf_counter()
drag_origin = None
drag_aim = 0.0
drag_power = 0.0
dragging_look = False


def display():
    draw_scene(game, camera, ball_model, pin_model, room_model)


def update(_value=0):
    global last_time
    now = time.perf_counter()
    dt = min(now - last_time, 0.05)
    last_time = now
    game.update(dt)
    camera.update(game.ball, dt)
    glutPostRedisplay()
    glutTimerFunc(16, update, 0)


def special_key(key, _x, _y):
    if game.phase == "menu":
        if key == GLUT_KEY_UP:
            game.move_menu_selection(-1)
        elif key == GLUT_KEY_DOWN:
            game.move_menu_selection(1)
        return
    if key == GLUT_KEY_LEFT:
        game.change_aim(1)
    elif key == GLUT_KEY_RIGHT:
        game.change_aim(-1)
    elif key == GLUT_KEY_UP:
        game.change_power(1)
    elif key == GLUT_KEY_DOWN:
        game.change_power(-1)


def keyboard(key, _x, _y):
    key = key.decode("utf-8").lower()
    if game.phase == "menu":
        if key in ("\r", "\n"):
            game.start_game(game.menu_selection)
        elif key == "1":
            game.start_game(1)
        elif key == "2":
            game.start_game(2)
        elif key == "\x1b":
            return
        return
    if key == "\x1b":
        game.return_to_menu()
        return
    if key == " " and game.phase == "aiming":
        game.throw()
    elif key == " " and game.phase == "result":
        game.next_roll()
    elif key == "c":
        camera.cycle_mode()
    elif key in ("1", "2", "3", "4"):
        camera.set_mode(CAMERA_MODES[int(key) - 1])
    elif key == "r":
        game.reset_frame()
    elif key == "a":
        game.change_start_position(1)
    elif key == "d":
        game.change_start_position(-1)


def mouse(button, state, x, y):
    global drag_origin, drag_aim, drag_power, dragging_look
    if button == GLUT_RIGHT_BUTTON and state == GLUT_DOWN and camera.mode == "follow":
        drag_origin = (x, y)
        dragging_look = True
        camera.begin_look()
    elif button == GLUT_RIGHT_BUTTON and state == GLUT_UP:
        dragging_look = False
        camera.end_look()
        drag_origin = None
    elif button == GLUT_LEFT_BUTTON and state == GLUT_DOWN and game.phase == "aiming":
        dragging_look = False
        camera.end_look()
        drag_origin = (x, y)
        drag_aim = game.aim
        drag_power = game.power
    elif button == GLUT_LEFT_BUTTON and state == GLUT_UP and drag_origin is not None:
        was_looking = dragging_look
        drag_origin = None
        if not was_looking:
            game.throw()


def mouse_motion(x, y):
    global drag_origin
    if drag_origin is None:
        return
    if dragging_look:
        dx = x - drag_origin[0]
        dy = y - drag_origin[1]
        camera.look(dx, dy)
        drag_origin = (x, y)
        return
    if game.phase != "aiming":
        return
    dx = x - drag_origin[0]
    dy = drag_origin[1] - y
    game.aim = max(-MAX_AIM_ANGLE, min(MAX_AIM_ANGLE, drag_aim - dx * 0.003))
    game.power = max(BALL_SPEED_MIN, min(BALL_SPEED_MAX, drag_power + dy * 0.025))


def reshape(width, height):
    height = max(height, 1)
    glViewport(0, 0, width, height)
    glMatrixMode(GL_PROJECTION)
    glLoadIdentity()
    gluPerspective(55.0, width / height, 0.1, 100.0)
    glMatrixMode(GL_MODELVIEW)


def main():
    glutInit()
    glutInitDisplayMode(GLUT_DOUBLE | GLUT_RGB | GLUT_DEPTH)
    glutInitWindowSize(WINDOW_WIDTH, WINDOW_HEIGHT)
    glutCreateWindow(WINDOW_TITLE.encode("utf-8"))
    glClearColor(0.055, 0.07, 0.11, 1.0)
    glEnable(GL_DEPTH_TEST)
    glEnable(GL_NORMALIZE)
    glEnable(GL_LIGHTING)
    light_positions = BULB_LIGHT_POSITIONS
    for index, position in enumerate(light_positions):
        light = GL_LIGHT0 + index
        glEnable(light)
        glLightfv(light, GL_POSITION, position)
        glLightfv(light, GL_DIFFUSE, (0.46, 0.43, 0.36, 1.0))
        glLightfv(light, GL_AMBIENT, (0.035, 0.035, 0.035, 1.0))
        glLightf(light, GL_CONSTANT_ATTENUATION, 0.8)
        glLightf(light, GL_LINEAR_ATTENUATION, 0.025)
    if room_model is not None:
        graffiti_light_start = GL_LIGHT0 + len(light_positions)
        for index, position in enumerate(GRAFFITI_LIGHT_POSITIONS):
            light = graffiti_light_start + index
            glEnable(light)
            glLightfv(light, GL_POSITION, position)
            glLightfv(light, GL_DIFFUSE, (0.3, 0.3, 0.3, 1.0))
            glLightfv(light, GL_AMBIENT, (0.0, 0.0, 0.0, 1.0))
            glLightfv(light, GL_SPECULAR, (0.0, 0.0, 0.0, 1.0))
            glLightf(light, GL_CONSTANT_ATTENUATION, 1.0)
            glLightf(light, GL_LINEAR_ATTENUATION, 0.02)
            glLightf(light, GL_QUADRATIC_ATTENUATION, 0.001)
            glLightf(light, GL_SPOT_CUTOFF, 78.0)
            glLightf(light, GL_SPOT_EXPONENT, 5.0)
    glEnable(GL_COLOR_MATERIAL)
    glColorMaterial(GL_FRONT_AND_BACK, GL_AMBIENT_AND_DIFFUSE)
    glMaterialfv(GL_FRONT_AND_BACK, GL_SPECULAR, (0.28, 0.28, 0.28, 1.0))
    glMaterialf(GL_FRONT_AND_BACK, GL_SHININESS, 28.0)
    if room_model is not None:
        room_model.prepare()
    glutDisplayFunc(display)
    glutReshapeFunc(reshape)
    glutSpecialFunc(special_key)
    glutKeyboardFunc(keyboard)
    glutMouseFunc(mouse)
    glutMotionFunc(mouse_motion)
    glutTimerFunc(16, update, 0)
    glutMainLoop()


if __name__ == "__main__":
    main()
