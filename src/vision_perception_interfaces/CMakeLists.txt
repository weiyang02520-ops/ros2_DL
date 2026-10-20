cmake_minimum_required(VERSION 3.8)
project(vision_perception_interfaces)

find_package(ament_cmake REQUIRED)
find_package(rosidl_default_generators REQUIRED)
find_package(std_msgs REQUIRED)
find_package(geometry_msgs REQUIRED)
find_package(vision_msgs REQUIRED)

rosidl_generate_interfaces(${PROJECT_NAME}
  "msg/VisionDetection2D.msg"
  "msg/VisionDetectionArray.msg"
  "msg/VisionObject.msg"
  "msg/VisionObjectArray.msg"
  DEPENDENCIES std_msgs geometry_msgs vision_msgs
)

install(FILES
  INTERFACE_CONTRACT.md
  README.md
  package.xml
  DESTINATION share/${PROJECT_NAME}
)

ament_export_dependencies(rosidl_default_runtime)
ament_package()
