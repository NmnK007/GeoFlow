# Operating the GeoFlow public beta

The supported public profile serves one immutable collection of scientific examples. The browser contacts Next.js at one origin. Next proxies the versioned API to a single FastAPI process. Public startup omits the job supervisor entirely. All four labs use the same public artifacts for every visitor. The writable mode is a separate installation for a trusted local researcher.

## Reproduce the public profile locally

Use the repository root, Python 3.14 for the pinned web environment, and Node 22 with npm. These PowerShell commands use two terminals. On Unix use `.venv/bin/python` and `export GEOFLOW_READ_ONLY=1`.

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -c requirements-web.txt -e ".[web,earth]"
$env:GEOFLOW_READ_ONLY="1"
.\.venv\Scripts\python -m uvicorn geoflow.web.api:app --host 127.0.0.1 --port 8000 --workers 1 --limit-concurrency 32
```

```powershell
cd web
npm ci
$env:GEOFLOW_API="http://127.0.0.1:8000"
npm run build
npm run start -- --hostname 127.0.0.1
```

Visit `http://127.0.0.1:3000`. The mode banner should say **Public demo**. The request to `/api/v1/mode` should return `{"read_only":true}` through the frontend. The read-only route policy also applies on the backend port. Clear the read-only variable and restart the loopback API to work privately. [Lab setup and variables](web.md)

Compose builds with the frontend lockfile and the web-specific Python constraints. It binds only the frontend to host loopback. The API filesystem is read-only, with 128 MiB of temporary storage and a 768 MiB container memory limit. The scientific demo requires the contents of `benchmarks/web-demo`, the HPC JSON and the preset configs. Docker copies these into the image. The API does not need persistent volumes, credentials, training weights or optional ocean registries in public mode. Live inference in a private installation uses the original v0.5 study and validates checkpoint and dataset compatibility. [Reproduce the checkpoints](hpc.md)

```sh
docker compose up --build --wait
docker compose ps
docker compose logs --tail 100 api web
curl --fail http://127.0.0.1:3000/api/v1/health
curl --fail http://127.0.0.1:3000/api/v1/mode
curl --fail http://127.0.0.1:3000/api/v1/research
```

## Threat model and deployment checklist

| Boundary or resource | Beta control | Operator check |
|---|---|---|
| Public visitor and operator data | Explicit GET route allowlist. Job status, results, private archives and every mutation are unavailable. Only two built-in Earth identifiers are accepted. Comparisons read curated archives. | Start the dedicated demo with `GEOFLOW_READ_ONLY=1`; verify the mode through the public-facing proxy and confirm a simulation POST returns 403. |
| Path selection and uploads | Routes use named presets, fixed export paths and registered model IDs. Public mode ignores operator registry entries. Local POSTs accept bounded JSON (16 KiB). | Keep datasets, studies, private keys and the artifact root outside the web document root. Keep the API behind the frontend and disable public origin access. |
| CPU, memory and concurrent reads | One event loop admits eight active public responses, including file transfers. Global bucket refills at 16 requests/s with burst 48. Overload returns 429 with Retry-After. The health route bypasses the application bucket. | Rate-limit by client at the edge, including health, static assets and frontend routes. Set socket, header, body, connection and upstream time limits. The application-wide bucket alone permits one visitor to exhaust the shared budget. |
| Browser and cross-origin access | The client uses same-origin API rewrites. No permissive CORS configuration, server credentials in client code or cross-user private jobs in the demo. | Terminate TLS at a trusted reverse proxy, enforce the expected Host, redirect HTTP to HTTPS, set nosniff and a restrictive framing policy. Only trust forwarding headers from that proxy. |
| Writable scientific work | One process supervises bounded subprocesses, limits workers, queue, timeout, records and retention. Job IDs are bearer capabilities. Possession permits reading and cancellation. Public mode disables that surface. | Keep writable instances on private loopback. A shared compute service needs authentication, ownership checks, fair quotas and persistent job state. |
| Errors and operational logs | Worker traceback stays in the private session directory. Clients receive short worker errors or parameter errors. Public invalid-value responses use generic messages. | Rotate access/error logs. Private request paths contain job IDs. Restrict log access and avoid recording submitted payloads. |
| Recovery and disk | Finished jobs expire after their retention interval. Active downloads hold a reader lease. Graceful shutdown cleans session storage. Browser polling backs off and can recover the job in the same tab. | After a hard crash, stop all supervisors before reviewing orphaned session directories under the configured private artifact root. An API restart invalidates old job IDs. Public mode creates no job directory. |
| Supply chain | Locked npm tree, pinned tested Python web packages, non-root images and limited Docker build contexts. | Recheck advisories for the release artifacts, generate an SBOM, pin and scan base-image digests and verify the target architecture. No OS-image or penetration-test certification is implied. |

On a staging host, provision DNS and certificates before enabling the reverse proxy. Proxy to the loopback frontend only. Configure host firewall rules so that the backend cannot be reached externally. Test HTTPS, headers, browser navigation, a denied mutation, a denied job read and overload/recovery from outside the host. Use target-host load, disk, memory and log measurements to set alerts. The scientific thresholds are independent of operational latency targets.

Before promotion, record the source commit, config and image digests. Retain the last approved image pair. To roll back, withdraw public traffic, restore both images and their matching config, then rerun the same mode and health probes. The local fallback source tag is `v0.6.0-verified` (749615a). Its public access policy predates v0.7. Keep a fallback to that version on loopback until the edge enforces the current archive-only policy. No database migrations are required.

## Attribution and release permissions

The Arabian Sea slice contains modified Copernicus Marine Service information from the historical DUACS archive. The associated NOAA Global Drifter Program hourly data are credited to Elipot et al. (GDP v2.01, DOI 10.25921/x46c-3620, CC BY 4.0). Keep the provider metadata, source identifiers and attribution with exports. The Earth documentation identifies the products, archive and terms. The analytical fixture and solver and surrogate trajectories are generated examples. [Dataset provenance and terms](earth.md)

Check distribution metadata and bundled notices for Python, Node and native dependencies. NumPy, Next.js, React, Three.js and PyTorch have separate upstream notices; wheel and container builds can include additional native libraries. The Python constraints and npm lockfile identify the versions. The pinned metadata identifies MIT for FastAPI, Pydantic, netCDF4, React, Next.js, Three.js, React Three Fiber and Tailwind, BSD-3-Clause for Starlette and Uvicorn, and Apache-2.0 for Xarray. NumPy declares multiple bundled licenses. Preserve applicable notices when redistributing. The repository has no top-level software license. Choosing terms for GeoFlow belongs to its owner and is an open release decision.
