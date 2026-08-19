#!/bin/zsh

set -eu

SCRIPT_DIR=${0:A:h}
source "$SCRIPT_DIR/macos_env.sh"

print "Open Teach host: $OPENTEACH_HOST"
print "Enter this address in the Quest Bimanual APK, then choose Stream."
exec python teleop.py robot=libero_sim sim_env=True "$@"
