#!/bin/zsh

set -e

SCRIPT_PATH=${(%):-%N}
SCRIPT_DIR=${SCRIPT_PATH:A:h}
source "$SCRIPT_DIR/macos_env.sh"

STAGE_NAMES=(
  "上の引き出しを開ける"
  "下の引き出しを開ける"
  "ボウルを上の引き出しへ入れる"
  "電子レンジを開ける"
  "モカポットをコンロへ置く"
  "スープ缶をバスケットへ入れる"
  "クリームチーズをトレイへ入れる"
  "本を棚へ置く"
)

TASK_NAMES=(
  "KITCHEN_SCENE1_open_the_top_drawer_of_the_cabinet"
  "KITCHEN_SCENE1_open_the_bottom_drawer_of_the_cabinet"
  "KITCHEN_SCENE1_open_the_top_drawer_of_the_cabinet_and_put_the_bowl_in_it"
  "KITCHEN_SCENE7_open_the_microwave"
  "KITCHEN_SCENE3_put_the_moka_pot_on_the_stove"
  "LIVING_ROOM_SCENE2_pick_up_the_alphabet_soup_and_put_it_in_the_basket"
  "LIVING_ROOM_SCENE3_pick_up_the_cream_cheese_and_put_it_in_the_tray"
  "STUDY_SCENE4_pick_up_the_book_in_the_middle_and_place_it_on_the_cabinet_shelf"
)

choice=${1:-}
if [[ -z "$choice" ]]; then
  print "LIBEROステージを選択してください:"
  for index in {1..${#STAGE_NAMES}}; do
    print "  $index. ${STAGE_NAMES[$index]}"
  done
  read "choice?番号 [3]: "
  choice=${choice:-3}
fi

if ! [[ "$choice" == <-> ]] || (( choice < 1 || choice > ${#STAGE_NAMES} )); then
  print -u2 "ステージ番号は1から${#STAGE_NAMES}で指定してください。"
  exit 2
fi

task_name=${TASK_NAMES[$choice]}
print "選択: ${STAGE_NAMES[$choice]}"
print "Task: $task_name"
print "Open Teach host: $OPENTEACH_HOST"

recording_overrides=()
if [[ "${OPENTEACH_RECORD_STREAMS:-0}" == "1" ]]; then
  print "Recording RGB/depth streams: enabled"
  recording_overrides+=(
    "robot.environment.0.publish_recording_streams=true"
    "robot.environment.0.publish_depth=true"
  )
fi

exec python teleop.py \
  robot=libero_sim \
  sim_env=True \
  "robot.environment.0.task_name=$task_name" \
  "${recording_overrides[@]}"
