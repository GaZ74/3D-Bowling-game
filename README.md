# 3D Bowling Game

A Python/PyOpenGL ten-pin bowling prototype. The project includes separate GLB ball and pin models, trajectory preview, aiming and power controls, two-roll frames, a dynamic camera, a shader that uses the room floor texture on the lane, and curved side-guide routes into a reset area.

## Run on Windows

Install Python 3.10 or newer and a GLUT/FreeGLUT runtime. FreeGLUT is a native Windows dependency and is not installed by pip; its DLL must be available on `PATH`.

From this project folder, run `setup_venv.bat` or `setup_venv.ps1`. Then launch with:

```powershell
.\.venv\Scripts\python.exe .\main.py
```

To install manually instead:

```powershell
py -m venv .venv
& .\.venv\Scripts\python.exe -m pip install --upgrade pip
& .\.venv\Scripts\python.exe -m pip install -r .\requirements.txt
& .\.venv\Scripts\python.exe .\main.py
```

## Controls

- Left/Right arrows: aim.
- Up/Down arrows: adjust power.
- A/D: move the starting position.
- Mouse drag: adjust aim and power; release to throw.
- Space: throw or continue after the pins settle.
- C: cycle camera mode.
- R: reset the frame.

## Physics and performance

Ball and pin motion use fixed 1/120-second physics steps. Swept ball-to-pin checks reduce tunneling, pin contacts transfer motion, and damping makes pins settle. A wide shot that crosses a lane boundary follows the curved outside guide around the pin deck to the reset zone. The lane and surrounding floor sample the same `assets/floor.jpg` texture.

Static GLB geometry is compiled into OpenGL display lists and reused. HUD text is also cached between changes. The HUD displays measured render FPS; the project target is 60 FPS, but the achieved rate depends on the test computer and display and still needs to be measured there.

The physics are an arcade approximation, not a full rigid-body simulation. Official strike/spare scoring and the GLB models' original PBR materials are not implemented yet.

