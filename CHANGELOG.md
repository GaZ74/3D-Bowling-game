# Changelog

## Physics and performance update

### Added

- Fixed-step physics updates to make ball and pin movement less dependent on frame rate.
- Ball-to-pin collision detection that checks the ball's movement between physics steps.
- Pin movement, tipping, damping, settling, and pin-to-pin collision response.
- A visible FPS readout in the game HUD.
- Cached static model geometry and HUD text to reduce repeated drawing work.
- Dark side guide rails with a curved path that routes wide shots around the pin deck and into the reset area.
- A reset pocket at the end of the guide path.

### Changed

- The bowling lane now uses the same `floor.jpg` texture as the room floor.
- The game update loop advances physics in fixed-size steps and limits catch-up work per frame.
- Dependency declarations now include PyOpenGL, Pillow, NumPy, and trimesh.
- README setup and gameplay notes now describe the physics update and controls.

### Notes

- Python syntax and basic center-strike and wide-shot simulations were checked.
- The 60 FPS target has not yet been measured on the target computer. Use the HUD readout during gameplay to check performance.
- Pin and ball motion use simplified arcade-style physics; official bowling scoring remains out of scope for this update.
