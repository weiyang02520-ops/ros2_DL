# V2/V3 observation item (plan §3). Published only after explicit V2 authorization.
# V1 must not publish /dg/vision/objects. This message is the frozen contract shape.
#
# Observations are NOT arm goals: position_valid=true does not authorize motion.
# ARM_READY lives on /dg/vision/status diagnostics only (always NO until arm stage).

# Source RGB acquisition timestamp and measured optical coordinate frame.
# Must match VisionObjectArray.header when both are set.
std_msgs/Header header

# Same observation key as the matching VisionDetection2D; not array-order association.
uint32 detection_index
# Stable only inside VisionObjectArray.tracking_session_id; empty in V2 (no tracking).
string object_id
# Only bottle or cup in the first version.
string class_name
# Classification score, not a position confidence or calibrated probability.
float32 confidence
vision_msgs/BoundingBox2D bbox

# Metres in header.frame_id. Store NaN and set position_valid=false when invalid.
geometry_msgs/Point position
bool position_valid
# Always visible_surface_sample when a surface sample is intended; do not encode failures here.
string position_reference
# OK / DEPTH_UNPAIRED / MASK_TOO_SMALL / DEPTH_INSUFFICIENT / DEPTH_DISCONTINUITY / INPUT_INVALID / STALE.
string invalid_reason
float64 reference_u
float64 reference_v
float32 valid_depth_fraction

# Unknown in V1/V2/V3; store NaN components and orientation_valid=false.
# Measuring orientation is a separate future task.
geometry_msgs/Quaternion orientation
bool orientation_valid
# false in V2; true in V3 only when a confirmed track matches this frame.
bool tracking_valid
