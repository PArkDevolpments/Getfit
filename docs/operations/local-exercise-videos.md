# Local exercise videos

Getfit reads user-supplied exercise videos from Home Assistant's shared media directory.

## Home Assistant location

Create this directory on the Home Assistant host:

`/media/getfit/videos/`

The Getfit app maps Home Assistant `media` read-only and serves those files internally through its Ingress-safe `/exercise-videos/` route.

## Required Week 1 filenames

Upload MP4 files using these exact lowercase filenames:

- `dumbbell_floor_press.mp4`
- `one_arm_dumbbell_row.mp4`
- `seated_dumbbell_shoulder_press.mp4`
- `dumbbell_biceps_curl.mp4`
- `overhead_triceps_extension.mp4`
- `goblet_squat.mp4`
- `dumbbell_romanian_deadlift.mp4`
- `supported_reverse_lunge.mp4`
- `standing_calf_raise.mp4`
- `dead_bug.mp4`
- `forearm_plank.mp4`
- `dumbbell_lateral_raise.mp4`
- `hammer_curl.mp4`

Getfit does not require these files to be committed to GitHub. They remain on the user's Home Assistant installation and are loaded only when the exercise Video tab is opened.

For maximum browser compatibility use H.264 video with AAC audio in an MP4 container.
