"""Safe DG-202611 three-model and measured-UWB integration entry point.

Start the existing robot bringup separately so that /scan, /odom and TF are
available. This launch adds only the DG observation/fusion/recovery layer.
Command arbitration and UWB-to-map fusion stay disabled until explicitly
enabled after on-robot interface checks.
"""

import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, GroupAction, IncludeLaunchDescription
from launch.conditions import IfCondition
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node, SetRemap
from launch_ros.parameter_descriptions import ParameterValue


def generate_launch_description():
    package_share = get_package_share_directory("ylhb_base")
    workspace_dir = os.environ.get("WS_DIR", os.path.expanduser("~/ros2_DL"))
    preferred_map = os.path.join(workspace_dir, "maps", "my_map.yaml")
    fallback_map = os.path.join(workspace_dir, "src", "my_map.yaml")
    default_map = preferred_map if os.path.exists(preferred_map) else fallback_map
    default_uwb_params = os.path.join(package_share, "config", "uwb_bringup_temporary.yaml")
    default_uwb_replay = os.path.join(
        package_share, "data", "uwb", "20260905", "static_raw_20260905_165208.csv"
    )

    enable_nav2 = LaunchConfiguration("enable_nav2")
    enable_cmd_vel_arbiter = LaunchConfiguration("enable_cmd_vel_arbiter")
    enable_multisource_fusion = LaunchConfiguration("enable_multisource_fusion")
    enable_uwb_replay = LaunchConfiguration("enable_uwb_replay")
    use_sim_time = LaunchConfiguration("use_sim_time")
    map_file = LaunchConfiguration("map")
    params_file = LaunchConfiguration("params_file")
    uwb_params_file = LaunchConfiguration("uwb_params_file")
    uwb_replay_file = LaunchConfiguration("uwb_replay_file")
    uwb_replay_rate_hz = LaunchConfiguration("uwb_replay_rate_hz")
    uwb_replay_loop = LaunchConfiguration("uwb_replay_loop")
    uwb_alignment_enabled = LaunchConfiguration("uwb_alignment_enabled")
    uwb_to_map_yaw = LaunchConfiguration("uwb_to_map_yaw")
    uwb_to_map_offset_x = LaunchConfiguration("uwb_to_map_offset_x")
    uwb_to_map_offset_y = LaunchConfiguration("uwb_to_map_offset_y")
    required_signals = LaunchConfiguration("required_signals")
    cmd_vel_output_topic = LaunchConfiguration("cmd_vel_output_topic")
    gnss_origin_latitude = LaunchConfiguration("gnss_origin_latitude")
    gnss_origin_longitude = LaunchConfiguration("gnss_origin_longitude")
    gnss_origin_altitude = LaunchConfiguration("gnss_origin_altitude")
    map_enu_yaw = LaunchConfiguration("map_enu_yaw")
    map_enu_offset_x = LaunchConfiguration("map_enu_offset_x")
    map_enu_offset_y = LaunchConfiguration("map_enu_offset_y")

    nav2_launch = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(os.path.join(package_share, "launch", "navigation.launch.py")),
        launch_arguments={
            "use_sim_time": use_sim_time,
            "map": map_file,
            "params_file": params_file,
            "autostart": "true",
        }.items(),
    )

    lidar = Node(
        package="ylhb_base",
        executable="lidar_robust_node",
        name="dg_lidar_robust_node",
        output="screen",
        parameters=[{"scan_topic": "/scan", "odom_topic": "/odom", "quality_topic": "/dg/lidar/quality"}],
    )
    gnss = Node(
        package="ylhb_base",
        executable="gnss_quality_node",
        name="dg_gnss_quality_node",
        output="screen",
        parameters=[
            {
                "fix_topic": "/gps/fix",
                "status_topic": "/gps/rtk_status",
                "quality_topic": "/dg/gnss/quality",
            }
        ],
    )
    uwb_replay = Node(
        package="ylhb_base",
        executable="uwb_replay_node",
        name="dg_uwb_replay_node",
        output="screen",
        condition=IfCondition(enable_uwb_replay),
        parameters=[
            uwb_params_file,
            {
                "input_file": uwb_replay_file,
                "playback_rate_hz": ParameterValue(uwb_replay_rate_hz, value_type=float),
                "loop": ParameterValue(uwb_replay_loop, value_type=bool),
            },
        ],
    )
    scan_map = Node(
        package="ylhb_base",
        executable="scan_map_relocalization_node",
        name="dg_scan_map_relocalization_node",
        output="screen",
        parameters=[
            {
                "map_topic": "/map",
                "scan_topic": "/scan",
                "initialpose_topic": "/initialpose",
                "seed_topic": "/dg/relocalization/seed",
                "scan_match_pose_topic": "/scan_match_pose",
                "match_quality_topic": "/dg/relocalization/match_quality",
            }
        ],
    )
    relocalization = Node(
        package="ylhb_base",
        executable="active_relocalization_node",
        name="dg_active_relocalization_node",
        output="screen",
        parameters=[
            {
                "scan_topic": "/scan",
                "odom_topic": "/odom",
                "amcl_pose_topic": "/amcl_pose",
                "lidar_quality_topic": "/dg/lidar/quality",
                "gnss_quality_topic": "/dg/gnss/quality",
                "match_quality_topic": "/dg/relocalization/match_quality",
                "cmd_vel_topic": "/cmd_vel_recovery",
                "required_signals": required_signals,
            }
        ],
    )
    health = Node(
        package="ylhb_base",
        executable="navigation_health_node",
        name="dg_navigation_health_node",
        output="screen",
        parameters=[
            {
                "required_signals": required_signals,
                "uwb_quality_topic": "/dg/uwb/quality",
                "status_topic": "/dg/navigation/status",
            }
        ],
    )
    arbiter = Node(
        package="ylhb_base",
        executable="cmd_vel_arbiter_node",
        name="dg_cmd_vel_arbiter_node",
        output="screen",
        condition=IfCondition(enable_cmd_vel_arbiter),
        parameters=[
            {
                "navigation_topic": "/cmd_vel_nav",
                "recovery_topic": "/cmd_vel_recovery",
                "output_topic": cmd_vel_output_topic,
                "navigation_status_topic": "/dg/navigation/status",
            }
        ],
    )
    multisource_fusion = Node(
        package="ylhb_base",
        executable="multisource_fusion_node",
        name="dg_multisource_fusion_node",
        output="screen",
        condition=IfCondition(enable_multisource_fusion),
        parameters=[
            uwb_params_file,
            {
                "local_odom_topic": "/odom",
                "gnss_fix_topic": "/dg/gnss/accepted_fix",
                "gnss_quality_topic": "/dg/gnss/quality",
                "lidar_quality_topic": "/dg/lidar/quality",
                "amcl_pose_topic": "/amcl_pose",
                "scan_match_pose_topic": "/scan_match_pose",
                "match_quality_topic": "/dg/relocalization/match_quality",
                "uwb_pose_topic": "/dg/uwb/pose",
                "uwb_quality_topic": "/dg/uwb/quality",
                "uwb_enabled": ParameterValue(enable_uwb_replay, value_type=bool),
                "uwb_alignment_enabled": ParameterValue(uwb_alignment_enabled, value_type=bool),
                "uwb_to_map_yaw": ParameterValue(uwb_to_map_yaw, value_type=float),
                "uwb_to_map_offset_x": ParameterValue(uwb_to_map_offset_x, value_type=float),
                "uwb_to_map_offset_y": ParameterValue(uwb_to_map_offset_y, value_type=float),
                "fusion_odom_topic": "/dg/fusion/odom",
                "fusion_pose_topic": "/dg/fusion/pose",
                "fusion_status_topic": "/dg/fusion/status",
                "publish_tf": False,
                "gnss_origin_latitude": ParameterValue(gnss_origin_latitude, value_type=float),
                "gnss_origin_longitude": ParameterValue(gnss_origin_longitude, value_type=float),
                "gnss_origin_altitude": ParameterValue(gnss_origin_altitude, value_type=float),
                "map_enu_yaw": ParameterValue(map_enu_yaw, value_type=float),
                "map_enu_offset_x": ParameterValue(map_enu_offset_x, value_type=float),
                "map_enu_offset_y": ParameterValue(map_enu_offset_y, value_type=float),
            },
        ],
    )

    return LaunchDescription(
        [
            DeclareLaunchArgument("enable_nav2", default_value="false", description="Start existing Nav2 launch"),
            DeclareLaunchArgument(
                "enable_cmd_vel_arbiter",
                default_value="false",
                description="Allow DG command output; disabled for observation-only startup",
            ),
            DeclareLaunchArgument(
                "enable_multisource_fusion",
                default_value="true",
                description="Start the DG side-channel multi-source fusion layer",
            ),
            DeclareLaunchArgument(
                "enable_uwb_replay",
                default_value="false",
                description="Replay the saved measured UWB stream into MODEL-1",
            ),
            DeclareLaunchArgument("uwb_replay_file", default_value=default_uwb_replay),
            DeclareLaunchArgument("uwb_replay_rate_hz", default_value="25.0"),
            DeclareLaunchArgument("uwb_replay_loop", default_value="false"),
            DeclareLaunchArgument("uwb_params_file", default_value=default_uwb_params),
            DeclareLaunchArgument("uwb_alignment_enabled", default_value="false"),
            DeclareLaunchArgument("uwb_to_map_yaw", default_value="0.0"),
            DeclareLaunchArgument("uwb_to_map_offset_x", default_value="0.0"),
            DeclareLaunchArgument("uwb_to_map_offset_y", default_value="0.0"),
            DeclareLaunchArgument("gnss_origin_latitude", default_value="nan"),
            DeclareLaunchArgument("gnss_origin_longitude", default_value="nan"),
            DeclareLaunchArgument("gnss_origin_altitude", default_value="0.0"),
            DeclareLaunchArgument("map_enu_yaw", default_value="nan"),
            DeclareLaunchArgument("map_enu_offset_x", default_value="0.0"),
            DeclareLaunchArgument("map_enu_offset_y", default_value="0.0"),
            DeclareLaunchArgument("use_sim_time", default_value="false"),
            DeclareLaunchArgument("map", default_value=default_map),
            DeclareLaunchArgument(
                "params_file",
                default_value=os.path.join(package_share, "config", "nav2_params.yaml"),
            ),
            DeclareLaunchArgument(
                "required_signals",
                default_value="['']",
                description="Optional required health signals, for example ['lidar']",
            ),
            DeclareLaunchArgument(
                "cmd_vel_output_topic",
                default_value="/dg/test_cmd_vel",
                description="Set /cmd_vel only during supervised robot motion validation",
            ),
            GroupAction(
                [SetRemap(src="/cmd_vel", dst="/cmd_vel_nav"), nav2_launch],
                condition=IfCondition(enable_nav2),
            ),
            lidar,
            gnss,
            uwb_replay,
            scan_map,
            relocalization,
            health,
            arbiter,
            multisource_fusion,
        ]
    )
