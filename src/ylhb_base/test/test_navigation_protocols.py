import ast
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
LAUNCH = ROOT / "launch" / "dg_navigation_integration.launch.py"
UWB_EVIDENCE_LAUNCH = ROOT / "launch" / "uwb_model1_replay_evidence.launch.py"
CMAKE = ROOT / "CMakeLists.txt"
REPOSITORY_ROOT = ROOT.parents[1]
DG_RUNNER = REPOSITORY_ROOT / "scripts" / "run_dg_integration.sh"


class NavigationProtocolAndLaunchTests(unittest.TestCase):
    def test_all_new_python_files_parse_without_ros_imports_at_module_scope(self) -> None:
        for path in (
            SCRIPTS / "navigation_health_core.py",
            SCRIPTS / "navigation_health_node.py",
            SCRIPTS / "cmd_vel_arbiter_core.py",
            SCRIPTS / "cmd_vel_arbiter_node.py",
            SCRIPTS / "uwb_input.py",
            SCRIPTS / "uwb_replay_node.py",
            SCRIPTS / "invalid_candidate_injector_node.py",
            LAUNCH,
            UWB_EVIDENCE_LAUNCH,
        ):
            ast.parse(path.read_text(encoding="utf-8"))

    def test_launch_contains_all_integration_nodes(self) -> None:
        text = LAUNCH.read_text(encoding="utf-8")
        for executable in (
            "lidar_robust_node",
            "gnss_quality_node",
            "scan_map_relocalization_node",
            "active_relocalization_node",
            "navigation_health_node",
            "cmd_vel_arbiter_node",
            "uwb_replay_node",
        ):
            self.assertIn(f'executable="{executable}"', text)

    def test_launch_has_explicit_topic_boundaries(self) -> None:
        text = LAUNCH.read_text(encoding="utf-8")
        for topic in (
            "/scan",
            "/odom",
            "/gps/fix",
            "/gps/rtk_status",
            "/dg/lidar/quality",
            "/dg/lidar/filtered_scan",
            "/dg/lidar/stable_features",
            "/dg/gnss/quality",
            "/dg/relocalization/seed",
            "/dg/relocalization/match_quality",
            "/cmd_vel_nav",
            "/cmd_vel_recovery",
            "/cmd_vel",
            "/dg/navigation/status",
        ):
            self.assertIn(topic, text)
        self.assertEqual(text.count('"scan_topic": "/dg/lidar/filtered_scan"'), 2)
        self.assertRegex(
            text,
            r'DeclareLaunchArgument\(\s*"enable_scan_map"',
        )

    def test_launch_defaults_nav2_disabled_and_remaps_cmd_vel(self) -> None:
        text = LAUNCH.read_text(encoding="utf-8")
        self.assertIn('DeclareLaunchArgument("enable_nav2", default_value="false"', text)
        self.assertIn('SetRemap(src="/cmd_vel", dst="/cmd_vel_nav")', text)
        self.assertIn('default_map = preferred_map if os.path.exists(preferred_map) else fallback_map', text)
        self.assertIn('DeclareLaunchArgument("map", default_value=default_map)', text)
        self.assertNotIn('DeclareLaunchArgument("map", default_value="")', text)

    def test_launch_defaults_motion_output_and_uwb_alignment_disabled(self) -> None:
        text = LAUNCH.read_text(encoding="utf-8")
        self.assertIn('"enable_cmd_vel_arbiter",', text)
        self.assertIn('default_value="/dg/test_cmd_vel"', text)
        self.assertIn('condition=IfCondition(enable_cmd_vel_arbiter)', text)
        self.assertIn('"enable_uwb_replay",', text)
        self.assertIn('DeclareLaunchArgument("uwb_alignment_enabled", default_value="false")', text)

    def test_uwb_evidence_launch_is_isolated_and_marks_test_frame(self) -> None:
        text = UWB_EVIDENCE_LAUNCH.read_text(encoding="utf-8")
        self.assertIn('executable="uwb_replay_node"', text)
        self.assertIn('executable="multisource_fusion_node"', text)
        self.assertIn('"uwb_alignment_enabled": True', text)
        self.assertIn('default_value="uwb_replay_test"', text)
        self.assertIn('default_value="uwb_replay_tag_test"', text)
        self.assertIn('"publish_tf": False', text)
        self.assertNotIn("cmd_vel", text)
        for disabled_input in (
            "/dg/evidence/no_local_odom",
            "/dg/evidence/no_gnss_fix",
            "/dg/evidence/no_amcl_pose",
            "/dg/evidence/no_scan_match_pose",
        ):
            self.assertIn(disabled_input, text)

    def test_uwb_evidence_wrapper_has_scenarios_and_no_motion_command(self) -> None:
        text = (REPOSITORY_ROOT / "scripts" / "run_uwb_model1_evidence.sh").read_text(
            encoding="utf-8"
        )
        for scenario in ("static", "move", "anchor_fault"):
            self.assertIn(scenario, text)
        self.assertIn("dg_uwb_evidence", text)
        self.assertNotIn("topic pub", text)
        self.assertNotIn("/cmd_vel", text)

    def test_fusion_wrapper_publishes_configured_output_frame(self) -> None:
        text = (SCRIPTS / "multisource_fusion_node.py").read_text(encoding="utf-8")
        self.assertIn('self.declare_parameter("output_frame_id", "map")', text)
        self.assertIn('self.declare_parameter("unanchored_output_frame_id", "odom")', text)
        self.assertIn("odom.header.frame_id = frame_id", text)
        self.assertIn("odom.child_frame_id = self._output_child_frame_id", text)
        self.assertIn('"output_frame_id": frame_id', text)

    def test_cmake_installs_new_wrappers_and_registers_tests(self) -> None:
        text = CMAKE.read_text(encoding="utf-8")
        for script in (
            "navigation_health_core.py",
            "navigation_health_node.py",
            "cmd_vel_arbiter_core.py",
            "cmd_vel_arbiter_node.py",
            "uwb_input.py",
            "uwb_replay_node.py",
            "invalid_candidate_injector_node.py",
        ):
            self.assertIn(f"scripts/{script}", text)
        for test_name in (
            "test_navigation_health_core",
            "test_cmd_vel_arbiter_core",
            "test_navigation_integration_core",
            "test_navigation_protocols",
        ):
            self.assertIn(test_name, text)

    def test_default_bringup_does_not_include_competition_launch(self) -> None:
        text = (ROOT / "launch" / "bringup.launch.py").read_text(encoding="utf-8")
        self.assertNotIn("dg_navigation_integration", text)

    def test_dg_runner_loads_base_then_isolated_overlay(self) -> None:
        text = DG_RUNNER.read_text(encoding="utf-8")
        base_source = 'source "${base_ws}/install/setup.bash"'
        integration_source = 'source "${integration_ws}/install/setup.bash"'
        self.assertIn(base_source, text)
        self.assertIn(integration_source, text)
        self.assertLess(text.index(base_source), text.index(integration_source))
        self.assertIn("dg_navigation_integration.launch.py", text)
        self.assertNotIn("topic pub", text)

    def test_active_relocalization_default_cmd_vel_remains_compatible(self) -> None:
        text = (SCRIPTS / "active_relocalization_node.py").read_text(encoding="utf-8")
        self.assertIn('"cmd_vel_topic": "/cmd_vel"', text)

    def test_gnss_is_not_wired_into_ekf_by_integration_launch(self) -> None:
        text = LAUNCH.read_text(encoding="utf-8")
        self.assertNotIn("ekf.yaml", text)
        self.assertNotIn("NavSatTransform", text)

    def test_controlled_invalid_candidate_tool_has_no_motion_interface(self) -> None:
        text = (SCRIPTS / "invalid_candidate_injector_node.py").read_text(encoding="utf-8")
        self.assertIn("DiagnosticArray", text)
        self.assertIn("CONTROLLED_INVALID_CANDIDATE", text)
        self.assertNotIn("Twist", text)
        self.assertNotIn("/cmd_vel", text)

    def test_poc_publishers_and_health_parser_share_real_field_names(self) -> None:
        lidar = (SCRIPTS / "lidar_robust_features.py").read_text(encoding="utf-8")
        gnss = (SCRIPTS / "gnss_quality_node.py").read_text(encoding="utf-8")
        scan_map = (SCRIPTS / "scan_map_relocalization_node.py").read_text(encoding="utf-8")
        active = (SCRIPTS / "active_relocalization_node.py").read_text(encoding="utf-8")
        health = (SCRIPTS / "navigation_health_node.py").read_text(encoding="utf-8")
        for field in ("valid_ratio", "geometry_score", "temporal_status"):
            self.assertIn(field, lidar)
        for field in ("current_state", "decision"):
            self.assertIn(field, gnss)
        for field in ("accepted", "score", "mean_distance", "inlier_ratio", "candidate_x", "candidate_y", "candidate_yaw", "reason"):
            self.assertIn(field, scan_map)
        for field in ("state", "attempt_id", "request_candidate", "seed_source"):
            self.assertIn(field, active)
        for field in ("gnss_state", "lidar_state", "uwb_state", "amcl_state", "scan_match_state", "relocalization_state", "overall_state", "reasons", "timestamp"):
            self.assertIn(field, health)

    def test_health_and_arbiter_have_freshness_guards(self) -> None:
        health = (SCRIPTS / "navigation_health_node.py").read_text(encoding="utf-8")
        arbiter = (SCRIPTS / "cmd_vel_arbiter_node.py").read_text(encoding="utf-8")
        core = (SCRIPTS / "cmd_vel_arbiter_core.py").read_text(encoding="utf-8")
        self.assertIn('"min_lidar_quality", 0.2', health)
        self.assertIn("relocalization_fresh", health)
        self.assertIn('"status_timeout", 1.0', arbiter)
        self.assertIn("navigation_status_received_at", arbiter)
        self.assertIn("NAVIGATION_STATUS_STALE", core)


if __name__ == "__main__":
    unittest.main()
