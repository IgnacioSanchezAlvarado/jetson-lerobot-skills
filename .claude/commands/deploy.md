---
description: Full project deployment from fresh clone to working demo. Covers Mac setup, cloud deploy, and Jetson edge sync.
---

Guide the user through deploying the LeRobot SO-101 AWS Sim2Real2Sim project. Follow these phases in order.

**Always prefer `aws-pai` CLI commands over raw AWS CLI or SSH commands.** The CLI wraps complex operations with proper error handling and config management. Fall back to raw commands when aws-pai doesn't cover the operation, isn't working properly, or doesn't provide enough detail for diagnosis.

## What's stable vs dynamic

**Stable commands (copy-paste as-is):**
- `python3 -m venv .venv && source .venv/bin/activate && pip install -e ".[dev]"`
- `aws-pai doctor`, `aws-pai init`, `aws-pai deploy`, `aws-pai status`
- `aws-pai edge setup --dev`, `aws-pai edge init`
- `aws-pai cloud diagnose`
- `cat ~/.cache/huggingface/token`
- `echo "HF_TOKEN=$(cat ~/.cache/huggingface/token)" > .env.local`
- `ssh jetson "sudo systemctl restart dt-edge-backend"`
- `ssh jetson "systemctl is-active dt-edge-backend"`
- `ssh jetson "journalctl -u dt-edge-backend -n 30 --no-pager"`
- `ssh jetson "ls /dev/ttyACM*"`
- `ssh jetson "ls /dev/video*"`

**Dynamic values (read from config.json or detect at runtime):**
- AWS region → `config.json` → `aws.region`
- IoT device ID → `config.json` → `iot.deviceId` (thingName = `lerobot-<deviceId>`)
- Jetson IP/host → `config.json` → `edge.host` (or SSH alias)
- Serial ports → detect from `/dev/ttyACM*` + compare to config
- Camera indices → detect from `/dev/video*` + compare to config
- Dashboard port → `config.json` → `edge.dashboardPort`
- Stack names → check CloudFormation, filter for project-related stacks
- ECR repos → check ECR, filter for `dt-*` or `cuda-*` prefixes

**Fixed references (don't change across deploys):**
- HuggingFace token location: `~/.cache/huggingface/token`
- Jetson SSH aliases: `jetson`, `jetson-eth`, `jetson-usb` (in `~/.ssh/config`)
- Jetson config path: `/opt/digital-twin/config.json`
- Jetson venv: `/opt/digital-twin/venv/`
- Jetson models: `/opt/digital-twin/models/` → symlink to `/mnt/ssd/models/`
- Calibration: `~/.cache/huggingface/lerobot/calibration/`

**Guides (consult for troubleshooting and detailed procedures):**
- Setup guides: `set-up/`
- LeRobot commands: `operations/01-lerobot_commands.md`
- Demo platform: `operations/02-demo_platform.md`
- Troubleshooting: `troubleshooting/`

---

## Phase 1: Mac Local Setup

### 1.1 Python Environment
- Create venv in repo root: `python3 -m venv .venv`
- Activate: `source .venv/bin/activate`
- Install: `pip install -e ".[dev]"`
- Verify: `aws-pai --help` runs without errors

**Common issues to diagnose:**
- `pip` not found → use `pip3` or `python3 -m pip`
- "externally-managed-environment" → venv not activated
- Stale binary shadows venv → check `which aws-pai`, remove if pointing outside `.venv/`

### 1.2 Prerequisites Check
- Run: `aws-pai doctor`
- All required checks must pass. If any fail, diagnose and fix before continuing.

### 1.3 HuggingFace Token
- Check if token exists: `cat ~/.cache/huggingface/token`
- Copy into project: `echo "HF_TOKEN=$(cat ~/.cache/huggingface/token)" > .env.local`
- `aws-pai init` reads from `.env.local` automatically
- If token is missing from `~/.cache/huggingface/token`: user needs to get one from https://huggingface.co/settings/tokens

### 1.4 Initialize Config
- Run: `aws-pai init`
- Key guidance for prompts:
  - **Device ID**: must match what's provisioned on Jetson (check Jetson's `/opt/digital-twin/config.json` → `_provision.thingName` to derive it)
  - **Fleet provisioning**: Yes if Jetson uses fleet self-registration (check if Greengrass is installed on Jetson)
  - **HuggingFace token**: should auto-detect from `.env.local`
  - **Region and instance type**: user's choice, use existing values if redeploying
- This creates `config.json` (gitignored, per-developer)

---

## Phase 2: Cloud Deploy

### 2.0 Pre-Deploy: Check CloudFormation State
Before deploying, check for orphaned stacks or resources from a previous deployment. Read the region from `config.json` and use it in all AWS CLI commands.

**Step 1 — Check stack status:**
```bash
aws cloudformation list-stacks --region <REGION> --query "StackSummaries[?contains(StackName,'LeRobot') || contains(StackName,'IsaacSim') || contains(StackName,'CodeBuild') || contains(StackName,'CudaMirror')].{Name:StackName,Status:StackStatus}" --output table
```

**Step 2 — Resolve based on what you find:**

| Stack Status | Action |
|---|---|
| No stacks exist | Clean slate — proceed to deploy |
| `CREATE_COMPLETE` / `UPDATE_COMPLETE` | Healthy — deploy will update |
| `DELETE_FAILED` | Investigate which resources are stuck (describe-stack-events, filter for DELETE_FAILED). Common culprits: IoT Thing/Policy with cert attachments. If Jetson is still provisioned, use `--retain-resources` to keep IoT resources alive. If starting fresh, detach certs first (`aws-pai edge fleet reset`) then delete. |
| `REVIEW_IN_PROGRESS` / `ROLLBACK_COMPLETE` / `CREATE_FAILED` | Stuck — delete the stack and retry |

**Step 3 — Check for orphaned resources that would block CDK:**
- ECR repos: `aws ecr describe-repositories --region <REGION>` — look for project repos that exist outside of any stack. CDK fails with "already exists" if it tries to create a resource that's orphaned. Delete empty repos; for repos with images, confirm user is OK losing them first.
- IoT things/policies: `aws iot list-things` / `aws iot list-policies` — look for `lerobot-*` resources. These are created by fleet provisioning OUTSIDE CloudFormation, so they persist after stack deletion. Clean approach: delete them and re-provision Jetson after deploy (re-provisioning is fast: `aws-pai edge provision`).
- IoT cleanup procedure (when certs are attached):
  1. `aws iot list-policy-principals --policy-name <POLICY>` → get cert ARN
  2. `aws iot detach-policy --policy-name <POLICY> --target <CERT_ARN>`
  3. `aws iot detach-thing-principal --thing-name <THING> --principal <CERT_ARN>`
  4. `aws iot update-certificate --certificate-id <ID> --new-status INACTIVE`
  5. `aws iot delete-certificate --certificate-id <ID>`
  6. `aws iot delete-policy --policy-name <POLICY>`
  7. `aws iot delete-thing --thing-name <THING>`
- Secrets Manager: check for `isaac-sim-dt/*` secrets that might block recreation.

**General principle**: When in doubt, prefer clean-slate: delete orphaned resources and re-provision the Jetson after deploy. Re-provisioning is cheap and fast. Trying to preserve orphaned IoT state across deploys causes more issues than it solves.

### 2.1 Deploy CDK Stacks
- Run: `aws-pai deploy`
- If it fails, read the error carefully:
  - "already exists" → orphaned resource, handle per step 2.0
  - "DELETE_FAILED" → stack stuck, handle per step 2.0
  - CDK synthesis errors → code issue, investigate `infra/` stack files
  - Permissions errors → check IAM role/user has CDK deploy permissions
- On success, stacks create IoT Core resources + EC2 with Isaac Sim

### 2.2 Verify Cloud
- Run: `aws-pai status` — confirm DCV URL, instance IP, IoT endpoint are present
- Run: `aws-pai cloud diagnose` — should pass all checks
- If instance is stopped: `aws-pai deploy --wake`

---

## Phase 3: Edge Sync (Jetson)

> For detailed SSH, WiFi, and Ethernet setup procedures, read `set-up/02-setup_ssh-guide.md`.
> For digital twin connection details, read `operations/05-digitaltwin_guide.md`.

### 3.1 Verify Jetson Connectivity
- Try SSH in priority order: WiFi alias → Ethernet alias → USB-C alias
- If Ethernet fails: Mac may need manual IP config on dongle interface (see SSH guide)

### 3.2 Check Jetson State Before Sync
- Check Greengrass: `ssh jetson "systemctl is-active greengrass"`
- Check provisioning: read `/opt/digital-twin/config.json` → `_provision` block
  - If `_provision` has `iotDataEndpoint` and `thingName` → safe to sync code
  - If missing → run `aws-pai edge provision` and bootstrap the Jetson first (see `set-up/01-setup_jetson-plan.md` Phase 4)
- **Re-provisioning after stack redeploy**: If IoT resources were deleted and recreated, the Jetson's old device cert is invalid. Run the bootstrap with `--force` to overwrite the old Greengrass config: `sudo bash fleet-bootstrap.sh --force`. Without `--force`, Greengrass skips install and keeps the stale cert, causing MQTT "connection closed unexpectedly" errors.

### 3.3 Configure Edge Connection in Local Config
- **Required on fresh clone** — `aws-pai init` does NOT configure edge settings. Without this, `aws-pai edge setup` will fail with "Edge device not configured".
- Run: `aws-pai edge init` (interactive — sets host, user, SSH key in config.json)
- Typical values: host=`jetson` (SSH alias), user=your Jetson username, key=`~/.ssh/id_ed25519`

### 3.4 Sync Code to Jetson
- Run: `aws-pai edge setup --dev`
- **CRITICAL**: config.json on Jetson is ONLY seeded on first deploy. Existing config is preserved.
- Never manually overwrite `/opt/digital-twin/config.json` — use targeted key merges only

### 3.5 Verify Hardware (Arms + Cameras)
- Check USB serial ports and cameras match Jetson config
- Key behavior: single arm always enumerates as `/dev/ttyACM0`
- For detailed port identification and camera mapping, read `operations/01-lerobot_commands.md` (camera wiring table and teleoperation sections)

### 3.6 Start Edge Services + Verify
- Restart: `ssh jetson "sudo systemctl restart dt-edge-backend"`
- Check logs for: "Connected to IoT Core" + "Telemetry publishing at N Hz"
- **Camera stale-lock**: if endpoint returns 204, restart service again (second restart clears V4L2 lock)
- Verify calibration files exist matching `teleop.robotId` and `teleop.leaderId`

---

## Phase 4: End-to-End Verification

### 4.1 Test Telemetry Flow
- Run: `aws-pai arm test real2sim --live`
- Verify: data flowing to cloud (check EC2 logs or Isaac Sim scene)

### 4.2 Dashboard
- Open browser at `http://<jetson-ip>:<dashboardPort>` (read port from config)
- Verify: joint positions updating, camera feed visible, health indicators green

### 4.3 Full System Status
- `aws-pai status` — cloud side
- `aws-pai edge status` — edge side

---

## Hard Rules (never violate)

- **Never run `cdk deploy` / `cdk destroy` directly** — always use `aws-pai deploy` / `aws-pai destroy`
- **Never overwrite Jetson config.json wholesale** — merge specific keys only (protects `_provision` block)
- **Before destroying stacks**: deregister fleet devices first (`aws-pai edge fleet reset <thingName>`), then destroy — prevents DELETE_FAILED
- **Cost awareness**: GPU instances cost ~$3-4/hour. Remind user to destroy when done.
- **Models on Jetson are preserved** across code syncs — they live on SSD (symlinked)
- **Venvs on Jetson are preserved** — Tegra-compiled PyTorch is expensive to rebuild
