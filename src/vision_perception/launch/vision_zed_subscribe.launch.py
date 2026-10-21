"""Launch vision_perception against existing ZED topics only (W3).

Does NOT start the ZED SDK, ZED ROS driver, Nav2, chassis, or any TF publisher.
Expects the operator to start the reviewed camera node separately.
Defaults: enable_objects=false, enable_tracking=false, lazy skeleton until mode:=v1_ros.
"""

import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue


def generate_launch_description():
    share = get_package_share_directory("vision_perception")
    default_config = os.path.join(
        share, "config", "profiles", "zed_subscribe.yaml"
    )
    return LaunchDescription(
        [
            DeclareLaunchArgument(
                "params_file",
                default_value=default_config,
                description="ZED subscribe-only profile YAML.",
            ),
            DeclareLaunchArgument(
                "mode",
                default_value="v1_ros",
                description="skeleton or v1_ros. mode:=v1 rejected.",
            ),
            DeclareLaunchArgument("model_path", default_value=""),
            DeclareLaunchArgument("model_manifest_path", default_value=""),
            DeclareLaunchArgument(
                "enable_objects",
                default_value="false",
                description="V2 depth→/objects. Default false; tracking stays off.",
            ),
            DeclareLaunchArgument(
                "enable_tracking",
                default_value="false",
                description="V3 tracker. First delivery keeps false.",
            ),
            DeclareLaunchArgument(
                "publish_debug_image",
                default_value="false",
            ),
            DeclareLaunchArgument(
                "rgb_topic",
                default_value="/zed/zed_node/rgb/color/rect/image",
            ),
            DeclareLaunchArgument(
                "depth_topic",
                default_value="/zed/zed_node/depth/depth_registered",
            ),
            DeclareLaunchArgument(
                "camera_info_topic",
                default_value="/zed/zed_node/rgb/color/rect/camera_info",
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
                        "depth_topic": LaunchConfiguration("depth_topic"),
                        "camera_info_topic": LaunchConfiguration(
                            "camera_info_topic"
                        ),
                        "model_path": LaunchConfiguration("model_path"),
                        "model_manifest_path": LaunchConfiguration(
                            "model_manifest_path"
                        ),
                        "camera_contract": (
                            "ZED_TOPIC_SUBSCRIBE_ONLY / NOT_START_SDK"
                        ),
                        "input_profile": "zed_subscribe",
                        "enable_objects": ParameterValue(
                            LaunchConfiguration("enable_objects"),
                            value_type=bool,
                        ),
                        "enable_tracking": ParameterValue(
                            LaunchConfiguration("enable_tracking"),
                            value_type=bool,
                        ),
                        "publish_debug_image": ParameterValue(
                            LaunchConfiguration("publish_debug_image"),
                            value_type=bool,
                        ),
                    },
                ],
            ),
        ]
    )
