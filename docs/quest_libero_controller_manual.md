# Quest 2 × Open Teach × LIBERO 操作マニュアル

## 構成

- Questアプリ: `Open Teach LIBERO Controller`
- Androidパッケージ: `com.NYU.Bimanual.Controller`
- 対応アプリ版: `1.4-low-latency` (`versionCode=5`)
- Mac常駐ランチャー: `scripts/quest_sim_launcher.py`
- 操作対象: LIBEROのPanda単腕アーム

QuestとMacは同じLANへ接続します。USBはAPKのインストールとADB診断にのみ必要です。

## 通常起動

Macを起動し、スリープさせない状態にします。常駐ランチャーは
LaunchAgentとして自動起動します。状態確認は以下です。

```zsh
launchctl print gui/$(id -u)/com.openteach.quest-launcher
tail -f ~/Library/Logs/OpenTeachQuestLauncher.log
```

Questの「不明な提供元」から `Open Teach LIBERO Controller`を起動します。
QuestはUDP discoveryでMacのIPアドレスを自動検出するため、通常はIPの手入力は不要です。

## コントローラー操作

- 右Touchの位置: Panda手先のXYZ目標位置
- 右Touchの姿勢: Panda手先のyaw / pitch / roll
- 右インデックストリガー: グリッパ閉
- A: 操作の一時停/再開。再開時のコントローラ位置と現在の手先を再対応付け
- B: 現在のLIBEROステージをリセット
- 左スティック左/右: ステージ選択
- 左スティック押し込み: 選択したステージでMacシミュレータを再起動

アームが可動域境界で目標に追従できない場合は、約300ms後に自動的に
コントローラと実アームの基準姿勢を再対応付けします。

## LIBEROステージ

1. 上の引き出しを開ける
2. 下の引き出しを開ける
3. ボウルを上の引き出しへ入れる
4. 電子レンジを開ける
5. モカポットをコンロへ置く
6. スープ缶をバスケットへ入れる
7. クリームチーズをトレイへ入れる
8. 本を棚へ置く

Macから直接選択する場合:

```zsh
scripts/run_teleop_stage_macos.sh 3
```

## 低遅延・切断時の動作

- コントローラ送信: 60Hz、最新値のみ
- LIBERO制御: 20Hz
- メイン/手元映像: 目標15Hz、受信キュー1枚
- HUD: 10Hz
- 入力タイムアウト: 250ms

タイムアウト時はグリッパ状態を保ったまま、手先の位置・姿勢差分をゼロにします。
通信が切れても古い差分命令でアームが動き続けることはありません。映像とHUDは継続します。

## 遅延計測

計測はPUB/SUBの購読だけで行うため、Questの操作パケットを奪いません。

```zsh
source scripts/macos_env.sh
scripts/profile_quest_teleop.py --seconds 60
```

`p95_gap_s`と `max_gap_s`が停止時間です。標準目安は制御の `max_gap_s < 0.15`、
映像の `max_gap_s < 0.25`です。

## データ記録

通常のテレオペでは、負荷を下げるため記録用RGB/depthストリームを停止しています。
記録するときだけ以下のように起動します。

```zsh
OPENTEACH_RECORD_STREAMS=1 scripts/run_teleop_stage_macos.sh 3
scripts/run_data_collect_macos.sh 1
```

記録中はRGBとdepthの生成・圧縮分だけ処理負荷が増えます。

## トラブル時

```zsh
adb devices -l
tail -100 ~/Library/Logs/OpenTeachQuestLauncher.log
pgrep -af 'quest_sim_launcher|teleop.py'
```

Questアプリの再インストール:

```zsh
scripts/install_quest_apk.sh
```
