#!/usr/bin/env bash
set -euo pipefail

pack_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
python_bin="${CHIEF_TEST_PYTHON:-$(command -v python3)}"

bash -n "$pack_dir/install.sh"
bash -n "$pack_dir/chief-send.sh"
"$python_bin" -m compileall -q "$pack_dir/profile" "$pack_dir/events-bridge" "$pack_dir/scripts"
"$python_bin" -m unittest discover -s "$pack_dir/tests" -p 'test_*.py' -v
