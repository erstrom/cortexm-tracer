#!/usr/bin/env python

from setuptools import setup

setup(name="cortexm_tracer",
      version="0.1",
      description="Tool for analyzing register dumps from Cortex-m based MCUs",
      url="https://github.com/erstrom/cortexm-tracer",
      author="Erik Stromdahl",
      author_email="erik.stromdahl@gmail.com",
      license="GPLv2",
      long_description="\n",
      entry_points={
        "console_scripts": ["cortexm_tracer=cortexm_tracer.__main__:main"]
      },
      packages=["cortexm_tracer"],
      classifiers=[
        "Development Status :: 4 - Beta",
        "Environment :: Console",
        "License :: GPLv2",
        "Operating System :: POSIX :: Linux",
        "Programming Language :: Python :: 2.7",
        "Programming Language :: Python :: 3.4",
        "Topic :: Software Development"
      ]
)
