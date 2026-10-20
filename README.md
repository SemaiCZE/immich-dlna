# Immich-DLNA

Immich-DLNA exposes your Immich photo/video library as a DLNA/UPnP Media Server so TVs and other DLNA clients can browse and play content.
The navigation mirrors Immich’s familiar structure: **Timeline** and **Albums**, including shared/partner content where available.
The current implementation is compatible with the Immich v3 album API.

## DLNA container structure

- `0` (root): `Immich`
  - `timeline`: flat asset list (newest first, non-trashed timeline-visible assets, includes partner timeline assets)
  - `albums`: album folders (newest albums first)
    - `album:{albumId}`: album assets, respecting Immich album order (oldest/newest)

## Features

- DLNA discovery over SSDP (LG TV-compatible behavior)
- Accurate Timeline and Albums container child counts for Samsung DLNA clients
- Streaming proxy for photos/videos (with HTTP Range support for video seeking)
- Thumbnail proxy for image previews
- Shared albums + partner timeline support
- Prometheus metrics at `/metrics`

## Configuration

Environment variables:

| Variable | Default | Required | Description |
|---|---|---|---|
| `IMMICH_URL` | – | Yes | Immich base URL. If URL has no path, `/api` is auto-appended. |
| `IMMICH_API_TOKEN` | – | Yes | Immich API key (read-only is sufficient for browsing/streaming). |
| `IMMICH_VERIFY_SSL` | `true` | No | TLS certificate verification for Immich upstream (`false` for self-signed/custom CA setups). |
| `IMMICH_DLNA_HTTP_HOST` | `0.0.0.0` | No | HTTP bind address for this server. |
| `IMMICH_DLNA_HTTP_PORT` | `8200` | No | HTTP port for DLNA control/device/media endpoints. |
| `IMMICH_DLNA_BASE_URL` | auto-detected | No | Public base URL advertised to DLNA clients (used for `device.xml` and media URLs). |
| `IMMICH_DLNA_FRIENDLY_NAME` | `Immich DLNA` | No | DLNA device name shown on clients. |
| `IMMICH_DLNA_SERVER_UUID` | auto-generated | No | Stable DLNA UUID (`uuid:` prefix optional). |
| `IMMICH_DLNA_LOG_LEVEL` | `INFO` | No | Python log level (`DEBUG`, `INFO`, etc.). |
| `IMMICH_DLNA_SSDP_MULTICAST_HOST` | `239.255.255.250` | No | SSDP multicast group. |
| `IMMICH_DLNA_SSDP_PORT` | `1900` | No | SSDP UDP port. |
| `IMMICH_DLNA_SSDP_MAX_AGE` | `1800` | No | SSDP cache lifetime in seconds. |
| `IMMICH_DLNA_SSDP_NOTIFY_INTERVAL` | `900` | No | Interval for SSDP alive announcements in seconds. |
| `IMMICH_DLNA_IMMICH_TIMEOUT_SECONDS` | `20` | No | Timeout for upstream Immich HTTP calls. |
| `IMMICH_DLNA_IMMICH_STREAM_READ_TIMEOUT_SECONDS` | `300` | No | Idle read timeout for upstream media/thumbnail streams; overall stream duration is not capped by this setting. |
| `IMMICH_DLNA_IMMICH_MAX_CONCURRENT_REQUESTS` | `16` | No | Max concurrent upstream Immich requests. |
| `IMMICH_DLNA_METADATA_CACHE_TTL_SECONDS` | `30` | No | TTL for metadata cache entries. |
| `IMMICH_DLNA_METADATA_CACHE_MAX_ENTRIES` | `2000` | No | Max metadata cache entries (bounded LRU cache). |

Immich-DLNA keeps connection pooling enabled for normal upstream performance, but retries metadata/media GET requests after reconnect-worthy transport failures and refreshes the affected upstream session so later requests do not stay pinned to stale pooled sockets.

## Local run (with uv)

```bash
uv sync --frozen
export IMMICH_URL="https://immich.example.com/api"
export IMMICH_API_TOKEN="your_token"
export IMMICH_VERIFY_SSL="false"   # only for self-signed/custom CA scenarios
uv run immich-dlna
```

Validate config only:

```bash
uv run immich-dlna --check-config
```

## Docker

Build image:

```bash
docker build -t immich-dlna:latest .
```

Run container (recommended: host networking):

```bash
docker run -d \
  --name immich-dlna \
  --network host \
  --restart unless-stopped \
  -e IMMICH_URL="https://immich.example.com/api" \
  -e IMMICH_API_TOKEN="your_token" \
  -e IMMICH_VERIFY_SSL="false" \
  immich-dlna:latest
```

### Docker networking caveats

- `--network host` is strongly recommended for DLNA/SSDP reliability.
- DLNA discovery uses multicast UDP (`239.255.255.250:1900`) and clients must reach the exact URLs announced by the server.
- Bridge/NAT setups often break discovery or media URL reachability unless you manually handle multicast and `IMMICH_DLNA_BASE_URL`.

## HTTP endpoints

- `/health` — health check
- `/metrics` — Prometheus metrics
- `/device.xml` — UPnP device description
- `/ContentDirectory/*`, `/ConnectionManager/*` — DLNA SOAP services
- `/media/asset/{asset_id}` — media stream proxy
- `/media/asset/{asset_id}/thumbnail` — thumbnail proxy

## Metrics

Prometheus metrics include:

- `requests_duration_seconds` (incoming HTTP request duration histogram)
- `outgoing_requests_duration_seconds` (upstream Immich request duration histogram)
- `errors_total`
- `connected_devices`
- `cache_hit_ratio`

All metrics include label: `app="immich-dlna"`.
