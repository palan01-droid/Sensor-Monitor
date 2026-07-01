# Sensor Monitor

A real-time IoT sensor dashboard with AI chat. Connect an Arduino or ESP32 and monitor temperature, humidity, gas, light, distance, vibration, and IMU data live — or explore the app in simulation mode without any hardware.

Built with Flask, WebSockets, Supabase auth, and the Groq LLM API.

**[Live Demo →](https://sensor-monitor.onrender.com)**

---

## Features

- **Real-time dashboard** — Live metric cards and scrolling charts over WebSockets
- **AI chat** — Ask questions about your sensor data; powered by Groq (Llama 3.3 70B)
- **Auto-analysis** — AI automatically explains anomalies when alerts fire
- **Alert history** — Timestamped log of every threshold breach
- **Google OAuth** — Secure login via Supabase
- **Simulation mode** — Full demo without any hardware at `/demo`
- **HTTP ingest** — WiFi boards (ESP32) can POST data directly to `/api/ingest`
- **Settings page** — Configurable thresholds, data retention, and baud rate

---

## Stack

| Layer | Tech |
|---|---|
| Backend | Python, Flask, Flask-SocketIO |
| Frontend | Vanilla JS, Chart.js, Socket.IO |
| Auth | Supabase (Google OAuth) |
| AI | Groq API (Llama 3.3 70B) |
| Database | SQLite (dev) / PostgreSQL (prod) |
| Server | Gunicorn + gevent (production) |

---

## Hardware

Designed for Arduino Uno/Nano or ESP32 with:

| Sensor | Measures |
|---|---|
| DHT11 | Temperature & humidity |
| MPU-6050 | Accelerometer & gyroscope (I2C) |
| HC-SR04 | Distance (ultrasonic) |
| MQ-2 | Gas / smoke |
| MQ-3 | Alcohol |
| LDR | Light level |
| Vibration switch | Vibration |
| IR sensor | Obstacle detection |

Firmware is in `arduino/sensor_monitor.ino`. Set `#define SIMULATE 0` for real hardware.

---

## Running Locally

### 1. Install dependencies

```bash
cd python
pip install -r requirements.txt
```

### 2. Configure environment

```bash
cp python/.env.example python/.env
```

Edit `python/.env`:

```
GROQ_API_KEY=...          # Required for AI chat
SUPABASE_URL=...          # Required for login
SUPABASE_ANON_KEY=...     # Required for login
SECRET_KEY=...            # Generate: python -c "import secrets; print(secrets.token_hex(32))"
FLASK_DEBUG=1             # Local dev only
```

Skip `SUPABASE_*` if you just want to run without auth (all routes open in debug mode).

### 3. Run

```bash
cd python
python app.py
```

Open `http://localhost:5000`. No hardware? Go to `/demo` for simulated data.

---

## Project Structure

```
sensor_monitor/
├── arduino/
│   └── sensor_monitor.ino       # ESP32/Arduino firmware
├── python/
│   ├── app.py                   # Flask app, routes, WebSocket handlers
│   ├── auth.py                  # Supabase OAuth blueprint
│   ├── models.py                # SQLAlchemy models (SensorReading, Alert, AppSetting)
│   ├── requirements.txt         # Python dependencies
│   ├── .env.example             # Environment variable template
│   └── templates/
│       ├── landing.html         # Public landing page with login
│       ├── index.html           # Main dashboard (auth required)
│       ├── settings.html        # Settings page
│       ├── login.html           # Login page
│       ├── signup.html          # Signup page
│       └── auth_callback.html   # OAuth callback handler
├── python/tests/
│   ├── conftest.py
│   ├── test_auth.py
│   ├── test_ingest.py
│   ├── test_settings.py
│   ├── test_api_input_validation.py
│   └── test_input_sanitization.py
├── Procfile                     # Gunicorn entry point
├── .env.example                 # Root env template
└── DEPLOYMENT.md                # Deployment guide (Render / Railway)
```

---

## API

| Endpoint | Auth | Description |
|---|---|---|
| `GET /` | Public | Landing page |
| `GET /demo` | Public | Live demo with simulated data |
| `GET /dashboard` | Required | Main dashboard |
| `GET /api/history` | Required | Sensor history (query: `range=1h/24h/7d/30d`) |
| `GET /api/alerts` | Required | Alert history |
| `GET /api/ports` | Required | Available serial ports |
| `POST /api/connect` | Required | Connect to serial port |
| `POST /api/ingest` | API key | HTTP sensor data ingest (for WiFi boards) |
| `POST /api/demo-chat` | Public | AI chat for demo mode |
| `GET /settings` | Required | Settings page |
| `POST /api/settings` | Required | Update settings |
| `GET /health` | Public | Health check |

WebSocket events: `sensor_data`, `new_alert`, `port_status`, `chat_message`, `chat_response`, `groq_analysis`

---

## Tests

```bash
cd python
pytest tests/
```

23 tests covering auth, ingest, settings, input validation, and sanitization.

---

## Deployment

See [DEPLOYMENT.md](DEPLOYMENT.md) for a full guide. Short version for Render:

1. Create a new Web Service from this repo
2. Set build command: `pip install -r python/requirements.txt`
3. Set start command: `cd python && gunicorn --worker-class geventwebsocket.gunicorn.workers.GeventWebSocketWorker --bind 0.0.0.0:$PORT app:app`
4. Add environment variables: `GROQ_API_KEY`, `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SECRET_KEY`, `DEVICE_API_KEY`, `FLASK_DEBUG=0`
5. Add a PostgreSQL database and set `DATABASE_URL`
