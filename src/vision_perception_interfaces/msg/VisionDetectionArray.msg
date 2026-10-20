# V1 batch on /dg/vision/detections_2d (plan §3).

# Source RGB acquisition timestamp and optical frame; must match per-item headers if present.
std_msgs/Header header
# UUID created when the node opens an input session; regenerated on restart/reset/clock rollback/calibration change.
string source_session_id
# Monotonic within the session from 1; assigned to accepted source frames; discarded indices are not reused.
uint64 observation_id
# Empty in V1 without CameraInfo; required for V2/V3.
string calibration_id
# LIVE_CAMERA / RECORDED_CAMERA. Plain offline images use file evaluation output, not this ROS observation contract.
string source_kind
VisionDetection2D[] detections
