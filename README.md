# 3D Bowling Game

A small Python/PyOpenGL starter structure for the accepted Computer Graphics project proposal. It keeps the original features (lane, ten pins, aiming and throwing, simple physics, scoring, lighting, and an on-screen display) and includes trajectory prediction, a second throw with pin reset, a dynamic camera, a short pre-throw setup, a mouse release gesture, and a procedural lane shader.

## Run

Install Python 3.10 or newer and a GLUT/FreeGLUT runtime. On Windows, make sure the FreeGLUT DLL is available on `PATH` (or beside `python.exe`). The Python packages can then be installed in a virtual environment:

```bash
py -m venv .venv
.venv\Scripts\activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python main.py
```

You can also run `setup_venv.bat` from Command Prompt or `setup_venv.ps1` from PowerShell. These scripts create `.venv` and install the Python packages. A virtual environment is created with Python's `venv` module; pip installs packages into it, rather than installing the environment itself.

`requirements.txt` contains PyOpenGL and its optional acceleration package. FreeGLUT is a native system runtime, so pip cannot install it. If the window fails to start with a GLUT/DLL error, install a Windows FreeGLUT runtime and ensure its DLL directory is on `PATH`.

Controls: Left/Right arrows aim, Up/Down arrows change power, A/D choose a starting position, Space throws, C changes camera mode, and R resets the frame. Or click and drag horizontally to set aim, drag upward/downward to adjust power, then release to throw.

This is an intentionally small scaffold. Collision response and official ten-pin scoring are marked as extension points; they are not full simulations yet. The mouse gesture is a simple input shortcut rather than a character animation.

#Alpha test issue:
Game executed successfully but having performance issue
Collision physics still in development
