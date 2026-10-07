# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Personal home-server configuration for a machine named **hobbiton**. It is not application code — it is the declarative config + deployment glue for three self-hosted services:

- **homeassistant/** — Home Assistant running in Docker (smart-home automation). This is the bulk of the repo.
- **pihole/** — Pi-hole (network-wide DNS ad-blocking + DHCP) in Docker.
- **autossh/** — a systemd unit holding a persistent reverse SSH tunnel so the home network's Home Assistant (`localhost:8123`) is reachable from a public host (`kaylee.mippit.pl:33100`).

Most user-facing strings (automation aliases, TTS messages) are in **Polish** — keep new ones consistent with that.

## Deployment model

**Mental model:** the server is the *live runtime* (Home Assistant's UI writes YAML directly into its `config/` there); this local checkout is the *git authority + GitHub backup*. Transport between them is `rsync`, **not** git — so you never have to commit just to deploy, and never have to commit on the server to pull UI changes back.

Syncing is done with **`./sync.sh`** at the repo root. It mirrors the whole repo (everything git would track — tracked + untracked-but-not-ignored), so `.envrc`, `secrets.yaml`, `.storage/`, the DB, logs and Pi-hole runtime data are never touched:

```bash
./sync.sh diff     # dry run: what deploy would change on the server
./sync.sh deploy   # lint YAML → rsync local→server → (for HA changes) validate → reload HA
./sync.sh pull     # rsync server→local to capture UI-made changes (mainly Home Assistant)
./sync.sh check    # validate the HA config currently on the server (read-only)
./sync.sh restart  # full HA restart via its API (reloads custom-integration code); waits until back
```

**After changing and deploying something, commit those changes and push to `origin`.** Commit only your own changes. If the working tree already has unrelated uncommitted edits, stage just your hunks and leave the rest alone.

`deploy`/`pull` print the change list and confirm before applying (`-y` to skip). When a `deploy` touches `homeassistant/config/`, it validates via the HA API first and **aborts the reload if invalid**, so a broken config never goes live; for Pi-hole / autossh / HA-compose changes it prints the manual activation step (rsync gets the files there but can't restart those services). Commit + push to GitHub (`origin`) yourself whenever you want a checkpoint — decoupled from deploying.

Requires a Home Assistant **long-lived access token** in `$HA_TOKEN`, kept in the gitignored root `.envrc` and loaded by **direnv** (`direnv allow` once). Validation/reload go through the HA REST API (`POST /api/config/core/check_config`, then `homeassistant.reload_all`) — no Docker/sudo needed. Defaults (`HA_URL`, `SSH_HOST`, `REMOTE_DIR`) are overridable via env.

**Caveats / fallbacks:**

- HA `reload_all` (what `deploy` runs) won't pick up *new* integrations/platforms or changed **custom-integration Python** (`custom_components/`) — those load only at a process boot. Use **`./sync.sh restart`**: it restarts HA via its own API (`homeassistant.restart`, no ssh/sudo/docker), relying on `restart: unless-stopped` so the container is recreated the instant the process exits. It validates config first and waits for HA to come back. Typical flow for integration work: `./sync.sh deploy && ./sync.sh restart`.
- **`docker-compose.yml` changes** (image tag, volumes, devices) are the exception `restart` can NOT apply — it restarts HA *inside* the existing container. Those need the container recreated on the server: `ssh hobbiton 'cd hobbiton/homeassistant && docker-compose up -d'` (needs sudo/docker access). `deploy` prints this when `docker-compose.yml` changes.
- The `hobbiton` git remote still has `receive.denyCurrentBranch=updateInstead`, so `git push hobbiton` deploys *committed* content to the server working tree — a fallback if `sync.sh` is unavailable.
- The mirror has no merge step: **`pull` before hand-editing locally.** In practice the two sides own different files (UI owns automations/scripts/scenes on the server; you own `configuration.yaml`/compose locally) and both commands show a diff + confirm, so a clash is visible, not silent.

## Home Assistant architecture (homeassistant/config/)

`configuration.yaml` is the entry point. It splits the config into separate files via `!include`:

- `automations.yaml` — trigger → condition → action rules
- `scripts.yaml` — reusable callable sequences (invoked as `script.<id>` from automations)
- `scenes.yaml` — saved entity-state snapshots

### Two things to know before editing these files

1. **Most of `automations.yaml` / `scripts.yaml` / `scenes.yaml` is UI-generated.** Entries are keyed by epoch-millisecond IDs (e.g. `'1707650979263'`) and reference hardware by opaque `device_id` / `entity_id` hashes (e.g. `device_id: 7045779a...`). These IDs map to physical devices that only exist in the live HA instance — you generally cannot resolve or invent them from this repo alone. Prefer editing automations/scripts/scenes through the Home Assistant UI; hand-editing the YAML here is for small, well-understood tweaks only.

2. **Runtime/secret files are deliberately untracked.** `homeassistant/config/.gitignore` ignores everything except `*.yaml`, `.gitignore`, and `*.md`. That means `secrets.yaml`, `.storage/` (entity registry, integrations, devices, dashboards), `known_devices.yaml`, and `ip_bans.yaml` live only on the server. Reference secrets with `!secret <key>`; never inline a credential.

### Scripts/automations reference things not in this repo

- **`impk`** — a custom integration (Wrocław MPK public-transport departures) used in `configuration.yaml` as `platform: impk`. Its code lives under `custom_components/` on the server, which is gitignored — it is not here.
- **`homeassistant/notify_leaving_zone.yaml`** — a blueprint referenced by several automations; also lives only on the server.

A common pattern in the scripts: a generic parameterized script (e.g. `minutnik_generyczny`, `uruchom_radio_357`) takes `target_device_id` / `target_entity_id`, and thin per-room wrapper scripts call it with hardcoded IDs. NFC tags (`platform: tag`) are the main trigger for kitchen/bedroom routines.

## Docker / hardware notes

- The Home Assistant container runs `privileged` with `network_mode: host` and passes through `/dev/ttyACM0` (a USB Zigbee/Z-Wave radio) and `/run/dbus`. Pinned to a specific image tag in `homeassistant/docker-compose.yml` — bump the tag to upgrade.
- `http:` in `configuration.yaml` trusts `127.0.0.1` as a proxy (`use_x_forwarded_for`), consistent with reaching HA through the autossh tunnel / a reverse proxy rather than directly.
