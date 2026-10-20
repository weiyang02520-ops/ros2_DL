# Source RGB acquisition timestamp and measured optical coordinate frame.
std_msgs/Header header

# Stable only inside VisionObjectArray.tracking_session_id; empty before tracking.
string object_id
string class_name
# Classification score, not a position confidence or calibrated probability.
float32 confidence

# Metres in header.frame_id. Ignore storage values when position_valid is false.
geometry_msgs/Point position
bool position_valid
# For example bbox_center_depth_surface; not automatically an object/grasp centre.
string position_reference

# Unknown in planned V1/V2/V3; consumers must not assume identity orientation.
geometry_msgs/Quaternion orientation
bool orientation_valid
bool tracking_valid
