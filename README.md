# Genio Tools

The Genio tools are a set of tools to flash, control or configure MediaTek
boards, and in particular the Genio evaluation kits.

Please refer to
[IoT Yocto Develop Guide](https://mediatek.gitlab.io/aiot/doc/aiot-dev-guide/master/tools/genio-tools.html)
for usage.

## Release Notes

### Version 1.6

Released in 2025/03/31, version 1.6 provide the following updates:

1. `genio-flash --list` now shows dtbo that will be auto-loaded.
2. Add `genio-flash --unload-dtbo` argument to allow disabling
   specific auto-load dtbo files.
3. Add support for "RAW Image Type"

#### Raw Image support

If a `raw_image.json` is given, use the json file
as partition file setting.

If not given, this image type checks a default set
of image binary names. The name came from the
MediaTek internal conversion tool.
Refer to the document named
"Converting Android Image to RAW Image and Flashing Using Public Tool"
for details.

### Version 1.5

- `genio-flash` now supports `--daemon` mode to flash multiple boards.
- New `genio-multi-download-cli` command to interact with the genio-flash daemon
  in a text-based UI.
- Add new argument `--skip-erase` to `genio-flash` to skip erasing the storage
  when flashing boards.
- Support `genio-board power` on Windows.
