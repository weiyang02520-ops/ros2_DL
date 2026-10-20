# Vision Evidence Policy

Status: NO_VISION_EXPERIMENT_RUN. This directory is a scaffold placeholder, not
evidence that detection, 3D projection, tracking or arm integration works.

Future runs use `<date>_<V1|V2|V3>_<run>/`. Each run must preserve:

- metadata with REAL_CAMERA / RECORDED_CAMERA / SYNTHETIC source classification;
- code commit plus dirty/source snapshot and exact parameter copy;
- detector model SHA256, class mapping, backend/version and resource settings;
- source images/depth/CameraInfo or rosbag, with acquisition stamps and frames;
- detections.csv, objects.csv and rejected-input.csv as applicable;
- metrics.json, raw logs, optional labelled visual evidence and SHA256 manifest.

V1 requires labelled bottle/cup and no-target scenes. V2 requires independent
position truth in the same coordinate frame. V3 requires identity-labelled
sequences and reset/occlusion/staleness cases. Metrics and numeric acceptance
thresholds must be fixed before the acceptance run.

Keep failed and incomplete runs. Never replace missing depth with a valid zero
position, fabricate an object or pose, or file an empty shell as a no-target run.
Synthetic examples, real camera results and hardware/arm experiments must remain
separately labelled. Do not copy existing navigation or UWB data here as vision
acceptance evidence.
