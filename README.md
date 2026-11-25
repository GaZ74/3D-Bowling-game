# 3D Bowling Game

A Python/PyOpenGL ten-pin bowling prototype. The project includes separate GLB ball and pin models, trajectory preview, aiming and power controls, ten-frame scoring with strike/spare bonuses and tenth-frame fill balls, a dynamic camera, a shader that uses the room floor texture on the lane, and curved side-guide routes into a reset area.

The project uses `assets/bowling_club.glb` for the alley, lanes, approach, ball returns, displays, and room decoration. Its orientation and original scale are mapped to the gameplay coordinates; the static pin meshes are replaced by the physics-driven pin rack at the same position. The procedural room remains available by setting `USE_CLUB_ROOM_MODEL = False` in `config.py`. The GLB loader preserves base-color materials and embedded textures. A title menu lets players choose single-player or local two-player mode. The live pinfall score board is fitted onto the model’s center monitor, with one row in single-player mode and two rows in local mode. In local mode, P1 and P2 alternate completed frames for 20 frame-turns. Three consecutive strikes unlock the in-game Gobble Gobble achievement, and a 300 game is recognized as a perfect game. The HUD also shows the current turn, score, controls, and camera information.

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

- Left/Right arrows: aim left/right on screen.
- Up/Down arrows: adjust power.
- A/D: move the ball left/right on screen.
- Title menu: Up/Down to select, Enter to start; `1` and `2` are quick selections.
- Mouse drag: adjust aim and power; release to throw.
- Right-click and drag: look around from the follow camera; release to recenter.
- Space: throw or continue after the pins settle.
- C: cycle follow, fixed, result, and scoreboard camera modes.
- R: reset the game and scorecards.
- Esc: return to the title menu.

## Physics and performance

Ball and pin motion use fixed 1/120-second physics steps. Swept ball-to-pin checks reduce tunneling, pin contacts transfer motion, and damping makes pins settle. Pins that leave the configured lane bounds or cross the far reset line are counted as fallen. Adjust `PIN_FALL_X_LIMIT`, `PIN_FALL_MIN_Z`, and `PIN_FALL_MAX_Z` in `config.py` to tune those limits. A wide shot that crosses a lane boundary follows the curved outside guide around the pin deck to the reset zone. The lane and surrounding floor sample the same `assets/floor.jpg` texture.

Static GLB geometry is compiled into OpenGL display lists and reused. HUD text is also cached between changes. The HUD displays measured render FPS; the project target is 60 FPS, but the achieved rate depends on the test computer and display and still needs to be measured there.

The physics are an arcade approximation, not a full rigid-body simulation. The floor shadows are contact-shadow approximations; full shadow mapping is not implemented. Room rendering supports base-color textures and factors, but does not reproduce advanced PBR channels.

