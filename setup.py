#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright 2020 BayLibre, SAS.

import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name="aiot-tools",
    use_scm_version={
        'write_to': 'aiot/version.py',
    },
    setup_requires = ['setuptools_scm'],
    author="Fabien Parent",
    author_email="fparent@baylibre.com",
    description="aiot tools",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://gitlab.com/mediatek/aiot/bsp/aiot-tools",
    packages=setuptools.find_packages(),
    entry_points={
        'console_scripts': [
            'aiot-config=aiot.config:main',
            'aiot-flash=aiot.flash:main',
            'aiot-board=aiot.board:main',
        ]},
    install_requires=[
        'aiot-bootrom @ git+https://gitlab.com/mediatek/aiot/bsp/aiot-bootrom#aiot_bootrom',
        'gpiod==1.4.0',
        'oyaml',
        'packaging',
        'pyftdi',
        'pyusb',
        'pyudev',
    ],
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires='>=3.7',
)
