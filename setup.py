#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright 2020 BayLibre, SAS.

import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name="rity-tools",
    use_scm_version={
        'write_to': 'rity/version.py',
    },
    setup_requires = ['setuptools_scm'],
    author="Fabien Parent",
    author_email="fparent@baylibre.com",
    description="RITY tools",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://gitlab.com/baylibre/rich-iot/tools/rity-tools",
    packages=setuptools.find_packages(),
    entry_points={
        'console_scripts': [
            'rity-config=rity.config:main',
            'rity-flash=rity.flash:main',
            'rity-board=rity.board:main',
        ]},
    install_requires=[
        'aiot-bootrom @ git+https://gitlab.com/mediatek/aiot/bsp/aiot-bootrom#aiot_bootrom',
        'gpiod==1.4.0',
        'oyaml',
        'packaging',
        'pyftdi',
        'pyusb',
        'pysimg @ git+https://github.com/dlenski/PySIMG#egg=pysimg',
    ],
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires='>=3.6',
)
