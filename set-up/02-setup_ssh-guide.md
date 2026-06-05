Jetson SSH Quick Reference

**Connection Methods**

| Method | Command | When to use |
|--------|---------|-------------|
| WiFi | `ssh jetson` | Both Mac and Jetson on same network |
| Ethernet | `ssh jetson-eth` | Direct cable via dongle, no WiFi needed (demo venues) |
| USB-C | `ssh jetson-usb` | Direct USB-C cable, no network needed |

Your `~/.ssh/config` has all three host aliases configured.

Ethernet setup: Jetson `eth1` → Ethernet cable → USB-C dongle → Mac. Static IPs: Jetson `10.0.0.1`, Mac `10.0.0.2`. Jetson side is persistent (NetworkManager). Mac side needs `sudo ifconfig en11 10.0.0.2 netmask 255.255.255.0 up` after each dongle reconnect.

USB-C note: `ssh jetson-usb` requires a **direct** USB-C cable between Mac and Jetson. Does NOT work through a dongle/hub.

**Common System Checks**

```bash
df -h                         # disk space (check /home and mounted drives)
free -h                       # RAM usage
sudo tegrastats               # real-time GPU, CPU, temp, power (Ctrl+C to exit)
sudo jtop                     # interactive dashboard with graphs (q to quit)
ps aux | grep python          # find running Python processes
ps aux | grep lerobot         # find LeRobot scripts
```

**File Transfer**

```bash
# Mac → Jetson
scp /path/to/file.txt jetson:~/
scp -r /path/to/folder jetson:~/

# Jetson → Mac
scp jetson:/path/to/file.txt ~/Downloads/
```

Replace `jetson` with `jetson-usb` for USB-C transfers.

**WiFi Management (headless / no monitor)**

Useful at demo venues — manage WiFi entirely over SSH (via USB-C direct or existing WiFi).

```bash
nmcli dev wifi list                                  # scan available networks
nmcli dev wifi connect "NetworkName" password "pass" # connect to a new network
nmcli con show                                       # list saved connections
nmcli con up "NetworkName"                           # switch to a saved network
nmcli con delete "NetworkName"                       # forget a network
ip addr show wlP1p1s0                                # check current WiFi IP
```

Demo venue workflow (Ethernet — recommended):
1. Plug Ethernet cable from Jetson → dongle → Mac
2. On Mac: `sudo ifconfig en11 10.0.0.2 netmask 255.255.255.0 up`
3. `ssh jetson-eth` — done, no WiFi needed
4. Optionally join venue WiFi from there: `nmcli dev wifi connect "VenueWiFi" password "pass"`

Demo venue workflow (WiFi only):
1. Connect Mac to Jetson via direct USB-C cable → `ssh jetson-usb`
2. Scan networks → `nmcli dev wifi list`
3. Connect Jetson to venue WiFi → `nmcli dev wifi connect "VenueWiFi" password "pass"`
4. Get new IP → `ip addr show wlP1p1s0`
5. Update `~/.ssh/config` on Mac with the new IP
6. Disconnect USB-C, switch to `ssh jetson` over WiFi

**Power Management**

```bash
sudo shutdown -h now    # shutdown immediately
sudo reboot             # reboot
```

**Notes**

* If WiFi IP changes (DHCP reassignment), update the `HostName` in `~/.ssh/config` for the `jetson` entry.
* USB connection IP (`192.168.55.1`) is fixed and won't change.
* At venues, you can also use a phone hotspot — connect both Mac and Jetson to it, no dongle needed.
