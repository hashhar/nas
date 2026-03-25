# Plan: Observability

## Context

The NAS already has Prometheus for metrics collection and Alertmanager for email-based alerting. This plan adds centralized log aggregation and consolidates alerting into Grafana — enabling log searching, correlation across services, unified alerting on both metrics and logs, all from the Grafana UI.

---

## 8. Loki + Promtail for Log Aggregation

**Problem:** No centralized log viewing. Debugging requires SSH + `docker logs` per container. Logs aren't searchable or correlated.

**Recommendation:**
- Deploy [Loki](https://grafana.com/oss/loki/) (lightweight log aggregation, pairs with Grafana)
- Deploy Promtail as a sidecar to ship Docker container logs to Loki
- Add Loki as a Grafana datasource
- This enables log searching, filtering by service, and log-based alerting from one UI

**Files:**
- New `loki/` directory (config file)
- New `promtail/` directory (config file)
- `docker-compose.yml` — new `loki` and `promtail` services
- `grafana/provisioning/datasources/` — Loki datasource config

---

## 9. Migrate Alerting from Alertmanager to Grafana Alerting

**Problem:** Alertmanager only handles Prometheus metric alerts. Adding Loki would require a separate Loki Ruler component for log-based alerts — an extra moving part. Alert management is done via YAML files requiring container restarts. This duplicates functionality Grafana already provides.

**Recommendation:** Replace standalone Alertmanager with Grafana Alerting (built-in since Grafana v9+).

**Why Grafana Alerting:**
- **Unified alerting** — query Prometheus (PromQL) and Loki (LogQL) from one place
- **Eliminates a container** — Grafana has a built-in Alertmanager; drop the standalone one
- **Single pane of glass** — alert rules, silences, contact points, notification history all in Grafana UI
- **Same Prometheus model** — existing PromQL expressions port directly, no rewrite
- **Extensible notifications** — email (Gmail SMTP) as primary; Ntfy (mobile push), Slack, Discord, webhooks can be added later as extra contact points without architecture changes

**What changes:**

| Component | Before | After |
|-----------|--------|-------|
| Alert rule definition | `prometheus/alerts.yml` (YAML) | Grafana provisioning YAML or UI |
| Alert routing/grouping | Standalone Alertmanager container | Grafana's built-in Alertmanager |
| Notification channel | Email via Alertmanager config | Email via Grafana contact points |
| Log-based alerts | Not possible | Possible via Loki datasource queries |
| Management | Edit YAML + restart containers | Grafana UI (or provisioned config) |

**What stays the same:**
- Prometheus continues to scrape and store metrics (no change)
- PromQL alert expressions remain identical — just defined in Grafana instead of `alerts.yml`
- Gmail SMTP for email notifications (same credentials, same `secrets.env` pattern)

**Migration steps:**
1. Configure SMTP in Grafana — add Gmail SMTP settings via environment variables or `grafana.ini`
2. Create email contact point in Grafana (replaces Alertmanager's receiver config)
3. Port the 7 existing PromQL rules from `prometheus/alerts.yml` into Grafana alert provisioning (`grafana/provisioning/alerting/`)
4. Add log-based alert rules using LogQL (e.g., alert on error log spikes across services)
5. Remove Alertmanager — delete `alertmanager/` directory, remove service from `docker-compose.yml`, remove from `dependabot.yml`
6. Clean up Prometheus — remove `alerting:` and `rule_files:` sections from `prometheus.yml.tpl`, delete `prometheus/alerts.yml`

**Files:**
- `grafana/provisioning/alerting/` — new alert rule and contact point provisioning configs
- `grafana/secrets.env` — add SMTP credentials (moved from `alertmanager/secrets.env`)
- `prometheus/prometheus.yml.tpl` — remove alerting/rule_files sections
- `prometheus/alerts.yml` — delete
- `alertmanager/` — delete entire directory
- `docker-compose.yml` — remove `alertmanager` service
- `.github/dependabot.yml` — remove `alertmanager` entry
- `README.md` — update Alertmanager references, update Special Instructions

**Alternatives considered:**

| Approach | Why rejected |
|----------|-------------|
| Keep Prometheus Alertmanager | Can't alert on Loki logs without Loki Ruler. YAML management is clunky. Duplicates Grafana functionality. |
| Loki Ruler + Prometheus Alertmanager | Adds complexity (Ruler config, hash ring) for a single-node NAS. Overkill. |
| Alertmanager for metrics + Grafana for logs | Split-brain alerting. Two systems to configure and monitor. |
| Uptime Kuma / standalone tool | Doesn't integrate with Prometheus/Loki. Adds another tool instead of consolidating. |

---

## Verification

### Loki + Promtail
1. `docker compose config` — validate compose file syntax
2. `docker compose up --build -d` — deploy Loki and Promtail
3. `docker compose ps` — verify both containers are healthy
4. Open Grafana → Explore → select Loki datasource
5. Query `{container_name="caddy"}` and confirm recent log lines appear
6. Verify logs from at least 3 different services are visible and correctly labeled
7. Confirm log volume does not cause unexpected disk growth (check Loki retention config)

### Alerting Migration
8. Verify all 7 original alert rules appear in Grafana UI under Alerting → Alert rules
9. Trigger a test alert (e.g., temporarily lower a threshold) and confirm email arrives
10. Confirm Prometheus config no longer has `alerting:` section
11. Create a test LogQL alert rule and verify it fires correctly
12. Confirm the Alertmanager container is removed and no longer running
