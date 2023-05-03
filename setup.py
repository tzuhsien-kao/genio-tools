#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright 2020 BayLibre, SAS.

import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name="genio-tools",
    use_scm_version={
        'write_to': 'aiot/version.py',
        'local_scheme':'no-local-version'
    },
    setup_requires = ['setuptools_scm'],
    author="Fabien Parent",
    maintainer="Pablo Sun",
    maintainer_email="pablo.sun@mediatek.com",
    description="Tools for flashing boards using MediaTek Genio SoCs",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://gitlab.com/mediatek/aiot/bsp/genio-tools",
    packages=setuptools.find_packages(),
    entry_points={
        'console_scripts': [
            'aiot-config=aiot.config:main',
            'aiot-flash=aiot.flash:main',
            'aiot-board=aiot.board:main',
            'aiot-efuse=aiot.efuse:main',
            'aiot-rpmb-write-key=aiot.rpmb:main',
            'genio-config=aiot.config:main',
            'genio-flash=aiot.flash:main',
            'genio-board=aiot.board:main',
            'genio-efuse=aiot.efuse:main',
            'genio-rpmb-write-key=aiot.rpmb:main',
        ]},
    install_requires=[
        'genio-bootrom',
        'gpiod==1.4.0',
        'oyaml',
        'packaging',
        'pyftdi',
        'pyusb',
        'pyudev;platform_system=="Linux"',
    ],
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires='>=3.7',
)
