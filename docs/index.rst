Genio tools manual
#################

Overview
********

Genio tools is a set of tools to configure or interact with MediaTek boards.
The Genio tools are written in `Python`_. You need to have Python 3 installed on
your system. The Genio tools have been tested with Python >= 3.7, they may work
with older versions of Python, but are untested against these older Python
releases.

For now the tools only work on Linux.

.. _Python: https://www.python.org/

Genio tools is composed of 4 tools:

	* aiot-board: tool to control the board (reset / power / download signals)
	* aiot-config: tool to setup your host system in order to be able to communicate with MediaTek's boards
	* aiot-flash: tool to flash a board with a RITY or RITA image

Prerequisites
*************

In order to install the Genio tools you must have `python3 >= 3.7` and
`pip3 >= 20.3` installed on your system. You can check their versions
by running the following commands:

.. prompt:: bash $ auto

	$ python3 --version
	Python 3.9.2
	$ pip3 --version
	pip 21.2.4 from /usr/bin/pip3 (python 3.9)

If your version of `pip3` is older than 20.3. Please upgrade it by running:

.. prompt:: bash $

	pip3 install --upgrade pip

Linux
=====

Please refer to your Linux distribution documentation in order to check
how to install `python3` and `pip3`.


Windows
=======

You can install `python3` and `pip3` from https://www.python.org/downloads/.

.. note::

	Make sure to check the "Add Python 3.X to PATH" in order to be able
	to access the Genio tools from any directory. If you installed Python
	from the Windows Store, you will need to manually add Python's Scripts
	to the PATH variable.

Genio tools are using fastboot to flash, so you also need to install the
fastboot driver and the fastboot executable. Please follow the following
guides to install the fastboot platform-tools and the fastboot driver:

* https://developer.android.com/studio/releases/platform-tools
* https://developer.android.com/studio/run/win-usb

Installation
************

To install `aiot-tools` and its dependencies please run the following command:

.. prompt:: bash $

	pip3 install -U -e "git+https://gitlab.com/mediatek/aiot/bsp/aiot-tools.git#egg=aiot-tools"

Using Two-factor authentication
===============================

For Two-factor authentication you need to create personal access tokens on
gitlab. These can then be used to login during installation instead of the
account password. See the gitlab documentation about [Personal access
tokens](https://docs.gitlab.com/ee/user/profile/personal_access_tokens.html)
for information on how to create one.

Tools
*****

This section will describe the usage of every Genio tool.

aiot-board
==========

.. warning::

	This tool is currently only supported on Linux

This tool is used to control MediaTek boards. It uses the `FTDI`_ chip that
provides the serial console to also control the reset / power / download
GPIO lines.

.. note::

	Not all the boards can be controlled with this tool. Please check your
	board documentation to know whether this tools can control your board.

.. _FTDI: https://www.ftdichip.com/

Configuration of the FTDI chip
------------------------------

In order to be able to control the GPIO lines, the FTDI chip must be properly
configured. Run the following command to configure the FTDI chip:

.. prompt:: bash $

	aiot-board program-ftdi --ftdi-product-name <board_name> \
	                          --gpio-power <power_gpio> \
	                          --gpio-reset <reset_gpio> \
	                          --gpio-download <download_gpio>

Please replace `<board_name>`, `<power_gpio>`, `<reset_gpio>`,
and `<download_gpio>` with the values corresponding to your board. You can
check your `board documentation`_ to know the values to use.

.. _board documentation: https://mediatek.gitlab.io/aiot/rity/meta-mediatek-bsp/boards/index.html

.. note::

	Only one board should be connected to the host when trying to program
	a FTDI chip. If more than one FTDI chip is detected, the tool will quit.

For example for the `i500-pumpkin` board, the command would be:

.. prompt:: bash $

	aiot-board program-ftdi --ftdi-product-name i500-pumpkin \
	                          --gpio-power 0 \
	                          --gpio-reset 1 \
	                          --gpio-download 2

.. warning::

	Be careful, configuring bad values into your FTDI chip could potentially
	brick your board.

Configuring the FTDI chip should only be done once per board.

Reset the board
---------------

In order to reset the board you can run the following command:

.. prompt:: bash $

	aiot-board reset --gpio-power <power_gpio> \
	                   --gpio-reset <reset_gpio> \
	                   --gpio-download <download_gpio>

Reset in download mode
----------------------

In order to reset the board and boot it in download mode you can run the
following command:

.. prompt:: bash $

	aiot-board download --gpio-power <power_gpio> \
	                      --gpio-reset <reset_gpio> \
	                      --gpio-download <download_gpio>

Power the board
---------------

To simulate pressing the power button (for 1 second), you can run the following
command:

.. prompt:: bash $

	aiot-board power --gpio-power <power_gpio> \
	                   --gpio-reset <reset_gpio> \
	                   --gpio-download <download_gpio>

Default values for the GPIOs
----------------------------

It is not necessary to set the `--gpio-power`, `--gpio-reset`,
and `--gpio-download` parameters if they match the default values. Please
check the default values used by the tool below:

+-----------------+-----------------+---------------+
| Parameter       | Parameter alias | Default value |
+=================+=================+===============+
| --gpio-power    | -p              | 0             |
+-----------------+-----------------+---------------+
| --gpio-reset    | -r              | 1             |
+-----------------+-----------------+---------------+
| --gpio-download | -d              | 2             |
+-----------------+-----------------+---------------+

aiot-config
===========

This tool is used to check the configuration of the host environment.

You run the following command to check that your environment is correctly
configured:

.. prompt:: bash $ auto

	 $ aiot-config
	 fastboot: OK
	 udev rules: OK

In case your environment is not setup correctly, the tool will give you some
instructions on how to correctly configure it.

aiot-flash
==========

This tool allows you to flash your board. `aiot-flash` supports flashing
Yocto images (RITY), and Android images (RITA).

You can flash an image by running the following command:

.. prompt:: bash $

	aiot-flash

The tool will try to find an image to flash in your current working directory.
If you want to flash an image in a different path your can use the `--path`
parameter:

.. prompt:: bash $

	aiot-flash --path /path/to/image

It is possible to flash invidual partitions by using:

.. prompt:: bash $

	aiot-flash <partition1> <partition2> <partitionX>

or

.. prompt:: bash $

	aiot-flash <partition1>:/path/to/file1 <partition2>:/path/to/file2

Yocto images
------------

Select an image
^^^^^^^^^^^^^^^

A few options are specific to flashing Yocto images. If your build folder
contains more than one image you can specify which image to flash by
using the `--image` parameter.

.. prompt:: bash $

	aiot-flash --image aiot-bringup-image

or

.. prompt:: bash $

	aiot-flash -i aiot-bringup-image

Load a DTBO
'''''''''''

When flashing you can also choose the Device-Tree Blob Overlays you wish
to be automatically loaded at boot:

.. prompt:: bash $

	aiot-flash --load-dtbo <dtbo_name> --load-dtbo <another_dtbo_name>

List available DTBO
'''''''''''''''''''

To know which DTBO is available with your image you can run the following
command:

.. prompt:: bash $

	aiot-flash --list-dtbo


Interactively choose DTBO
'''''''''''''''''''''''''

Instead of specifying the DTBO to load you can also run `aiot-flash` in
interactive mode:

.. prompt:: bash $

	aiot-flash --interactive

or

.. prompt:: bash $

	aiot-flash -I


Android images
--------------

When flashing an Android image you can select the DTBO by using the following
command:

.. prompt:: bash $

	aiot-flash --dtbo-index <dtbo_index>

Please check your RITA board documentation to check the available DTBO indexes.

Bootstrap configuration
-----------------------

In case your bootstrap has a configuration different from the default values,
you can use the following parameter:

.. prompt:: bash $

	aiot-flash --bootstrap lk.bin --bootstrap-addr 0x201000 \
	             --bootstrap-mode aarch64

Board control
-------------

If your board supports `aiot-board`, `aiot-flash` will also be able to
control the reset and download GPIOs. You can flash and control your
board using the following command:

.. prompt:: bash $

	aiot-flash --gpio-power <power_gpio> \
	             --gpio-reset <reset_gpio> \
	             --gpio-download <download_gpio>

.. warning::

	Board control is currently only supported on Linux
