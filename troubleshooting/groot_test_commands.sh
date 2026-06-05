#!/bin/bash
# GR00T Inference Troubleshooting — Copy-paste commands
# See groot_inference_stuck.md for full context on each test
#
# STATUS:
#   Test A (n_action_steps=16): DONE — no improvement
#   Test C (raw action logging): DONE — actions are healthy [-1.96, 2.98]
#     -> Model outputs a fixed pose, not responding to visual input
#     -> First 6 values (joints) nearly identical across timesteps
#   Test D (16 denoising steps): PATCHED on Jetson — ready to test
#
# CURRENT: Run PREP then TEST D below

# ============================================================
# PREP (run before each test)
# ============================================================
sudo chmod 666 /dev/ttyACM0
sudo rm -rf /tmp/eval_dt-edge

# ============================================================
# TEST D: 16 denoising steps (PATCHED — ready to run)
# Base model uses 4 steps. Code patched on Jetson to use 16.
# Will print ">>> PATCHED denoising steps: 4 -> 16" on startup.
# NOTE: This will be ~4x slower per inference call.
# ============================================================
/opt/digital-twin/venv/bin/lerobot-record \
  --robot.type=so101_follower \
  --robot.port=/dev/ttyACM0 \
  --robot.id=my_awesome_follower_arm \
  --robot.cameras="{ top: {type: opencv, index_or_path: /dev/video0, width: 640, height: 480, fps: 30, warmup_s: 5}, front: {type: opencv, index_or_path: /dev/video2, width: 640, height: 480, fps: 30, warmup_s: 5}}" \
  --display_data=false \
  --dataset.repo_id=local/eval_dt-edge \
  --dataset.root=/tmp/eval_dt-edge \
  --dataset.single_task="Pick up the red block" \
  --dataset.num_episodes=1 \
  --dataset.episode_time_s=30 \
  --dataset.reset_time_s=10 \
  --dataset.fps=30 \
  --dataset.push_to_hub=false \
  --policy.path=/opt/digital-twin/models/groot_1 \
  --policy.n_action_steps=16

# ============================================================
# REVERT ALL PATCHES (when done troubleshooting)
# ============================================================
# sudo /opt/digital-twin/venv/bin/pip install --force-reinstall lerobot==0.4.4
