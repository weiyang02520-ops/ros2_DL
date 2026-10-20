# All objects share this source acquisition timestamp and coordinate frame.
std_msgs/Header header
# Empty before V3. Restart/reset creates a new ID namespace.
string tracking_session_id
VisionObject[] objects
