#!/bin/zsh

set -e

SCRIPT_PATH=${(%):-%N}
SCRIPT_DIR=${SCRIPT_PATH:A:h}
PLIST_NAME=com.openteach.quest-launcher.plist
SOURCE_PLIST="$SCRIPT_DIR/$PLIST_NAME"
TARGET_PLIST="$HOME/Library/LaunchAgents/$PLIST_NAME"

mkdir -p "$HOME/Library/LaunchAgents" "$HOME/Library/Logs"
plutil -lint "$SOURCE_PLIST"

launchctl bootout "gui/$UID/com.openteach.quest-launcher" 2>/dev/null || true
sleep 1
cp "$SOURCE_PLIST" "$TARGET_PLIST"
chmod 644 "$TARGET_PLIST"
if ! launchctl bootstrap "gui/$UID" "$TARGET_PLIST"; then
    sleep 2
    launchctl bootstrap "gui/$UID" "$TARGET_PLIST"
fi
launchctl enable "gui/$UID/com.openteach.quest-launcher"
launchctl kickstart -k "gui/$UID/com.openteach.quest-launcher"

print "Installed Quest launcher: $TARGET_PLIST"
print "Log: $HOME/Library/Logs/OpenTeachQuestLauncher.log"
