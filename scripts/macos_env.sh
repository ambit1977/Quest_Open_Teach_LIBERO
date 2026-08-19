#!/bin/zsh

SCRIPT_PATH=${(%):-%N}
SCRIPT_DIR=${SCRIPT_PATH:A:h}
PROJECT_DIR=${SCRIPT_DIR:h}
PARC_UPSTREAM="/Users/ambit/Documents/キャリアデザイン/東大松尾研究室/コンテスト/PARC2026/upstream"

if [[ ! -x "$PROJECT_DIR/.venv/bin/python" ]]; then
  print -u2 "Missing $PROJECT_DIR/.venv. Run scripts/setup_macos_libero.sh first."
  return 1 2>/dev/null || exit 1
fi

source "$PROJECT_DIR/.venv/bin/activate"

export LIBERO_ROOT="$PARC_UPSTREAM/LIBERO-plus"
export PYTHONPATH="$PROJECT_DIR:$LIBERO_ROOT:$PARC_UPSTREAM/venv/lib/python3.10/site-packages${PYTHONPATH:+:$PYTHONPATH}"
export MUJOCO_GL=${MUJOCO_GL:-glfw}

if [[ -z ${OPENTEACH_HOST:-} ]]; then
  DEFAULT_IFACE=$(route -n get default 2>/dev/null | awk '/interface:/{print $2; exit}')
  if [[ -n "$DEFAULT_IFACE" ]]; then
    OPENTEACH_HOST=$(ipconfig getifaddr "$DEFAULT_IFACE" 2>/dev/null || true)
  fi
  export OPENTEACH_HOST=${OPENTEACH_HOST:-127.0.0.1}
fi

cd "$PROJECT_DIR"
