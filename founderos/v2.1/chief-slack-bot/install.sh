#!/usr/bin/env bash
set -euo pipefail

pack_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
phase=1
activate=0
dry_run=0
non_interactive=0

usage() {
  printf '%s\n' \
    'Usage: ./install.sh [--phase 1|2] [--activate] [--dry-run] [--non-interactive]' \
    '' \
    'Phase 1 installs outbound CHIEF identity only.' \
    'Phase 2 also installs the strict Slack Events API bridge.' \
    '--activate is valid only for Phase 2 and starts the LaunchAgent.' \
    'No Slack message is sent by this installer.'
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --phase)
      phase="${2:-}"
      shift 2
      ;;
    --activate)
      activate=1
      shift
      ;;
    --dry-run)
      dry_run=1
      shift
      ;;
    --non-interactive)
      non_interactive=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      printf 'ERROR: unknown argument: %s\n' "$1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

if [[ "$phase" != "1" && "$phase" != "2" ]]; then
  printf 'ERROR: --phase must be 1 or 2\n' >&2
  exit 2
fi
if [[ "$activate" == "1" && "$phase" != "2" ]]; then
  printf 'ERROR: --activate is valid only with --phase 2\n' >&2
  exit 2
fi

python_bin="${CHIEF_PYTHON3:-$(command -v python3 || true)}"
if [[ -z "$python_bin" || ! -x "$python_bin" ]]; then
  printf 'ERROR: python3 is required\n' >&2
  exit 1
fi

profile_home="${CHIEF_PROFILE_HOME:-$HOME/.hermes/profiles/chief}"
hermes_env="${HERMES_ROOT_ENV:-$HOME/.hermes/.env}"
local_bin="${CHIEF_LOCAL_BIN:-$HOME/.local/bin}"
launch_agents="${CHIEF_LAUNCH_AGENT_DIR:-$HOME/Library/LaunchAgents}"
plist_label="com.digitalmavericks.chief-slack-events"
plist_target="${launch_agents}/${plist_label}.plist"
canonical_channel_id="C0BL2AM4KCY"
backup_stamp="$(date -u +%Y%m%dT%H%M%SZ)"
backup_root="${profile_home}/backups/${backup_stamp}"

printf '[1/4] Offline technical tests\n'
"$pack_dir/tests/run.sh"

if [[ "$dry_run" == "1" ]]; then
  printf '[DRY RUN] phase=%s profile=%s env=%s activate=%s\n' \
    "$phase" "$profile_home" "$hermes_env" "$activate"
  exit 0
fi

mkdir_mode() {
  install -d -m "$1" "$2"
}

backup_if_different() {
  local source="$1"
  local target="$2"
  if [[ -e "$target" ]] && ! cmp -s "$source" "$target"; then
    local relative="${target#/}"
    local backup="${backup_root}/${relative}"
    mkdir_mode 700 "$(dirname "$backup")"
    cp -p "$target" "$backup"
    printf 'BACKUP %s -> %s\n' "$target" "$backup"
  fi
}

install_file() {
  local mode="$1"
  local source="$2"
  local target="$3"
  backup_if_different "$source" "$target"
  mkdir_mode 700 "$(dirname "$target")"
  install -m "$mode" "$source" "$target"
}

install_value() {
  local mode="$1"
  local value="$2"
  local target="$3"
  local temporary
  temporary="$(mktemp "${profile_home}/state/.install-value.XXXXXX")"
  printf '%s\n' "$value" > "$temporary"
  install_file "$mode" "$temporary" "$target"
  rm -f -- "$temporary"
}

install_link() {
  local source="$1"
  local target="$2"
  if [[ -L "$target" && "$(readlink "$target")" == "$source" ]]; then
    return
  fi
  if [[ -e "$target" || -L "$target" ]]; then
    local relative="${target#/}"
    local backup="${backup_root}/${relative}"
    mkdir_mode 700 "$(dirname "$backup")"
    cp -pP "$target" "$backup"
    printf 'BACKUP %s -> %s\n' "$target" "$backup"
  fi
  mkdir_mode 700 "$(dirname "$target")"
  ln -sfn "$source" "$target"
}

env_has() {
  "$python_bin" "$pack_dir/profile/upsert_env.py" has "$hermes_env" "$1"
}

env_get() {
  "$python_bin" "$pack_dir/profile/upsert_env.py" get "$hermes_env" "$1"
}

env_set() {
  local key="$1"
  local value="$2"
  printf '%s' "$value" | "$python_bin" "$pack_dir/profile/upsert_env.py" set "$hermes_env" "$key"
}

ensure_value() {
  local key="$1"
  local label="$2"
  local secret="$3"
  local current="${!key:-}"
  if [[ -n "$current" ]]; then
    env_set "$key" "$current"
    return
  fi
  if env_has "$key"; then
    return
  fi
  if [[ "$non_interactive" == "1" || ! -t 0 ]]; then
    printf 'ERROR: %s is missing from the environment and %s\n' "$key" "$hermes_env" >&2
    exit 1
  fi
  local entered
  if [[ "$secret" == "1" ]]; then
    read -r -s -p "${label}: " entered
    printf '\n'
  else
    read -r -p "${label}: " entered
  fi
  if [[ -z "$entered" ]]; then
    printf 'ERROR: %s cannot be empty\n' "$key" >&2
    exit 1
  fi
  env_set "$key" "$entered"
  unset entered
}

printf '[2/4] Relay-only profile\n'
mkdir_mode 700 "$profile_home"
mkdir_mode 700 "$profile_home/bin"
mkdir_mode 700 "$profile_home/lib"
mkdir_mode 700 "$profile_home/logs"
mkdir_mode 700 "$profile_home/state"
mkdir_mode 700 "$profile_home/home"
install_file 600 "$pack_dir/profile/RELAY_ONLY" "$profile_home/RELAY_ONLY"
install_file 600 "$pack_dir/profile/config.yaml" "$profile_home/config.yaml"
install_file 700 "$pack_dir/chief-send.sh" "$profile_home/bin/chief-send"
install_file 600 "$pack_dir/profile/envfile.py" "$profile_home/lib/envfile.py"
  install_file 700 "$pack_dir/profile/chief_slack_post.py" "$profile_home/lib/chief_slack_post.py"
  install_file 700 "$pack_dir/profile/upsert_env.py" "$profile_home/lib/upsert_env.py"
  install_value 600 "$python_bin" "$profile_home/state/python3.path"
  install_value 600 "$hermes_env" "$profile_home/state/hermes-env.path"
  install_link "$profile_home/bin/chief-send" "$local_bin/chief-send"
  env_set "CHIEF_PROFILE_HOME" "$profile_home"

printf '[3/4] Phase %s configuration\n' "$phase"
ensure_value "CHIEF_SLACK_BOT_TOKEN" "CHIEF Slack bot token (input hidden)" 1
ensure_value "CHIEF_SLACK_BOT_USER_ID" "CHIEF Slack bot user ID" 0
ensure_value "CHIEF_SLACK_TEAM_ID" "Slack workspace team ID" 0
if [[ -n "${CHIEF_SLACK_DEFAULT_CHANNEL_ID:-}" &&
      "$CHIEF_SLACK_DEFAULT_CHANNEL_ID" != "$canonical_channel_id" ]]; then
  printf 'ERROR: CHIEF_SLACK_DEFAULT_CHANNEL_ID must be #rogue-ops (%s)\n' "$canonical_channel_id" >&2
  exit 1
fi
if env_has "CHIEF_SLACK_DEFAULT_CHANNEL_ID"; then
  configured_default="$(env_get "CHIEF_SLACK_DEFAULT_CHANNEL_ID")"
  if [[ "$configured_default" != "$canonical_channel_id" ]]; then
    printf 'ERROR: stored CHIEF_SLACK_DEFAULT_CHANNEL_ID must be #rogue-ops (%s)\n' "$canonical_channel_id" >&2
    exit 1
  fi
else
  env_set "CHIEF_SLACK_DEFAULT_CHANNEL_ID" "$canonical_channel_id"
fi
if [[ -n "${CHIEF_SLACK_ALLOWED_CHANNEL_IDS:-}" ]]; then
  env_set "CHIEF_SLACK_ALLOWED_CHANNEL_IDS" "$CHIEF_SLACK_ALLOWED_CHANNEL_IDS"
elif ! env_has "CHIEF_SLACK_ALLOWED_CHANNEL_IDS"; then
  env_set "CHIEF_SLACK_ALLOWED_CHANNEL_IDS" "$canonical_channel_id"
fi
configured_default="$(env_get "CHIEF_SLACK_DEFAULT_CHANNEL_ID")"
configured_allowed=",${CHIEF_SLACK_ALLOWED_CHANNEL_IDS:-$(env_get "CHIEF_SLACK_ALLOWED_CHANNEL_IDS")},"
configured_allowed="${configured_allowed//[[:space:]]/}"
if [[ "$configured_default" != "$canonical_channel_id" ]]; then
  printf 'ERROR: CHIEF_SLACK_DEFAULT_CHANNEL_ID must be #rogue-ops (%s)\n' "$canonical_channel_id" >&2
  exit 1
fi
if [[ "$configured_allowed" != *",${canonical_channel_id},"* ]]; then
  printf 'ERROR: CHIEF_SLACK_ALLOWED_CHANNEL_IDS must include #rogue-ops (%s)\n' "$canonical_channel_id" >&2
  exit 1
fi

if [[ "$phase" == "2" ]]; then
  ensure_value "CHIEF_SLACK_SIGNING_SECRET" "CHIEF Slack signing secret (input hidden)" 1
  ensure_value "CHIEF_SLACK_API_APP_ID" "CHIEF Slack API app ID" 0
  ensure_value "CHIEF_SLACK_ALLOWED_USER_IDS" "Comma-separated allowed Slack human user IDs" 0
  ensure_value "CHIEF_AGENTBUS_ROOT" "Absolute AgentBus root ending in _AgentBus" 0
  if ! env_has "CHIEF_SLACK_EVENTS_PORT"; then
    env_set "CHIEF_SLACK_EVENTS_PORT" "${CHIEF_SLACK_EVENTS_PORT:-18793}"
  fi

  mkdir_mode 700 "$profile_home/events-bridge"
  install_file 600 "$pack_dir/events-bridge/bridge_core.py" "$profile_home/events-bridge/bridge_core.py"
  install_file 700 "$pack_dir/events-bridge/server.py" "$profile_home/events-bridge/server.py"
  mkdir_mode 700 "$launch_agents"

  rendered_plist="$profile_home/state/${plist_label}.rendered.plist"
  "$python_bin" "$pack_dir/scripts/render_plist.py" \
    --template "$pack_dir/events-bridge/com.digitalmavericks.chief-slack-events.plist.template" \
    --output "$rendered_plist" \
    --python "$python_bin" \
    --profile-home "$profile_home" \
    --env-file "$hermes_env"
  if [[ -e "$plist_target" ]] && ! grep -Fq \
    'Managed by FounderOS CHIEF Slack identity pack' "$plist_target"; then
    printf 'ERROR: existing LaunchAgent is not owned by this pack: %s\n' "$plist_target" >&2
    exit 1
  fi
  install_file 600 "$rendered_plist" "$plist_target"
  if command -v plutil >/dev/null 2>&1; then
    plutil -lint "$plist_target"
  fi

  if [[ "$activate" == "1" ]]; then
    if [[ "$(uname -s)" != "Darwin" ]]; then
      printf 'ERROR: --activate requires macOS launchd\n' >&2
      exit 1
    fi
    launchctl bootout "gui/$(id -u)/${plist_label}" >/dev/null 2>&1 || true
    launchctl bootstrap "gui/$(id -u)" "$plist_target"
    launchctl enable "gui/$(id -u)/${plist_label}"
    launchctl kickstart -k "gui/$(id -u)/${plist_label}"
  fi
fi

printf '[4/4] Install receipt\n'
printf 'INSTALLED phase=%s profile=%s env_mode=' "$phase" "$profile_home"
stat -f '%Lp' "$hermes_env" 2>/dev/null || stat -c '%a' "$hermes_env"
printf 'No Slack message was sent. No Hermes gateway or LLM route was started.\n'
if [[ "$phase" == "2" && "$activate" == "0" ]]; then
  printf 'Phase 2 LaunchAgent installed but not activated: %s\n' "$plist_target"
fi
