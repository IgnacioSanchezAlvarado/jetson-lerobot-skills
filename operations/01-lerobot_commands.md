# LeRobot Commands — Quick Reference

## Before Running Any Model

```bash
sudo nvpmodel -m 0 && sudo jetson_clocks   # unlock full GPU
sudo systemctl stop dt-edge-backend
sudo chmod 666 /dev/ttyACM0
sudo rm -rf /tmp/eval_dt-edge
```

**Camera wiring** (must match training dataset order):

| USB-A Port | Camera | Device | Role |
|------------|--------|--------|------|
| Bottom | Logitech C922 | /dev/video0 | top (overhead) |
| Top | Generic USB cam (Sonix) | /dev/video2 | front (wrist/gripper) |

Verify: `v4l2-ctl --list-devices`

---

## Inference

### ACT
- 80M params, single-task, 10-30 Hz
- Model: `/opt/digital-twin/models/act_color_blocks_red`
- Task: "Pick up the red block" (single-task only)

```bash
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
  --dataset.episode_time_s=120 \
  --dataset.reset_time_s=0 \
  --dataset.fps=30 \
  --dataset.push_to_hub=false \
  --policy.path=/opt/digital-twin/models/act_color_blocks_red
```

### SmolVLA (Recommended)
- 450M params, multi-task + language, 1-2 Hz
- Model: `/opt/digital-twin/models/smolvla_1`
- Tasks: "Pick up the red/blue/yellow block"

```bash
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
  --dataset.episode_time_s=120 \
  --dataset.reset_time_s=0 \
  --dataset.fps=30 \
  --dataset.push_to_hub=false \
  --policy.path=/opt/digital-twin/models/smolvla_1 \
  --policy.compile_model=false
```

Note: `compile_model=false` required (no Triton on ARM)

### Pi0.5
- 2.3B params, diffusion-based, high-quality
- Model: `/opt/digital-twin/models/pi05_color_blocks`
- Venv: `/opt/digital-twin/venv-pi05` (different venv!)
- Tasks: "Pick up the red/blue/yellow block"

**Config fix first:**
```bash
/opt/digital-twin/venv/bin/python3 -c "
import json
p = '/opt/digital-twin/models/pi05_color_blocks/config.json'
cfg = json.load(open(p))
for k in ['use_relative_actions', 'relative_exclude_joints', 'action_feature_names']:
    cfg.pop(k, None)
json.dump(cfg, open(p, 'w'), indent=4)
print('Done — removed unsupported fields')
"
```

**Run inference:**
```bash
/opt/digital-twin/venv-pi05/bin/lerobot-record \
  --robot.type=so101_follower \
  --robot.port=/dev/ttyACM0 \
  --robot.id=my_awesome_follower_arm \
  --robot.cameras="{ top: {type: opencv, index_or_path: /dev/video0, width: 640, height: 480, fps: 30, warmup_s: 5}, front: {type: opencv, index_or_path: /dev/video2, width: 640, height: 480, fps: 30, warmup_s: 5}}" \
  --display_data=false \
  --dataset.repo_id=local/eval_dt-edge \
  --dataset.root=/tmp/eval_dt-edge \
  --dataset.single_task="Pick up the red block" \
  --dataset.num_episodes=1 \
  --dataset.episode_time_s=120 \
  --dataset.reset_time_s=0 \
  --dataset.fps=30 \
  --dataset.push_to_hub=false \
  --policy.path=/opt/digital-twin/models/pi05_color_blocks \
  --policy.compile_model=false
```

Note: `compile_model=false` required

### GR00T N1.7
- 3B params, server-client architecture, ~2 Hz
- Model: `/opt/digital-twin/models/groot_so101_v2`
- Venv: `/opt/digital-twin/venv-groot`
- Tasks: "Pick up the red/blue/yellow block"

**Start server:**
```bash
cd /opt/Isaac-GR00T && source /opt/digital-twin/venv-groot/bin/activate
nohup python gr00t/eval/run_gr00t_server.py \
  --model-path /opt/digital-twin/models/groot_so101_v2 \
  --embodiment-tag NEW_EMBODIMENT \
  --host 0.0.0.0 --port 5555 \
  > /tmp/groot_server.log 2>&1 &
```

**Wait for load:**
```bash
tail -f /tmp/groot_server.log
# Wait for "Loading checkpoint shards: 100%"
```

**Run eval:**
```bash
timeout 120 python /opt/digital-twin/groot-eval/eval_so100.py \
  --config_path /opt/digital-twin/groot-eval/eval_groot.yaml
```

**Release servos:**
```bash
/opt/digital-twin/venv/bin/python3 -c "
from pathlib import Path
from lerobot.robots.so_follower import SOFollower, SOFollowerRobotConfig
cfg = SOFollowerRobotConfig(port='/dev/ttyACM0', id='my_awesome_follower_arm',
    calibration_dir=Path('/home/igsalvarjetson/.cache/huggingface/lerobot/calibration/robots/so_follower'), cameras={})
robot = SOFollower(cfg); robot.bus.connect()
for m in ['shoulder_pan','shoulder_lift','elbow_flex','wrist_flex','wrist_roll','gripper']:
    robot.bus.write('Torque_Enable', m, 0)
robot.bus.disconnect(); print('Servos released')
"
```

**Stop server:**
```bash
pkill -f run_gr00t_server
```

Note: Camera mapping differs — GR00T front=Logitech overhead, wrist=USB gripper

---

## Teleoperation

### Prepare
```bash
sudo systemctl stop dt-edge-backend
sudo chmod 666 /dev/ttyACM0 /dev/ttyACM1
```

### Identify Ports
Typically: /dev/ttyACM0 = follower, /dev/ttyACM1 = leader

```bash
udevadm info -q property /dev/ttyACM0 | grep ID_SERIAL
udevadm info -q property /dev/ttyACM1 | grep ID_SERIAL
```

### Calibrate (one-time)

**Follower:**
```bash
/opt/digital-twin/venv/bin/python -m lerobot.calibrate \
  --robot.type=so101_follower \
  --robot.port=/dev/ttyACM0 \
  --robot.id=my_awesome_follower_arm
```

**Leader:**
```bash
/opt/digital-twin/venv/bin/python -m lerobot.calibrate \
  --robot.type=so101_leader \
  --robot.port=/dev/ttyACM1 \
  --robot.id=my_awesome_leader_arm
```

Note: Interactive, follow on-screen prompts

### Basic Teleop (no recording)
```bash
/opt/digital-twin/venv/bin/python -m lerobot.teleoperate \
  --robot.type=so101 \
  --robot.leader.port=/dev/ttyACM1 \
  --robot.leader.id=my_awesome_leader_arm \
  --robot.follower.port=/dev/ttyACM0 \
  --robot.follower.id=my_awesome_follower_arm \
  --teleop.fps=30
```

### Record Dataset
```bash
sudo rm -rf /tmp/teleop_dataset

/opt/digital-twin/venv/bin/lerobot-record \
  --robot.type=so101 \
  --robot.leader.port=/dev/ttyACM1 \
  --robot.leader.id=my_awesome_leader_arm \
  --robot.follower.port=/dev/ttyACM0 \
  --robot.follower.id=my_awesome_follower_arm \
  --robot.cameras="{ top: {type: opencv, index_or_path: /dev/video0, width: 640, height: 480, fps: 30, warmup_s: 5}, front: {type: opencv, index_or_path: /dev/video2, width: 640, height: 480, fps: 30, warmup_s: 5}}" \
  --display_data=false \
  --dataset.repo_id=local/teleop_dataset \
  --dataset.root=/tmp/teleop_dataset \
  --dataset.single_task="Pick up the red block" \
  --dataset.num_episodes=5 \
  --dataset.episode_time_s=60 \
  --dataset.reset_time_s=10 \
  --dataset.fps=30 \
  --dataset.push_to_hub=false
```

Note: `reset_time_s=10` between episodes, camera order must be top→front

---

## Quick Servo Commands

### Release all servos
```bash
/opt/digital-twin/venv/bin/python3 -c "
from lerobot.robots.so_follower import SOFollower, SOFollowerRobotConfig
from pathlib import Path
cfg = SOFollowerRobotConfig(port='/dev/ttyACM0', id='my_awesome_follower_arm',
    calibration_dir=Path('/home/igsalvarjetson/.cache/huggingface/lerobot/calibration/robots/so_follower'), cameras={})
robot = SOFollower(cfg); robot.bus.connect()
for m in ['shoulder_pan','shoulder_lift','elbow_flex','wrist_flex','wrist_roll','gripper']:
    robot.bus.write('Torque_Enable', m, 0)
robot.bus.disconnect(); print('All servos released')
"
```

### Read joint positions
```bash
/opt/digital-twin/venv/bin/python3 -c "
from lerobot.robots.so_follower import SOFollower, SOFollowerRobotConfig
from pathlib import Path
cfg = SOFollowerRobotConfig(port='/dev/ttyACM0', id='my_awesome_follower_arm',
    calibration_dir=Path('/home/igsalvarjetson/.cache/huggingface/lerobot/calibration/robots/so_follower'), cameras={})
robot = SOFollower(cfg); robot.connect()
state = robot.get_observation()
print('Joint positions:', {k: round(v.item(), 2) for k, v in state.items() if 'position' in k})
robot.disconnect()
"
```

### Scan servos (raw bus)
```bash
/opt/digital-twin/venv/bin/python3 -c "
from lerobot.common.motors.feetech import FeetechMotorsBus, FeetechMotorsBusConfig
cfg = FeetechMotorsBusConfig(port='/dev/ttyACM0', motors={
    'shoulder_pan': [1, 'sts3215'],
    'shoulder_lift': [2, 'sts3215'],
    'elbow_flex': [3, 'sts3215'],
    'wrist_flex': [4, 'sts3215'],
    'wrist_roll': [5, 'sts3215'],
    'gripper': [6, 'sts3215'],
})
bus = FeetechMotorsBus(cfg); bus.connect()
for name, (motor_id, _) in cfg.motors.items():
    try:
        pos = bus.read('Present_Position', name)
        print(f'Motor {motor_id} ({name}): position={pos} — OK')
    except Exception as e:
        print(f'Motor {motor_id} ({name}): FAILED — {e}')
bus.disconnect()
"
```

### Unlock stuck servo
```bash
/opt/digital-twin/venv/bin/python3 -c "
from lerobot.common.motors.feetech import FeetechMotorsBus, FeetechMotorsBusConfig
cfg = FeetechMotorsBusConfig(port='/dev/ttyACM0', motors={
    'shoulder_pan': [1, 'sts3215'],
    'shoulder_lift': [2, 'sts3215'],
    'elbow_flex': [3, 'sts3215'],
    'wrist_flex': [4, 'sts3215'],
    'wrist_roll': [5, 'sts3215'],
    'gripper': [6, 'sts3215'],
})
bus = FeetechMotorsBus(cfg); bus.connect()
for name in cfg.motors:
    bus.write('Torque_Enable', name, 0)
    bus.write('Lock', name, 0)
bus.disconnect(); print('All servos unlocked and torque disabled')
"
```

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| PermissionError /dev/ttyACM0 | `sudo chmod 666 /dev/ttyACM0` |
| FileExistsError /tmp/eval_dt-edge | `sudo rm -rf /tmp/eval_dt-edge` |
| Camera timeout | Increase `warmup_s` or check `v4l2-ctl --list-devices` |
| TritonMissing error | `--policy.compile_model=false` |
| Overheating servo | Unplug USB, wait 5s, replug, immediately release servos |
