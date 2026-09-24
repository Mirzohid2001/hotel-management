# Ops scripts (backup / deploy / restore)

Run **on the VPS**. They never SSH from your laptop by themselves — so a bad local run cannot wipe production.

## First-time setup (server)

```bash
cd /home/hotel/hotel-management   # or your APP_DIR
cp scripts/ops.env.example scripts/ops.env
nano scripts/ops.env              # DB name, BACKUP_DIR, RESTART_CMD
chmod +x scripts/backup.sh scripts/deploy.sh scripts/restore.sh
sudo mkdir -p /var/backups/hotel-pms
sudo chown "$(whoami)" /var/backups/hotel-pms
```

`scripts/ops.env` is gitignored — do not commit it.

## Daily backup (cron)

```bash
./scripts/backup.sh --dry-run     # preview
./scripts/backup.sh               # real dump + media
```

Cron example (every day 03:15):

```cron
15 3 * * * /home/hotel/hotel-management/scripts/backup.sh >> /var/log/hotel-backup.log 2>&1
```

Keeps the last `KEEP_BACKUPS` folders (default 14).

## Deploy (safe path)

Your usual flow: **git push locally → pull on server**. Use the script so every deploy takes a backup first:

```bash
./scripts/deploy.sh --dry-run     # no changes
./scripts/deploy.sh --confirm     # backup → pull --ff-only → migrate → static → restart
```

Safety rules baked in:

- refuses to run without `--confirm` or `--dry-run`
- `git pull --ff-only` only (no `--force`, no `reset --hard`)
- migrate forward only
- empty `RESTART_CMD` = skip restart until you set the real systemd unit

## Restore (only if needed)

```bash
./scripts/restore.sh --list
./scripts/restore.sh --dry-run /var/backups/hotel-pms/YYYYMMDD_HHMMSS
./scripts/restore.sh --confirm /var/backups/hotel-pms/YYYYMMDD_HHMMSS
```

Restore **overwrites** the live database. Always `--dry-run` first.

## Off-server copy (recommended)

After Contabo outage: copy dumps off the VPS weekly:

```bash
# from your laptop
scp -r root@YOUR_IP:/var/backups/hotel-pms ./hotel-pms-backups
```

Or sync to another VPS / Object Storage later.
