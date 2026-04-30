from setuptools import setup, find_packages

setup(
    name="vex",
    version="0.3.0",
    description="Version generator for make/cmake projects",
    packages=find_packages(),
    python_requires=">=3.10",
    entry_points={
        "console_scripts": [
            "vex=vex.cli:main",
        ],
    },
)
