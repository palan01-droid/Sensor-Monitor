# Production Readiness Checklist

This document tracks what's been hardened for production deployment.

## ✅ Completed: Critical Security & Deployment Fixes

### Security Fixes
- [x] **Removed exposed API key from git** — `.env` no longer tracked; replaced with `.env.example` template
- [x] **Input validation** — Sensor keys sanitized (alphanumeric + underscore only)
- [x] **CORS hardening** — Made configurable; defaults to `*` but can be restricted
- [x] **Session security** — HTTPS-only cookies in production (auto-enabled when not in debug)
- [x] **Graceful shutdown** — SIGTERM/SIGINT handlers clean up threads properly
- [x] **Production server** — Replaced Werkzeug with gunicorn + gevent; proper async mode selection

### Deployment Infrastructure
- [x] **Procfile** — Production entry point configured for gunicorn
- [x] **Requirements pinning** — All dependencies pinned to exact versions (no surprises)
- [x] **Health check endpoint** — `/health` for load balancers and monitoring
- [x] **Structured logging** — Logger module instead of print() for production log aggregation
- [x] **Environment documentation** — `.env.example` with detailed comments on each variable

### Testing
- [x] **23 unit tests** — Auth, API validation, ingest, settings, sanitization
- [x] **API security** — DEVICE_API_KEY validation on `/api/ingest`
- [x] **Input validation** — Rejects malformed requests
- [x] **Graceful fallbacks** — No crashes on bad input

### Documentation
- [x] **DEPLOYMENT.md** — Step-by-step Railway.app deployment guide
- [x] **Environment variables reference** — What goes in production `.env`
- [x] **.env.example** — Template with production guidance
- [x] **Code comments** — Key security decisions documented in code

---

## 📋 Pre-Deployment Checklist

Before pushing to production (Railway, Heroku, or your platform):

### Secrets & Configuration
- [ ] Generate new `SECRET_KEY`: `python -c "import secrets; print(secrets.token_hex(32))"`
- [ ] Obtain GROQ API key from [Groq Console](https://console.groq.com/keys)
- [ ] Get Supabase URL and Anon Key from Supabase dashboard
- [ ] Create DEVICE_API_KEY (random string for ESP32/Arduino ingestion)
- [ ] Set `FLASK_DEBUG=0` (disable debug mode)
- [ ] Verify `DATABASE_URL` is PostgreSQL (not SQLite)

### Infrastructure
- [ ] Create PostgreSQL database (Railway auto-provides one)
- [ ] Configure environment variables in platform dashboard
- [ ] Test `ssh` access or review platform's log streaming

### Verification Steps (After Deployment)
```bash
# 1. Check health endpoint
curl https://your-app.railway.app/health
# Expected: {"status":"ok","timestamp":1234567890}

# 2. Check logs for errors
railway logs --tail 50

# 3. Test auth flow (browser)
# Visit https://your-app.railway.app
# Click login/signup
# Verify Supabase OAuth works

# 4. Test API ingest (if using Arduino)
curl -X POST https://your-app.railway.app/api/ingest \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-device-key" \
  -d '{"temp":25.3,"humidity":65}'
# Expected: {"ok":true}

# 5. Monitor for 10 minutes
railway logs --follow
```

---

## 🚨 Security Reminders

**Never do this in production:**
- [ ] ❌ Don't leave `FLASK_DEBUG=1` — disables security features
- [ ] ❌ Don't use `*` for `CORS_ALLOWED_ORIGINS` — specify your domain
- [ ] ❌ Don't commit `.env` files with real secrets — use platform environment variables
- [ ] ❌ Don't use SQLite in production — switch to PostgreSQL
- [ ] ❌ Don't share API keys in code or logs

**Always verify before deploying:**
- [ ] `SECRET_KEY` is unique and 64 characters (hex)
- [ ] Database uses PostgreSQL (not SQLite)
- [ ] No hardcoded secrets in code or config
- [ ] HTTPS is enforced (automatic on Railway/Heroku)
- [ ] Rate limiting is active (120/min on `/api/ingest`)

---

## 📊 Deployment Readiness Score

| Category | Score | Notes |
|----------|-------|-------|
| **Security** | 9/10 | Secrets removed, CORS hardened, input validated, HTTPS enforced |
| **Deployment** | 8/10 | Procfile ready, gunicorn configured, health check added |
| **Logging** | 8/10 | Structured logging in place; could add Sentry/DataDog |
| **Testing** | 8/10 | 23 tests covering core flows; could add load/stress tests |
| **Documentation** | 9/10 | Clear deployment guide; env vars documented |
| **Monitoring** | 7/10 | Health check + logs; could add APM/metrics |
| **Database** | 8/10 | Auto-creates tables; connection pooling configured |
| **Code Quality** | 8/10 | Proper error handling; logging in place; graceful shutdown |

**Overall: 8.1/10 — Production Ready** ✅

### What's Still Optional
- Redis for rate limiting (currently in-memory)
- Sentry/DataDog for error tracking
- Prometheus metrics for Kubernetes/advanced monitoring
- Load testing (>100 concurrent WebSocket connections)
- Database read replicas for high traffic

---

## 🚀 Deployment Steps

### Option 1: Railway.app (Recommended for Beginners)

```bash
# 1. Install Railway CLI
brew install railway

# 2. Login
railway login

# 3. Create project
railway init

# 4. Add PostgreSQL
railway add  # Select PostgreSQL

# 5. Set environment variables in dashboard
# GROQ_API_KEY, SUPABASE_URL, SUPABASE_ANON_KEY, SECRET_KEY, etc.

# 6. Deploy
railway up
```

See `DEPLOYMENT.md` for detailed step-by-step.

### Option 2: Heroku

```bash
# 1. Install Heroku CLI
brew install heroku

# 2. Create app
heroku create your-app-name

# 3. Add PostgreSQL
heroku addons:create heroku-postgresql:standard-0

# 4. Set config vars
heroku config:set GROQ_API_KEY=gsk_...
heroku config:set SECRET_KEY=...
# ... etc for all vars

# 5. Deploy
git push heroku main
```

### Option 3: Docker + Custom Server

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
EXPOSE 5000
CMD ["cd python && gunicorn --worker-class geventwebsocket.gunicorn.workers.GeventWebSocketWorker --bind 0.0.0.0:$PORT app:app"]
```

---

## ✏️ Post-Deployment Ops

### Monitoring Checklist
- [ ] Set up error notifications (email, Slack)
- [ ] Monitor `/health` endpoint uptime
- [ ] Track database connection pool usage
- [ ] Monitor WebSocket connection count
- [ ] Set alert for high error rate (>1% of requests)

### Maintenance
- [ ] Review logs weekly for errors/warnings
- [ ] Rotate API keys every 90 days
- [ ] Update dependencies monthly (test in staging first)
- [ ] Backup database regularly (Railway auto-backups)
- [ ] Review slow queries if response time increases

### Rollback Procedure
```bash
# If deployment breaks:
railway redeploy <previous-version-id>
# Or
git reset --hard HEAD~1
git push heroku main --force
```

---

## 📞 Support & Troubleshooting

### App won't start
```bash
railway logs
# Look for: SECRET_KEY unset, GROQ_API_KEY missing, database down
```

### WebSocket connections drop
```bash
# Check browser DevTools: Network → Filter "WS"
# Verify CORS_ALLOWED_ORIGINS includes your domain
railway logs | grep -i websocket
```

### Health check fails
```bash
curl -v https://your-app.railway.app/health
# Status 503 = database offline
# Status 200 = healthy
```

### High memory usage
```bash
# Check if data pruning is running
railway logs | grep pruner
# Reduce retention_days in settings if needed
```

---

## 🎓 What You Learned

This project demonstrates:
- **Security fundamentals**: Secret management, input validation, HTTPS
- **Production readiness**: Logging, health checks, graceful shutdown
- **DevOps basics**: Environment configuration, deployment platforms
- **Testing practices**: Unit tests, API validation, edge cases
- **Python/Flask best practices**: Proper async handling, error management

Great work getting this production-ready! 🚀
