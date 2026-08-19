#!/bin/zsh

set -eu

SCRIPT_DIR=${0:A:h}
source "$SCRIPT_DIR/macos_env.sh"

DEMO_NUM=${1:-1}
if (( $# > 0 )); then
  shift
fi

print "Recording demonstration $DEMO_NUM from $OPENTEACH_HOST"
exec python data_collect.py robot=libero_sim sim_env=True demo_num="$DEMO_NUM" "$@"
