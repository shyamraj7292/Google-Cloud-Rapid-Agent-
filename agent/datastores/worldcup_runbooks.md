# World Cup 2026 — Deployment Runbooks

## Match Day Deployment Protocol

### Pre-Match Checklist (T-4 hours before kickoff)
1. **Freeze Merges**: Set all repos to "Merge Freeze" — no non-critical MRs merged
2. **Pipeline Verification**: Ensure all 3 core services have green pipelines on `main`
3. **Scale Up**: Increase Cloud Run instances for the target venue
   - fan-app: min 5 → min 20 instances
   - ticketing-api: min 3 → min 15 instances
   - stadium-dashboard: min 2 → min 8 instances
4. **Smoke Tests**: Run smoke test suite against staging environment
5. **CDN Cache Warm**: Pre-warm CDN caches for venue-specific static assets
6. **Notify Team**: Post in #worldcup-ops Slack channel: "Match Day Protocol ACTIVE for [Venue]"

### During Match
- **ZERO deployments** — no pipelines should be triggered
- Monitor error rates via dashboard
- If error rate > 1%: Initiate automatic rollback to last known good tag
- If error rate > 5%: Page on-call engineer immediately
- Log all anomalies for post-match review

### Post-Match (T+2 hours after final whistle)
1. Scale down Cloud Run instances to normal levels
2. Unfreeze all merge requests
3. Generate and post match-day incident report
4. Review any queued merge requests
5. Clear CDN cache for time-sensitive content (scores, standings)

---

## Standard Deployment Procedure

### For fan-app (React PWA)
```bash
# Build
npm ci
npm run build
npm run test

# Deploy to Cloud Run
gcloud run deploy worldcup-fan-app \
  --source . \
  --region us-central1 \
  --allow-unauthenticated \
  --min-instances 5 \
  --max-instances 100
```

### For ticketing-api (Python FastAPI)
```bash
# Build & Test
pip install -r requirements.txt
pytest tests/ -v --cov=app --cov-report=term-missing

# Deploy
gcloud run deploy worldcup-ticketing-api \
  --source . \
  --region us-central1 \
  --no-allow-unauthenticated \
  --min-instances 3 \
  --max-instances 50
```

### For stadium-dashboard (Static + JS)
```bash
# Build
npm ci
npm run build
npm run test:e2e

# Deploy
gcloud run deploy worldcup-stadium-dashboard \
  --source . \
  --region us-central1 \
  --no-allow-unauthenticated \
  --min-instances 2 \
  --max-instances 20
```

---

## Rollback Procedure
1. Identify the last known good release tag (e.g., `v1.2.3`)
2. Deploy that specific tag:
   ```bash
   gcloud run deploy [SERVICE] --image gcr.io/[PROJECT]/[SERVICE]:[TAG]
   ```
3. Create an incident issue in GitLab with label `rollback`
4. Notify the team in #worldcup-ops

---

## Environment Matrix

| Environment | URL Pattern | Purpose |
|-------------|------------|---------|
| Development | `dev-*.copa2026.dev` | Feature development |
| Staging | `staging-*.copa2026.dev` | Pre-production testing |
| Production | `*.copa2026.com` | Live fan-facing services |
| Venue-Specific | `[venue].copa2026.com` | Per-venue staging/prod |

---

## Service Dependencies

```
fan-app ──depends on──> ticketing-api
fan-app ──depends on──> stadium-dashboard (iframe embed)
ticketing-api ──depends on──> Firestore (ticket DB)
stadium-dashboard ──depends on──> ticketing-api (capacity data)
```

**Deploy Order**: ticketing-api → stadium-dashboard → fan-app
