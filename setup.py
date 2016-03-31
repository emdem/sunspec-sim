"""
Setup module
"""

from setuptools import setup, find_packages

setup(
    name="sunspec_sim",
    version="0.0.1",
    author="Emre Demirors",
    package=find_packages(),
    setup_requires=["modbus_tk"]
)
