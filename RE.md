# Reverse Engineering

## Frontend Deobfuscation Analysis

The web UI JavaScript (`resources/index-BX-yLeHZ.js`) is obfuscated using **obfuscator.io** with the following techniques:

### Obfuscation Method
- **String Array**: 6,922 encoded strings stored in `o11_0xf6cf()` array
- **Decoder Function**: `o11_0x3b01(index)` — performs base64 decode followed by RC4 decryption
- **Control Flow Flattening**: All string references replaced with `o11_0x3b01(0xHEX)` calls
- **Dead Code Injection**: Anti-debug traps with `debugger` statements and `parseInt` chains
- **Self-Defending**: Checksum validation that crashes if the code is modified

### Deobfuscated Vue Components

| Component | Purpose |
|-----------|---------|
| `LoginView` | Authentication page |
| `ProvidersView` | Provider list and management |
| `LinearView` | Live stream channel grid |
| `EventsView` | Scheduled event streams |
| `VodView` | Video-on-demand browser |
| `RecordingsView` | Recording scheduler and manager |
| `MonitoringView` | Real-time stream monitoring |
| `LogsView` | Log viewer |
| `UsersView` | User administration |
| `ServerView` | Remote server management |
| `ConfigView` | Provider configuration |
| `StreamPlayer` | HLS.js embedded video player |
| `Mp4VideoPlayer` | MP4 playback for VOD downloads |
| `DropdownProviderSelector` | Provider dropdown filter |
| `StreamTypeSelector` | Stream type filter (linear/event/VOD) |
| `EpgTimezoneSelector` | EPG timezone picker |
| `DropdownTrackSelector` | Audio/subtitle track selector |
| `ItemProvider` | Provider list item |
| `ItemProviderAccount` | Script account item |
| `ItemStream` | Stream list item |
| `ItemStreamCompact` | Compact stream row |
| `ItemStreamConfig` | Stream configuration editor |
| `ItemEpg` | EPG program entry |
| `ItemVod` | VOD title entry |
| `ItemJob` | Scheduled job entry |
| `ItemServer` | Remote server entry |
| `ItemUser` | User management entry |
| `ItemMonitoring` | Monitoring status card |
| `ItemTableStreams` | Stream data table row |
| `ItemTableEpg` | EPG data table row |
| `ItemTableEvent` | Event data table row |
| `ItemTableRecording` | Recording data table row |
| `CheckBoxConfig` | Toggle config option |
| `ButtonDanger` | Destructive action button |
| `ButtonText` | Text-style action button |
| `ConfirmationModal` | Confirm dialog |
| `InformationModal` | Info dialog |
| `ServerInfoModal` | Server details dialog |
| `ServerSelector` | Remote server picker |

### Deobfuscated Config Sections

| Section ID | Purpose |
|------------|---------|
| `config-page` | Main config page |
| `config-script` | Provider script settings |
| `config-script-accounts` | Script account management |
| `config-update-channels` | Channel update/refresh settings |
| `config-epg-timezone` | EPG timezone configuration |
| `config-network-parameters` | Network/proxy settings |
| `config-additional-parameters` | Extra provider parameters |
| `config-stream-config` | Stream type and output mode |
| `config-stream-options` | Stream start/stop options |
| `config-manifest-script` | Manifest download script |
| `config-cdm-script` | CDM/DRM script settings |
| `config-modal-cdm-mode` | CDM mode selector |
| `config-modal-cdm-type` | CDM type selector |
| `config-events-channels-script` | Events/channels script settings |
| `config-channels` | Channel list editor |
| `config-hw-accel` | Hardware acceleration toggle |

### Provider JSON Schema (Deobfuscated)

```json
{
  "ManifestUrl": "<manifest url>",
  "Cdn": [
    {
      "Name": "akamai",
      "ManifestUrl": "http://..."
    }
  ],
  "Headers": {
    "manifest": {
      "user-agent": "mozilla/5.0 ...",
      "custom-header": "value"
    },
    "media": {
      "user-agent": "mozilla/5.0 ...",
      "custom-header": "value"
    }
  },
  "Heartbeat": {
    "Url": "<heartbeat url>",
    "Params": ["param1", "param2"],
    "PeriodMs": 300000
  }
}
```

---

## TODO

- [ ] Full deobfuscation of `resources/index-BX-yLeHZ.js` — replace all `o11_0x3b01(0xHEX)` calls with decoded string literals for readability
- [ ] Reconstruct Vue SFC components from the flattened render functions
- [ ] Map all API endpoint handlers to their backend Go functions
- [ ] Reverse engineer the Go backend API handler routing logic
- [ ] Deobfuscate and document the provider script Python API (`scripts/o11.py`)
- [ ] Extract and analyze embedded Go symbol names (obfuscated with `ha4dhe`, `ijo4VwtOa`, etc.)
- [ ] Document the CDM integration flow (Widevine/PlayReady/Verimatrix)
- [ ] Analyze the internal remuxer pipeline (HLS → FMP4 conversion)
