#!/bin/zsh

set -eu

SCRIPT_PATH=${(%):-%N}
SCRIPT_DIR=${SCRIPT_PATH:A:h}
PROJECT_DIR=${SCRIPT_DIR:h}
APK="$PROJECT_DIR/build/BimanualController.apk"
PACKAGE=com.NYU.Bimanual.Controller

if ! command -v adb >/dev/null 2>&1; then
  print -u2 "adb is missing. Install it with: brew install --cask android-platform-tools"
  exit 1
fi

DEVICE_COUNT=$(adb devices | awk 'NR > 1 && $2 == "device" {count++} END {print count+0}')
if [[ "$DEVICE_COUNT" -ne 1 ]]; then
  print -u2 "Expected exactly one authorized Quest, found $DEVICE_COUNT."
  print -u2 "Connect Quest 2 by USB, unlock it, and approve USB debugging."
  adb devices -l
  exit 1
fi

print "Installing $APK"
adb install -r "$APK"

if adb shell pm list packages "$PACKAGE" | grep -q "package:$PACKAGE"; then
  print "Installed package: $PACKAGE"
else
  print -u2 "adb returned success but $PACKAGE was not found on the Quest."
  exit 1
fi
