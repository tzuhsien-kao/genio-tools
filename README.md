# Genio Tools

The Genio tools are a set of utilities to flash, control, and configure MediaTek
boards, in particular the Genio evaluation kits.

These tools are typically used during board bring-up, firmware flashing, and
system development for Genio-based platforms.

## Installation

This tool depends on the **fastboot** utility and drivers.

Please refer to [IoT Yocto Develop Guide](https://mediatek.gitlab.io/aiot/doc/aiot-dev-guide/master/tools/genio-tools.html)
to setup drivers and tool dependencies before installing Genio Tools.

## Usage

After installation, then following command-line utilities are available:

- `genio-flash`
- `genio-board`

Below are a few common examples. For detailed options, use `--help` on each
command or refer to the online documentation.

To flash an IoT Yocto image, unarchive the tarball first, then:

```bash
cd path/to/image/directory
genio-flash
```

or:

```bash
genio-flash -P path/to/image/directory
```

For full documentation, please refer to the
[IoT Yocto Develop Guide](https://mediatek.gitlab.io/aiot/doc/aiot-dev-guide/master/tools/genio-tools.html).

## Release Notes

### Version 1.7

Released on 2025-12-29, version 1.7 provides the following updates:

1. Support for the
   [Genio 520](https://genio.mediatek.com/genio-520) and
   [Genio 720](https://genio.mediatek.com/genio-720) SoC families.
2. Fix the failure caused by using `-P` and `-daa` in conjunction.
3. Add a timeout mechanism for multi-download scenarios.
4. Improved support for AOSP Android "RITA" images, including erasing
   arbitrary partitions that are not in the image list.
5. Fix out-of-order logs when launched non-interactively on Windows.

### Version 1.6

Released on 2025-03-31, version 1.6 provides the following updates:

1. `genio-flash --list` now shows dtbo files that will be auto-loaded.
2. Add the `genio-flash --unload-dtbo` argument to allow disabling
   specific auto-load dtbo files.
3. Add support for the "RAW Image Type".

#### RAW Image support

If a `raw_image.json` is provided, the JSON file will be used as the
partition file configuration.

If no JSON file is given, this image type checks a default set of image
binary names. The names come from the MediaTek internal conversion tool.
Refer to the document titled
"Converting Android Image to RAW Image and Flashing Using Public Tool"
for more details.

### Version 1.5

- `genio-flash` now supports `--daemon` mode to flash multiple boards.
- New `genio-multi-download-cli` command to interact with the `genio-flash`
  daemon via a text-based UI.
- Add a new argument `--skip-erase` to `genio-flash` to skip erasing the
  storage when flashing boards.
- Support `genio-board power` on Windows.
