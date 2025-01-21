# Genio Tools

The Genio tools are a set of tools to flash, control or configure MediaTek
boards, and in particular the Genio evaluation kits.

Please refer to 
[IoT Yocto Develop Guide](https://mediatek.gitlab.io/aiot/doc/aiot-dev-guide/master/tools/genio-tools.html)
for usage.

## Release Notes

### Version 1.5

- `genio-flash` now supports `--daemon` mode to flash multiple boards.
- New `genio-multi-download-cli` command to interact with the genio-flash daemon
  in a text-based UI.
- Add new argument `--skip-erase` to `genio-flash` to skip erasing the storage
  when flashing boards.
- Support `genio-board power` on Windows.
