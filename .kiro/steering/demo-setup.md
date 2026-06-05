---
inclusion: manual
---
# Flow: Demo Pre-Flight Check

Run a complete pre-flight check for the demo hardware setup at a new venue. SSH into the Jetson proactively — do not ask the user to run commands on their behalf.

## Core Principles

**Prefer `aws-pai` CLI commands over raw SSH/AWS CLI when possible:**
- Use `aws-pai edge status` instead of raw `ssh jetson "systemctl ..."`
- Use `aws-pai edge logs` instead of raw `ssh jetson "journalctl ..."`
- Use `aws-pai cloud fix-ip` instead of manual security group edits
- Use `aws-pai deploy --wake` instead of raw `aws ec2 start-instances`
- Use `aws-pai status` instead of raw `aws ec2 describe-instances`
- Use `aws-pai arm detect` instead of raw `ssh jetson "ls /dev/ttyACM*"`

**Fall back to raw SSH/AWS CLI when:**
- `aws-pai` command fails or produces unexpected output
- Need more detail than `aws-pai` provides (camera mapping, config reads, calibration files, disk space)
- Diagnosing why `aws-pai` itself isn't working (venv issues, config corruption)

Reference the operations guides for troubleshooting steps if checks fail.

## What's stable vs dynamic

**Stable commands (copy-paste as-is):**
- `ssh jetson "systemctl is-active greengrass"`
- `ssh jetson "systemctl is-active dt-edge-backend"`
- `ssh jetson "sudo systemctl restart dt-edge-backend"`
- `ssh jetson "journalctl -u dt-edge-backend -n 30 --no-pager"`
- `ssh jetson "ls /dev/ttyACM*"`
- `ssh jetson "ls /dev/video*"`
- `ssh jetson "df -h"`
- `ssh jetson "free -h"`
- `ssh jetson "ping -c 2 8.8.8.8"`
- `ssh jetson "ls -la /opt/digital-twin/models"`

**Dynamic values (read from Jetson config at `/opt/digital-twin/config.json`):**
- IoT region → `aws.region` (for DNS resolution check: `host iot.<REGION>.amazonaws.com`)
- Dashboard port → `edge.dashboardPort`
- Telemetry rate → `iot.pollingRateHz` (verify against what logs report)
- Serial ports → `teleop.leaderPort`, `teleop.followerPort`, `component.serialPort`
- Camera indices → `camera.deviceIndex`, `cameras[]` array
- Calibration IDs → `teleop.robotId`, `teleop.leaderId`
- Device ID → `iot.deviceId`

**Fixed references (don't change):**
- Jetson SSH aliases: `jetson` (WiFi), `jetson-eth` (Ethernet), `jetson-usb` (USB-C)
- Jetson config path: `/opt/digital-twin/config.json`
- Calibration path: `~/.cache/huggingface/lerobot/calibration/`
- Model storage: `/opt/digital-twin/models/` → symlink to `/mnt/ssd/models/`

**Guides (read these for troubleshooting and detailed procedures):**
- LeRobot commands: #[[file:operations/01-lerobot_commands.md]]
- Demo platform: #[[file:operations/02-demo_platform.md]]
- Setup guides: `set-up/`
- Troubleshooting: `troubleshooting/`

---

## SSH Connection Strategy

> For full SSH setup, WiFi management, and venue workflows, read #[[file:set-up/02-setup_ssh-guide.md]].

Try connections in this priority order for demo venues:
1. **Ethernet (direct cable)**: most reliable at venues, no WiFi dependency
2. **USB-C (direct cable)**: always works, fixed IP
3. **WiFi**: fallback, IP may change between locations

If Ethernet fails: Mac side may need manual IP config on the dongle interface (the specific interface name varies — check with `ifconfig` for the new adapter).

---

## Checks to perform (in parallel where possible):

### 0. Cloud Instance Access
This is the first thing to verify — the dashboard and DCV run on EC2, so nothing works if it's stopped or your IP is blocked.

**Check instance state:**
```bash
aws-pai status
```

**If stopped — wake it (~2-3 min boot):**
```bash
aws-pai deploy --wake
```
Then get the new IP: `aws-pai status`

**If running but dashboard/DCV unreachable — IP drift (new venue/WiFi):**

Your public IP changed but the security group still allows the old one. This is the most common issue at new venues.
```bash
aws-pai cloud fix-ip
```
This auto-detects your new IP, updates the EC2 security group ingress rules (ports 8443 DCV + 22 SSH + 3000 dashboard), and updates `config.json`.

If auto-detect fails (e.g. behind captive portal), provide IP manually:
```bash
aws-pai cloud fix-ip --ip <YOUR_PUBLIC_IP>
```
Find your IP at https://ifconfig.me.

**To stop the instance after the demo:**
```bash
aws-pai cloud stop
```

**Key facts:**
- Instance: `<YOUR_INSTANCE_ID>` in your configured region (g6e.8xlarge)
- Public IP changes on every stop/start — always re-check with `aws-pai status`
- Dashboard: `http://<public-ip>:3000` — works even with Jetson off (edge shows disconnected)
- DCV (Isaac Sim remote desktop): `https://<public-ip>:8443`
- IP drift happens whenever you connect to a new WiFi network — always run `fix-ip` at new venues

### 1. Network Connectivity
- Verify SSH access to Jetson (try available methods until one works)
- Check Jetson has internet access: `ping -c 2 8.8.8.8`
- Check Jetson can resolve AWS IoT endpoint: `host iot.<REGION>.amazonaws.com` (derive region from Jetson config)
- Check MQTT connectivity from service logs (look for "Connected to IoT Core")
- If no internet: the digital twin still works over direct cable (telemetry publishes when connectivity returns), but real-time cloud sync won't work. Suggest connecting to venue WiFi via `nmcli` or using the demo in local-only dashboard mode.

### 2. USB Serial Ports (Arms)
- List `/dev/ttyACM*` devices on Jetson
- Identify each device using `udevadm info` (serial number + USB path)
- Check serial port permissions (should be accessible to service user)
- Read serial port config from Jetson's config.json:
  - `teleop.leaderPort` — leader arm
  - `teleop.followerPort` — follower arm
  - `component.serialPort` — telemetry source
- Compare actual devices against config and flag mismatches
- Key behavior: single arm always enumerates as lowest index. Both arms → stable assignment per physical USB port.
- If ports reassigned (hot-plug): reboot resets stable numbering. If still wrong: update Jetson config with targeted merge (never overwrite full file).

### 3. Cameras
- List `/dev/video*` devices on Jetson
- Identify each camera using `v4l2-ctl --device=/dev/videoN --info`
- Read camera config from Jetson config.json: `camera.deviceIndex` and `cameras[]` array
- Compare actual devices against config
- Flag any missing or reordered cameras
- Camera stale-lock: if backend reports camera started but endpoint returns 204, restart the service (second restart clears V4L2 lock)

### 4. Services
- Check service status: `aws-pai edge status`
- Check recent logs: `aws-pai edge logs`
- Verify these indicators in logs:
  - "Connected to IoT Core" — MQTT working
  - "Telemetry publishing at N Hz" — servo reader working
  - Camera endpoint returning 200 — camera feed active
- If MQTT shows `UNEXPECTED_HANGUP` or credential errors: IoT certs may be invalid (happens if cloud stack was destroyed and redeployed with new certs — Jetson needs re-provisioning)

### 5. Calibration Files
- Check calibration directory exists: `~/.cache/huggingface/lerobot/calibration/`
- Read `teleop.robotId` and `teleop.leaderId` from Jetson config
- Verify matching calibration files exist for both IDs
- If missing: re-run calibration with project venv, or restore from backup if available

### 6. Config Alignment
- Compare local repo `config.json` against Jetson `/opt/digital-twin/config.json` for key fields:
  - Serial ports (teleop, component, edge)
  - Camera indices
  - IoT settings (deviceId, topicPrefix)
  - Inference model settings
- Flag any drift between local and deployed config
- If drift found: update local config to match Jetson (Jetson config is authoritative for device-specific settings)

### 7. Dashboard
- Verify dashboard is accessible at `http://<jetson-ip>:<port>` (derive from config/SSH)
- Check camera feed is loading (not just HTML)
- If dashboard shows unstyled/raw HTML: UI dist may need rebuild and resync

### 8. System Health
- Check disk space: `df -h` — flag if root < 10% free or SSD is full
- Verify model storage: `/opt/digital-twin/models` should be a symlink to SSD mount
  - If symlink broken or models on root: disk will fill fast (models are 10-30 GB each)
- Check RAM: `free -h`
- Check for thermal throttling in logs (Jetson power mode)

---

## Output

Present results as a checklist:
- **PASS** / **FAIL** / **WARN** for each check
- For failures: explain what's wrong and suggest the fix (run it if obvious and safe)
- At the end: one-line verdict — "Ready for demo" or "Needs fixes: ..."

---

## Troubleshooting References

When a check fails, read the relevant guide for fix procedures:
- Network/SSH issues → #[[file:set-up/02-setup_ssh-guide.md]]
- Serial port / arm / camera issues → #[[file:operations/01-lerobot_commands.md]]
- Digital twin / MQTT / service errors → #[[file:operations/02-demo_platform.md]]
- GR00T-specific issues → #[[file:troubleshooting/groot_inference_stuck.md]]

---

## Hard Rules

- **SSH proactively** — do not ask user to run commands on Jetson, do it directly
- **Never overwrite Jetson config.json** — merge specific keys only if fixes needed
- **Read config values from actual files** — don't assume hardcoded defaults
- **Region, ports, IPs can change** — always derive from config, not from memory
