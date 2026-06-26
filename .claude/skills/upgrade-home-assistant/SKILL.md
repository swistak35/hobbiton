---
name: upgrade-home-assistant
description: Upgrade the Home Assistant Docker container on the hobbiton server. Defaults to ONE release behind the latest (the previous minor) — never the newest unless explicitly asked. Walks every release in the upgrade path, reports (1) noteworthy new features and (2) breaking/relevant changes to the user's actually-configured integrations, links each release's blog post and changelog, then on approval bumps the image tag, redeploys, has the user recreate the container, and verifies. Use when the user wants to update/upgrade Home Assistant, asks whether HA is out of date, or asks what a new HA release changes.
---

# Upgrade Home Assistant

Upgrades the HA Docker container defined in `homeassistant/docker-compose.yml` on the **hobbiton** server, the safe way: analyze first, present, get approval, then upgrade and verify.

## Policy (read this first)

- **Target = one release behind the latest.** HA ships a new minor on the first Wednesday of each month (CalVer `YYYY.M`, e.g. `2026.5`). The newest release is the least-tested. So the **default target is the minor immediately *before* the newest** — its `.x` patch releases have had a month to shake out bugs. Example: if the newest is `2026.6`, the default target is `2026.5`.
- **Never jump to the newest minor unless the user explicitly asks** ("to latest", "the newest", "2026.6"). If they name a specific version, honor it.
- **Patch level: use the bare `YYYY.M` image tag** (e.g. `2026.5`). That tag always tracks the latest patch within the series, so you get `2026.5.<latest>` automatically.
- **Always present the analysis and STOP for approval before changing anything.** This skill is analyze → report → confirm → upgrade → verify. Do not bump the tag before the user approves.

## Deployment reality on this server (constraints that shape the steps)

- The SSH user (`ssh hobbiton`) has **no Docker *daemon* access** (the socket returns "permission denied") and **sudo requires a password** — verified. So this skill **cannot recreate the container autonomously.** `./sync.sh deploy` pushes the changed `docker-compose.yml` to the server (plain rsync, no Docker needed), but the actual image pull + container recreate is a **manual step the user runs interactively** (sudo password prompt). Hand them the exact command; do not try to run `docker ps`/`docker-compose up` over plain ssh — those hit the daemon and fail with a permission error.
- **Exception: `docker --version` works over plain ssh** (it's just the client binary, no daemon needed). Use it to auto-verify the Docker-version gate below — you do NOT need to ask the user for it.
- `restart` via the HA API (what `./sync.sh restart` does) restarts HA *inside the existing container* — it does **NOT** apply an image-tag change. Only `docker-compose up -d` (recreating the container) pulls the new image. Do not use `sync.sh restart` for the upgrade itself.
- HA's REST API is reachable with the long-lived token in `$HA_TOKEN` (loaded by direnv in the repo root). `GET /api/config` returns the live `version`. Defaults: `HA_URL=http://192.168.0.81:8123`.

---

## Step 1 — Determine the current version

Read the declared tag and confirm what's actually running:

```bash
grep 'image:' /home/swistak35/projs/hobbiton/homeassistant/docker-compose.yml          # declared tag, e.g. 2025.9
cd /home/swistak35/projs/hobbiton && curl -fsS --max-time 8 "${HA_URL:-http://192.168.0.81:8123}/api/config" \
  -H "Authorization: Bearer $HA_TOKEN" | python3 -c 'import sys,json;print("running:",json.load(sys.stdin)["version"])'
```

(direnv loads `$HA_TOKEN` in the repo root. If it's missing, tell the user to run `direnv allow` and `! ` it.) The minor of the running version should match the declared tag; use the **declared tag's minor** as the upgrade origin.

## Step 2 — Determine the latest release and the target

Find the two newest stable minors. Fetch the release-notes index once:

- `https://www.home-assistant.io/blog/categories/release-notes/` (newest first), or WebSearch `Home Assistant latest release` on `home-assistant.io`.

From that: `newest` = the top stable minor; **`target` = the minor immediately before `newest`** (the policy default). If the user named a version or said "latest", use that instead and say so.

Sanity-check edge cases:
- If the running minor is already **≥ target**, there's nothing to do under policy (you're already one-behind-latest or newer). Report that; only offer a patch bump if relevant.
- If running minor **== target − 1**, it's a single-release upgrade.

## Step 3 — Enumerate the upgrade path

List every minor strictly after the origin, up to and including the target (HA months are 1–12; roll the year at 12→1):

```bash
# usage: gen_path <origin YYYY.M> <target YYYY.M>   e.g. gen_path 2025.9 2026.5
gen_path() {
  local y=${1%.*} m=${1#*.} ty=${2%.*} tm=${2#*.}
  while :; do
    m=$((m+1)); [ $m -gt 12 ] && { m=1; y=$((y+1)); }
    echo "$y.$m"
    [ "$y" -eq "$ty" ] && [ "$m" -eq "$tm" ] && break
    [ "$y" -gt "$((ty+1))" ] && break   # safety
  done
}
```

Example: `2025.9 → 2026.5` yields `2025.10 2025.11 2025.12 2026.1 2026.2 2026.3 2026.4 2026.5` (8 releases). **Every one of these gets reviewed and linked** — breaking changes accumulate across all skipped releases, not just the target.

For each version `v`, the **changelog URL is deterministic**:
`https://www.home-assistant.io/changelogs/core-<v>/`  (e.g. `core-2026.5`).
The **blog URL needs the release date** (`/blog/YYYY/MM/DD/release-YYYYMM/`, day varies). Get the exact blog URLs from the release-notes index page (Step 2) or one WebSearch per version.

## Step 4 — Discover which integrations the user ACTUALLY uses

Don't guess from `configuration.yaml` — most integrations are UI-configured and live only in server-side `.storage/`. Read them live (source of truth):

```bash
ssh hobbiton 'python3 -c "import json;d=json.load(open(\"hobbiton/homeassistant/config/.storage/core.config_entries\"));print(\"\n\".join(sorted(set(e[\"domain\"] for e in d[\"data\"][\"entries\"]))))"'
ssh hobbiton 'ls hobbiton/homeassistant/config/custom_components/'   # custom integrations (HACS + bespoke)
```

Also note the YAML-configured platforms in `homeassistant/config/configuration.yaml` (`impk`, `spacerek`, `template`, `http`, etc.).

**Snapshot for reference (re-run the command — this WILL drift):** as of writing the configured domains were:
`androidtv_remote, backup, bluetooth, cast, elevenlabs, gios, go2rtc, google, google_generative_ai_conversation, google_translate, hacs, holiday, homekit_controller, ibeacon, imgw_pib, ipp, local_calendar, met, min_max, mobile_app, openweathermap, plex, radio_browser, shopping_list, smartthings, spotify, sun, template, time_date, tuya, upnp, xiaomi_ble, zha`.
Custom components: `impk` (Wrocław MPK transport, YAML), `spacerek` (kids' clothing recommendations, YAML), `hacs`.

The highest-risk ones to scan changelogs for: **`zha`** (Zigbee), **`tuya`**, **`smartthings`**, **`bluetooth`/`xiaomi_ble`/`ibeacon`**, **`spotify`/`plex`/`cast`/`androidtv_remote`/`go2rtc`**, **`google_generative_ai_conversation`/`elevenlabs`** (AI/voice), the weather/air stack **`met`/`openweathermap`/`imgw_pib`/`gios`**, **`homekit_controller`**, **`ipp`**, **`upnp`**. And custom code (`impk`, `spacerek`, anything HACS-managed) — core upgrades frequently break custom integrations; HACS items must be re-checked for updates after the core bump.

## Step 5 — Fetch and analyze each release

For each release in the path, read its **blog post** (human summary: highlights + a "Backward-incompatible changes" / "Breaking changes" section) and, when needed, its **changelog** (exhaustive; grep it for the user's domains).

For a multi-release jump this is a lot of pages — **dispatch one subagent per release in parallel** (Agent tool, `general-purpose`), each given the version, its blog+changelog URLs, and the integration list, returning structured findings: `{ noteworthy: [...], breaking_for_user: [{integration, change, action_needed}], other_breaking_notable: [...] }`. Then synthesize. For a single-release upgrade, just WebFetch the two pages directly.

When scanning, prioritize:
1. **Breaking changes that touch a domain the user has** → these may need a config edit or re-auth and are the ones that can take HA down on boot. Flag loudly.
2. **Removed/renamed integrations or entities** the user depends on.
3. **New noteworthy features** (the "you may want this" list) — dashboards, automations/triggers, voice/AI, backup, energy, anything broadly useful.

## Step 6 — Present the report and STOP for approval

Present to the user in the terminal (markdown), in this shape:

- **Header:** `Current: <running>  →  Target: <target>  (policy: one behind latest <newest>)` and the full ordered path of releases being crossed.
- **Links — every release in the path**, each with both:
  - Blog post: `https://www.home-assistant.io/blog/YYYY/MM/DD/release-YYYYMM/`
  - Changelog: `https://www.home-assistant.io/changelogs/core-<v>/`
- **① New & potentially interesting** — bulleted highlights across the path, each tagged with the release it landed in.
- **② Changes in areas you use** — grouped by the user's integration; for each, what changed, which release, and **whether action is required** (config edit / re-auth / removed). Put anything that can break boot at the top.
- **⚠ Pre-upgrade actions** (if any) and **custom-integration risk** (`impk`/`spacerek`/HACS may need updates for the new core).

**Docker-version gate:** if the path crosses **2026.3 or later**, the new image is zstd-compressed and needs **Docker ≥ 23.0** on the server. Auto-check it (works without sudo):
```bash
ssh hobbiton 'docker --version'   # e.g. "Docker version 29.3.1" → gate clear
```
Report the result in the pre-upgrade section; only flag a problem if it's below 23.0.

Then ask for approval to proceed. **Do not continue without it.**

## Step 7 — Back up before upgrading

A core upgrade migrates `.storage` and the database; **downgrading afterward is not reliable** without a backup. Before bumping:

- Trigger HA's built-in backup (best-effort), or tell the user to make one in **Settings → System → Backups**:
  ```bash
  curl -fsS -X POST "${HA_URL:-http://192.168.0.81:8123}/api/services/backup/create_automatic" \
    -H "Authorization: Bearer $HA_TOKEN" -H 'Content-Type: application/json' -d '{}' || \
    echo "could not trigger automatic backup via API — ask the user to create one in Settings → System → Backups"
  ```
- Confirm a recent backup exists before proceeding. The repo's git history covers the YAML, but **not** `.storage`/DB — only an HA backup does.

## Step 8 — Perform the upgrade

1. **Check for pre-existing drift FIRST — do NOT assume the only change is the tag.** Local and server drift (the UI edits config server-side; the mirror has no merge step). Run:
   ```bash
   cd /home/swistak35/projs/hobbiton && ./sync.sh diff
   ```
   **If anything other than `homeassistant/docker-compose.yml` appears**, STOP. A blind `deploy` would overwrite server-side UI/config edits with older local copies. Reconcile first: `./sync.sh pull` to bring server changes into local (then re-check `git diff`), or extract the pre-push state from a backup and diff it, so you understand each drifted file before pushing. Only proceed once you know every file in the diff is one you intend to overwrite. **Never use `deploy -y` here** — review the diff interactively.
2. **Bump the tag** in `homeassistant/docker-compose.yml`:
   `image: "ghcr.io/home-assistant/home-assistant:<target>"` (bare `YYYY.M`).
3. **Push it to the server** (rsync only; HA only reloads if a `config/` file is in the changeset):
   ```bash
   cd /home/swistak35/projs/hobbiton && ./sync.sh deploy   # review the diff, confirm manually
   ```
   It prints a reminder to recreate the container.
4. **Recreate the container — USER RUNS THIS** (needs sudo password; the SSH user has no Docker daemon access). Give them this to paste with the `! ` prefix so output is captured:
   ```
   ! ssh -t hobbiton 'cd hobbiton/homeassistant && sudo docker-compose pull && sudo docker-compose up -d'
   ```
   (`-t` allocates a TTY for the sudo prompt; `pull` fetches the new image, `up -d` recreates only because the tag changed.) If they prefer, they can run the `cd … && sudo docker-compose pull && sudo docker-compose up -d` part directly on the server.

## Step 9 — Verify

Wait for HA to come back, then confirm the new version is live and the config is healthy:

```bash
cd /home/swistak35/projs/hobbiton
for i in $(seq 1 60); do curl -fsS --max-time 4 "${HA_URL:-http://192.168.0.81:8123}/api/config" \
  -H "Authorization: Bearer $HA_TOKEN" >/dev/null 2>&1 && break; sleep 4; done
curl -fsS "${HA_URL:-http://192.168.0.81:8123}/api/config" -H "Authorization: Bearer $HA_TOKEN" \
  | python3 -c 'import sys,json;d=json.load(sys.stdin);print("now running:",d["version"],"state:",d["state"])'
./sync.sh check   # config still valid
```

Then sanity-check that integrations loaded (look for setup errors), especially the high-risk and custom ones:

```bash
ssh hobbiton "grep -iE 'error|traceback|setup failed|not load|deprecat' hobbiton/homeassistant/config/home-assistant.log | tail -40"
```

Report: confirmed new version, config valid, and any integrations that failed to set up (cross-reference against the breaking-changes you flagged in Step 6). If a custom component (`impk`/`spacerek`) or a HACS integration broke, that's expected fallout — note it and offer to look at updating it.

## Step 10 — Commit the version bump

Per the repo's git-as-authority model (deploy ≠ commit), offer to checkpoint the tag change:

```bash
cd /home/swistak35/projs/hobbiton && git add homeassistant/docker-compose.yml && \
  git commit -m "Upgrade Home Assistant to <target>" && git push origin
```

(End the commit message with the `Co-Authored-By` trailer per repo convention. Only commit/push when the user wants a checkpoint.)

---

## Rollback

If the new version is broken:

1. Revert the tag in `homeassistant/docker-compose.yml` to the previous one and `./sync.sh deploy`.
2. User recreates the container again:
   `! ssh -t hobbiton 'cd hobbiton/homeassistant && sudo docker-compose pull && sudo docker-compose up -d'`
3. **If `.storage`/DB was already migrated by the new version, the old core may refuse to start or behave oddly** — restore the pre-upgrade backup from Step 7 (Settings → System → Backups → restore). This is exactly why Step 7 is mandatory.

## URL reference

- Release blog post: `https://www.home-assistant.io/blog/YYYY/MM/DD/release-YYYYMM/` (day = release date, varies — discover it; the rest is fixed).
- Full changelog (deterministic): `https://www.home-assistant.io/changelogs/core-YYYY.M/`.
- Release-notes index (all recent, newest first): `https://www.home-assistant.io/blog/categories/release-notes/`.
- Release schedule / cadence: `https://www.home-assistant.io/faq/release/`.
