# vision_perception

Independent manipulation-vision ROS2 scaffold. No arm integration, object detector,
depth projection or tracking is implemented. The shell publishes only
`/dg/vision/status` with `SKELETON_ONLY`; it has no image subscriptions and does not
publish empty or fabricated detection/object arrays.

The future pipeline is ZED RGB/depth/CameraInfo → detector → depth-qualified 3D
surface position → tracking. V1 uses `vision_msgs/Detection2DArray`; V2/V3 use
`vision_perception_interfaces/VisionObjectArray`. Unknown orientation stays
invalid. A perception observation is not an arm grasp command.

Design and acceptance criteria:

- `../../docs/dg202611/VISION_INTEGRATION_PLAN.md`
- `../../docs/dg202611/VISION_MODULE.md`
- `../../evidence/vision/README.md`

Future Linux ROS2 build/run, not executed during scaffold creation:

```bash
source /opt/ros/humble/setup.bash
colcon build --symlink-install --packages-select vision_perception_interfaces vision_perception
source install/setup.bash
ros2 launch vision_perception vision.launch.py
```

No TensorRT/CUDA, cv_bridge, YOLO, ZED SDK or tracking dependency is installed or
required by this shell. The existing camera driver remains external.
