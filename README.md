# Gaze Arm

**Hands-free robot arm for people who cannot use their hands.** Look at an
object and the arm picks it up; look at an empty spot and it sets it down
there. The only extra hardware is the laptop's own webcam.

Winner, Viam "Fine Motor Skills" robot hackathon, September 2026.

## How it works

1. **Eyes → a point on screen.** The laptop webcam tracks the irises with
   MediaPipe's face landmarker. A short per-user calibration (look at nine
   dots, then eight directions where the head follows the eyes slightly) fits
   a small regression from eye + head features to screen pixels, so the gaze
   point stays right when the head moves a little.
2. **A point on screen → an object.** The arm's wrist camera (RealSense D435)
   streams to the screen with the detector's boxes drawn on it. Resting the
   gaze on a box fills a dwell timer and **locks** that object, freezing the
   exact frame the boxes came from.
3. **An object → a place in the world.** While the arm is still, one 3D
   segmentation runs; the object whose center projects into the locked box is
   the target, and it and every other object are frozen into world
   coordinates before anything moves. The object's top comes from its own
   depth points, not from the segmenter's box center, which is pulled upward
   by the dense top face.
4. **Then the arm moves.** Viam's motion service plans around the table,
   walls and the other objects: approach above, open, straight down, close
   until the jaws meet the object, straight up, and back to the viewing pose.

Nothing moves without `--execute`, and every stage is verified rather than
assumed: the gripper must report itself open before the descent, the arm must
actually be at the grasp pose before the jaws close, and the jaws must show
evidence of contact before anything is lifted.

**When it cannot do it, it stops and waits for a person.** An object more than
700 mm from the base is refused before anything moves, with the distance on
screen. An object the planner cannot find a way to reach pauses the run at
`PLAN REJECTED`, and an action interrupted part-way pauses at `ACTION
PAUSED`; neither is retried automatically. Pressing `R` re-checks the arm and
gripper (stopped, open, empty) before selection resumes. That is on purpose:
the person using this often cannot reach the object *or* the robot, so when
something is out of range the arm holds still and says so instead of
straining toward it, and whoever is helping resets it and confirms.

## The three versions

| folder | what it is |
| --- | --- |
| `arm-control-grid` | **the demo that won.** Everything below, plus the screen split into nine regions during placement: the place point snaps to the center of the region you look at, so eye jitter does not move it. The regions stay invisible on the feed. |
| `arm-control-place` | the same picking, plus **look-to-place**: while holding, look at an empty spot on the table and the arm sets the object down there, without the region grid. |
| `arm-control` | the base version: look at an object to pick it up; while holding, look at a different object to put the first back and pick the new one. `--menu` adds a post-pick gaze menu (bring it to me, raise/lower, place, let go) and `--user head` adds head-motion steering. |

Each folder is self-contained and has its own README with the details. The
loose scripts at the repo root are earlier prototypes kept for reference.

## Running it

```bash
cd arm-control-grid
python -m venv .venv && .venv\Scripts\activate
pip install -r requirements.txt
curl -L -o models/face_landmarker.task https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/latest/face_landmarker.task
```

Copy `.env.example` to `arm-control-grid/.env` and fill in your Viam machine
address and API key, then:

```bash
python main.py --execute
```

Calibrate when asked (about a minute), then look at an object and hold your
gaze on it. `Q` stops and quits, `P` puts a held object back, `C`
recalibrates. **Keep a hand on the physical E-stop.**

## Hardware

UFactory xArm6 with a two-finger gripper, an Intel RealSense D435 on the
wrist, and any laptop with a webcam. Everything on the robot side runs
through [Viam](https://www.viam.com/): the camera, a trained object detector,
3D segmentation, the motion service and the gripper.

## Credits

This started as my idea, and it came from people I know: adults and children
with cerebral palsy, people with missing or impaired limbs, and patients
confined to bed. They get fed and handed things by somebody else, but their
eyes work perfectly well. If the eyes are the part that still moves freely,
they should be enough to pick something up.

What I pitched to the team was specific, and it is what we built. A robot arm
with a two-finger gripper and a depth camera on it, running on Viam. The
camera streams the scene to a laptop while the laptop's own webcam watches
the user: two cameras, one looking out at the room and one looking back at
the person. The webcam turns your gaze into coordinates on that screen, those
coordinates get matched against the objects detected in the feed, the object
you are looking at is highlighted, and the arm acts on it. The live feed is
the whole interface — it is how someone who cannot move reaches into the
room. Two rules came with it: do not make the user move their eyes or head
much, because the people this is for often cannot, and keep head gestures as
an option for those who have some movement, never a requirement.

Two problems I raised in that first conversation ended up shaping the code.
The camera rides the arm, so the target has to be committed the instant it is
chosen — once the arm moves, the view you picked from is gone. And the
gripper needs a position in the room, not a rectangle on a screen, so the
pixels inside the detection box have to become a 3D location through the
depth data. Work backwards from what the arm needs, and make the gaze
pipeline hand it over in that form.

After that, Ireen and I mostly worked in parallel, each taking a different
route to the same goal on our own machines. Plenty of those attempts never
reached this repo, so the commit history is a thin record of who did what;
the notes below fill it in.

### [@reenj01](https://github.com/reenj01)

Ireen built the first working webcam gaze tracker, `gaze_dot.py`: MediaPipe's
478-point face mesh including the iris landmarks, nine on-screen targets held
1.5 s each with a half-second settle so samples are not taken mid-saccade, a
ridge-regression fit from eye features to screen pixels, and exponential
smoothing on the resulting dot. That program is what the calibration in this
repo grew out of. She also owned perception and the machine itself:
labelled the image dataset and trained the detector the arm picks from (the
`blockcanbox` model, served through Viam's TFLite runtime), then moved the
whole stack onto it, and she configured the machine — camera, vision
services, and the saved arm poses the demo returns to. When the depth data
came back as a cloud of shrapnel rather than objects, she made it usable:
cropping the point cloud to the table volume, filtering outliers
statistically, and tuning the clustering (15 mm radius, at least 150 points
per segment) until the segmenter returned separable objects. Every world
coordinate the arm aims at comes out of that pipeline.

Alongside it she ran her own line of pick-and-place work, most of it before
anything in `arm-control` existed. `viam_scene_select.py` put fullscreen gaze
selection on a frozen camera snapshot, rotating a wrist joint to calibrate
against the laptop and returning the arm to its pose afterwards, then
hit-testing the gaze against detection boxes with a margin at their edges.
`pick_cup.py` went from a detection box to that object's 3D segment and
picked it in deliberate stages — a hover stage you had to watch and approve
before a grab stage was allowed — and documented that `objects-3d` must be
wired to the same detector or the labels will not correspond.
`tutorial_phase5_pick.py` adapted Viam's perception-guided pick-and-place
sequence to this machine: observe from one repeatable wrist pose, get 3D
segments, approach in the camera frame, descend in the gripper frame, grab,
travel, place, return home, including which saved pose switches had to exist
first. `face.py` drove the arm through saved joint positions to aim it at a
person, and `move_to_standoff.py` sent it to the table-viewing pose. All of
it converged in `main2.py`, her own 449-line gaze-select program: select by
looking, confirm with a keypress before anything moves, then pick and lift,
with a dry-run mode for everything short of motion. We worked through the bad
grasps together, including the vertical offset that drove the gripper down
into objects, and it was her call to cut the post-pick menu down to two
actions, which is what the demo does. Much more of this happened on
her laptop in runs that were never committed.

### [@rwezzy](https://github.com/rwezzy) — me

**Concept and interaction design**

- Proposed the project and the people it is for, and specified the system
  that got built: a two-finger gripper and a depth camera on the arm running
  on Viam, the scene streamed to a laptop, the laptop's webcam reading the
  user's gaze as coordinates on that screen, those coordinates matched
  against the objects detected in the feed, and the arm acting on whichever
  object is being looked at — with minimal eye and head movement demanded of
  the user, and head gestures an option rather than a requirement.
- Proposed locking the object from a frozen frame. The image and its boxes
  come from a single capture, so what the arm commits to is exactly what the
  user was looking at; the camera rides the wrist, so a moment later that
  view is gone.
- Designed a selection model that tolerates an imperfect gaze: attention
  accumulates on a box while you look at or near it (scored by distance
  outside the box)
  and fades with a 1.5 s time constant when you look away, the winner has to
  hold twice the runner-up's evidence, boxes are followed frame to frame by
  overlap so a detection that flickers does not reset the timer, and a box
  nested inside another wins over the one around it.
- Worked backwards from what the arm needs: isolate what is inside the
  detector's box, hand that to 3D segmentation, and map the gaze point into
  the same pixel space as the feed so a look can be tested against a box.
- Designed what happens after a pick: a menu of actions for users with no
  movement (bring it to me, raise, lower, place down, place away) and
  head-motion steering for users with some, later cut to the two actions the
  demo uses.
- Proposed placing an object at a new x, y by looking at an empty spot: the
  gaze pixel's camera ray is intersected with the table, and the spot is
  refused if it is out of reach, inside 200 mm of the arm's base, or within
  25 mm of another object's footprint.
- Proposed snapping the gaze to a grid of screen cells so eye jitter stops
  moving the cursor, a cell changing only after the gaze stays in it for
  several frames, with a coarser grid for placement and the grid left
  invisible on the feed.

**Gaze tracking and calibration**

- Rebuilt the calibration around what actually broke: predictions that only
  held while the head stayed perfectly still. Features became each iris's
  position inside its own eye measured in eye widths, so where the face sits
  in the webcam frame stops dragging the cursor, with head-pose terms
  alongside so the fit can tell a turned head from a moved eye.
- Specified nine targets with the head still, then eight directional stages
  of two targets each — the midpoint toward that side and the corner or edge
  — so the
  regions that tracked worst (the diagonals between the center and the
  corners) are measured directly.
- Insisted the head turns be *subtle*: nobody looking at the left of a screen
  turns their head fully left, so calibration asks for the small turn
  attention actually produces, and a stage never waits on a measured angle.
- Added skipping for any direction a user cannot reach, so a person with
  limited neck movement still finishes calibration.
- Noticed the cursor drifted *after* a blink rather than during it, and
  specified the fix: a per-user open-eye baseline, no prediction while the
  lids are reopening, and predictions resuming only once the eyes have been
  fully open for a moment.
- Called for a prediction that lands far outside the window to return
  nothing at all, rather than a cursor pinned to an edge.
- Spotted the framing problem that left faces squished and flat, and the bias
  from starting calibration at a corner right after the user has been reading
  instructions in the middle of the screen.

**Grasping, safety and diagnosis**

- Diagnosed the crushing: the gripper senses force between the fingers but
  nothing on the way down, so objects were being compressed from above. The
  fix positions the gripper against the object's measured top, taken from the
  object's own depth points, with the fingers entering 15 mm below it and the
  housing kept clear above it.
- Found that the configured table height and the one the depth camera
  measures disagree by about 28 mm; the floor the fingertips may never pass
  now takes whichever is higher.
- Required two independent depth captures to agree before the arm moves, so
  one bad frame cannot send it to a plausible but wrong height.
- The gripper must read fully open before the descent, the arm must be
  measurably stopped at the grasp pose (within 5 mm and 2 degrees) before the
  jaws close, and the jaws must stop short of the commanded position — the
  evidence that something is between them — before anything is lifted.
- Called for the gripper to close until it actually grips, and for the
  closing width to suit the object so a paper cup is not crushed.
- Specified the return-to-rest behaviour: after a pick the arm comes back to
  a set height above the table, holding its wrist orientation so nothing
  spills.
- Proposed the out-of-reach failure state, and specified how it behaves: an
  object too far from the base is refused before the arm moves, and one the
  planner cannot solve stops the run with the reason on screen rather than
  straining toward it. Nothing retries on its own; a helper resets the arm
  and presses `R`, which re-checks that it is stopped, open and empty before
  selection resumes. The reasoning was that the people this is built for
  cannot reach the robot any more than they can reach the object, so when
  something is placed out of range the run has to end in a clear stop and a
  handover to whoever is helping, never in the arm forcing itself toward
  something it cannot get to.
- Proposed ignoring detections that swallow the whole scene (the "dining
  table" box around everything) so the background cannot be selected, and
  refusing to act on a camera frame older than a few seconds.
- Traced the stalls and crashes: frames fetched inside the display loop
  making the cursor lag, connections to the machine dropping mid-grasp, two
  detections of one object colliding over a duplicate name, and grasps
  reporting success with an empty gripper.

**Proposed, not built**

- Selection by deliberate blinks (double to confirm, triple to reject and
  ignore that object for a minute), and nodding or shaking the head to
  confirm or reject a highlighted object.
- Predicting the intended target from the direction of a look rather than
  requiring an exact fixation.
- Calibrating at several distances from the screen, not only several
  orientations.

### Taylor Ye

- The original face-framing gate in `gaze_dot.py`: the oval that checks you
  are centered and at the right distance, and holds calibration until you are.
