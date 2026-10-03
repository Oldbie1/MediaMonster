#!/usr/bin/env bash
set -euo pipefail

read -rs -p "Media Monster-wachtwoord: " media_monster_password
printf '\n'
export MM_SETUP_PASSWORD="$media_monster_password"
cd "$(dirname "$0")"
python3 -c 'import os, server; server.save_password(os.environ["MM_SETUP_PASSWORD"])'
unset MM_SETUP_PASSWORD media_monster_password

export XDG_RUNTIME_DIR="/run/user/$(id -u)"
export DBUS_SESSION_BUS_ADDRESS="unix:path=$XDG_RUNTIME_DIR/bus"
systemctl --user restart mediamonster-api
printf '%s\n' 'Wachtwoord opgeslagen. Media Monster is opnieuw gestart.'
