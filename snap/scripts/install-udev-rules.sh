# scripts/install-udev-rules.sh
#!/bin/bash

RULE_FILE="/etc/udev/rules.d/72-aiot.rules"

USERNAME=$(logname)

if groups "$USERNAME" | grep -qw dialout; then
  echo "✅ User '$USERNAME' is already in the 'dialout' group."
else
  echo "➕ Adding user '$USERNAME' to the 'dialout' group for USB device access..."
  sudo usermod -aG dialout "$USERNAME"
fi

echo "🔧 Installing udev rules for Mediatek Genio devices..."

sudo tee "$RULE_FILE" > /dev/null <<EOR
SUBSYSTEM=="usb", ATTR{idVendor}=="0e8d", ATTR{idProduct}=="201c", MODE="0660", TAG+="uaccess"
SUBSYSTEM=="usb", ATTR{idVendor}=="0e8d", ATTR{idProduct}=="0003", MODE="0660", TAG+="uaccess"
SUBSYSTEM=="usb", ATTR{idVendor}=="0403", MODE="0660", TAG+="uaccess"
SUBSYSTEM=="gpio", MODE="0660", TAG+="uaccess"
EOR

echo "🔄 Reloading udev rules..."
sudo udevadm control --reload-rules
sudo udevadm trigger

echo "✅ udev rules successfully installed."
echo "🔌 Please **reconnect your USB device** to apply the new rules."
echo "🚪 Please **log out and log back in** (or open a new terminal) for group changes to take effect."
