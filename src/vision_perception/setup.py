"""Install the independent perception shell and its launch/config assets."""

from glob import glob

from setuptools import setup


PACKAGE_NAME = "vision_perception"

setup(
    name=PACKAGE_NAME,
    version="0.0.1",
    packages=[PACKAGE_NAME],
    data_files=[
        ("share/ament_index/resource_index/packages", ["resource/" + PACKAGE_NAME]),
        ("share/" + PACKAGE_NAME, ["package.xml", "README.md"]),
        ("share/" + PACKAGE_NAME + "/launch", glob("launch/*.launch.py")),
        ("share/" + PACKAGE_NAME + "/config", glob("config/*.yaml")),
    ],
    install_requires=["setuptools"],
    zip_safe=True,
    maintainer="liaojingwu20041031",
    maintainer_email="206929594+liaojingwu20041031@users.noreply.github.com",
    description="Independent manipulation-vision scaffold without inference or control.",
    license="Apache-2.0",
    entry_points={
        "console_scripts": [
            "vision_perception_node = vision_perception.vision_node:main",
        ],
    },
)
