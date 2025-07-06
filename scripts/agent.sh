#!/usr/bin/env bash
set -euo pipefail
 
echo "=== Creating Agent ==="
echo

temp_folder="/tmp/$(pwgen -1 -A 4)"
agentup agent create -q --no-git --output-dir "$temp_folder" myagent

cd $temp_folder

uv sync --active
agentup agent serve


trap 'rm -rf "$temp_folder"' EXIT



