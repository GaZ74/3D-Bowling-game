# Next Patch TODO: Physics and Performance

This patch focuses on frame rate and bowling physics. Gameplay polish, model-material work, and other features are deferred until these priorities are complete.

## Priority 1: Reach the 60 FPS target

- [ ] Measure frame rate on the target computer during aiming, ball travel, and pinfall.
- [ ] Sustain at least 60 FPS during normal gameplay at the agreed test resolution.
- [ ] Record the test resolution, Python version, GPU, average FPS, and worst sustained FPS.
- [ ] Profile any dips below 60 FPS and optimize the measured bottleneck before adding visual complexity.
- [ ] Check that static model geometry is cached and reused instead of resending every triangle from Python each frame.
- [ ] Check texture loading, HUD drawing, and scene rendering for avoidable work each frame.

## Priority 2: Add pin collision and fall physics

- [ ] Detect ball-to-pin contact reliably, including when the ball moves quickly between frames.
- [ ] Give struck pins a simple physical response: translation, rotation, friction, and settling.
- [ ] Allow pin-to-pin contact to transfer motion so neighboring pins can fall.
- [ ] Stop pin motion when it slows enough, and count each pin as down only once.
- [ ] Keep the result and second-roll flow compatible with the physics; standing pins remain until the frame ends.
- [ ] add a parameter for the pin (consider the bowling reset line), if the pin go out of that parameter then it considered fallen.
## Priority 3: Keep the ball inside the lane

- [ ] Follow the room sketch: use the existing room-floor texture (`floor.jpg`) for the bowling street too; do not add a separate `bowling_street.png` texture.
- [ ] Add dark guide rails along both sides of the lane, curving around the pin area toward the reset zone.
- [ ] Set the curve clearance from the ball radius so the ball can follow the guide without clipping through the rail.
- [ ] If a shot misses the pin path and reaches a guide rail, steer it along the curve into the reset zone, clear of the pins.
- [ ] Detect ball-to-rail contact reliably and keep the ball from escaping the room or lane boundary.
- [ ] Make the rails visible enough to read, while keeping them low and out of the normal pin path.

## Acceptance checks

- [ ] The game sustains at least 60 FPS on the agreed target computer during a normal throw and pinfall.
- [ ] A ball strike can knock down pins, and pin-to-pin contact can create a simple chain reaction.
- [ ] A ball moving toward either side boundary cannot leave the lane unnoticed.
- [ ] An intentionally wide shot follows the curved guide into the reset zone without touching the pins.
- [ ] The first and second throws, standing-pin state, and next-frame reset still work.

## Deferred until the physics/performance patch is stable

- [x] Implement open frames, strikes, spares, cumulative totals, and tenth-frame bonus rolls.
- [ ] Render the GLB models' original materials and textures.
- [ ] Tune camera transitions and refine lane/environment visuals.
- [ ] Update the sketch, README, and changelog after the patch is complete.

## Beta-test ideas to add

- Add observations, bugs, and feature requests here after the beta test.
