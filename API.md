# REST API Reference

All API endpoints are served from the web UI port. Authentication uses a JWT token passed via the `o11-token` localStorage key or `?token=` query parameter.

## Authentication

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/login` | Login with username/password, returns JWT token |
| POST | `/account/login` | Account login (provider script account) |
| POST | `/account/pairstart` | Start device pairing flow |
| POST | `/account/pairinput` | Submit pairing input |
| GET | `/account/pairstatus` | Check pairing status |
| POST | `/account/pairstop` | Stop pairing flow |

## Providers

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/providers` | List all providers |
| GET | `/provider/get` | Get provider details |
| POST | `/provider/add` | Add a new provider |
| POST | `/provider/edit` | Edit provider configuration |
| POST | `/provider/delete` | Delete a provider |
| POST | `/provider/import` | Import provider config |
| GET | `/provider/export` | Export provider config |
| GET | `/provider/exportkeys` | Export decryption keys |
| GET | `/provider/exportmanifestandkeys` | Export manifest + keys |
| POST | `/provider/pushkeys` | Push decryption keys to streams |
| POST | `/provider/rescan` | Rescan provider scripts |
| POST | `/provider/backup` | Backup provider data |
| POST | `/provider/cachelogos` | Cache provider logos |
| POST | `/provider/massupdate` | Bulk update providers |
| GET | `/provider/config` | Get provider configuration |

## Accounts

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/account/get` | Get account details |
| POST | `/account/add` | Add a script account |
| POST | `/account/edit` | Edit account |
| POST | `/account/disableall` | Disable all accounts |

## Streams

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/stream/status` | Get all stream statuses |
| GET | `/stream/get` | Get stream details |
| POST | `/stream/start` | Start a stream |
| POST | `/stream/add` | Add a new stream |
| POST | `/stream/refresh` | Refresh stream |
| POST | `/stream/refreshkeys` | Refresh decryption keys |
| POST | `/stream/flushkeys` | Flush key cache |
| POST | `/stream/stoprefresh` | Stop refreshing a stream |

## EPG

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/epg` | EPG overview |
| GET | `/epg/:provider?/:stream?` | EPG for specific provider/stream |
| GET | `/epg/get` | Get EPG data |
| POST | `/epg/refresh` | Trigger EPG refresh |
| POST | `/epg/refreshapply` | Refresh and apply EPG |

## Events & Recordings

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/events/:provider?` | List events for provider |
| GET | `/recordings/:provider?` | List recordings for provider |
| POST | `/recording/add` | Schedule a recording |
| POST | `/recording/edit` | Edit a recording |
| POST | `/recording/delete` | Delete a recording |
| POST | `/recording/stop` | Stop an active recording |
| GET | `/recording/get` | Get recording details |
| POST | `/replay/delete` | Delete a replay |

## Users & Servers

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/users` | List all users |
| POST | `/user/add` | Add a new user |
| POST | `/user/edit` | Edit user |
| POST | `/user/delete` | Delete user |
| GET | `/user/get` | Get user details |
| GET | `/servers` | List remote servers |
| POST | `/server/add` | Add a remote server |

## Jobs

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/jobs` | List all jobs |
| POST | `/job/add` | Add a job |
| POST | `/job/edit` | Edit a job |
| POST | `/job/delete` | Delete a job |
| POST | `/job/run` | Run a job |

## System

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/config` | Get server configuration |
| GET | `/bootstrap` | Bootstrap/init data for UI |
| GET | `/logos` | List available logos |
| GET | `/logos/:name` | Get logo image |
| POST | `/log/clean` | Clean old logs |
| GET | `/log/export` | Export logs |
| GET | `/search` | Search across streams |
| POST | `/refreshrequest` | Request data refresh |
| POST | `/shutdown` | Shutdown the server |
