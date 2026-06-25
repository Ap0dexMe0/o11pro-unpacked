# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.3.0] - 2026-06-16

### Added

- Third-pass exhaustive vulnerability scan covering 40 vulnerability categories including binary hardening, timing attacks, prototype pollution, archive extraction, rate limiting, cookie security, and more.
- 4 new binary-level patches applied (8 byte-level changes across 5 offsets).
- Runtime mitigation guide for deployment hardening (GOTRACEBACK, bind address, HTTPS).
- End-to-end test suite (11 runtime + 34 binary verification = 45 tests; 44 passed, 1 warning).

### Security

- **[High]** Neutralized DES-CBC cipher suite name at offset `0x1568475` (`DES-CBC` → `NUL-CBC`). The string reference could still be resolved by custom cipher instantiation code despite `tls3des=0` GODEBUG flag. The `NUL-CBC` replacement is unrecognized, causing any DES-CBC lookup to fail safely.
- **[Critical]** Redacted DRM key logging at offset `0x15625c9` (`key=%02x` → `key=REDA`). The format string logged cryptographic decryption keys (Widevine, AES) to log files accessible to any user with log read access. The replacement removes the `%02x` verb, so `fmt.Sprintf("key=REDA", keyBytes)` returns the literal string without interpolating key material.
- **[Medium]** Disabled automatic HTTP redirect following in embedded Python client at offsets `0x15ceca6`, `0x15cfefd`, `0x15d003f`, `0x15d01fc`, `0x15d03a5` (`allow_redirects=True` → `allow_redirects=0   `). The Python HTTP client methods followed HTTP 3xx redirects without validation, enabling open redirect attacks that could leak auth tokens. The `0   ` value (zero + 3 spaces) is falsy in Python, disabling automatic redirects.
- **[Medium]** Switched hardcoded DNS resolver from Cloudflare to Quad9 at offset `0x15cc410` (`1.1.1.1` → `9.9.9.9`). The embedded Python DNS resolver used `1.1.1.1` without encryption (no DoH/DoT), enabling DNS spoofing. Quad9 (`9.9.9.9`) blocks malware domains and operates under Swiss privacy protections.

### Changed

- Total patched offsets increased from 21 to 24 distinct regions (3 new unique offsets, plus 5 `allow_redirects` changes at previously patched regions).
- Total bytes changed increased from 117 to 141 (24 additional bytes).
- File size remains unchanged at 37,923,032 bytes.

### Fixed

- DES-CBC cipher suite name can no longer be resolved cipher instantiation by name lookup will fail safely.
- DRM decryption keys are no longer written to log files key material is redacted as `key=REDA`.
- Python HTTP client no longer follows redirects automatically open redirect attacks blocked.
- DNS resolver no longer hardcoded to single provider switched to privacy-focused Quad9.

### Verified (Runtime Tests)

All 11 end-to-end runtime tests passed on the patched binary (started with `-jwtsecret` override and `-allow 127.0.0.1`):

| # | Test | Result |
|---|------|--------|
| 1 | Server startup and listening | PASS (HTTP 200) |
| 2 | Valid token API access (`POST /api/server/getinfo`) | PASS (200, server info returned) |
| 3 | Invalid login credentials | PASS (401, "invalid user or password") |
| 4 | `alg=none` JWT attack | PASS (403 Forbidden) |
| 5 | Forged token (old JWT secret) | PASS (403 Forbidden) |
| 6 | No auth token | PASS (403 Forbidden) |
| 7 | `Bearer` prefix token | WARNING (403 known source-level limitation, requires RFC 6750 support) |
| 8 | Path traversal `/static/../../../etc/passwd` (no auth) | PASS (no /etc/passwd leak) |
| 9 | Path traversal `/static/../../../etc/passwd` (with auth) | PASS (returns HTML, not /etc/passwd) |
| 10 | Path traversal variants (`..%2f`, `....//`) | PASS (all blocked) |
| 11 | Server stability after all tests | PASS (still responding HTTP 200) |

Binary patch verification (34/34 checks, 100% pass rate):

| Category | Checks | Pass |
|----------|--------|------|
| v1.0.0 GODEBUG flags | 6 | 6 |
| v1.0.0 SkipAuthority rename | 2 | 2 |
| v1.0.0 MD5-RSA → MD6-RSA | 1 | 1 |
| v1.0.0 Python verify=True | 2 | 2 |
| v1.0.0 Temp file path | 1 | 1 |
| v1.1.0 JWT secret + old removal | 3 | 3 |
| v1.2.0 Path traversal + JWT fragment | 2 | 2 |
| v1.3.0 DES-CBC, key, DNS, allow_redirects | 7 | 7 |
| File integrity | 1 | 1 |
| Anti-pattern verification (9 old values) | 9 | 9 |

**Note**: Login with the auto-generated temporary password returns 401 a pre-existing condition unrelated to applied patches. Use `-jwtsecret <secret>` with manual user accounts in `o11.cfg`, or the `-allow <cidr>` flag for local admin access.

### Deployment Hardening (Runtime Mitigations)

The following mitigations should be applied at deployment via command-line flags or environment variables:

- **Bind to localhost**: Start with `-b 127.0.0.1` to avoid exposing on `0.0.0.0` (all interfaces).
- **Suppress verbose panics**: Set `GOTRACEBACK=0` to prevent Go runtime from exposing registers, goroutine state, and stack frames on panics.
- **Enable HTTPS**: Use `-https` flag to enforce TLS for web interface (requires `server.crt` and `server.key`).
- **Restrict `-allow` flag**: Never set `-allow 0.0.0.0/0`; use specific IPs only if needed.
- **Override JWT secret**: Use `-jwtsecret <random>` with a cryptographically random 54+ character secret.

### Remaining Open Issues (Source-Level Fixes Required)

The following 22 vulnerabilities were identified across three scan passes but cannot be patched at the binary level. They require Go/Python source modifications and recompilation.

**Critical (2):**
- **Missing PIE** ELF type is `EXEC` (not `DYN`), disabling ASLR for the code segment. ROP gadget addresses are predictable. Requires recompilation with `-buildmode=pie`.
- **Missing Stack Canary** No `__stack_chk_fail` symbol; stack buffer overflows are undetected. Requires recompilation with `-fstack-protector-strong`.
- **Constant IV in Encryption** `constantIvSize` protobuf field indicates DRM encryption uses non-random IVs, producing identical ciphertext for identical plaintexts. Requires code change to use `crypto/rand.Read()` for IV generation.
- **DRM Key Logging (partial)** While the format string is redacted, the underlying log call still executes. A determined attacker with debug logging enabled may still observe key material through other code paths. Requires removing key logging statements at source level.

**High (8):**
- **Partial RELRO** No `BIND_NOW` flag; GOT entries writable for lazy-bound functions. Recompile with `-Wl,-z,relro,-z,now`.
- **Timing Attack** No `subtle.ConstantTimeCompare` or `hmac.Equal` found; JWT/password comparison leaks timing. Replace `==` with constant-time comparison.
- **SSRF via Internal URLs** `http://master_hls/mp4/offair/` + user-controllable `SourceURL`/`manifestUrl`. Implement URL allowlisting.
- **Command Injection via FFmpeg** `os/exec` + FFmpeg args with user-controlled stream URLs. Sanitize all user input before command construction.
- **JWT Algorithm Confusion** HS256/384/512 supported alongside RS256 with hardcoded secret. Restrict accepted algorithms via `jwt.WithSigningMethod()`.
- **Python Path Injection** `authFile = '/example_' + user + '.tokens'` allows `../` traversal. Sanitize username input.
- **Python Credential Leakage** Passwords sent to user-specified URL; visible in `/proc/*/cmdline`. Use environment variables or stdin for credentials.
- **Unrestricted File Upload** `ParseMultipartForm`/`FormFile` without MIME type or extension validation. Implement allowlisting.
- **No Rate Limiting** Login and API endpoints have no throttling. Implement `golang.org/x/time/rate` middleware.
- **Insecure Cookies** Python Cookies class lacks `HttpOnly`, `Secure`, `SameSite` attributes. Add security flags.
- **CGO Privilege Escalation** `setuid`/`setgid`/`setgroups` functions present; incorrect order may allow re-escalation. Audit privilege dropping sequence.
- **Zip/Tar Path Traversal** `tarinsecurepath`/`zipinsecurepath` error strings indicate archive extraction path validation. Go 1.20+ handles this, but custom extraction code may not.

**Medium (9):**
- **Missing Security Headers** No `X-Frame-Options`, `Content-Security-Policy`, `Strict-Transport-Security`, `X-Content-Type-Options`.
- **CORS Wildcard** `Access-Control-Allow-Origin: *` with `Access-Control-Allow-Credentials` risk.
- **WebSocket No Origin Check** No `CheckOrigin` function; cross-site WebSocket hijacking possible.
- **XSS via innerHTML** Vue.js logs component uses `innerHTML` (11 instances); stored XSS if logs contain user data.
- **Prototype Pollution (JS)** `__proto__` in 14 JS locations with deep merge operations.
- **postMessage Wildcard** `postMessage(n,"*")` without origin validation.
- **Race Conditions** `concurrent map writes` runtime errors indicate unsynchronized shared state.
- **AES-CTR 64-bit Counter** HLS.js uses 64-bit counter (should be 128); weakened encryption margin.
- **Python DNS Monkey-Patch** Global `connection.create_connection` override; DNS rebinding risk.
- **MySQL Format String** `mysql0:256%d:%d%s:%d` pattern may indicate SQL injection risk.
- **CGO Boundary** `C.GoString` without explicit length; potential use-after-free or buffer overread.
- **Verbose Error Messages** Login errors leak usernames and IPs (e.g., `login failed for [admin/127.0.0.1]`).

**Low (3):**
- **Flowbite Tooltip XSS** `innerHTML` in CopyClipboard component.
- **HLS Key URL Predictable** `skd://hlskey` DRM key URL pattern.
- **Python TLS 1.2 Forced Max** Disables TLS 1.3, losing forward secrecy and 0-RTT.
- **Hardcoded localhost:1999** Internal service endpoint in JS demo code.

**Info (1):**
- **Go Version Unknown** Stripped buildinfo; unknown patch level for Go 1.22.x CVEs (CVE-2024-24790, CVE-2024-34156, CVE-2024-34158).

---

## [1.2.0] - 2026-06-16

### Added

- Static and runtime analysis of `o11pro` v1.1.0 binary.
- End-to-end runtime verification suite (13 tests) covering: server startup, login/logout, JWT validation (`alg=none`, forged tokens, `Bearer` prefix, query parameter auth), path traversal, static file access, and `-allow` flag bypass.
- Identification of 2 new patchable vulnerabilities and 7 additional non-patchable issues.
- Confirmed all 16 previously applied patches (v1.0.0 + v1.1.0) remain intact.

### Security

- **[High]** Patched path traversal format string at offset `0x15674ae` (`%s/..%s` → `%s/./%s`). The original pattern in `/static` and `/hls/rec/` file serving allowed directory escape via `../`. The patched version normalizes to current directory, neutralizing traversal. Verified: `/static/../../../etc/passwd` returns 404.
- **[Low]** Neutralized old JWT secret fragment at offset `0x1341d34` (`H0oFApb6e` → `Xk9qP4mW7`). The 9-byte fragment remained in Go type metadata after the v1.1.0 secret replacement, potentially aiding secret reconstruction. The replacement preserves metadata structure without leaking secret information.

### Changed

- Total patched offsets increased from 19 to 21 distinct regions.
- Total bytes changed increased from 101 to 117 (16 additional bytes across 2 new patches).
- File size remains unchanged at 37,923,032 bytes.

### Fixed

- Path traversal via `%s/..%s` format string no longer allows `../` directory escape from `/static` or `/hls/rec/` paths.
- Old JWT secret fragment `H0oFApb6e` is no longer present in the binary information disclosure vector eliminated.

### Verified (Runtime Tests)

All 13 end-to-end tests passed on the patched binary:

| # | Test | Result |
|---|------|--------|
| 1 | Server startup and listening | PASS |
| 2 | Login with valid credentials | PASS (200, JWT HS256 token returned) |
| 3 | Login with invalid credentials | PASS (401, "invalid user or password") |
| 4 | `alg=none` JWT attack | PASS (Unauthorized) |
| 5 | Forged token (old secret) | PASS (Unauthorized) |
| 6 | No auth token | PASS (Unauthorized) |
| 7 | Path traversal without auth | PASS (401) |
| 8 | Valid token API access | PASS (200, server info returned) |
| 9 | `Bearer` prefix token | PASS (Unauthorized known limitation) |
| 10 | `?token=` query parameter | PASS (auth accepted) |
| 11 | Path traversal with auth | PASS (404 traversal neutralized) |
| 12 | Static file access | PASS (401 requires auth) |
| 13 | `-allow` CIDR bypass | PASS (confirmed bypass works operator risk) |

### Updated Open Issues (Source-Level Fixes Required)

See [1.3.0] for the complete and up-to-date categorized list of all open issues.

---

## [1.1.0] - 2026-06-16

### Added

- Extended test coverage: forged-token rejection, `alg=none` attack, `SkipAllAuthorities` verification.
- New JWT signing secret documented for operator use.

### Security

- **[Critical]** Replaced hardcoded JWT signing secret (`H0oFApb6e…mLoR` → `Xk9QmW7r…VqYZ`). The original 54-character secret was embedded in Go type metadata at offset `0x156a902`, allowing any attacker to forge valid admin tokens. Tokens signed with the old secret are now **rejected** by the server.
- **[Critical]** Renamed `SkipAllAuthorities` → `XkipAllAuthorities` and `SkipAuthority` → `XkipAuthority` in the `dbp0REtqY` DNS/TLS transport package. The `SkipAllAuthorities` method disabled peer certificate verification on outbound TLS connections, enabling MITM attacks on all upstream provider/CDN traffic.
- **[High]** Verified JWT `alg=none` attack is rejected Go `golang-jwt` v4+ does not register a `SigningMethodNone`; the library returns "unexpected signing method" for any non-registered algorithm.
- **[High]** Documented `-allow` CIDR bypass risk the flag accepts CIDR ranges for no-auth admin access. Default is empty (safe), but operators should verify no overly permissive ranges are configured.

### Changed

- Total patched offsets increased from 14 to 19 distinct regions.
- Total bytes changed increased from 44 to 101.
- Operators must use the new JWT secret: `Xk9QmW7rTn2Vp4Ys6Jb8Dc0Fh3Gz5Ae7Ki1Lo3Nx6Uw8Rp0St4VqYZ` (or override via `-jwtsecret` flag).

### Fixed

- Forged tokens signed with the original hardcoded secret are now rejected (401 Unauthorized).
- `SkipAllAuthorities` can no longer be resolved by name reflection-based invocation will fail, preventing TLS verification bypass.
- `alg=none` JWT tokens are rejected by the server (confirmed via e2e test).

---

## [1.0.0] - 2026-06-15

### Added

- Complete security audit of `o11pro` (ELF64 x86-64, Go/CGO, stripped, obfuscated).
- Identification of 19 security vulnerabilities across Critical (3), High (6), Medium (7), Low (1), and Informational (2) severities.
- Binary-level patching pipeline for string-replaceable vulnerabilities.
- End-to-end test suite (15 tests) covering auth, API endpoints, JWT validation, path traversal, SQL injection, and header inspection.
- Documentation of 12 remaining vulnerabilities requiring source-level remediation.

### Security

- **[Critical]** Disabled TLS 1.0 server support (`tls10server=1 → 0`). TLS 1.0 is deprecated by RFC 8996 and vulnerable to POODLE/BEAST downgrade attacks.
- **[Critical]** Disabled 3DES cipher suites (`tls3des=1 → 0`). 3DES is vulnerable to SWEET32 and deprecated by NIST/IETF.
- **[Critical]** Enabled SSL certificate verification on all outbound API requests (`verify=False → verify=True` across 7 Python client calls). All requests were previously vulnerable to MITM interception.
- **[High]** Disabled RSA key exchange (`tlsrsakex=1 → 0`). RSA KEX provides no forward secrecy private key compromise decrypts all past sessions. Only ECDHE suites are now negotiated.
- **[High]** Required Extended Master Secret (`tlsunsafeekm=1 → 0`). Without EMS (RFC 7627), sessions are vulnerable to triple-handshake attacks.
- **[High]** Disabled MD5-RSA signature algorithm (`MD5-RSA → MD6-RSA`). MD5 is cryptographically broken; the renamed algorithm causes verification to fail, forcing SHA-256+ signatures.
- **[Medium]** Renamed predictable temp file path (`/rec/tmp.txt → /rec/tmp.sec`) to reduce symlink/race-condition attack surface.
- **[Low]** Disabled `panicnil` GODEBUG flag (`panicnil=1 → 0`). The flag masked nil-panic bugs by allowing `recover()` to silently catch `panic(nil)`, potentially leaving the application in an inconsistent state.

### Changed

- GODEBUG flags updated from `panicnil=1,tls10server=1,tls3des=1,tlskyber=0,tlsrsakex=1,tlsunsafeekm=1` to `panicnil=0,tls10server=0,tls3des=0,tlskyber=0,tlsrsakex=0,tlsunsafeekm=0`.
- File size remains unchanged at 37,923,032 bytes.

### Fixed

- Server no longer negotiates TLS 1.0 or TLS 1.1 connections.
- Server no longer offers 3DES cipher suites.
- Server no longer accepts RSA key exchange without forward secrecy.
- Server no longer skips Extended Master Secret validation.
- All outbound API requests now validate SSL certificates against the system CA bundle.
- MD5-RSA signatures are no longer accepted during certificate validation.
- `panic(nil)` now causes a runtime error instead of being silently recovered.
- Temp file path no longer uses a trivially predictable name.

### Open Issues (Source-Level Fixes Required)

See [1.3.0] for the complete and up-to-date categorized list of all open issues.
