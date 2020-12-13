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
        'write_to_template': '__version__ = "{version}"',
    },
    setup_requires = ['setuptools_scm'],
    author="Fabien Parent",
    author_email="fparent@baylibre.com",
    description="RITY tools",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://gitlab.com/baylibre/rich-iot/tools/rity-tools",
    packages=setuptools.find_packages(),
    scripts=[
        'tools/rity-board',
        'tools/rity-config',
        'tools/rity-flash',
    ],
    install_requires=[
        'aiot-bootrom @ git+https://gitlab.com/mediatek/aiot/bsp/aiot-bootrom#aiot_bootrom',
        'gpiod',
        'oyaml',
        'pyftdi',
        'pyusb',
    ],
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires='>=3.8',
)
