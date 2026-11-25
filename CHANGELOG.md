# Changelog

## [0.2.0-beta.1] - 2026-11-25

First beta build, following the 0.1.0 alpha.

### Added and changed

- Integrated `bowling_club.glb` as the playable room, aligned its lane and pin deck with the gameplay coordinates, and hid duplicate static pins.
- Added stable IDs and saved home positions for pins. After the first throw, fallen pins are swept away and only standing pins reset for the second throw. Frame transitions and tenth-frame bonus racks still use a fresh rack.
- Suspended the compact 4:3 scoreboard from the ceiling with longer supports while keeping it near the ball holder.
- Adjusted ball and pin lane bounds and narrowed the reset guide path to keep play closer to its own lane.
- Lowered camera views, stopped the follow camera before the pin deck, and kept the camera mode visible in the HUD.
- Kept the procedural room available as a fallback with `USE_CLUB_ROOM_MODEL = False`.

### Known issues and beta checks

- Scoreboard text can overlap: long notifications such as the Turkey message run past the display, and frame marks and totals can collide in their cells.
- Arrow-key aiming is too sensitive. Each press changes aim by 0.04 radians (about 2.3 degrees), so one press can send a shot to the reset guide on the long lane.
- The game is too easy at full power; a straight full-power throw produces strikes too often.
- Ball and reset-guide alignment with the imported room still needs tuning. Wide shots may enter a gutter or appear to follow a neighboring lane's guide.
- The new second-throw pin reset and tighter out-of-bounds pin threshold need a full play-through to confirm pin IDs, pinfall totals, and frame transitions remain correct.
- The 60 FPS target has not been measured consistently on the intended computer and resolution.
- Ball and pin motion use simplified arcade physics rather than full rigid-body simulation.
- Room-model PBR materials are not fully rendered. Shadows are floor contact approximations and do not cast onto the pins, ball, or room.
- The Gobble Gobble achievement is tracked only in-game; it is not connected to an external achievement or trophy platform.

## [0.1.0-alpha] - 2026-11-24

First complete alpha build of the 3D Bowling Game prototype.

### Added

- Title menu for Single Player and Local 2 Players, with keyboard selection and quick-start keys.
- Separate ten-frame scorecards for each player. Local players alternate completed frames for 20 frame-turns.
- Open-frame, spare, and strike scoring, including strike/spare bonuses and tenth-frame fill balls.
- Turkey notification and the in-game Gobble Gobble achievement after three consecutive strikes.
- Perfect-game recognition for a 300-point game.
- Physical overhead score board with one score row in single-player mode and two rows in local multiplayer. Frame columns read left to right; both rolls and the cumulative score appear in the same frame cell.
- Fixed-step ball and pin physics, swept ball-to-pin contact, pin-to-pin motion transfer, pin settling, and configurable out-of-bounds pin limits.
- Curved ball-return guides that route wide shots around the pin deck to the reset zone.
- Follow, fixed, result, and score-board camera views. Right-click drag looks around from follow view; left-click drag controls aim and power.
- FPS and gameplay status HUD.
- Ceiling light fixtures, room lighting, floor contact-shadow approximations, lane target arrows, approach markers, neon wall trim, back-wall plaques, and a ball-return rack.
- Shared floor texture for the room and lane, GLB ball and pin models, and cached static model/HUD drawing.

### Changed

- Left/Right aiming, A/D ball placement, and menu Up/Down now follow screen directions.
- The fixed overview camera sits below the hanging score board's sightline.
- `R` resets the current game and scorecards; `Esc` returns to the title menu.

### Known limitations

- Pin and ball motion use simplified arcade physics rather than a full rigid-body simulation.
- Floor shadows are contact-shadow approximations; full shadow mapping and shadows cast onto other objects are not implemented.
- The Gobble Gobble achievement is tracked in-game and is not connected to an external trophy platform.
- The project targets 60 FPS, but performance has not been formally measured across the intended test hardware.
- Original PBR materials from the GLB assets are not implemented.

### Verification

- Python syntax compilation passed for all 8 Python modules.
- Interactive gameplay, scoring scenarios, and final visual presentation still need a full alpha play-through.






