# O11 Pro  WSL (Windows Subsystem for Linux) Setup Guide

Complete guide to running O11 Pro on Windows using WSL. This covers everything from installing WSL to running O11 as a background service with auto-start.

---

## Prerequisites

- **Windows 10** (Build 19041+) or **Windows 11**
- **WSL 2** with Ubuntu (recommended)
- At least **2 GB RAM** free for WSL
- **4 GB+ disk space** for O11 + dependencies

---

## Step 1  Install WSL 2

Open **PowerShell as Administrator** (right-click Start → Terminal (Admin)):

```powershell
wsl --install
```

This installs WSL 2 with Ubuntu by default. Restart your computer when prompted.

After restart, a Ubuntu terminal will open and ask you to create a username and password. This is your Linux user  remember it.

> **If you already have WSL installed**, make sure you're on WSL 2:
> ```powershell
> wsl --set-default-version 2
> wsl --install Ubuntu
> ```

Verify your installation:

```powershell
wsl --list --verbose
```

You should see:

```
  NAME      STATE           VERSION
* Ubuntu    Running         2
```

If VERSION shows `1`, upgrade it:

```powershell
wsl --set-version Ubuntu 2
```

---

## Step 2  Update Ubuntu

Open WSL (search "Ubuntu" in Start menu or run `wsl` in PowerShell):

```bash
sudo apt update && sudo apt upgrade -y
```

---

## Step 3  Install Dependencies

O11 requires FFmpeg for transcoding and remuxing streams. Install it along with other useful tools:

```bash
sudo apt install -y ffmpeg curl wget nano unzip
```

Verify FFmpeg:

```bash
ffmpeg -version | head -1
```

You should see something like: `ffmpeg version 4.4.2-0ubuntu0.22.04.1`

---

## Step 4  Download O11 Pro

### Option A: From GitHub Release

```bash
# Create o11 directory
mkdir -p ~/o11 && cd ~/o11

# Download the latest unpacked binary
wget https://github.com/Ap0dexMe0/o11pro-unpacked/releases/latest/download/o11pro -O o11pro

# Make it executable
chmod +x o11pro
```

### Option B: From Local Windows File

If you already downloaded the binary on Windows, you can access it from WSL. Windows drives are mounted under `/mnt/`:

```bash
# Example: file is in your Windows Downloads folder
mkdir -p ~/o11 && cd ~/o11

# Copy from Windows to WSL home
cp /mnt/c/Users/YOUR_USERNAME/Downloads/o11pro ./

# Make it executable
chmod +x o11pro
```

> **Replace `YOUR_USERNAME`** with your actual Windows username. Use tab-completion: type `/mnt/c/Users/` and press Tab.

### Option C: Using Windows Explorer

You can also drag and drop files directly into the WSL filesystem:

1. Open WSL terminal
2. Type `explorer.exe .` to open Windows Explorer at the current WSL directory
3. Copy `o11pro` into the Explorer window

---

## Step 5  First Run

```bash
cd ~/o11

# Start with a port and credentials
./o11pro -p 8080 -user admin -password mypass -stdout
```

You should see:

```
  ╔══════════════════════════════════════════════╗
  ║     o11 Pro Cracked [Nulled]                 ║
  ║            Unpacked Version [Ap0dexMe0]      ║
  ╚══════════════════════════════════════════════╝

INFO: O11 is starting [version nulled!!]
INFO: loglevel set to 2
WARN: Use temporary account to login to Web UI: admin / OtoN4Fx0
INFO: streaming listening at 0.0.0.0:8080
INFO: webif http listening at 0.0.0.0:8080
INFO: loaded 0 provider(s)
```

> **If you get "Permission denied"**: Run `chmod +x o11pro` again. If you get a "cannot execute binary file" error, make sure you're on WSL 2 (not WSL 1) and using an x86-64 Ubuntu.

Open your Windows browser and go to:

```
http://localhost:8080
```

Log in with `admin` / `mypass` (or the temporary credentials shown in the log).

Press `Ctrl+C` in the WSL terminal to stop O11.

---

## Step 6  Accessing the Web UI from Windows

WSL 2 automatically forwards ports to Windows. You can access O11 from your Windows browser using:

| URL | When to use |
|-----|-------------|
| `http://localhost:8080` | Works in most cases (automatic port forwarding) |
| `http://127.0.0.1:8080` | Same as above, explicit IP |
| `http://<WSL-IP>:8080` | If localhost doesn't work (find IP with `hostname -I` inside WSL) |

### Finding your WSL IP address

```bash
hostname -I | awk '{print $1}'
```

Example output: `172.26.155.210`  then access `http://172.26.155.210:8080`

### Accessing from other devices on your LAN

By default, WSL 2 uses a NAT network. To allow other devices on your local network to access O11, you need to set up port forwarding on Windows:

Open **PowerShell as Administrator** and run:

```powershell
# Get WSL IP
$wslIP = wsl hostname -I
$wslIP = $wslIP.Trim()

# Forward port 8080 from Windows to WSL
netsh interface portproxy add v4tov4 address=0.0.0.0 port=8080 connectaddress=$wslIP connectport=8080

# Open Windows Firewall
New-NetFirewallRule -DisplayName "O11 Pro" -Direction Inbound -LocalPort 8080 -Protocol TCP -Action Allow
```

Now other devices can access O11 at `http://<YOUR_WINDOWS_IP>:8080`

> **Note**: The port proxy resets when WSL restarts (WSL gets a new IP). See the [Auto-Start section](#step-10--auto-start-on-windows-boot) for a permanent solution.

---

## Step 7  Running in Background

### Method A: Using `nohup` (Simple)

```bash
cd ~/o11

nohup ./o11pro -p 8080 -user admin -password mypass \
  -path ~/o11/data -stdout >> ~/o11/o11.log 2>&1 &

echo $! > ~/o11/o11.pid
echo "O11 started with PID $(cat ~/o11/o11.pid)"
```

To check if it's running:

```bash
ps -p $(cat ~/o11/o11.pid)
```

To stop it:

```bash
kill $(cat ~/o11/o11.pid)
```

To view logs:

```bash
tail -f ~/o11/o11.log
```

### Method B: Using `screen` (Recommended for Interactive)

```bash
# Install screen if not already
sudo apt install -y screen

# Create a named screen session
screen -S o11

# Start O11
cd ~/o11
./o11pro -p 8080 -user admin -password mypass -path ~/o11/data

# Detach from screen: press Ctrl+A then D
# Reattach later:
screen -r o11
```

### Method C: Using `systemd` Service (Best for Production)

WSL 2 supports systemd (on Ubuntu 22.04+). Create a service file:

```bash
sudo nano /etc/systemd/system/o11.service
```

Paste the following (adjust paths and user):

```ini
[Unit]
Description=O11 Pro Streaming Server
After=network.target

[Service]
Type=simple
User=YOUR_LINUX_USERNAME
WorkingDirectory=/home/YOUR_LINUX_USERNAME/o11
ExecStart=/home/YOUR_LINUX_USERNAME/o11/o11pro -p 8080 -user admin -password mypass -path /home/YOUR_LINUX_USERNAME/o11/data
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

> **Replace `YOUR_LINUX_USERNAME`** with your WSL username (run `whoami` to check).

Enable and start:

```bash
sudo systemctl daemon-reload
sudo systemctl enable o11
sudo systemctl start o11
```

Check status:

```bash
sudo systemctl status o11
```

View logs:

```bash
sudo journalctl -u o11 -f
```

Stop / restart:

```bash
sudo systemctl stop o11
sudo systemctl restart o11
```

> **If systemd doesn't work in WSL**, add this to `/etc/wsl.conf`:
> ```ini
> [boot]
> systemd=true
> ```
> Then restart WSL: `wsl --shutdown` in PowerShell, then reopen Ubuntu.

---

## Step 8  Setting Up with Working Directory

Use the `-path` flag to keep all O11 data organized:

```bash
mkdir -p ~/o11/data

./o11pro -p 8080 -user admin -password mypass -path ~/o11/data
```

O11 will create its directory structure automatically:

```
~/o11/data/
├── hls/live/          # Live stream segments
├── hls/replay/        # Replay segments
├── hls/vod/           # VOD segments
├── dl/tmp/            # VOD download temp files
├── epg/               # EPG data
├── logos/             # Channel logos
├── logs/              # Log files
├── providers/         # Provider scripts & configs
├── scripts/           # Auto-generated o11.py
├── rec/               # Recordings
├── o11.cfg            # Main config
├── o11-job.cfg        # Jobs config
└── o11-rec.cfg        # Recordings config
```

---

## Step 9  Adding Providers

### Via Web UI (Easiest)

1. Open `http://localhost:8080` in your Windows browser
2. Log in with your credentials
3. Click **"Add New Provider"** on the Providers page
4. Fill in the provider name and script settings
5. Click Save

### Via Provider Script

Place a Python script in the `providers/` directory:

```bash
nano ~/o11/data/providers/my_provider.py
```

Example provider script:

```python
#!/usr/bin/env python3
import requests, json

def get_channels():
    # Return list of channels
    return [
        {"name": "Channel 1", "url": "https://example.com/stream1.m3u8", "type": "live"},
        {"name": "Channel 2", "url": "https://example.com/stream2.m3u8", "type": "live"},
    ]

if __name__ == "__main__":
    action = sys.argv[1] if len(sys.argv) > 1 else "channels"
    if action == "channels":
        print(json.dumps(get_channels()))
```

Make it executable:

```bash
chmod +x ~/o11/data/providers/my_provider.py
```

Then configure O11 to use this script through the Web UI → Config → Script section.

---

## Step 10  Auto-Start on Windows Boot

### Method A: Windows Task Scheduler

This is the most reliable method for auto-starting O11 when Windows boots.

1. Open **Task Scheduler** on Windows (search "Task Scheduler")

2. Click **Create Task** (not Basic Task)

3. **General tab**:
   - Name: `O11 Pro Server`
   - Select **Run whether user is logged on or not**
   - Check **Run with highest privileges**

4. **Triggers tab**:
   - Click **New**
   - Begin the task: **At log on**
   - Click OK

5. **Actions tab**:
   - Click **New**
   - Action: **Start a program**
   - Program/script: `wsl`
   - Add arguments:
     ```
     -d Ubuntu -u YOUR_LINUX_USERNAME -- bash -c "cd ~/o11 && ./o11pro -p 8080 -user admin -password mypass -path ~/o11/data -stdout >> ~/o11/o11.log 2>&1"
     ```
   - Click OK

6. **Conditions tab**:
   - Uncheck "Start the task only if the computer is on AC power"

7. **Settings tab**:
   - Check "Run task as soon as possible after a scheduled start is missed"
   - Click OK

### Method B: Windows Startup Script with Port Forwarding

Create a PowerShell script that starts WSL + sets up port forwarding:

Open Notepad and save this as `C:\o11-start.ps1`:

```powershell
# Start O11 in WSL
wsl -d Ubuntu -u YOUR_LINUX_USERNAME -- bash -c "cd ~/o11 && nohup ./o11pro -p 8080 -user admin -password mypass -path ~/o11/data >> ~/o11/o11.log 2>&1 & echo $! > ~/o11/o11.pid"

# Wait for O11 to start
Start-Sleep -Seconds 3

# Set up port forwarding for LAN access
$wslIP = (wsl hostname -I).Trim()
netsh interface portproxy delete v4tov4 address=0.0.0.0 port=8080 2>$null
netsh interface portproxy add v4tov4 address=0.0.0.0 port=8080 connectaddress=$wslIP connectport=8080

# Open firewall
$rule = Get-NetFirewallRule -DisplayName "O11 Pro" -ErrorAction SilentlyContinue
if (-not $rule) {
    New-NetFirewallRule -DisplayName "O11 Pro" -Direction Inbound -LocalPort 8080 -Protocol TCP -Action Allow
}

Write-Host "O11 Pro is running at http://localhost:8080"
Write-Host "LAN access: http://$((Get-NetIPAddress -AddressFamily IPv4 | Where-Object { $_.InterfaceAlias -notmatch 'Loopback|vEthernet' -and $_.IPAddress -notmatch '^169' } | Select-Object -First 1).IPAddress):8080"
```

Create a shortcut in the Startup folder:

1. Press `Win+R`, type `shell:startup`, press Enter
2. Right-click → New → Shortcut
3. Location: `powershell.exe -ExecutionPolicy Bypass -File "C:\o11-start.ps1"`
4. Name: `O11 Pro`
5. Right-click the shortcut → Properties → Advanced → Check **Run as administrator**

### Method C: WSL Boot Command

If using systemd (Ubuntu 22.04+), O11 starts automatically via the systemd service created in Step 7. You just need to ensure WSL starts on boot.

Create a Windows startup shortcut:

1. Press `Win+R`, type `shell:startup`, press Enter
2. Right-click → New → Shortcut
3. Location: `wsl -d Ubuntu`
4. Name: `Start WSL for O11`

Or use Task Scheduler as in Method A, but with simpler arguments:

```
wsl -d Ubuntu -- sudo systemctl start o11
```

---

## Step 11  HTTPS Setup

### Generate Self-Signed Certificates (for testing)

```bash
cd ~/o11

openssl req -x509 -newkey rsa:4096 -keyout server.key -out server.crt \
  -days 365 -nodes -subj "/CN=localhost"
```

### Use Let's Encrypt (for production with a domain)

```bash
# Install certbot
sudo apt install -y certbot

# Get certificate (replace example.com and your email)
sudo certbot certonly --standalone -d o11.example.com --non-interactive --agree-tos -m your@email.com

# Copy certificates to o11 directory
sudo cp /etc/letsencrypt/live/o11.example.com/fullchain.pem ~/o11/server.crt
sudo cp /etc/letsencrypt/live/o11.example.com/privkey.pem ~/o11/server.key
```

Start with HTTPS:

```bash
./o11pro -p 8443 -https -user admin -password mypass -path ~/o11/data
```

> **Note for WSL**: Windows Firewall will prompt you to allow the connection. Click **Allow**.

---

## Step 12  Network Configuration for WSL

### Port Forwarding Reference

If you need to expose multiple ports (streaming, EPG), forward each one:

```powershell
# Run in PowerShell as Administrator
$wslIP = (wsl hostname -I).Trim()

# Web UI
netsh interface portproxy add v4tov4 address=0.0.0.0 port=8080 connectaddress=$wslIP connectport=8080

# Streaming port
netsh interface portproxy add v4tov4 address=0.0.0.0 port=9090 connectaddress=$wslIP connectport=9090

# EPG port
netsh interface portproxy add v4tov4 address=0.0.0.0 port=9091 connectaddress=$wslIP connectport=9091

# Firewall rules
New-NetFirewallRule -DisplayName "O11 Pro Web" -Direction Inbound -LocalPort 8080 -Protocol TCP -Action Allow
New-NetFirewallRule -DisplayName "O11 Pro Stream" -Direction Inbound -LocalPort 9090 -Protocol TCP -Action Allow
New-NetFirewallRule -DisplayName "O11 Pro EPG" -Direction Inbound -LocalPort 9091 -Protocol TCP -Action Allow
```

### View Current Port Forwards

```powershell
netsh interface portproxy show all
```

### Remove Port Forwards

```powershell
netsh interface portproxy delete v4tov4 address=0.0.0.0 port=8080
```

---

## Step 13  Performance Tuning for WSL

### RAMFS for HLS Live Segments

By default, O11 uses `hls/live/` for live stream segments. On a real Linux system, this is typically a RAMFS for performance. On WSL, you can create one:

```bash
# Create a 512MB RAMFS
sudo mkdir -p ~/o11/data/hls/live
sudo mount -t tmpfs -o size=512m tmpfs ~/o11/data/hls/live
```

To make it persistent across reboots, add to `/etc/fstab`:

```bash
echo "tmpfs /home/YOUR_LINUX_USERNAME/o11/data/hls/live tmpfs defaults,size=512m 0 0" | sudo tee -a /etc/fstab
```

> If you skip RAMFS, use the `-noramfs` flag when starting O11:
> ```bash
> ./o11pro -p 8080 -noramfs -path ~/o11/data
> ```

### WSL Memory Limits

Create or edit `%USERPROFILE%\.wslconfig` on Windows:

```ini
[wsl2]
memory=4GB
swap=2GB
processors=4
```

Apply changes:

```powershell
wsl --shutdown
```

Reopen Ubuntu. Check memory:

```bash
free -h
```

---

## Step 14  File Management Between Windows and WSL

### Accessing WSL Files from Windows

In Windows Explorer, navigate to:

```
\\wsl$\Ubuntu\home\YOUR_LINUX_USERNAME\o11
```

Or type this in Explorer's address bar:

```
\\wsl.localhost\Ubuntu\home\YOUR_LINUX_USERNAME\o11
```

You can also open Explorer from WSL:

```bash
explorer.exe ~/o11/data
```

### Accessing Windows Files from WSL

Windows drives are mounted under `/mnt/`:

| Windows Path | WSL Path |
|-------------|----------|
| `C:\` | `/mnt/c/` |
| `D:\` | `/mnt/d/` |
| `C:\Users\John\Downloads` | `/mnt/c/Users/John/Downloads` |

### Moving O11 Data to a Windows Drive (for larger storage)

If your `C:` drive is small, you can point `-path` to a Windows drive:

```bash
# Create data directory on D: drive (Windows)
mkdir -p /mnt/d/o11-data

# Start O11 with data on Windows drive
./o11pro -p 8080 -path /mnt/d/o11-data -user admin -password mypass
```

> **Performance note**: WSL filesystem (`~/o11/`) is faster than Windows drives (`/mnt/d/`). For best performance, keep the binary and live HLS segments in WSL, and use Windows drives only for VOD downloads and recordings.

---

## Step 15  Troubleshooting

### "Permission denied" when running the binary

```bash
chmod +x ~/o11/o11pro
```

If still failing, check if the file is on a Windows drive (NTFS doesn't support Linux permissions):

```bash
# Move to WSL filesystem
mv /mnt/c/Users/.../o11pro ~/o11/
chmod +x ~/o11/o11pro
```

### "cannot execute binary file: Exec format error"

You're likely on WSL 1 or ARM. Verify:

```powershell
wsl --list --verbose
```

Make sure VERSION is `2`. If not:

```powershell
wsl --set-version Ubuntu 2
```

### Port already in use

```bash
# Find what's using port 8080
sudo lsof -i :8080

# Kill the process
kill -9 <PID>
```

Or use a different port:

```bash
./o11pro -p 8081 -path ~/o11/data
```

### Can't access from Windows browser

1. Check O11 is running: `curl http://localhost:8080` inside WSL
2. Check Windows Firewall  it may be blocking the connection
3. Try the WSL IP directly: `http://$(wsl hostname -I).Trim():8080`
4. If using a specific bind address, try `-b 0.0.0.0`:
   ```bash
   ./o11pro -p 8080 -b 0.0.0.0 -path ~/o11/data
   ```

### WSL keeps shutting down O11 when terminal closes

Use `nohup`, `screen`, or `systemd` as described in Step 7. The `nohup` method is simplest:

```bash
nohup ./o11pro -p 8080 -path ~/o11/data >> ~/o11/o11.log 2>&1 &
```

### FFmpeg not found

```bash
sudo apt install -y ffmpeg
which ffmpeg
# Should output: /usr/bin/ffmpeg

# If using a custom path:
./o11pro -p 8080 -f /usr/bin/ffmpeg -path ~/o11/data
```

### WSL port forwarding resets after reboot

This happens because WSL gets a new IP on each start. Use the PowerShell script from Step 10 (Method B) to automatically reconfigure port forwarding.

To manually fix right now:

```powershell
# PowerShell as Administrator
$wslIP = (wsl hostname -I).Trim()
netsh interface portproxy delete v4tov4 address=0.0.0.0 port=8080 2>$null
netsh interface portproxy add v4tov4 address=0.0.0.0 port=8080 connectaddress=$wslIP connectport=8080
```

---

## Quick Reference Card

### Start O11

```bash
cd ~/o11
./o11pro -p 8080 -user admin -password mypass -path ~/o11/data
```

### Start in Background

```bash
cd ~/o11
nohup ./o11pro -p 8080 -user admin -password mypass -path ~/o11/data >> ~/o11/o11.log 2>&1 &
echo $! > ~/o11/o11.pid
```

### Stop O11

```bash
kill $(cat ~/o11/o11.pid)
```

### View Logs

```bash
tail -f ~/o11/o11.log
```

### Check if Running

```bash
ps aux | grep o11pro
```

### Update Binary

```bash
cd ~/o11
wget https://github.com/Ap0dexMe0/o11pro-unpacked/releases/latest/download/o11pro -O o11pro
chmod +x o11pro
```

### Complete Start with All Options

```bash
./o11pro \
  -p 8080 \
  -streamport 9090 \
  -epgport 9091 \
  -user admin \
  -password mysecretpass \
  -jwtsecret my-secret-key-12345 \
  -path ~/o11/data \
  -f /usr/bin/ffmpeg \
  -v 2 \
  -noramfs \
  -b 0.0.0.0
```
