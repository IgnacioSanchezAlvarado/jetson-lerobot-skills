# Jetson AGX Orin 32GB H01 — Full Setup & Demo Plan

## Context
Seeed NVIDIA Jetson AGX Orin 32GB H01 Kit (DigiKey 114110207) with Kingston NV2 500GB NVMe SSD.
Goal: flash JetPack 6.2, install SSD, set up remote access from Mac, run Dario's edge bootstrap, run SmolVLA inference on SO-101 arm.

- **Flashed**: JetPack 6.2 (L4T 36.4.3)
- **Display**: HDMI 2.1 (regular HDMI cable works)
- **Case screws**: Allen/hex key (~2.5mm), NOT Phillips
- **SSD retaining screw**: M2 size (may be included in box)
- **Trained model**: https://huggingface.co/nacho92sa/smolvla_color_blocks
- **Demo repo**: <INTERNAL_REPO_URL> (branch: `dario-edge-jetson`)
- **Jetson credentials**: igsalvarjetson / <ASK_TEAM_FOR_PASSWORD>
- **Jetson IP**: 192.168.1.20 (WiFi) / 192.168.55.1 (USB-C) / 10.0.0.1 (Ethernet)
- **Jetson storage**: 57GB eMMC (46GB free), SSD not yet installed

---

## Phase 1: Flash JetPack 6.2 — COMPLETE

Flashed JetPack 6.2 (not 6.1) manually using L4T BSP + Root FS + Seeed H01 drivers.
- Files: `Jetson_Linux_r36.4.3_aarch64.tbz2` + `Tegra_Linux_Sample-Root-Filesystem_r36.4.3_aarch64.tbz2` + `605_jp62.tar.gz`
- Flash command: `sudo ./flash.sh jetson-agx-orin-devkit internal`
- Flashed from Ubuntu 24.04 workstation (Alienware m15)

---

## Phase 2: Install SSD & Configure Storage

### 2.1 Install NVMe SSD
- Flip unit upside down → peel off **4 rubber feet** → remove **4 hex/Allen screws** (~2.5mm) → separate top shell
- Find **M.2 Key M slot** on carrier board (PCIe Gen 4, NVMe only — no SATA)
- Insert Kingston NV2 at ~30° angle (gold pins first, label up), press flat, secure with M2 screw
- Reassemble

### 2.2 Configure SSD Storage
```bash
ssh jetson

# Verify SSD detected
lsblk  # Should show /dev/nvme0n1

# Partition and format
sudo parted /dev/nvme0n1 mklabel gpt
sudo parted /dev/nvme0n1 mkpart primary ext4 0% 100%
sudo mkfs.ext4 -F /dev/nvme0n1p1

# Mount permanently
sudo mkdir -p /mnt/nvme
sudo mount /dev/nvme0n1p1 /mnt/nvme
echo '/dev/nvme0n1p1 /mnt/nvme ext4 defaults,nofail 0 2' | sudo tee -a /etc/fstab
sudo chown -R $USER:$USER /mnt/nvme

# Symlink heavy directories to SSD
mkdir -p /mnt/nvme/{models,data,docker}
ln -s /mnt/nvme/models ~/.cache/huggingface
```

**Note**: Can proceed with Phase 4 without SSD — 46GB eMMC free should be enough for bootstrap. Move heavy files to SSD later.

---

## Phase 3: Remote Access from Mac — COMPLETE

SSH key auth configured. Three connection methods available (see `ssh_guide.md`):

```bash
ssh jetson       # WiFi (192.168.1.20) — home/office
ssh jetson-usb   # USB-C (192.168.55.1) — direct cable, always works
ssh jetson-eth   # Ethernet (10.0.0.1) — demo venues, most reliable
```

**Ethernet setup** (recommended for demos): Jetson `eth1` → RJ45 cable → USB-C dongle → Mac.
Static IPs configured: Jetson `10.0.0.1` (persistent via NetworkManager), Mac `10.0.0.2` (run after each dongle reconnect: `sudo ifconfig en11 10.0.0.2 netmask 255.255.255.0 up`).

---

## Phase 4: Edge Bootstrap via aws-pai CLI — COMPLETE

The `aws-pai` CLI automates Jetson provisioning: fleet registration, Greengrass, Python venv with PyTorch (Jetson wheel from `pypi.jetson-ai-lab.dev/jp6/cu126`), inference server, edge backend, and dashboard.

**This replaces manual installation of PyTorch, LeRobot, SmolVLA, and Greengrass.**

**Repo location (Mac):** `~/Documents/claude-code/jetson-lerobot/lerobot-so101-aws-sim2real2sim/`

**Note:** CUDA toolkit 12.6 was already installed on the Jetson manually (`sudo apt install cuda-toolkit-12-6`). This shouldn't conflict with the bootstrap — the bootstrap uses NVIDIA's Jetson-specific PyTorch wheel, not standard pip torch.

**Issues found & fixed during setup:**
- Fleet provisioning role missing IAM permissions → replaced inline policy with AWS managed `AWSIoTThingsRegistration`
- Greengrass Nucleus version mismatch (2.14.2 pinned, 2.17.0 installed) → updated config to 2.17.0
- `setup-jetson.sh`: `scservo-sdk` removed from PyPI → changed to `feetech-servo-sdk`
- `setup-jetson.sh`: cuDNN 9 not installed → added `apt-get install libcudnn9-cuda-12`
- `setup-jetson.sh`: venv owned by root → added final `chown -R` at end of script
- `cli/edge.py`: SSH sudo needs TTY → added `tty=True` parameter to `_run_ssh()`
- Passwordless sudo configured on Jetson for `igsalvarjetson`

### 4.1 Install aws-pai CLI (Mac)
```bash
cd ~/Documents/claude-code/jetson-lerobot/lerobot-so101-aws-sim2real2sim
pip install -e ".[dev]"   # puts aws-pai on PATH
aws-pai --help             # verify
aws-pai doctor             # check prerequisites (AWS CLI, Node, Python, CDK, AMI, localproxy)
```

### 4.2 Initialize Config
```bash
aws-pai init    # interactive — auto-detects IP, region, creates config.json
```
Key settings to configure:
- **Region**: `eu-south-2` (or your target region)
- **Edge host**: `10.0.0.1` (Ethernet) or `192.168.1.20` (WiFi)
- **Edge user**: `igsalvarjetson`
- **Edge SSH key**: `~/.ssh/id_ecdsa`
- **Fleet provisioning**: enabled (default)

### 4.3 Deploy Cloud Stacks
```bash
aws-pai deploy   # deploys IoT + Isaac Sim CDK stacks (~3 min)
aws-pai status   # verify — shows DCV URL, instance info
```

### 4.4 Provision the Jetson (Fleet Bootstrap)
```bash
# On Mac:
aws-pai edge provision   # generates fleet bootstrap bundle, outputs a one-liner

# On Jetson (copy-paste the one-liner):
curl -sfL "<presigned-url>" | tar xz && cd fleet-bundle && sudo bash fleet-bootstrap.sh
```
The bootstrap installs:
- Java → Greengrass v2 (IoT runtime)
- Python venv at `/opt/digital-twin/venv`
- PyTorch (Jetson ARM64 wheel)
- Inference server (`dt-inference.service`)
- Edge backend + dashboard (`dt-edge-backend.service`, port 3000)
- Self-registration via FleetProvisioningByClaim plugin

### 4.5 Download Model to Jetson
```bash
# From Mac — SSHes into Jetson and downloads directly (weights never touch laptop):
aws-pai edge download-model smolvla_color_blocks   # ~1.2GB → /opt/digital-twin/models/
```

### 4.6 Verify Bootstrap
```bash
# From Mac:
aws-pai edge fleet list    # device shows in lerobot-fleet ThingGroup
aws-pai edge status        # services running, GPU info

# On Jetson (via ssh jetson-eth):
sudo systemctl status greengrass
sudo systemctl status dt-inference
sudo systemctl status dt-edge-backend
/opt/digital-twin/venv/bin/python3 -c "import torch; print(f'CUDA: {torch.cuda.is_available()}')"
```

### 4.7 Fallback: Manual Install (only if bootstrap doesn't cover something)
If the bootstrap doesn't install something, here are manual steps:

```bash
# JetPack SDK components (CUDA, cuDNN, TensorRT)
sudo apt install nvidia-jetpack

# PyTorch — MUST use NVIDIA ARM64 wheels
sudo apt install -y python3-pip libopenblas-dev python3-venv
python3 -m venv ~/lerobot-env
source ~/lerobot-env/bin/activate
pip install numpy==1.26.1
# Get wheel URL from: https://forums.developer.nvidia.com (search "PyTorch for JetPack 6.2")

# LeRobot from source
git clone https://github.com/huggingface/lerobot.git
cd lerobot && pip install -e .

# SmolVLA model
pip install huggingface_hub
huggingface-cli download nacho92sa/smolvla_color_blocks

# jetson-stats (monitoring — useful regardless)
sudo pip3 install jetson-stats
sudo systemctl restart jtop
```

---

## Phase 5: Robot Hardware & Demo Testing

### 5.1 Connect SO-101 Arm
- Connect SO-101 follower arm via USB to Jetson
- Verify: `ls /dev/ttyACM*` or `ls /dev/ttyUSB*`
- Connect cameras (wrist + table) via USB — use separate USB controllers

### 5.2 Test Robot Connection
```bash
python3 -c "
from lerobot.common.robots.so101_follower import SO101Follower
robot = SO101Follower(port='/dev/ttyACM0', id='my_follower')
robot.connect()
print(robot.get_state())
robot.disconnect()
"
```

### 5.3 Run the Demo (Sim2Real / Real2Sim)
- Follow `dario-edge-jetson` branch README
- Components:
  - **Real2Sim**: Robot state published via MQTT → Isaac Sim mirrors movements
  - **Sim2Real**: Commands from UI/cloud → robot executes
  - **DirectControls**: UI sliders to manually move the arm
  - **SmolVLA inference**: Camera frames + language prompt → action predictions → servo commands

### 5.4 Test SmolVLA with Robot
```bash
lerobot-infer \
  --robot.type=so101_follower \
  --robot.port=/dev/ttyACM0 \
  --policy.path=nacho92sa/smolvla_color_blocks \
  --policy.task="Pick up the red block"
```

---

## Verification Checklist

- [x] JetPack 6.2 flashed: `cat /etc/nv_tegra_release` → R36, REVISION 4.3
- [x] SSH from Mac works: `ssh jetson` (WiFi), `ssh jetson-usb` (USB-C), `ssh jetson-eth` (Ethernet)
- [ ] SSD recognized: `lsblk` shows `/dev/nvme0n1`
- [x] aws-pai CLI installed: `aws-pai --help` works on Mac
- [x] aws-pai doctor passes: all prerequisites green
- [x] config.json created: `aws-pai init` completed
- [x] Cloud stacks deployed: `aws-pai deploy` succeeded
- [x] Fleet bootstrap complete: `aws-pai edge provision` → one-liner ran on Jetson
- [x] Device registered: `aws-pai edge fleet list` shows device (lerobot-1422725057298)
- [x] Greengrass running: `sudo systemctl status greengrass` → active
- [x] Edge backend running: `aws-pai edge status` → active (dashboard on port 3000)
- [x] PyTorch + CUDA: torch 2.8.0, cuda=True, gpu=Orin
- [x] SmolVLA model cached: `/opt/digital-twin/models/smolvla_color_blocks`
- [ ] Robot connected: servo state readable via LeRobot
- [ ] MQTT publishing: messages visible in AWS IoT Core console
- [ ] Demo UI: sliders and DirectControls functional
- [ ] SmolVLA inference: model produces action predictions from camera feed

---

## Key Resources

- **Seeed Wiki (flashing)**: https://wiki.seeedstudio.com/Jetson_AGX_Orin_32GB_H01_Flash_Jetpack/
- **NVIDIA JetPack**: https://developer.nvidia.com/embedded/jetpack
- **PyTorch for Jetson**: https://forums.developer.nvidia.com (search "PyTorch for JetPack 6.2")
- **jetson-containers**: https://github.com/dusty-nv/jetson-containers
- **LeRobot**: https://github.com/huggingface/lerobot
- **Demo repo**: <INTERNAL_REPO_URL> (branch: dario-edge-jetson)
- **Trained model**: https://huggingface.co/nacho92sa/smolvla_color_blocks
