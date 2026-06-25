# O11 Pro Cracked – Unpacked Version

**O11 Pro** is a streaming media server capable of proxying, remuxing, and redistributing IPTV/OTT live and VOD streams. It features a built-in web UI, EPG support, HLS/DASH handling, and DRM decryption via CDM integration.

---

## Further Reading

| Document                           | Description                                                                                             |
| ---------------------------------- | ------------------------------------------------------------------------------------------------------- |
| [DISCLAIMER](docs/DISCLAIMER.md) | To avoid misunderstandings, here are some things to know about this release                             |
| [CHANGELOG](docs/CHANGELOGS.md) | A completed changelog released                             |
| [API](docs/API.md)              | Complete REST API reference: endpoints, methods, and authentication details                             |
| [WSL](docs/WSL.md)              | Complete WSL setup guide                                                                                |
| [MONITORING](docs/MONITORING.md) | Real-time attack detection: HTTP proxy monitor, audit logging, process/file/network surveillance       |

---

## Quick Start

```bash
# Minimum: just set a port
./o11pro -p 8080

# With web UI login credentials
./o11pro -p 8080 -user admin -password yourpassword

# Headless mode (no web UI)
./o11pro -p 8080 -headless

# With separate EPG and streaming ports
./o11pro -p 8080 -epgport 8081 -streamport 8082

# Debug mode
./o11pro -p 8080 -v 3 -stdout
```

When started without `-user` and `-password`, a temporary admin account is auto-generated and printed to the log:

```
WARN: Use temporary account to login to Web UI: admin / OtoN4Fx0
```

Open `http://<your-ip>:<port>` in a browser to access the web interface.

---

## Command-Line Options

### Server & Network

| Flag          | Description                                           | Default           |
| ------------- | ----------------------------------------------------- | ----------------- |
| `-p`          | HTTP port to listen on (required)                     | `0` (must be set) |
| `-b`          | HTTP bind address                                     | `0.0.0.0`         |
| `-https`      | Enable HTTPS (requires `server.crt` and `server.key`) | `false`           |
| `-baseurl`    | HTTP base URL for reverse proxy setups                | *(empty)*         |
| `-streamport` | Dedicated streaming port (0 = same as HTTP port)      | `0`               |
| `-streambind` | Streaming bind address                                | `0.0.0.0`         |
| `-epgport`    | EPG (Electronic Program Guide) port                   | `0`               |
| `-epgbind`    | EPG bind address                                      | `0.0.0.0`         |
| `-allow`      | Comma-separated IP whitelist for no-auth admin access | *(empty)*         |

---

### Authentication & Security

| Flag         | Description             | Default                            |
| ------------ | ----------------------- | ---------------------------------- |
| `-user`      | Static admin username   | *(empty – temp account generated)* |
| `-password`  | Static admin password   | *(empty – temp account generated)* |
| `-jwtsecret` | JWT secret for sessions | *(random)*                         |

---

### Configuration & Files

| Flag         | Description            | Default           |
| ------------ | ---------------------- | ----------------- |
| `-c`         | Main config file path  | `o11.cfg`         |
| `-job`       | Jobs config file       | `o11-job.cfg`     |
| `-rec`       | Recordings config file | `o11-rec.cfg`     |
| `-path`      | Working directory      | current directory |
| `-providers` | Providers directory    | `providers/`      |
| `-keys`      | KID:KEY fallback file  | `keys.txt`        |
| `-f`         | FFmpeg binary path     | `ffmpeg`          |
| `-tsplay`    | Tsplay binary path     | `tsplay`          |

---

### Logging

| Flag             | Description                       | Default   |
| ---------------- | --------------------------------- | --------- |
| `-v`             | Log level (0–5)                   | `2`       |
| `-stdout`        | Output logs to stdout             | `false`   |
| `-logsize`       | Max log size (MB)                 | `100`     |
| `-logscount`     | Log rotation count                | `7`       |
| `-logtomain`     | Send stream logs to main log      | `false`   |
| `-logtomainonly` | Only main log output              | `false`   |
| `-V`             | Enable module-specific debug logs | *(empty)* |

---

### Runtime Behavior

| Flag             | Description                     | Default   |
| ---------------- | ------------------------------- | --------- |
| `-headless`      | Run without web UI              | `false`   |
| `-noautostart`   | Disable auto-start of providers | `false`   |
| `-flushperiod`   | Config flush interval (seconds) | `300`     |
| `-keep`          | Keep temporary files            | `true`    |
| `-noramfs`       | Disable RAMFS requirement       | `false`   |
| `-remuxondisk`   | Store remux temp files on disk  | `false`   |
| `-debugspeed`    | Show stream download queue      | `false`   |
| `-defaultprovid` | Default provider ID             | *(empty)* |

---

### Playlist & Naming

| Flag                  | Description               | Default            |
| --------------------- | ------------------------- | ------------------ |
| `-plstreamname`       | Stream name format        | `[%p] %s`          |
| `-alteventdateformat` | Alternate EPG date format | `false`            |
| `-novodmetadata`      | Disable VOD metadata      | `false`            |
| `-pipeoutputcmd`      | Pipe output command       | `tsplay -stdin %s` |

---

### Replay Mode

| Flag          | Description       | Default           |
| ------------- | ----------------- | ----------------- |
| `-replay`     | Local stream path | *(empty)*         |
| `-replaymode` | Replay mode       | `internalremuxer` |

---

### User-Agent & HTTP

| Flag | Description        | Default          |
| ---- | ------------------ | ---------------- |
| `-a` | Default User-Agent | Chrome 122 macOS |

---

### VOD Downloader

| Flag           | Description                   | Default   |
| -------------- | ----------------------------- | --------- |
| `-manifest`    | Download manifest and convert | *(empty)* |
| `-video`       | Video track index             | all       |
| `-audio`       | Audio track indexes           | all       |
| `-subs`        | Subtitle indexes              | none      |
| `-extrasubs`   | External subtitle URL         | *(empty)* |
| `-maxsegments` | Max segments                  | `0`       |
| `-dashperiod`  | DASH period index             | `-2`      |

---

### DRM / CDM

| Flag         | Description           | Default    |
| ------------ | --------------------- | ---------- |
| `-usecdm`    | Enable CDM decryption | `false`    |
| `-cdmtype`   | CDM type              | `widevine` |
| `-cdmmode`   | CDM mode              | `internal` |
| `-script`    | CDM script            | `auto`     |
| `-cdmparams` | Script parameters     | *(empty)*  |
| `-key`       | KID:KEY pair          | *(empty)*  |
| `-doh`       | DNS-over-HTTPS URL    | *(empty)*  |
| `-H`         | Custom HTTP headers   | *(empty)*  |

---

## Web UI Pages

| Page       | Route                       | Description               |
| ---------- | --------------------------- | ------------------------- |
| Providers  | `/providers`                | Manage IPTV/OTT providers |
| Linear     | `/linear`                   | Live stream control       |
| Events     | `/events/:provider?`        | Scheduled streams         |
| VOD        | `/vod`                      | Video-on-demand library   |
| Recordings | `/recordings/:provider?`    | Stream recordings         |
| Monitoring | `/monitoring`               | Live stream status        |
| Logs       | `/logs/:provider?/:stream?` | Log viewer                |
| Users      | `/users`                    | User management           |
| Config     | `/config`                   | System configuration      |
| Help       | `/help`                     | Documentation             |
| Login      | `/login`                    | Authentication            |

---

## Examples

### Basic IPTV Proxy

```bash
./o11pro -p 8080 -user admin -password mysecretpass
```

### Separate Streaming + EPG

```bash
./o11pro -p 8080 -streamport 9090 -epgport 9091
```

### HTTPS Mode

```bash
./o11pro -p 8443 -https
```

### Full Debug Mode

```bash
./o11pro -p 8080 -v 5 -stdout
```

---

## Directory Structure

```
o11pro-unpacked/
├── hls/
├── dl/
├── epg/
├── fonts/
├── logos/
├── logs/
├── manifests/
├── offair/
├── overlay/
├── providers/
├── rec/
├── scripts/
├── keys.txt
├── o11.cfg
├── o11-job.cfg
└── o11-rec.cfg
```

---

## EPG Access

| Format     | URL                                 |
| ---------- | ----------------------------------- |
| XML (gzip) | `http://ip:epgport/provider.xml.gz` |
| XML        | `http://ip:epgport/provider.xml`    |
| API        | `/epg/:provider?/:stream?`          |

---

## Notes

* `-p` is required
* Temp admin is generated if no credentials provided
* HTTPS requires valid cert + key
* `-manifest` runs download-only mode
* Multiple `-key` and `-H` flags supported

---

## Credits

* Nulled with his bullshit Backdoor (Cracked O11Pro)
* Lossui011

---