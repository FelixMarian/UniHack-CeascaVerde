#!/usr/bin/env bash
set -euo pipefail
package="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
target=/home/djoldskull/smartwaste
python="$target/.venv-mobile/bin/python"
test -f "$target/.env"
test -f "$target/backend/main.py"
test -x "$python"
test -f "$package/backend/migrations/003_company_proofs.sql"
if [[ "$package" == "$target" ]]; then
    echo 'Run this installer from the extracted update package, not the live folder.' >&2
    exit 1
fi
backup="$target/backups/mobile-$(date +%Y%m%d-%H%M%S)"
mkdir -p "$backup"
chmod 700 "$backup"
cp -a "$target/backend" "$backup/backend"
echo "Backend backup: $backup/backend"
"$python" -m pip install -r "$package/backend/requirements.txt"
cd "$target"
# Migrate from the package first. Existing code keeps working with additive columns.
PYTHONPATH="$package/backend" "$python" -m smartwaste.manage migrate --env-file "$target/.env"
sudo systemctl stop smartwaste.service
trap 'echo "Update interrupted. Backend backup is at: $backup/backend. Check journalctl before restarting." >&2' ERR
cp -a "$package/backend/smartwaste" "$target/backend/"
cp -a "$package/backend/migrations" "$target/backend/"
cp -a "$package/backend/main_mobile.py" "$target/backend/"
cp -a "$package/backend/requirements.txt" "$package/backend/requirements-solana.txt" "$package/backend/smartwaste-solana.service" "$target/backend/"
sudo systemctl enable smartwaste.service
sudo systemctl restart smartwaste.service
sleep 5
sudo systemctl status smartwaste.service --no-pager -l
curl --fail --max-time 10 http://127.0.0.1:8000/health
echo
echo 'Mobile backend updated. main.py, .env, LoRa receiver and its .venv were preserved.'
