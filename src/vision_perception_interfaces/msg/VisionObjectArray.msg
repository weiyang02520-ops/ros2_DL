# V2/V3 batch on /dg/vision/objects (plan §3). Not published in V1.
# Carries the same observation keys as VisionDetectionArray, plus tracking_session_id.

# All objects share this source acquisition timestamp and coordinate frame.
std_msgs/Header header
# UUID for the input session; regenerate on restart/reset/clock rollback/calibration change.
string source_session_id
# Monotonic within the session from 1; discarded indices are not reused.
uint64 observation_id
# Required non-empty for V2/V3 (CameraInfo hash). Empty only if input invalid.
string calibration_id
# LIVE_CAMERA / RECORDED_CAMERA for ROS observations.
string source_kind
# Empty before V3. Restart/reset creates a new ID namespace.
string tracking_session_id
# One entry per retained 2D detection, including depth failures (do not drop failures).
VisionObject[] objects
