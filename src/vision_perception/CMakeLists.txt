cmake_minimum_required(VERSION 3.8)
project(vision_perception)

# Hybrid ament_cmake + ament_cmake_python so `ament_package()` generates
# ament_prefix_path environment hooks. Pure setuptools ament_python installs on
# this workspace were left with package.dsv containing only pythonpath, which
# broke `ros2 pkg prefix` / launch after `source install/setup.bash`.
#
# Note: ament_python_install_package() generates its own setup.py without
# setuptools entry_points, so console scripts are installed explicitly below
# into lib/${PROJECT_NAME}/ (required by ros2 launch / libexec).

find_package(ament_cmake REQUIRED)
find_package(ament_cmake_python REQUIRED)

ament_python_install_package(${PROJECT_NAME})

install(DIRECTORY launch config examples evidence
  DESTINATION share/${PROJECT_NAME}
)

install(FILES
  package.xml
  README.md
  requirements-runtime.txt
  .gitattributes
  DESTINATION share/${PROJECT_NAME}
)

install(FILES
  scripts/bootstrap_isolated_ws.sh
  scripts/check_ament_prefix_hook.sh
  scripts/ensure_scripts_executable.sh
  DESTINATION share/${PROJECT_NAME}/scripts
  PERMISSIONS OWNER_READ OWNER_WRITE OWNER_EXECUTE GROUP_READ GROUP_EXECUTE WORLD_READ WORLD_EXECUTE
)

# ROS 2 libexec location for package executables.
# Explicit PERMISSIONS: zip/SFTP often drops +x on the source tree; with
# colcon --symlink-install the install path is a symlink to that source file,
# so a copy-time mode alone is not enough — see install(CODE) chmod below.
install(PROGRAMS
  scripts/vision_perception_node
  scripts/vision_offline_detect
  scripts/vision_offline_objects
  scripts/vision_offline_track
  scripts/vision_webcam_publisher
  scripts/vision_fake_image_publisher
  scripts/vision_fake_depth_publisher
  DESTINATION lib/${PROJECT_NAME}
  PERMISSIONS OWNER_READ OWNER_WRITE OWNER_EXECUTE GROUP_READ GROUP_EXECUTE WORLD_READ WORLD_EXECUTE
)

# Force +x on installed libexec after every install. Follows symlinks, so
# --symlink-install also repairs the source bit lost after zip/SFTP.
#
# IMPORTANT: do NOT expand a CMake list (semicolon-separated) into install(CODE)
# via ${_LIST} — cmake_install.cmake treats ';' as statement separators and
# truncates the foreach. Use a bracket argument + foreach(... IN ITEMS ...).
install(CODE [[
  set(_vision_libexec "$ENV{DESTDIR}${CMAKE_INSTALL_PREFIX}/lib/vision_perception")
  foreach(_name IN ITEMS
      vision_perception_node
      vision_offline_detect
      vision_offline_objects
      vision_offline_track
      vision_webcam_publisher
      vision_fake_image_publisher
      vision_fake_depth_publisher
    )
    set(_path "${_vision_libexec}/${_name}")
    if(EXISTS "${_path}")
      execute_process(
        COMMAND chmod a+x "${_path}"
        RESULT_VARIABLE _vision_chmod_res
      )
      if(NOT _vision_chmod_res EQUAL 0)
        message(WARNING "chmod a+x failed for ${_path} (res=${_vision_chmod_res})")
      endif()
    else()
      message(WARNING "expected libexec script missing at install time: ${_path}")
    endif()
  endforeach()
]])

ament_package()
