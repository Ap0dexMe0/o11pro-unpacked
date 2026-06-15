# O11 Pro Cracked - Unpacked Version

**O11 Pro** is a streaming media server capable of proxying, remuxing, and redistributing IPTV/OTT live and VOD streams. It features a built-in web UI, EPG support, HLS/DASH handling, and DRM decryption via CDM integration.

---

## Further Reading

| Document | Description |
|----------|-------------|
| [API.md](docs/API.md) | Complete REST API reference all endpoints, methods, and auth details |
| [RE.md](docs/RE.md) | Reverse engineering notes frontend deobfuscation analysis, Vue component map, config schema, and TODO

---

## Quick Start

```bash
# Minimum: just set a port
./o11pro_unpacked -p 8080

# With web UI login credentials
./o11pro_unpacked -p 8080 -user admin -password yourpassword

# Headless mode (no web UI)
./o11pro_unpacked -p 8080 -headless

# With separate EPG and streaming ports
./o11pro_unpacked -p 8080 -epgport 8081 -streamport 8082

# Debug mode
./o11pro_unpacked -p 8080 -v 3 -stdout
```

When started without `-user` and `-password`, a temporary admin account is auto-generated and printed to the log:

```
WARN: Use temporary account to login to Web UI: admin / OtoN4Fx0
```

Open `http://<your-ip>:<port>` in a browser to access the web interface.

---

## Command-Line Options

### Server & Network

| Flag | Description | Default |
|------|-------------|---------|
| `-p` | **HTTP port** to listen on (required) | `0` (none  must be set) |
| `-b` | HTTP bind address | `0.0.0.0` (all interfaces) |
| `-https` | Enable HTTPS (requires `server.crt` and `server.key` in the O11 directory) | `false` |
| `-baseurl` | HTTP base URL (for reverse proxy setups) | *(empty)* |
| `-streamport` | Dedicated streaming port. If not set, the HTTP port is used | `0` (shares HTTP port) |
| `-streambind` | Streaming bind address | `0.0.0.0` |
| `-epgport` | EPG (Electronic Program Guide) port | `0` (disabled) |
| `-epgbind` | EPG bind address | `0.0.0.0` |
| `-allow` | Comma-separated list of no-auth admin source IP addresses (e.g. `192.168.1.0/24,10.0.0.1`) | *(empty)* |

### Authentication & Security

| Flag | Description | Default |
|------|-------------|---------|
| `-user` | Static admin username for web UI login | *(empty  temp account generated)* |
| `-password` | Static admin password for web UI login | *(empty  temp account generated)* |
| `-jwtsecret` | JWT secret for login sessions. Default is randomly generated on each start | *(random)* |

### Configuration & Files

| Flag | Description | Default |
|------|-------------|---------|
| `-c` | Main config file path | `o11.cfg` |
| `-job` | Jobs config file path | `o11-job.cfg` |
| `-rec` | Recordings config file path | `o11-rec.cfg` |
| `-path` | Working directory. All sub-directories (HLS, logs, etc.) are created here | current directory |
| `-providers` | Providers directory path | `providers/` |
| `-keys` | File with KID:KEY pairs for decryption fallback | `keys.txt` |
| `-f` | FFmpeg binary path | `ffmpeg` |
| `-tsplay` | Tsplay binary path (for UDP output mode) | `tsplay` |

### Logging

| Flag | Description | Default |
|------|-------------|---------|
| `-v` | Log level: `0`=error, `1`=warning, `2`=info, `3`=debug, `4`=verbose, `5`=trace | `2` (info) |
| `-stdout` | Log to stdout instead of log files | `false` |
| `-logsize` | Max log file size in MB (per file) | `100` |
| `-logscount` | Number of log file rotations to keep | `7` |
| `-logtomain` | Also send stream-specific logs to the main log | `false` |
| `-logtomainonly` | Only send stream logs to main log (no separate stream logs) | `false` |
| `-V` | Module to enable special debug logs from (e.g. `subtitles`) | *(empty)* |

### Runtime Behavior

| Flag | Description | Default |
|------|-------------|---------|
| `-headless` | Run without the web UI | `false` |
| `-noautostart` | Do not auto-start providers/channels on launch | `false` |
| `-flushperiod` | Seconds between config/key flushes to disk. `0` to disable | `300` |
| `-keep` | Keep temp media files after processing (debugging) | `true` |
| `-noramfs` | Allow FFmpeg mode even if `./hls/live` is not a RAMFS | `false` |
| `-remuxondisk` | Write internal remuxer temporary files to disk instead of RAM | `false` |
| `-debugspeed` | Print current fragment download queue per channel/media type | `false` |
| `-defaultprovid` | Default provider ID to display when none specified | *(empty)* |

### Playlist & Stream Naming

| Flag | Description | Default |
|------|-------------|---------|
| `-plstreamname` | Format for stream names in playlists. `%p` = provider name, `%s` = stream name | `[%p] %s` |
| `-alteventdateformat` | Use alternate date format `02 Jan. 2006 15:04` for EPG events | `false` |
| `-novodmetadata` | Disable metadata for VOD tracks | `false` |
| `-pipeoutputcmd` | Pipe output command format (overridable per provider). `%s` = format placeholder | `tsplay -stdin %s` |

### Replay Mode

| Flag | Description | Default |
|------|-------------|---------|
| `-replay` | Local stream path to replay (from `hls/live/`) | *(empty)* |
| `-replaymode` | Replay mode: `ffmpeg`, `internalremuxer`, etc. | `internalremuxer` |

### User-Agent & HTTP Headers

| Flag | Description | Default |
|------|-------------|---------|
| `-a` | Default User-Agent for HTTP connections | Chrome 122 on macOS |

### VOD Downloader

These options are used when downloading and converting VOD (Video On Demand) streams:

| Flag | Description | Default |
|------|-------------|---------|
| `-manifest` | Download and convert this manifest URL to MP4, then exit | *(empty)* |
| `-video` | Video track index to grab | *(empty  all)* |
| `-audio` | Audio track indexes to grab (comma-separated) | *(empty  all)* |
| `-subs` | Subtitle indexes to grab (comma-separated or `all`) | *(empty  none)* |
| `-extrasubs` | Extra subtitle file URL. Can be used multiple times | *(empty)* |
| `-maxsegments` | Max segments to download (`0` = unlimited) | `0` |
| `-dashperiod` | Force DASH period index. `-1` = all non-ad periods | `-2` |

### DRM / CDM Decryption

| Flag | Description | Default |
|------|-------------|---------|
| `-usecdm` | Enable CDM script for DRM decryption | `false` |
| `-cdmtype` | CDM type: `widevine`, `playready`, or `verimatrix` | `widevine` |
| `-cdmmode` | CDM mode: `internal` or `external` | `internal` |
| `-script` | CDM script name | `auto` |
| `-cdmparams` | CDM script parameters | *(empty)* |
| `-key` | KID:KEY pair for decryption. Can be used multiple times | *(empty)* |
| `-doh` | DNS-over-HTTPS URL for CDM requests | *(empty)* |
| `-H` | Custom HTTP header for VOD requests (format: `key:value`). Can be used multiple times | *(empty)* |

---

## Web UI Pages

The Vue.js frontend provides the following pages accessible via the navigation sidebar:

| Page | Route | Description |
|------|-------|-------------|
| **Providers** | `/providers` | List of configured IPTV/OTT providers. Add, edit, delete, import, export providers |
| **Linear** | `/linear` | Live channel management. Start/stop streams, view on-air status |
| **Events** | `/events/:provider?` | Scheduled event streams with filtering and replay support |
| **VOD** | `/vod` | Video-on-demand library per provider. Download and convert to MP4 |
| **Recordings** | `/recordings/:provider?` | Manage stream recordings. Schedule and review recorded events |
| **Monitoring** | `/monitoring` | Real-time stream status overview, running streams dashboard |
| **Logs** | `/logs/:provider?/:stream?` | Per-channel and main log viewer. Export and clean logs |
| **Users** | `/users` | User management. Create/edit users, set admin, assign provider access |
| **Config** | `/config` | Provider configuration (script, CDM, network, channels, stream options) |
| **Help** | `/help` | Built-in documentation with table of contents |
| **Login** | `/login` | Authentication page. JWT-based token auth |

---

## Examples

### Basic IPTV Proxy

```bash
./o11pro_unpacked -p 8080 -user admin -password mysecretpass
```

Access the web UI at `http://localhost:8080`, log in with `admin` / `mysecretpass`, and add your providers through the interface.

### Separate Streaming + EPG Ports

```bash
./o11pro_unpacked -p 8080 -streamport 9090 -epgport 9091 -user admin -password pass
```

- **Web UI**: `http://localhost:8080`
- **Streaming**: `http://localhost:9090`
- **EPG**: `http://localhost:9091`

### HTTPS Mode

```bash
# Place your certificates in the working directory first
cp server.crt server.key /path/to/o11/
./o11pro_unpacked -p 8443 -https -user admin -password pass
```

Access via `https://localhost:8443`.

### VOD Download with DRM

```bash
# Download with manual decryption keys
./o11pro_unpacked -manifest "https://example.com/manifest.mpd" \
  -key "eb676abbcb345e96bbcf616630f1a3da:234567890abcdef1234567890abcdef1" \
  -video 0 -audio 0,1 -subs all

# Download with CDM script
./o11pro_unpacked -manifest "https://example.com/manifest.mpd" \
  -usecdm -cdmtype widevine -cdmmode internal
```

### Headless with Custom Config

```bash
./o11pro_unpacked -p 8080 -headless -c /etc/o11/myconfig.cfg \
  -path /var/lib/o11 -providers /etc/o11/providers/
```

### Bind to Localhost Only

```bash
./o11pro_unpacked -p 8080 -b 127.0.0.1 -streambind 127.0.0.1
```

### Full Debug Mode

```bash
./o11pro_unpacked -p 8080 -v 5 -stdout -debugspeed
```

### Replay a Local Stream

```bash
./o11pro_unpacked -p 8080 -replay my_channel_stream -replaymode internalremuxer
```

---

## Directory Structure

When using `-path`, O11 creates the following sub-directories:

```
o11pro-unpacked/
├── hls/
│   ├── live/          # Live HLS segments (recommend RAMFS)
│   ├── replay/        # Replayed stream segments
│   └── vod/           # VOD stream segments
├── dl/
│   └── tmp/           # VOD download temp files
├── epg/               # EPG data cache
├── fonts/             # Custom fonts
├── logos/             # Channel/provider logos
├── logs/              # Rotating log files
├── manifests/         # Downloaded manifest cache
├── offair/            # Off-air placeholder media
├── overlay/           # Picture overlays for streams
├── providers/         # Provider configuration files & scripts
├── rec/               # Recording output files
├── scripts/           # CDM scripts (o11.py auto-generated)
├── keys.txt           # KID:KEY decryption fallback
├── o11.cfg            # Main configuration
├── o11-job.cfg        # Jobs configuration
└── o11-rec.cfg        # Recordings configuration
```

---

## EPG Access

O11 serves EPG data in multiple formats:

| Format | URL |
|--------|-----|
| XML (gzip) | `http://ip:epgport/providerid.xml.gz` |
| XML (plain) | `http://ip:epgport/providerid.xml` |
| Web UI | `http://ip:port/epg` |
| API | `GET /epg/:provider?/:stream?` |

Use the `-epgport` flag to enable the EPG endpoint.

---

## Playlist Access

Streams are accessible via playlist format. The `-plstreamname` flag controls the display name format:

- Default: `[%p] %s`  shows `[ProviderName] StreamName`
- Custom: `-plstreamname "%s (%p)"`  shows `StreamName (ProviderName)`

---

## Log Levels Reference

| Level | Name | Description |
|-------|------|-------------|
| `0` | Error | Critical errors only |
| `1` | Warning | Warnings and errors |
| `2` | Info | General operational info (default) |
| `3` | Debug | Detailed debug information |
| `4` | Verbose | Very detailed output |
| `5` | Trace | Maximum verbosity, including internal state |

---

## Notes

- **The `-p` flag is required.** The binary will not start without an HTTP port.
- Without `-user` / `-password`, a temporary admin account is generated on each start and printed to the log.
- For HTTPS, both `server.crt` and `server.key` must exist in the O11 working directory.
- The `-key` flag accepts KID:KEY pairs in hex format and can be specified multiple times for multiple keys.
- The `-H` flag for custom headers can be repeated: `-H "Authorization:Bearer token" -H "X-Custom:value"`.
- VOD downloader mode (`-manifest`) downloads, converts, and exits  it does not start the server.
- Script accounts use the format: `user=join@mail.com password=mypassword device=123456 pin=1234`
- Proxy support: `http://user:pass@ip:port` and `socks5://user:pass@ip:port`

## Credits
- Nulled (Cracked o11pro)
- Lossui011