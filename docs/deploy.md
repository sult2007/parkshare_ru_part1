# Kubernetes / Helm blueprint

High-availability topology for ParkShare without changing local docker-compose flows.

## Components
- `k8s/web-deployment.yaml`: Django/Gunicorn pods behind `k8s/web-service.yaml`, rolling update (maxUnavailable=0, maxSurge=1) and readiness/liveness probes on `/readyz`/`/healthz`.
- `k8s/worker-deployment.yaml`: Celery worker replicas (HPA ready), same image/env as web.
- `k8s/beat-deployment.yaml`: Celery beat scheduler (1 replica, non-root).
- `k8s/hpa.yaml`: CPU-based autoscaling for web and worker, behavior tuned for graceful scale-down.
- `k8s/configmap.yaml` / `k8s/secret-example.yaml`: non-sensitive vs secret env separation; wire to Vault/SM/SealedSecrets in real clusters.
- `k8s/ingress.yaml`: nginx ingress with sane timeouts and TLS secret placeholder.

## Deployment strategy
- Default: RollingUpdate (0 downtime) with `maxUnavailable:0` / `maxSurge:1`. Readiness gate is `/readyz`; slow-start is handled by Gunicorn workers.
- Blue/green: create a parallel deployment (e.g., `parkshare-web-green`) with the same selectors except color, then flip Service/Ingress selector to the new color; keep both colors for fast rollback.
- Canary: split traffic by Ingress annotations or Gateway routes; HPA supports separate scaling for canary if selector differs.

## Migration workflow (high-traffic safe)
1) Build/push image.
2) Run migrations out of band before traffic cutover:
   ```bash
   python manage.py migrate_safe --plan-only  # review plan
   python manage.py migrate_safe --apply      # non-interactive apply
   ```
3) Deploy app pods (rolling or blue/green).
4) If schema includes new columns, ship code that is backward-compatible first; avoid destructive drops until the next deploy.
5) For locking migrations, run them in maintenance window (toggle `MAINTENANCE_MODE=true` via env/ConfigMap) or temporarily scale web to 0.

## Read replicas
- Configure `DATABASE_REPLICA_URL` to enable the read replica alias (`replica`) and router (`core.db_router.ReadReplicaRouter`).
- Analytics/heavy read queries automatically route to the replica; writes stay on `default`. If no replica is set, everything stays on primary.
- For explicit usage in tasks:
  ```python
  from core.utils import read_replica_queryset
  qs = read_replica_queryset(MyModel.objects.all())
  ```

## Safe rollout hooks
- Health: `/healthz` for liveness, `/readyz` for readiness.
- Metrics: `/metrics` (when `ENABLE_METRICS=true`) for Prometheus scraping; protect via network policy or auth if exposed.
- Celery: liveness probes run lightweight `celery inspect ping`; keep broker/Redis highly available.

## Externalized services
- PostgreSQL/PostGIS and Redis are assumed managed (RDS/Cloud SQL, MemoryDB/Elasticache). Provide URLs via secrets; no in-cluster stateful components are required.
- Object storage/CDN for staticfiles should be mounted via bucket sync or baked into the image; `staticfiles` volume is an `emptyDir` placeholder here.
