---
inclusion: auto
name: LeRobot Demo Context
description: Project context for the LeRobot SO-101 AWS digital twin demo — hardware, software stack, architecture, and common workflows.
---
# Product: LeRobot SO-101 AWS Sim2Real2Sim Demo

## What This Is

A physical AI demo showcasing a robotic arm (SO-101) with an AWS-powered digital twin. The system demonstrates:
- **Real2Sim**: Physical arm movements replicated in real-time in Isaac Sim (cloud)
- **Sim2Real**: AI inference (SmolVLA/GR00T) controlling the physical arm from vision input

## Hardware

- **Edge device**: NVIDIA Jetson AGX Orin (64GB) + 1TB NVMe SSD
- **Arms**: SO-101 leader (teleoperation input) + SO-101 follower (actuated output)
- **Cameras**: USB cameras for wrist and workspace views
- **Connectivity**: WiFi, Ethernet (direct cable), USB-C (always works)

## Software Stack

| Layer | Component | Purpose |
|-------|-----------|---------|
| Edge | LeRobot framework | Arm control, calibration, data recording |
| Edge | dt-edge-backend (systemd) | Telemetry publishing, camera streaming, dashboard |
| Edge | AWS IoT Greengrass | Device provisioning, MQTT connectivity |
| Cloud | AWS IoT Core | MQTT broker for telemetry |
| Cloud | EC2 g6e.8xlarge | Isaac Sim digital twin rendering |
| Cloud | NICE DCV | Remote desktop to Isaac Sim |
| Inference | SmolVLA / GR00T | Vision-language-action models for sim2real |

## CLI Tool: `aws-pai`

The project includes a CLI (`aws-pai`) that wraps common operations:
- `aws-pai status` — cloud infrastructure state
- `aws-pai deploy` / `aws-pai destroy` — CDK stack lifecycle
- `aws-pai edge status` / `aws-pai edge setup` — Jetson management
- `aws-pai arm detect` / `aws-pai arm test` — hardware verification
- `aws-pai cloud fix-ip` — security group IP update (venue changes)
- `aws-pai infer` — run inference on Jetson

## Key Architecture Decisions

- Config lives at `/opt/digital-twin/config.json` on Jetson — never overwrite wholesale
- Models stored on SSD (`/mnt/ssd/models/`) symlinked to `/opt/digital-twin/models/`
- Jetson venv has Tegra-compiled PyTorch — never recreate without good reason
- IoT things/certs created by fleet provisioning (outside CloudFormation)
- GPU instances cost $3-4/hour — always stop when not in use

## Reference Docs

- #[[file:operations/01-lerobot_commands.md]] — Arm control, cameras, calibration
- #[[file:operations/02-demo_platform.md]] — Digital twin platform, MQTT, services
- #[[file:set-up/01-setup_jetson-plan.md]] — Initial Jetson setup
- #[[file:set-up/02-setup_ssh-guide.md]] — SSH, WiFi, venue connectivity
- #[[file:set-up/03-training_guide.md]] — Model training (SageMaker)
- #[[file:troubleshooting/groot_inference_stuck.md]] — GR00T inference issues
- #[[file:troubleshooting/edge_backend_camera_fix.md]] — Camera lock fixes
