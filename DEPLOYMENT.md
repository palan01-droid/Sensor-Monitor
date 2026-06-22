# Production Deployment Guide

This guide explains how to deploy SensorMonitor to production.

## Platform: Railway.app

Railway is a modern PaaS (like Heroku) that works great for Flask + PostgreSQL apps.

### Step 1: Create Railway Project

```bash
# Install Railway CLI
brew install railway  # or npm install -g @railway/cli

# Login
railway login

# Create new project
railway init
```

### Step 2: Add PostgreSQL Database

```bash
# Add Postgres service
railway add

# Select "PostgreSQL"
```

### Step 3: Set Environment Variables

In Railway dashboard, go to **Variables** and add:

```
GROQ_API_KEY=gsk_...                           # Your Groq API key
SECRET_KEY=<generate-new-value>               # python -c "import secrets; print(secrets.token_hex(32))"
FLASK_DEBUG=0                                  # MUST be 0 in production
SUPABASE_URL=https://xxx.supabase.co          # Your Supabase project URL
SUPABASE_ANON_KEY=eyJ...                      # Your Supabase anon key
DATABASE_URL=<auto-populated by Railway>      # Postgres connection string
CORS_ALLOWED_ORIGINS=https://yourdomain.com   # Your production domain
DEVICE_API_KEY=<optional-device-key>          # For ESP32/Arduino HTTP ingestion
```

**Important**: 
- `SECRET_KEY` must be unique and strong. Generate it once and reuse.
- `DATABASE_URL` is auto-set by Railway's Postgres plugin — don't override.
- `FLASK_DEBUG=0` is critical — dev mode disables security features.

### Step 4: Deploy

```bash
# Deploy from repo root
railway up

# Or push to GitHub and enable GitHub integration in Railway dashboard
```

### Step 5: Verify

```bash
# View logs
railway logs

# Test health endpoint
curl https://your-app-url.railway.app/health

# Monitor in dashboard
railway logs --follow
```

---

## Environment Variables Reference

### Required

| Variable | Purpose | How to Get |
|----------|---------|-----------|
| `GROQ_API_KEY` | AI chat & analysis | [Groq Console](https://console.groq.com/keys) |
| `SUPABASE_URL` | Auth database | Supabase → Settings → API → Project URL |
| `SUPABASE_ANON_KEY` | Auth public key | Supabase → Settings → API → Anon Key |
| `SECRET_KEY` | Session encryption | `python -c "import secrets; print(secrets.token_hex(32))"` |
| `DATABASE_URL` | Postgres connection | Auto-set by Railway, or your cloud database |

### Optional

| Variable | Default | Purpose |
|----------|---------|---------|
| `FLASK_DEBUG` | `0` | Enable dev mode (NEVER use in production) |
| `CORS_ALLOWED_ORIGINS` | `*` | Comma-separated list of allowed domains |
| `DEVICE_API_KEY` | `` | Required to post to `/api/ingest` |
| `SERIAL_PORT` | `` | Only needed if running on a machine with Arduino |
| `BAUD_RATE` | `115200` | Serial port speed |
| `PORT` | `5000` | Server port (don't override on Railway) |
| `SESSION_COOKIE_SECURE` | `auto` | Force HTTPS-only cookies |

---

## Database Setup

The app uses Flask-SQLAlchemy and auto-creates tables on startup.

### Local Development (SQLite)

```bash
# .env
DATABASE_URL=sqlite:///sensor_monitor.db

# Tables auto-create on startup
python app.py
```

### Production (PostgreSQL)

Railway auto-provides a PostgreSQL database. The `DATABASE_URL` environment variable is pre-set.

**Schema:**
- `sensor_readings` — Timestamped sensor data (JSON payload + flags)
- `alerts` — Timestamped alert events
- `app_settings` — Key-value config store

**Tables auto-create** on first deployment. No manual migration needed.

### Database Connection Details

```python
# From app.py:
_db_url = os.environ.get('DATABASE_URL', 'sqlite:///sensor_monitor.db')
if _db_url.startswith('postgres://'):
    _db_url = _db_url.replace('postgres://', 'postgresql://', 1)
app.config['SQLALCHEMY_DATABASE_URI'] = _db_url
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
    'pool_pre_ping': True,      # Verify connection before use
    'pool_recycle': 300,         # Recycle connections after 5 min
}
```

---

## Monitoring & Logging

### Application Logs

Logs output to stdout in production (Railway captures these):

```bash
railway logs --follow
```

Look for:
- `INFO` — Normal operation
- `ERROR` — Problems that need attention
- `WARNING` — Degraded performance or warnings

### Health Check

```bash
# Verify app is running
curl https://your-app.railway.app/health

# Response if healthy:
# {"status":"ok","timestamp":1234567890.123}

# Response if database down:
# {"status":"error","error":"..."}
```

### WebSocket Connections

The app uses Flask-SocketIO for real-time updates. Monitor these in browser DevTools:

```
Network → Filter by "WS"
```

If WebSockets drop, browser auto-reconnects after 5-30 seconds.

---

## Security Checklist

- [ ] `SECRET_KEY` is a strong, unique 64-character hex string
- [ ] `FLASK_DEBUG=0` (debug mode disabled)
- [ ] `GROQ_API_KEY` is never logged or printed
- [ ] `SUPABASE_ANON_KEY` is restricted to only auth operations in Supabase rules
- [ ] `DATABASE_URL` is PostgreSQL (not SQLite)
- [ ] `CORS_ALLOWED_ORIGINS` is set to your domain, not `*`
- [ ] `SESSION_COOKIE_SECURE=1` in production (auto-enabled when FLASK_DEBUG=0)
- [ ] HTTPS is enforced (Railway does this automatically)
- [ ] Rate limiting is active on `/api/ingest` (120/min per IP)

---

## Troubleshooting

### App Won't Start

```bash
railway logs
# Check for:
# - Missing environment variables
# - Database connection errors
# - Syntax errors in app.py
```

### Health Check Fails

```bash
curl -v https://your-app.railway.app/health
# Status 503 = Database offline
# Status 200 = Healthy
```

### WebSocket Connection Drops

- Browser DevTools → Network → Filter "WS"
- Check if server logs show disconnects
- Verify CORS_ALLOWED_ORIGINS includes your domain

### High Memory Usage

- Check `/api/history` queries for large date ranges
- Verify data pruning is working (logs should show `[pruner]` messages)
- Consider reducing `retention_days` setting

---

## Rollback

If a deployment breaks production:

```bash
# Railway keeps previous versions
railway logs --tail 50

# Redeploy previous version
railway redeploy <previous-deployment-id>
```

---

## Performance Tips

1. **Cache HTTP responses**: Add `Cache-Control` headers for static assets
2. **Database indexing**: The app has indexes on `ts` columns; add more if query slow
3. **Rate limiting**: Default 120/min per IP on `/api/ingest`; adjust if needed
4. **WebSocket tuning**: `ping_interval=25s`, `ping_timeout=60s` — adjust for latency

---

## Next Steps

1. Generate a strong SECRET_KEY
2. Create Railway account and project
3. Connect PostgreSQL
4. Set all required env vars
5. Deploy with `railway up`
6. Test health check and auth flow
7. Monitor logs for 5 minutes after deploy
