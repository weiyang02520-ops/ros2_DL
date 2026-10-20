"""Vision launch: default skeleton; optional v1_ros + local webcam/fake Image.

Optional V2 offline smoke: use_fake_depth:=true + enable_objects:=true
(default false). Optional V3: enable_tracking:=true (v1_ros only, default false).
mode:=v1 remains unsupported (node rejects). ZED is not started.
camera_contract for v1_ros is DEV_WEBCAM_ONLY / NOT_ZED.
"""

import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, OpaqueFunction
from launch.conditions import IfCondition
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue


def _launch_setup(context, *args, **kwargs):
    use_fake_depth = LaunchConfiguration("use_fake_depth").perform(context)
    use_fake_depth_on = str(use_fake_depth).strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
    depth_topic = LaunchConfiguration("depth_topic").perform(context)
    camera_info_topic = LaunchConfiguration("camera_info_topic").perform(context)
    if use_fake_depth_on:
        # Remap node inputs to fake topics unless the user already overrode them
        # away from the ZED defaults.
        if depth_topic == "/zed/zed_node/depth/depth_registered":
            depth_topic = "/dg/vision/fake/depth"
        if camera_info_topic == "/zed/zed_node/rgb/color/rect/camera_info":
            camera_info_topic = "/dg/vision/fake/camera_info"

    # Stamp sync for V2 smoke: fake_depth timer is master; fake_image copies
    # depth stamps so RGB is published only after depth+CameraInfo for that stamp.
    fake_image_stamp_source = depth_topic if use_fake_depth_on else ""

    nodes = [
        Node(
            package="vision_perception",
            executable="vision_webcam_publisher",
            name="vision_webcam_publisher",
            output="screen",
            condition=IfCondition(LaunchConfiguration("use_webcam")),
            parameters=[{
                "video_device": LaunchConfiguration("video_device"),
                "image_topic": LaunchConfiguration("rgb_topic"),
                "frame_id": "webcam_optical_frame",
            }],
        ),
        # Start depth stamp-master before RGB so the first ticks have depth ready.
        Node(
            package="vision_perception",
            executable="vision_fake_depth_publisher",
            name="vision_fake_depth_publisher",
            output="screen",
            condition=IfCondition(LaunchConfiguration("use_fake_depth")),
            parameters=[{
                # Empty rgb_topic → timer stamp master (not RGB-driven mirror).
                "rgb_topic": "",
                "frame_rate_hz": 5.0,
                "depth_topic": depth_topic,
                "camera_info_topic": camera_info_topic,
                "frame_id": "fake_webcam_optical_frame",
                "constant_depth_m": LaunchConfiguration("fake_depth_m"),
            }],
        ),
        Node(
            package="vision_perception",
            executable="vision_fake_image_publisher",
            name="vision_fake_image_publisher",
            output="screen",
            condition=IfCondition(LaunchConfiguration("use_fake_image")),
            parameters=[{
                "image_topic": LaunchConfiguration("rgb_topic"),
                "frame_id": "fake_webcam_optical_frame",
                "image_path": LaunchConfiguration("fake_image_path"),
                "fake_image_path": LaunchConfiguration("fake_image_path"),
                "stamp_source_topic": fake_image_stamp_source,
            }],
        ),
        Node(
            package="vision_perception",
            executable="vision_perception_node",
            name="vision_perception_node",
            output="screen",
            parameters=[
                LaunchConfiguration("params_file"),
                {
                    "mode": LaunchConfiguration("mode"),
                    "rgb_topic": LaunchConfiguration("rgb_topic"),
                    "depth_topic": depth_topic,
                    "camera_info_topic": camera_info_topic,
                    "model_path": LaunchConfiguration("model_path"),
                    "model_manifest_path": LaunchConfiguration("model_manifest_path"),
                    "camera_contract": LaunchConfiguration("camera_contract"),
                    "publish_debug_image": ParameterValue(
                        LaunchConfiguration("publish_debug_image"), value_type=bool
                    ),
                    "enable_objects": ParameterValue(
                        LaunchConfiguration("enable_objects"), value_type=bool
                    ),
                    "enable_tracking": ParameterValue(
                        LaunchConfiguration("enable_tracking"), value_type=bool
                    ),
                },
            ],
        ),
    ]
    return nodes


def generate_launch_description():
    default_config = os.path.join(
        get_package_share_directory("vision_perception"), "config", "vision.yaml"
    )
    return LaunchDescription([
        DeclareLaunchArgument("params_file", default_value=default_config),
        DeclareLaunchArgument(
            "mode",
            default_value="skeleton",
            description="skeleton (default) or v1_ros. mode:=v1 is rejected.",
        ),
        DeclareLaunchArgument(
            "use_webcam",
            default_value="false",
            description="If true, also start vision_webcam_publisher (V4L2/OpenCV).",
        ),
        DeclareLaunchArgument(
            "use_fake_image",
            default_value="false",
            description="If true, publish synthetic/file RGB (no camera hardware).",
        ),
        DeclareLaunchArgument(
            "use_fake_depth",
            default_value="false",
            description=(
                "If true, start vision_fake_depth_publisher (32FC1 + CameraInfo). "
                "For V2 smoke with enable_objects:=true. Does not start ZED."
            ),
        ),
        DeclareLaunchArgument(
            "fake_image_path",
            default_value="",
            description=(
                "Optional local RGB file for fake publisher "
                "(.jpg/.png/.npy). Real bottle/cup photo recommended for "
                "non-empty detections."
            ),
        ),
        DeclareLaunchArgument(
            "fake_depth_m",
            default_value="1.0",
            description="Constant depth (metres) for fake depth publisher.",
        ),
        DeclareLaunchArgument("video_device", default_value="0"),
        DeclareLaunchArgument(
            "rgb_topic",
            default_value="/dg/vision/webcam/image_raw",
        ),
        DeclareLaunchArgument(
            "depth_topic",
            default_value="/zed/zed_node/depth/depth_registered",
            description=(
                "Depth Image topic. With use_fake_depth:=true defaults remap to "
                "/dg/vision/fake/depth when left at the ZED default."
            ),
        ),
        DeclareLaunchArgument(
            "camera_info_topic",
            default_value="/zed/zed_node/rgb/color/rect/camera_info",
            description=(
                "CameraInfo topic. With use_fake_depth:=true defaults remap to "
                "/dg/vision/fake/camera_info when left at the ZED default."
            ),
        ),
        DeclareLaunchArgument("model_path", default_value=""),
        DeclareLaunchArgument("model_manifest_path", default_value=""),
        DeclareLaunchArgument(
            "camera_contract",
            default_value="DEV_WEBCAM_ONLY / NOT_ZED",
        ),
        DeclareLaunchArgument(
            "publish_debug_image",
            default_value="false",
            description=(
                "If true, publish annotated rgb8 on /dg/vision/debug_image "
                "(≤2 Hz). Default off; no GUI."
            ),
        ),
        DeclareLaunchArgument(
            "enable_objects",
            default_value="false",
            description=(
                "If true (v1_ros only), run V2 depth pairing and publish "
                "VisionObjectArray on /dg/vision/objects. Default false."
            ),
        ),
        DeclareLaunchArgument(
            "enable_tracking",
            default_value="false",
            description=(
                "If true (v1_ros only), run V3 short-horizon 2D IoU tracker. "
                "Default false. Fills object_id/tracking_valid when objects on."
            ),
        ),
        OpaqueFunction(function=_launch_setup),
    ])
