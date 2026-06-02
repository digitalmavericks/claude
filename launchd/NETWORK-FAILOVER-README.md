# ECHO Mac mini · Network Failover Watchdog — Install Guide

**Purpose:** Keep the Mac mini reachable when its primary uplink dies. The
Mac's main internet is the **wired LAN (FrontierDC)**. When that dropped while
DC was out of town, there was no fallback, so Tailscale and the remote-control
Funnel went dark for ~7 days. This watchdog detects loss of internet and
**fails the Mac over to the "Frenchie Fam" Wi-Fi** (a *different* ISP), then
re-arms the Tailscale Funnel so remote access comes back on its own.

> **Why not FrontierDC Wi-Fi?** Because the `FrontierDC` SSID rides the *same
> physical uplink* as the wired LAN. If the wired link is down, FrontierDC
> Wi-Fi is down too. The watchdog will **never** join it.

## Files in this folder

- `network-failover-watchdog.sh` — the watchdog script
- `com.digitalmavericks.network-failover-watchdog.plist` — the LaunchDaemon
- `NETWORK-FAILOVER-README.md` — this file

## What it does, every 2 minutes (and at boot)

1. Tests real internet reachability (pings `1.1.1.1` / `8.8.8.8` / `9.9.9.9`,
   with an HTTPS probe fallback for ICMP-blocked networks).
2. **If online** → ensures `tailscale up` and re-arms the Funnel
   (`tailscale funnel --bg 18789`), then exits quietly. It does **not** touch
   Wi-Fi while the wired link is healthy.
3. **If offline** → powers on Wi-Fi, joins **`Frenchie Fam`**, waits for DHCP,
   re-checks, re-arms Tailscale, and posts a Slack alert (which now delivers,
   because the backup link is live).

State transitions (`UP` → `DOWN`/`FAILOVER` and back) are logged and alerted;
while fully offline it re-alerts at most every 6 hours to avoid spam.

## One-time setup: the Wi-Fi password (no secrets in git)

The script reads the `Frenchie Fam` password, in order, from:

1. env var `FRENCHIE_FAM_PSK`, then
2. a line in `ECHO-CONFIG.md`:
   ```
   FRENCHIE_FAM_PSK=your-frenchie-fam-wifi-password
   ```
3. the macOS **System keychain** — if `Frenchie Fam` is already a "known"
   network on this Mac, **no password is needed at all**.

**Easiest path:** join `Frenchie Fam` once manually from the Mac (so it's saved
to the System keychain as a preferred network). Then you can skip steps 1–2
entirely. Otherwise add `FRENCHIE_FAM_PSK=...` to `ECHO-CONFIG.md`.

Slack alerts reuse the existing `SLACK_OPS_WEBHOOK` from `ECHO-CONFIG.md` (same
key the iMessage health-check uses).

## Install (run on the Mac mini, in Terminal)

```bash
# 0. Put the files in the ECHO launchd folder (if not already there)
mkdir -p /Users/echo/Documents/Claude/Projects/ECHO/launchd
#   …copy network-failover-watchdog.sh + the .plist into that folder…

# 1. Make the script executable
chmod +x /Users/echo/Documents/Claude/Projects/ECHO/launchd/network-failover-watchdog.sh

# 2. Install the LaunchDaemon (root-owned, in the SYSTEM LaunchDaemons dir)
sudo cp /Users/echo/Documents/Claude/Projects/ECHO/launchd/com.digitalmavericks.network-failover-watchdog.plist \
        /Library/LaunchDaemons/
sudo chown root:wheel /Library/LaunchDaemons/com.digitalmavericks.network-failover-watchdog.plist
sudo chmod 644       /Library/LaunchDaemons/com.digitalmavericks.network-failover-watchdog.plist

# 3. Load it
sudo launchctl bootstrap system /Library/LaunchDaemons/com.digitalmavericks.network-failover-watchdog.plist
#   (older macOS: sudo launchctl load -w /Library/LaunchDaemons/com.digitalmavericks.network-failover-watchdog.plist)
```

Verify it's loaded:

```bash
sudo launchctl list | grep digitalmavericks
```

## Test it manually

```bash
# Run a single pass right now (safe — won't change Wi-Fi while you're online)
sudo /Users/echo/Documents/Claude/Projects/ECHO/launchd/network-failover-watchdog.sh

# Watch the log
tail -f /Users/echo/Library/Logs/digitalmavericks/network-failover.log
```

**Real failover test:** unplug the Mac's Ethernet cable (simulating the
FrontierDC uplink dropping). Within ~2 minutes the watchdog should join
`Frenchie Fam`, you should see `Failover SUCCESS` in the log, get a Slack
alert, and still be able to reach the Mac at
`https://echos-mac-mini-1.tail074467.ts.net/`. Plug Ethernet back in and the
next run logs `Internet: UP` + a "back online" alert.

## Uninstall

```bash
sudo launchctl bootout system /Library/LaunchDaemons/com.digitalmavericks.network-failover-watchdog.plist
sudo rm /Library/LaunchDaemons/com.digitalmavericks.network-failover-watchdog.plist
#   (older macOS: sudo launchctl unload -w /Library/LaunchDaemons/...plist)
```

## Notes & limits

- **macOS Sequoia location permission:** reading the current Wi-Fi SSID and
  switching networks may require Location Services enabled for system Wi-Fi.
  Joining still works; only the SSID name shown in alerts may read blank if
  location is fully disabled.
- **Tailscale CLI:** the script auto-detects the binary
  (`/usr/local/bin`, `/opt/homebrew/bin`, or inside `Tailscale.app`). If the
  Funnel is managed entirely at the OS level and the CLI can't re-arm it, the
  watchdog still restores internet — the externally-managed Funnel then comes
  back on its own. The re-arm is best-effort and logged either way.
- **Optional hardening:** to stop macOS ever auto-joining `FrontierDC` Wi-Fi,
  remove it from *System Settings → Wi-Fi → Advanced → Known Networks*, or push
  `Frenchie Fam` above it in the preferred order. The watchdog never joins
  FrontierDC, but this keeps macOS's own auto-join from wasting time on a dead
  link.
