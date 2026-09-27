# Handing a material layer to Blender through a coding agent

Part of the `procedural-video-frames` skill. Read this when a layer needs
believable cloth, true perspective, physically correct depth of field, or any
material that a 2.5D height field has failed to sell after a revision or two;
when procedural elements must sit on a moving surface rendered elsewhere; and
before dispatching a coding agent to drive Blender.

## When to split the work

Two-and-a-half-D height fields do metal, lacquer and light very well from a
fixed camera. They do not do believable cloth, true perspective, or physically
correct depth of field; a silk plate stayed "a gradient with a light shaft"
through several procedural revisions. If the user has Blender and a coding
agent that can drive it (validated here with Codex running a model the user
named), split the work:

- **The procedural layer owns timing and exact geometry**: growing elements,
  threads, small objects, their contact shadows, the text.
- **The Blender layer owns the material-heavy plate**: cloth, a set, anything
  whose look comes from a physically based material.

## The contract

Write a precise contract for the agent, and verify it rather than trusting it:

- one world coordinate system, with the mapping to Blender axes spelled out;
- a per-frame camera file exported from the same timeline module the renderer
  uses (centre, width, rotation, and any animated scalars);
- an orthographic camera with the sensor fit and scale stated, plus a check that
  projects known points through Blender's actual camera matrix and compares
  them to the expected pixels (sub-pixel agreement is achievable; ~1e-4 px was
  measured);
- any lighting that must match between layers given as a formula (e.g. a
  reveal's spatial falloff), not a description;
- output format: 16-bit PNG with the Standard view transform, highlights kept
  below ~0.9 so the procedural layer can be the brightest thing, and a
  linearisation step (inverse sRGB) before compositing in linear light;
- test frames first, which the agent must open and iterate on, then the full
  sequence, with per-frame timing reported.

## Elements riding a moving surface

**Share the surface's motion as code.** Put the surface's motion (height and any
in-plane sway) in one small module that both the Blender script and the
procedural renderer import, and invert the sway per pixel (a few damped
fixed-point iterations) to find which material point each pixel shows. Elements
laid on top of a separately rendered moving surface otherwise look pasted on.

- **The strongest "it is on the surface" cue is lighting, not motion.** Tilt
  the elements' normals by the surface's slope and dim them in the surface's
  valleys.
- **A coupling factor that ramps from 0 to 1** lets an element start rigid and
  settle onto the surface.

**Check that the projection can show height at all.** An orthographic camera
looking straight down sees only in-plane position: a surface's height changes
move nothing on screen, so "elements ride a waving cloth" is invisible no
matter how large the waves are -- the only visible trace is shading. Two ways
to make height visible:

- **Map height to screen displacement** (a parallel-oblique view): a point at
  height `z` is seen at `seen_y = y - K * z`, with the sign chosen so raised
  surface moves up the screen. `K = 0.4` (screen units per unit of height) made
  the waving clearly visible. **Both layers must use the same mapping** -- put
  it in the shared motion module, apply it to the Blender mesh's vertices and in
  the procedural layer's per-pixel inverse. Keep `K * |dz/dy| < 1`, and check
  that no projected mesh face flips (all projected quads keep a positive
  orientation); otherwise the surface folds over itself on screen.
- **Give the camera perspective.** **Untested** in this pipeline: it breaks the
  orthographic camera contract above, so the procedural layer would need the
  same perspective projection and the camera-matrix check redone.

Sanity check: render the surface with a regular grid drawn on it. If the grid
lines do not bend visibly on screen as the waves pass, a viewer will not see the
elements ride them either.

**Let one travelling wave dominate.** Two crossing wave systems superposed on
cloth read as latex or rubber, not silk. Real flags in wind show one dominant
wave travelling from the hoist to the fly with lighter secondary ripples; once
the wind is up, ramp the other system down.

**When a shared plate looks wrong, check the shared motion module first.** If
the motion lives in one module, both the plate and the procedural layer inherit
its mistakes. The latex look above came from the shared motion definition, not
from the agent's Blender work or the renderer; blaming the agent would have
cost a round of re-dispatching with the wrong fix.

## Composite in your pipeline, not theirs

Load the plate, linearise it, apply the procedural layer's contact shadows to
it, put the procedural elements on top, then tone map once.

## Operating the coding agent

- **Blender may crash in the agent's write sandbox.** It segfaulted on startup
  inside the coding agent's default write sandbox and rendered normally
  unsandboxed. Run the agent without the sandbox, scope it in the prompt to one
  directory, and tell it not to touch other processes.
- **The agent inherits workspace rules.** One run refused to write its own
  technical notes because a workspace rule routed prose to another tool; say
  explicitly which files it should write itself.
- **Tell it explicitly not to call other agents**, so one process owns the
  render and its logs and timings are the ones you read.
- **Pass the model explicitly** if the user names one.
- **Once a working render script exists, run parameter changes yourself.** The
  agent's value is producing the script and passing the contract checks.
  Re-dispatching it to change a constant and re-render is slower and less
  reliable: one such run stalled on network reconnects, while running the same
  script directly took about 8.5 minutes for 180 frames. Re-dispatch only for
  changes that need new code or new judgement.
- **Close its stdin when you background it.** A headless agent started with
  `nohup ... &` can sit waiting for input ("Reading additional input from
  stdin"); start it with `< /dev/null`, and watch for its process to exit rather
  than polling its output files.
- **Stopping it means stopping its children.** Killing the agent leaves the
  Blender processes it started running; find them by their script names and
  stop them too, or they keep the GPU busy.
- **Timing to expect** (1080x1920, Metal): the first kernel compile took about
  two minutes; afterwards a plate frame rendered in about 2.5-3 s. Render the
  parts of the film that do not need the plate while the agent works.
