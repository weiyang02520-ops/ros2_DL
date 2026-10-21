"""Launch W5 object transform adapter (default disabled).

Does not start ZED, Nav2, or publish TF. Pass enabled:=true only with real
extrinsics or a live TF tree provided by the peer robot.
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
    default_config = os.path.join(share, "config", "transform_config.yaml")
    return LaunchDescription(
        [
            DeclareLaunchArgument("params_file", default_value=default_config),
            DeclareLaunchArgument("enabled", default_value="false"),
            DeclareLaunchArgument("mode", default_value="static_extrinsics"),
            DeclareLaunchArgument("source_frame", default_value=""),
            DeclareLaunchArgument("target_frame", default_value=""),
            DeclareLaunchArgument("extrinsics_id", default_value=""),
            DeclareLaunchArgument(
                "objects_input_topic", default_value="/dg/vision/objects"
            ),
            DeclareLaunchArgument(
                "objects_target_topic",
                default_value="/dg/vision/objects_target",
            ),
            Node(
                package="vision_perception",
                executable="vision_object_transform_node",
                name="vision_object_transform_node",
                output="screen",
                parameters=[
                    LaunchConfiguration("params_file"),
                    {
                        "enabled": ParameterValue(
                            LaunchConfiguration("enabled"), value_type=bool
                        ),
                        "mode": LaunchConfiguration("mode"),
                        "source_frame": LaunchConfiguration("source_frame"),
                        "target_frame": LaunchConfiguration("target_frame"),
                        "extrinsics_id": LaunchConfiguration("extrinsics_id"),
                        "objects_input_topic": LaunchConfiguration(
                            "objects_input_topic"
                        ),
                        "objects_target_topic": LaunchConfiguration(
                            "objects_target_topic"
                        ),
                    },
                ],
            ),
        ]
    )
