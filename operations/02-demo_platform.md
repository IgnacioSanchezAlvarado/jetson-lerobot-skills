# Demo Platform — Quick Reference

## Demo Day Checklist

Quick sequence when arriving at a new venue:

1. `source .venv/bin/activate` (Mac, in project dir)
2. `aws-pai deploy --wake` (start cloud instance)
3. `aws-pai cloud fix-ip` (update security group for new WiFi)
4. Connect to Jetson (Ethernet preferred): `ssh jetson-eth`
5. `ssh jetson "sudo systemctl restart dt-edge-backend"`
6. Open Jetson dashboard: `http://<jetson-ip>:3000`
7. Open EC2 dashboard: `http://<public-ip>:3000` (get IP from `aws-pai status`)
8. Open DCV: `https://<public-ip>:8443`
9. Test: `aws-pai arm test real2sim --live`

After demo:
- `aws-pai cloud stop` (stop EC2, save money)

---

## Python venv (Mac)

The `aws-pai` CLI requires a Python venv in the project repo:

```bash
cd ~/Documents/Claude-code/jetson-lerobot/lerobot-so101-aws-sim2real2sim
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

After initial setup, just activate before use:
```bash
cd ~/Documents/Claude-code/jetson-lerobot/lerobot-so101-aws-sim2real2sim
source .venv/bin/activate
```

Verify: `aws-pai --help`

---

## Digital Twin — Quick Connect

Steps to get the arm mirroring in the dashboard:

1. Fix serial permissions: `ssh jetson "sudo chmod 666 /dev/ttyACM0"`
2. Restart service: `ssh jetson "sudo systemctl restart dt-edge-backend.service"`
3. Open a dashboard (see below)

Verify (want to see "Connected to IoT Core" + "Telemetry publishing"):
```bash
ssh jetson "journalctl -u dt-edge-backend -n 10 --no-pager"
```

If arm not detected: `ssh jetson "ls /dev/ttyACM*"` — replug if missing.

### Two dashboards

| Dashboard | URL | When to use |
|-----------|-----|-------------|
| **Jetson (local)** | `http://<jetson-ip>:3000` | Edge-only demos, no cloud needed, lower latency |
| **EC2 (cloud)** | `http://<ec2-public-ip>:3000` | Full system view, works even with Jetson off |

Both share the same UI. The EC2 dashboard adds Isaac Sim integration, training panels, and GR00T controls. The Jetson dashboard focuses on mode switching, edge inference, and local servo control.

**Jetson dashboard**: requires direct network to Jetson (Ethernet/WiFi/USB-C).

**EC2 dashboard**: requires cloud instance running + IP allowed in security group. Get the public IP from `aws-pai status`.

---

## Cloud Instance

Commands you'll use most at demo venues:

| Command | What it does |
|---------|--------------|
| `aws-pai deploy --wake` | Start stopped EC2 instance (~2-3 min boot) |
| `aws-pai cloud stop` | Stop instance (save $$$) |
| `aws-pai cloud fix-ip` | Update security group after IP change (new WiFi/venue) |
| `aws-pai status` | Show DCV URL, public IP, instance state |
| `aws-pai cloud diagnose` | Run 12-check diagnostics |
| `aws-pai arm mode <target>` | Switch mode: real2sim / sim2real / cloud_inference / edge_inference |
| `aws-pai arm estop` | Emergency stop — kill all servo torque |

Key facts:
- Instance: g6e.8xlarge in us-east-1, ~$3.44/hr
- Public IP changes on every stop/start — always re-check with `aws-pai status`
- **At new venues**: always run `aws-pai cloud fix-ip` (your public IP changed)

---

## Appendix: Full CLI Reference

### Getting Started

| Command | What it does |
|---------|--------------|
| `aws-pai` | Rich status dashboard (no subcommand) |
| `aws-pai doctor` | Check all prerequisites |
| `aws-pai demo` | Guided bidirectional demo walkthrough |
| `aws-pai cost` | Show GPU cost estimate |
| `aws-pai deploy` | Deploy CDK stacks |
| `aws-pai deploy --wake` | Start stopped EC2 (no full CDK deploy) |
| `aws-pai deploy --ui-only` | Fast-sync dashboard UI only (~30s) |
| `aws-pai destroy` | Destroy all stacks (careful!) |

### Cloud Instance

| Command | What it does |
|---------|--------------|
| `aws-pai cloud ssh` | Shell on EC2 via SSM |
| `aws-pai cloud logs` | Tail EC2 logs (--backend, --bootstrap, --groot) |
| `aws-pai cloud refresh` | Terminate + re-launch EC2 with latest code |
| `aws-pai cloud fix-ip` | Update security group after IP change |
| `aws-pai cloud fix-ip --ip X.X.X.X` | Manual IP if auto-detect fails |
| `aws-pai cloud stop` | Stop instance |
| `aws-pai cloud diagnose` | Full pipeline diagnostics (12 checks) |

### Edge (Jetson)

| Command | What it does |
|---------|--------------|
| `aws-pai edge status` | Service status + GPU info |
| `aws-pai edge logs` | Tail edge backend logs |
| `aws-pai edge ssh` | SSH via IoT Secure Tunnel (works anywhere) |
| `aws-pai edge ssh --direct` | Direct SSH (LAN/USB-C, lower latency) |
| `aws-pai edge setup --dev` | Push code updates to Jetson (fast rsync) |
| `aws-pai edge init` | Configure Jetson connection (IP, SSH key) |
| `aws-pai edge provision` | Generate fleet bootstrap bundle |
| `aws-pai edge download-model <key>` | Download model weights to Jetson |
| `aws-pai edge remove-model <key>` | Delete model from Jetson |
| `aws-pai edge download-groot <name>` | Pull GR00T model from S3 |
| `aws-pai edge fleet list` | List all devices in fleet |
| `aws-pai edge fleet diagnose <name>` | Check cloud-side state |
| `aws-pai edge fleet reset <name>` | Deregister a fleet device |

### Robot

| Command | What it does |
|---------|--------------|
| `aws-pai arm test real2sim` | Test arm→sim telemetry (--live for real-time) |
| `aws-pai arm test sim2real` | Test sim→arm commands |
| `aws-pai arm mode <target>` | Switch mode: real2sim / sim2real / cloud_inference / edge_inference |
| `aws-pai arm estop` | Emergency stop — kill all servo torque |
| `aws-pai arm detect` | Auto-detect arm serial port (--save to persist) |

### Models

| Command | What it does |
|---------|--------------|
| `aws-pai models list` | Show available models + cache status |
| `aws-pai models use <key>` | Set active model |
| `aws-pai models infer <task>` | Run VLA inference (--model, --continuous) |
| `aws-pai models build [key]` | Build Docker image (--push, --local) |
| `aws-pai models download <key>` | Pre-cache model on EC2 |
| `aws-pai models remove <key>` | Delete cached model from EC2 |
| `aws-pai models groot status` | GR00T pipeline status |
| `aws-pai models groot publish` | Publish GR00T checkpoint (EC2→S3) |
