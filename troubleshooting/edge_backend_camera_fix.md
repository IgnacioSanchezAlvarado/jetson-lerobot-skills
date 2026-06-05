# Edge Backend Camera Fix (2026-05-26)

## Symptoms

- Dashboard shows no camera feed (204 No Content on `/api/camera/latest`)
- Logs show: `Camera capture not available: local variable 'prefix' referenced before assignment`
- Or: `NameError: free variable 'inference_runner' referenced before assignment in enclosing scope`
- Service crash-loops with: `PermissionError: [Errno 13] Permission denied: '/opt/digital-twin/edge-backend/main.py'`

## Root Causes

### 1. Greengrass file permissions

Greengrass deploys files as `ggc_user:ggc_group` with mode `640`. The `dt-edge-backend` systemd service runs as `igsalvarjetson`, who can't read them.

**Fix (temporary — resets on next Greengrass deploy):**
```bash
ssh jetson-eth "sudo chmod -R o+rX /opt/digital-twin/"
ssh jetson-eth "sudo systemctl restart dt-edge-backend"
```

**Fix (permanent — survives redeploys):**
```bash
ssh jetson-eth "sudo usermod -aG ggc_group igsalvarjetson"
# Requires logout/login or reboot to take effect
```

### 2. Variable ordering bug in main.py

The camera-pump closure in `main.py` references `prefix` and `inference_runner` before they're assigned in the enclosing scope. The camera block (~line 166) runs before:
- `prefix` is defined (~line 282)
- `inference_runner` is defined (~line 288)

**Fix — add before the camera section (before `# 2c. Start local camera capture`):**
```python
    # Compute MQTT topic prefix early (camera pump needs it)
    iot_cfg = config["iot"]
    prefix = f"{iot_cfg['topicPrefix']}/{iot_cfg['deviceId']}"
    inference_runner = None  # initialized later; camera pump checks it
```

The later assignment of `iot_cfg`/`prefix` at line ~284 and `inference_runner` at ~290 will simply reassign.

### 3. Camera device index shift after crash-loop

After multiple restarts or a crash-loop, V4L2 device indices can shift (e.g., C922 moves from `/dev/video2` to `/dev/video3`). The service fails with:
```
VIDEOIO(V4L2:/dev/video2): can't open camera by index
```

**Diagnose:**
```bash
ssh jetson-eth "for d in /dev/video*; do echo \$d:; v4l2-ctl --device=\$d --info 2>&1 | grep 'Card type'; done"
```

**Fix — update config with correct index:**
```bash
ssh jetson-eth 'sudo python3 -c "
import json
with open(\"/opt/digital-twin/config.json\") as f: c = json.load(f)
c[\"camera\"][\"deviceIndex\"] = NEW_INDEX  # replace with actual index
with open(\"/opt/digital-twin/config.json\", \"w\") as f: json.dump(c, f, indent=2)
"'
ssh jetson-eth "sudo systemctl restart dt-edge-backend"
```

A reboot typically restores the original device numbering.

## Proper Code Fix (for the repo)

In `edge/component/edge-backend/main.py`, move the `prefix` and `inference_runner` definitions to before the camera block. The diff should look like:

```diff
     smoother.start()

+    # Compute MQTT topic prefix early (camera pump closure needs it)
+    iot_cfg = config['iot']
+    prefix = f"{iot_cfg['topicPrefix']}/{iot_cfg['deviceId']}"
+    inference_runner = None  # assigned later in §3; camera pump checks it safely
+
     # 2c. Start local camera capture for MQTT streaming.
```

And remove the duplicate `iot_cfg = config['iot']` / `prefix = ...` from the later inference section (or leave it — reassignment is harmless).

## Ethernet Connection Troubleshooting

The Jetson AGX Orin has **two physical RJ45 ports**. Only one has the static IP `10.0.0.1` configured via NetworkManager. If Ethernet SSH gives "Host is down" (ARP incomplete):

1. Swap the cable to the other RJ45 port
2. Verify Mac-side IP: `sudo ifconfig en11 10.0.0.2 netmask 255.255.255.0 up`
3. Retry: `ssh jetson-eth`

## Full Recovery Sequence

```bash
# 1. Fix permissions
ssh jetson-eth "sudo chmod -R o+rX /opt/digital-twin/"

# 2. Check camera device index
ssh jetson-eth "for d in /dev/video*; do echo \$d:; v4l2-ctl --device=\$d --info 2>&1 | grep 'Card type'; done"
# Update config.json if C922 moved from expected index

# 3. Restart service
ssh jetson-eth "sudo systemctl restart dt-edge-backend"

# 4. Verify (wait 5s for startup)
ssh jetson-eth "curl -s -o /dev/null -w '%{http_code}' http://localhost:3000/api/camera/latest"
# Should return 200
```
