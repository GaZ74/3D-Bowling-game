"""PyOpenGL/GLUT application entry point."""

import time
from pathlib import Path

from OpenGL.GL import *
from OpenGL.GLU import gluPerspective
from OpenGL.GLUT import *

from camera import Camera
from config import (BALL_SPEED_MAX, BALL_SPEED_MIN, MAX_AIM_ANGLE, WINDOW_HEIGHT,
                    WINDOW_TITLE, WINDOW_WIDTH)
from game import BowlingGame
from renderer import draw_scene

from model_loader import Model

ASSETS = Path(__file__).parent / "assets"

ball_model = Model(ASSETS / "bowling_ball.glb", target_size=0.44)
pin_model = Model(ASSETS / "bowling_pin.glb", target_size=0.52, anchor="bottom")

game = BowlingGame()
camera = Camera()
last_time = time.perf_counter()
drag_origin = None
drag_aim = 0.0
drag_power = 0.0


def display():
    draw_scene(game, camera, ball_model, pin_model)


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
    if key == GLUT_KEY_LEFT:
        game.change_aim(-1)
    elif key == GLUT_KEY_RIGHT:
        game.change_aim(1)
    elif key == GLUT_KEY_UP:
        game.change_power(1)
    elif key == GLUT_KEY_DOWN:
        game.change_power(-1)


def keyboard(key, _x, _y):
    key = key.decode("utf-8").lower()
    if key == " " and game.phase == "aiming":
        game.throw()
    elif key == " " and game.phase == "result":
        game.next_roll()
    elif key == "c":
        camera.cycle_mode()
    elif key == "r":
        game.reset_frame()
    elif key == "a":
        game.change_start_position(-1)
    elif key == "d":
        game.change_start_position(1)


def mouse(button, state, x, y):
    global drag_origin, drag_aim, drag_power
    if button != GLUT_LEFT_BUTTON:
        return
    if state == GLUT_DOWN and game.phase == "aiming":
        drag_origin = (x, y)
        drag_aim = game.aim
        drag_power = game.power
    elif state == GLUT_UP and drag_origin is not None:
        drag_origin = None
        game.throw()


def mouse_motion(x, y):
    if drag_origin is None or game.phase != "aiming":
        return
    dx = x - drag_origin[0]
    dy = drag_origin[1] - y
    game.aim = max(-MAX_AIM_ANGLE, min(MAX_AIM_ANGLE, drag_aim + dx * 0.003))
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
    glEnable(GL_LIGHTING)
    glEnable(GL_LIGHT0)
    glLightfv(GL_LIGHT0, GL_POSITION, (0.0, 8.0, -1.0, 1.0))
    glLightfv(GL_LIGHT0, GL_DIFFUSE, (1.0, 0.96, 0.86, 1.0))
    glEnable(GL_COLOR_MATERIAL)
    glColorMaterial(GL_FRONT_AND_BACK, GL_AMBIENT_AND_DIFFUSE)
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
