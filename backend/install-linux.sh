#!/usr/bin/env bash
set -euo pipefail

src_dir="$(cd "$(dirname "$0")" && pwd)"
app_dir="${1:-/home/$(id -un)/mediamonster}"
user_name="$(id -un)"
user_id="$(id -u)"

# Update detection compares local and registry digests through Buildx.
if ! docker buildx version >/dev/null 2>&1; then
    sudo apt-get update
    sudo apt-get install -y docker-buildx
fi

install -d -m 700 "$app_dir" "$HOME/.config/systemd/user"

for file in server.py push.py app-release.json mediamonster-api.service set-password.sh install-linux.sh; do
    if [[ -f "$src_dir/$file" ]]; then
        mode=600
        if [[ "$file" == *.sh ]]; then
            mode=700
        fi
        install -m "$mode" "$src_dir/$file" "$app_dir/$file"
    fi
done

if [[ ! -s "$app_dir/api.env" ]]; then
    token="$(openssl rand -hex 32)"
    {
        printf 'MM_TOKEN=%s\n' "$token"
        printf 'MM_BIND=0.0.0.0\n'
        printf 'MM_PORT=8787\n'
        printf '%s\n' 'MM_STORAGE='\''{"NUC 11":"/","DS224":"/mnt/DS224/video","DS716":"/mnt/DS716/video"}'\'''
    } > "$app_dir/api.env"
fi

chmod 600 "$app_dir/api.env"
if [[ -f "$app_dir/firebase-service-account.json" ]]; then
    chmod 600 "$app_dir/firebase-service-account.json"
fi
cp "$app_dir/mediamonster-api.service" "$HOME/.config/systemd/user/mediamonster-api.service"

sudo loginctl enable-linger "$user_name"
if sudo ufw status 2>/dev/null | grep -q 'Status: active'; then
    sudo ufw allow from 192.168.72.0/24 to any port 8787 proto tcp
fi

export XDG_RUNTIME_DIR="/run/user/$user_id"
export DBUS_SESSION_BUS_ADDRESS="unix:path=$XDG_RUNTIME_DIR/bus"
systemctl --user daemon-reload
systemctl --user enable --now mediamonster-api
systemctl --user is-active mediamonster-api
