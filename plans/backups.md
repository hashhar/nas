# Plan: Backups

## Context

The NAS has a Restic REST server deployed and Synology snapshots enabled, but there is no automated backup scheduling, integrity verification, or offsite copy. A hardware failure, fire, or ransomware could destroy all data. This plan covers local automated backups, database-level dumps for Immich, and offsite cloud replication.

---

## 1. Automated Restic Backup Scheduling & Verification

**Problem:** Restic REST server is deployed but there's no automated backup scheduling or integrity verification. Backups only happen if triggered manually.

**Recommendation:**
- Add a `restic-backup` sidecar container (or cron-based container like `lobaro/restic-backup-docker`) that runs scheduled `restic backup` commands against the REST server
- Schedule nightly backups of critical data (Immich DB dumps, Docker appdata, config files)
- Run weekly `restic check` for repository integrity verification
- Add a Prometheus exporter or push-gateway metric for last successful backup timestamp
- Add an Alertmanager rule: `ResticBackupStale` if no successful backup in 48h

**Files:**
- New `stacks/infra/restic-backup/` directory (alongside restic-rest-server in the infra stack)
- `stacks/infra/docker-compose.yml` — new service
- `stacks/monitoring/prometheus/alerts.yml` — new alert rule

---

## 2. PostgreSQL Backup for Immich

**Problem:** Immich's PostgreSQL database holds all photo metadata, face recognition data, and user accounts. A volume corruption would lose all this. Synology snapshots help but a logical backup is more portable.

**Recommendation:**
- Add a `postgres-backup` sidecar container (e.g., `prodrigestivill/postgres-backup-local`) that runs `pg_dump` on a schedule
- Store dumps in the Restic-backed-up directory for offsite protection
- Retain 7 daily + 4 weekly dumps locally

> Note: the stacks restructure already added an ongoing logical DB backup —
> Immich's built-in scheduled `pg_dumpall` writes to
> `$DATA_ROOT/Personal/Pictures/immich/upload/backups` (a restic-covered path).
> A separate `postgres-backup` sidecar is now only needed if you want dumps
> independent of Immich's scheduler.

**Files:**
- `stacks/photos/docker-compose.yml` — new service, new volume mount for dump output

---

## 15. Offsite Backup via Restic to Cloud

**Problem:** All backups are currently on the same NAS (Restic REST server + Synology snapshots). A hardware failure, fire, or ransomware could destroy everything.

**Recommendation:**
- Configure Restic to also push to a cloud backend (Backblaze B2 is cheapest at $0.005/GB/month)
- Use the same scheduled backup container from item #1
- Add a second Restic repository target for offsite
- Even 100GB of critical data (configs, DB dumps, irreplaceable photos) costs ~$0.50/month

**Files:**
- `stacks/infra/restic-backup/` configuration (second repository target)

---

## Verification

1. Trigger a manual backup run and verify it completes without errors
2. Check Restic repository with `restic check` and `restic snapshots`
3. Verify `pg_dump` output files appear in the expected directory with correct timestamps
4. Confirm Prometheus metric for last successful backup is updated
5. Trigger the `ResticBackupStale` alert by advancing the threshold and verify email delivery
6. For offsite: verify a snapshot appears in the B2 bucket
7. Test a restore from both local and offsite repositories for a non-critical file
