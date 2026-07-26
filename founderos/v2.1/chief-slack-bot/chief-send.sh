#!/usr/bin/env bash
set -euo pipefail

source_path="${BASH_SOURCE[0]}"
while [[ -L "$source_path" ]]; do
  source_dir="$(cd "$(dirname "$source_path")" && pwd)"
  source_path="$(readlink "$source_path")"
  [[ "$source_path" = /* ]] || source_path="${source_dir}/${source_path}"
done
script_dir="$(cd "$(dirname "$source_path")" && pwd)"
installed_candidate="$(cd "${script_dir}/.." && pwd)"
if [[ -f "${installed_candidate}/lib/chief_slack_post.py" ]]; then
  profile_home="$installed_candidate"
else
  profile_home="${CHIEF_PROFILE_HOME:-$HOME/.hermes/profiles/chief}"
fi

python_bin="${CHIEF_PYTHON3:-}"
if [[ -z "$python_bin" && -f "$profile_home/state/python3.path" ]]; then
  IFS= read -r python_bin < "$profile_home/state/python3.path"
fi
if [[ -z "$python_bin" ]]; then
  python_bin="$(command -v python3 || true)"
fi
env_file="${HERMES_ROOT_ENV:-}"
if [[ -z "$env_file" && -f "$profile_home/state/hermes-env.path" ]]; then
  IFS= read -r env_file < "$profile_home/state/hermes-env.path"
fi
env_file="${env_file:-$HOME/.hermes/.env}"
sender="${profile_home}/lib/chief_slack_post.py"

if [[ -z "$python_bin" || ! -x "$python_bin" ]]; then
  printf 'ERROR: python3 is not executable at %s\n' "$python_bin" >&2
  exit 1
fi

if [[ ! -f "$sender" ]]; then
  printf 'ERROR: CHIEF sender is not installed at %s\n' "$sender" >&2
  exit 1
fi

exec "$python_bin" "$sender" --env-file "$env_file" "$@"
