cmake_minimum_required(VERSION 3.16)
project(dg_hvs_bridge)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
if(CMAKE_COMPILER_IS_GNUCXX OR CMAKE_CXX_COMPILER_ID MATCHES "Clang")
  add_compile_options(-Wall -Wextra -Wpedantic)
endif()

find_package(ament_cmake REQUIRED)
find_package(rclcpp REQUIRED)
find_package(sensor_msgs REQUIRED)
find_package(diagnostic_msgs REQUIRED)
find_package(OpenCV REQUIRED COMPONENTS core imgproc imgcodecs)

set(HV_TOOLKIT_ROOT "$ENV{HV_TOOLKIT_ROOT}" CACHE PATH
    "Root of shimetapi_hybrid_vision_toolkit on the RDK X5")
if(NOT HV_TOOLKIT_ROOT)
  message(FATAL_ERROR
    "HV_TOOLKIT_ROOT is required. Point it at shimetapi_hybrid_vision_toolkit and build on RDK X5.")
endif()

set(HV_INCLUDE_DIR "${HV_TOOLKIT_ROOT}/include")
set(HV_LIB_DIR "${HV_TOOLKIT_ROOT}/lib/x5")
foreach(component core codec io hv)
  set(versioned_library "${HV_LIB_DIR}/libshimetapi_${component}.so.2.0.0")
  if(NOT EXISTS "${versioned_library}")
    message(FATAL_ERROR "Missing ShiMetaPi X5 library: ${versioned_library}")
  endif()
  add_library(shimetapi_${component} SHARED IMPORTED)
  set_target_properties(shimetapi_${component} PROPERTIES
    IMPORTED_LOCATION "${versioned_library}"
    INTERFACE_INCLUDE_DIRECTORIES "${HV_INCLUDE_DIR}")
endforeach()

add_executable(dg_hvs_bridge_node src/dg_hvs_bridge_node.cpp)
target_include_directories(dg_hvs_bridge_node PRIVATE ${OpenCV_INCLUDE_DIRS})
target_link_libraries(dg_hvs_bridge_node
  shimetapi_hv shimetapi_io shimetapi_codec shimetapi_core ${OpenCV_LIBS})
target_link_options(dg_hvs_bridge_node PRIVATE -Wl,--allow-shlib-undefined)
ament_target_dependencies(dg_hvs_bridge_node rclcpp sensor_msgs diagnostic_msgs)
set_target_properties(dg_hvs_bridge_node PROPERTIES
  BUILD_RPATH "${HV_LIB_DIR}"
  INSTALL_RPATH "${HV_LIB_DIR};$ORIGIN"
  INSTALL_RPATH_USE_LINK_PATH TRUE)

install(TARGETS dg_hvs_bridge_node DESTINATION lib/${PROJECT_NAME})
install(DIRECTORY config launch DESTINATION share/${PROJECT_NAME})
install(PROGRAMS scripts/run_hvs_capture_session.sh DESTINATION lib/${PROJECT_NAME})

ament_package()
