#!/usr/bin/env bash
set -euo pipefail
package="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
target=/home/djoldskull/smartwaste
python="$target/.venv-mobile/bin/python"
test -f "$target/.env"
test -f "$target/backend/main.py"
test -x "$python"
test -f "$package/backend/migrations/004_routes_statistics.sql"
if [[ "$package" == "$target" ]]; then
 echo 'Run from the extracted package on Desktop, not the live directory.' >&2; exit 1
fi
backup="$target/backups/mobile-v130-$(date +%Y%m%d-%H%M%S)"
mkdir -p "$backup"
chmod 700 "$backup"
cp -a "$target/backend" "$backup/backend"
echo "Backup: $backup/backend"
"$python" -m pip install -r "$package/backend/requirements-solana.txt"
cd "$target"
PYTHONPATH="$package/backend" "$python" -m smartwaste.manage migrate --env-file "$target/.env"
sudo systemctl stop smartwaste.service
if systemctl is-active --quiet smartwaste-solana.service; then sudo systemctl stop smartwaste-solana.service; fi
trap 'echo "Update interrupted. Backend backup: $backup/backend" >&2' ERR
cp -a "$package/backend/smartwaste" "$package/backend/migrations" "$target/backend/"
cp -a "$package/backend/main_mobile.py" "$package/backend/requirements.txt" "$package/backend/requirements-solana.txt" "$package/backend/smartwaste-solana.service" "$package/backend/demo_timisoara.sql" "$package/backend/company_statistics.sql" "$target/backend/"
sudo systemctl enable smartwaste.service
sudo systemctl restart smartwaste.service
sudo cp "$target/backend/smartwaste-solana.service" /etc/systemd/system/smartwaste-solana.service
sudo systemctl daemon-reload
if [[ -f /home/djoldskull/.config/smartwaste/solana-devnet.json ]]; then
 sudo systemctl enable --now smartwaste-solana.service
else
 echo 'Create/fund the Devnet wallet before enabling smartwaste-solana.service. Reports show SOLANA_NOT_CONFIGURED until then.'
fi
sleep 5
sudo systemctl status smartwaste.service --no-pager -l
curl --fail --max-time 10 http://127.0.0.1:8000/health
echo
echo 'Update installed. Demo SQL has NOT been executed. main.py, .env, LoRa and thresholds preserved.'
