import os
import json
import threading
import logging
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), '.env'))
import time
from datetime import timedelta
from flask import Flask, render_template, jsonify, request, session
from flask_socketio import SocketIO, emit
from flask_wtf.csrf import CSRFProtect
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from models import db, SensorReading, Alert, AppSetting
from auth import auth_bp, login_required, SUPABASE_URL

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

_DEFAULT_SECRET = 'dev-secret-change-in-prod'
_secret_key = os.environ.get('SECRET_KEY', _DEFAULT_SECRET)
_is_debug = os.environ.get('FLASK_DEBUG', '').lower() in ('1', 'true')
if _secret_key == _DEFAULT_SECRET and not _is_debug:
    raise RuntimeError(
        'SECRET_KEY is unset and FLASK_DEBUG is not enabled. '
        'Set a real SECRET_KEY (e.g. via `python -c "import secrets; print(secrets.token_hex(32))"`) '
        'before running outside local development.'
    )
app.config['SECRET_KEY'] = _secret_key
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=30)
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['SESSION_COOKIE_SECURE'] = os.environ.get(
    'SESSION_COOKIE_SECURE', str(not _is_debug)
).lower() in ('1', 'true')
app.config['SESSION_COOKIE_HTTPONLY'] = True

_db_url = os.environ.get('DATABASE_URL', 'sqlite:///sensor_monitor.db')
if _db_url.startswith('postgres://'):
    _db_url = _db_url.replace('postgres://', 'postgresql://', 1)
app.config['SQLALCHEMY_DATABASE_URI'] = _db_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {'pool_pre_ping': True, 'pool_recycle': 300}

db.init_app(app)
app.register_blueprint(auth_bp)

# Production-safe CORS: specify allowed origins explicitly
_cors_origins = os.environ.get('CORS_ALLOWED_ORIGINS', 'http://localhost:5001').split(',')
# Use threading for local dev (no extra dependencies), gevent for production (via gunicorn)
_async_mode = 'threading' if _is_debug else 'gevent'
socketio = SocketIO(
    app,
    cors_allowed_origins=_cors_origins,
    async_mode=_async_mode,
    ping_timeout=60,
    ping_interval=25,
)

csrf = CSRFProtect(app)
limiter = Limiter(get_remote_address, app=app, storage_uri='memory://')

SERIAL_PORT = os.environ.get('SERIAL_PORT')
BAUD_RATE = int(os.environ.get('BAUD_RATE', '115200'))
GROQ_API_KEY = os.environ.get('GROQ_API_KEY', '')
GROQ_COOLDOWN = 30
DB_WRITE_INTERVAL = float(os.environ.get('DB_WRITE_INTERVAL', '5'))

groq_client = None
if GROQ_API_KEY:
    from groq import Groq
    groq_client = Groq(api_key=GROQ_API_KEY)

state_lock = threading.Lock()  # guards globals below, touched from serial/Socket.IO/request threads

last_flags: set = set()
last_groq_time: float = 0.0
last_db_write: float = 0.0
alert_history: list = []
chat_history: list = []
last_sensor_data: dict = {}
chat_last_sent: dict = {}  # socket sid -> last chat_message timestamp
CHAT_MIN_INTERVAL = 2.0  # seconds between chat messages per connection

serial_stop_event: threading.Event = threading.Event()
serial_thread: threading.Thread | None = None
connected_port: str | None = None

SETTINGS_DEFAULTS = {
    'default_baud': 115200,
    'db_write_interval': 5,     # seconds between DB writes
    'retention_days': 30,       # days of sensor history to keep
    'auto_analysis': True,      # run analysis automatically when alerts fire
}
settings_cache: dict = dict(SETTINGS_DEFAULTS)


def load_settings():
    for row in AppSetting.query.all():
        if row.key in SETTINGS_DEFAULTS:
            settings_cache[row.key] = row.value


def save_setting(key: str, value):
    settings_cache[key] = value
    row = db.session.get(AppSetting, key)
    if row:
        row.value = value
    else:
        db.session.add(AppSetting(key=key, value=value))
    db.session.commit()


def chat_with_groq(user_message: str) -> str | None:
    if not groq_client:
        return None

    with state_lock:
        sensor_snapshot = dict(last_sensor_data)
        recent_history = list(chat_history[-10:])

    sensor_lines = ''
    active_flags = []
    if sensor_snapshot:
        for key, value in sensor_snapshot.items():
            if key == 'flags':
                active_flags = value or []
            elif key != 'simulated':
                sensor_lines += f"  {key.replace('_', ' ').title()}: {value}\n"

    alert_ctx = f"Currently alerting: {', '.join(active_flags)}." if active_flags else ""

    system_prompt = f"""You are a helpful, conversational AI assistant embedded in a real-time IoT sensor dashboard called SensorMonitor. You have two sides to you:

1. You're a great general-purpose assistant — friendly, natural, and engaging, just like ChatGPT or Claude. You can chat about anything, help with code, explain concepts, answer questions, have a real conversation.

2. You also have live access to the user's sensor data right now, so when they ask about their hardware, sensors, readings, or alerts you can give specific, insightful answers grounded in real data.

Keep responses natural and conversational. Don't be robotic or overly formal. Match the energy of the message — short question gets a short answer, deeper question gets a real answer. Use markdown naturally (bold for important values, bullets when it actually helps readability).

{"Here's what the sensors are reading right now:" if sensor_lines else "No sensor data yet — the board isn't connected."}
{sensor_lines}{alert_ctx}"""

    try:
        messages = [{"role": "system", "content": system_prompt}]
        for entry in recent_history:
            messages.append({"role": entry["role"], "content": entry["content"]})
        messages.append({"role": "user", "content": user_message})

        resp = groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=messages,
            max_tokens=600,
            temperature=0.75,
        )
        return resp.choices[0].message.content.strip()
    except Exception as exc:
        return f"Error: {exc}"


def analyze_with_groq(data: dict, flags: list) -> str | None:
    global last_groq_time
    if not groq_client or not flags:
        return None
    now = time.time()
    with state_lock:
        if now - last_groq_time < GROQ_COOLDOWN:
            return None
        last_groq_time = now

    sensor_lines = '\n'.join(
        f"  {k.replace('_', ' ').title()}: {v}"
        for k, v in data.items()
        if k not in ('flags', 'simulated')
    )
    prompt = (
        "Analyze these sensor readings and format as:\n"
        "**ALERTS**: List active alerts\n"
        "**STATUS**: 1-2 word severity (Normal/Warning/Critical)\n"
        "**ACTION**: What to do (if anything)\n"
        "Keep it short and actionable.\n\n"
        f"Sensor readings:\n{sensor_lines}\n"
        f"Active alerts: {', '.join(flags)}"
    )
    try:
        resp = groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=220,
            temperature=0.3,
        )
        return resp.choices[0].message.content.strip()
    except Exception as exc:
        return f"Analysis unavailable: {exc}"


def save_reading(data: dict, flags: set) -> None:
    global last_db_write
    now = time.time()
    with state_lock:
        if now - last_db_write < float(settings_cache['db_write_interval']):
            return
        last_db_write = now
    try:
        sensor_data = {k: v for k, v in data.items() if k not in ('flags', 'simulated')}
        reading = SensorReading(ts=now, data=sensor_data, flags=sorted(flags))
        db.session.add(reading)
        db.session.commit()
    except Exception as exc:
        db.session.rollback()
        logger.error(f"save_reading failed: {exc}")


def save_alert(ts: float, flags: list) -> None:
    try:
        db.session.add(Alert(ts=ts, flags=flags))
        db.session.commit()
    except Exception as exc:
        db.session.rollback()
        logger.error(f"save_alert failed: {exc}")


def sanitize_sensor_keys(data: dict) -> dict:
    """Sanitize sensor data keys to prevent injection; allow alphanumeric + underscore"""
    import re
    safe_data = {}
    key_pattern = re.compile(r'^[a-zA-Z0-9_]+$')
    for key, value in data.items():
        if key_pattern.match(key):
            safe_data[key] = value
        else:
            logger.warning(f"Rejecting unsafe sensor key: {key}")
    return safe_data


def process_sensor_data(data: dict) -> None:
    global last_flags, last_sensor_data
    data = sanitize_sensor_keys(data)  # Validate keys before processing
    flags = set(data.get('flags', []))
    with state_lock:
        last_sensor_data = data
    payload: dict = {'sensor': data, 'ts': time.time()}

    save_reading(data, flags)

    with state_lock:
        flags_changed = flags != last_flags and bool(flags)
        if flags_changed:
            entry = {'ts': time.time(), 'flags': sorted(flags)}
            alert_history.append(entry)
            if len(alert_history) > 50:
                alert_history.pop(0)
        last_flags = flags

    if flags_changed:
        save_alert(entry['ts'], entry['flags'])
        socketio.emit('new_alert', entry)
        if settings_cache['auto_analysis']:
            analysis = analyze_with_groq(data, list(flags))
            if analysis:
                payload['groq_analysis'] = analysis

    socketio.emit('sensor_data', payload)


def serial_reader(port: str, baud: int, stop_event: threading.Event):
    global connected_port

    try:
        import serial as pyserial
        ser = pyserial.Serial(port, baud, timeout=2)
        logger.info(f"Connected to serial port {port} @ {baud} baud")
        connected_port = port
        socketio.emit('port_status', {'connected': True, 'port': port})
    except Exception as exc:
        logger.error(f"Could not open serial port {port}: {exc}")
        socketio.emit('port_status', {'connected': False, 'error': str(exc)})
        return

    with app.app_context():
        while not stop_event.is_set():
            try:
                raw = ser.readline().decode('utf-8', errors='ignore').strip()
                if not raw:
                    continue
                raw = raw.replace(':nan', ':null').replace(':NaN', ':null')
                process_sensor_data(json.loads(raw))

            except (json.JSONDecodeError, UnicodeDecodeError):
                continue
            except Exception as exc:
                logger.error(f"serial_reader error: {exc}")
                db.session.rollback()
                time.sleep(1)

    try:
        ser.close()
    except Exception:
        pass
    connected_port = None
    socketio.emit('port_status', {'connected': False})
    logger.info(f"Disconnected from serial port {port}")


def start_serial_connection(port: str, baud: int):
    global serial_thread, serial_stop_event
    if serial_thread and serial_thread.is_alive():
        if connected_port == port:
            return  # already connected to this port, nothing to do
        serial_stop_event.set()
        serial_thread.join(timeout=3)
        time.sleep(0.5)  # give OS time to release the port
    serial_stop_event = threading.Event()
    serial_thread = threading.Thread(
        target=serial_reader,
        args=(port, baud, serial_stop_event),
        daemon=True,
    )
    serial_thread.start()


def pruner():
    while True:
        time.sleep(86400)
        with app.app_context():
            days = int(settings_cache['retention_days'])
            cutoff = time.time() - (days * 86400)
            try:
                SensorReading.query.filter(SensorReading.ts < cutoff).delete()
                Alert.query.filter(Alert.ts < cutoff).delete()
                db.session.commit()
                logger.info(f"Pruned data older than {days} days")
            except Exception as exc:
                db.session.rollback()
                logger.error(f"Pruner failed: {exc}")


@app.route('/health')
def health():
    """Health check endpoint for load balancers and monitoring"""
    try:
        # Verify database connection
        db.session.execute(db.text('SELECT 1'))
        return jsonify({'status': 'ok', 'timestamp': time.time()}), 200
    except Exception as exc:
        return jsonify({'status': 'error', 'error': str(exc)}), 503


@app.route('/')
def landing():
    return render_template('landing.html',
                           supabase_url=os.environ.get('SUPABASE_URL', ''),
                           supabase_anon_key=os.environ.get('SUPABASE_ANON_KEY', ''))


@app.route('/demo')
def demo():
    return render_template('index.html', demo=True, user_email='')


@app.route('/dashboard')
@login_required
def index():
    return render_template('index.html',
                           user_email=session.get('user_email', ''))



@app.route('/auth/me')
def auth_me():
    if 'user_email' in session:
        return jsonify({'email': session['user_email']})
    return jsonify({})


@app.route('/api/history')
@login_required
def api_history():
    range_map = {'1h': 3600, '24h': 86400, '7d': 604800, '30d': 2592000}
    seconds = range_map.get(request.args.get('range', '24h'), 86400)
    since = time.time() - seconds
    readings = (
        SensorReading.query
        .filter(SensorReading.ts >= since)
        .order_by(SensorReading.ts.asc())
        .all()
    )
    return jsonify([r.to_dict() for r in readings])


@app.route('/api/alerts')
@login_required
def api_alerts():
    try:
        limit = min(int(request.args.get('limit', 50)), 200)
    except ValueError:
        return jsonify({'error': 'limit must be an integer'}), 400
    alerts = (
        Alert.query
        .order_by(Alert.ts.desc())
        .limit(limit)
        .all()
    )
    return jsonify([a.to_dict() for a in reversed(alerts)])


@app.route('/api/ports')
@login_required
def api_ports():
    try:
        import serial.tools.list_ports
        ports = [
            {'port': p.device, 'description': p.description or p.device}
            for p in serial.tools.list_ports.comports()
        ]
        return jsonify({'ports': ports, 'connected': connected_port})
    except Exception as exc:
        return jsonify({'ports': [], 'error': str(exc), 'connected': connected_port})


@app.route('/api/connect', methods=['POST'])
@login_required
def api_connect():
    data = request.get_json() or {}
    port = data.get('port', '').strip()
    if not port:
        return jsonify({'error': 'No port specified'}), 400
    try:
        baud = int(data.get('baud', settings_cache['default_baud']))
    except (TypeError, ValueError):
        return jsonify({'error': 'baud must be an integer'}), 400
    start_serial_connection(port, baud)
    return jsonify({'ok': True, 'port': port})


@app.route('/api/disconnect', methods=['POST'])
@login_required
def api_disconnect():
    serial_stop_event.set()
    return jsonify({'ok': True})


@app.route('/api/ingest', methods=['POST'])
@csrf.exempt
@limiter.limit('120 per minute')
def api_ingest():
    # WiFi boards can't hold a login session or a CSRF token — protect with an API key instead.
    api_key = os.environ.get('DEVICE_API_KEY', '')
    if api_key and request.headers.get('X-API-Key') != api_key:
        return jsonify({'error': 'Invalid or missing X-API-Key header'}), 401

    data = request.get_json(silent=True)
    if not isinstance(data, dict) or not data:
        return jsonify({'error': 'Send a JSON object of sensor values, e.g. {"temp": 25.3}'}), 400

    process_sensor_data(data)
    return jsonify({'ok': True})


@app.route('/settings')
@login_required
def settings_page():
    return render_template('settings.html',
                           user_email=session.get('user_email', ''))


@app.route('/api/settings', methods=['GET', 'POST'])
@login_required
def api_settings():
    if request.method == 'GET':
        return jsonify(settings_cache)

    data = request.get_json() or {}
    errors = []
    validators = {
        'default_baud':      lambda v: int(v) in (9600, 19200, 38400, 57600, 115200, 230400, 250000),
        'db_write_interval': lambda v: 1 <= float(v) <= 3600,
        'retention_days':    lambda v: 1 <= int(v) <= 365,
        'auto_analysis':     lambda v: isinstance(v, bool),
    }
    for key, value in data.items():
        if key not in SETTINGS_DEFAULTS:
            continue
        try:
            if not validators[key](value):
                errors.append(f'{key}: invalid value')
                continue
        except (TypeError, ValueError):
            errors.append(f'{key}: invalid value')
            continue
        save_setting(key, value)
    if errors:
        return jsonify({'ok': False, 'errors': errors}), 400
    return jsonify({'ok': True, 'settings': settings_cache})


@app.route('/api/clear-data', methods=['POST'])
@login_required
def api_clear_data():
    global alert_history, chat_history
    target = (request.get_json() or {}).get('target', '')
    try:
        if target == 'readings':
            SensorReading.query.delete()
            db.session.commit()
        elif target == 'alerts':
            Alert.query.delete()
            db.session.commit()
            alert_history = []
        elif target == 'chat':
            chat_history = []
        else:
            return jsonify({'error': 'Unknown target'}), 400
        return jsonify({'ok': True})
    except Exception as exc:
        db.session.rollback()
        return jsonify({'error': str(exc)}), 500


@socketio.on('connect')
def on_connect():
    if SUPABASE_URL and 'user_id' not in session:
        return False  # reject unauthenticated WebSocket connections
    db_alerts = Alert.query.order_by(Alert.ts.desc()).limit(50).all()
    emit('config', {
        'groq_available': groq_client is not None,
        'alert_history': [a.to_dict() for a in reversed(db_alerts)],
        'chat_history': chat_history,
        'connected_port': connected_port,
        'default_baud': settings_cache['default_baud'],
    })


@socketio.on('disconnect')
def on_disconnect():
    with state_lock:
        chat_last_sent.pop(request.sid, None)


@socketio.on('request_analysis')
def on_request_analysis(data):
    if not groq_client:
        emit('groq_analysis', {'text': 'Groq API not configured — set GROQ_API_KEY to enable.'})
        return
    if data:
        analysis = analyze_with_groq(data, data.get('flags', []))
        if analysis:
            emit('groq_analysis', {'text': analysis})
        else:
            emit('groq_analysis', {'text': 'Rate limit active — please wait 30 s between analyses.'})


@socketio.on('chat_message')
def on_chat_message(data):
    if not groq_client:
        emit('chat_response', {'error': 'Groq API not configured'})
        return

    user_msg = data.get('message', '').strip()[:2000]
    if not user_msg:
        return

    sid = request.sid
    now = time.time()
    with state_lock:
        if now - chat_last_sent.get(sid, 0) < CHAT_MIN_INTERVAL:
            emit('chat_response', {'error': 'Slow down — please wait a moment between messages.'})
            return
        chat_last_sent[sid] = now

    user_entry = {'role': 'user', 'content': user_msg, 'ts': time.time()}
    with state_lock:
        chat_history.append(user_entry)
        if len(chat_history) > 100:
            chat_history.pop(0)

    socketio.emit('chat_message_received', {'message': user_msg, 'ts': user_entry['ts']})

    response = chat_with_groq(user_msg)
    if response:
        assist_entry = {'role': 'assistant', 'content': response, 'ts': time.time()}
        with state_lock:
            chat_history.append(assist_entry)
            if len(chat_history) > 100:
                chat_history.pop(0)
        socketio.emit('chat_response', {'message': response, 'ts': assist_entry['ts']})
    else:
        socketio.emit('chat_response', {'error': 'No response from AI'})


def _shutdown_handler(signum, frame):
    """Graceful shutdown: stop serial thread and close DB"""
    logger.info(f"Shutdown signal {signum} received, cleaning up...")
    global serial_stop_event
    serial_stop_event.set()
    if serial_thread and serial_thread.is_alive():
        serial_thread.join(timeout=2)
    db.session.close()
    logger.info("Cleanup complete, exiting")
    exit(0)


def _init_app():
    """Initialize app context and background tasks"""
    import signal
    signal.signal(signal.SIGTERM, _shutdown_handler)
    signal.signal(signal.SIGINT, _shutdown_handler)

    with app.app_context():
        db.create_all()
        load_settings()
        logger.info("Database tables ready")
    if SERIAL_PORT:
        start_serial_connection(SERIAL_PORT, BAUD_RATE)
    socketio.start_background_task(pruner)
    logger.info("Background tasks started (pruner, serial reader if configured)")


if __name__ == '__main__':
    _init_app()
    port = int(os.environ.get('PORT', 5000))
    if _is_debug:
        # Local development: use Werkzeug dev server
        logger.info(f"Starting in DEBUG mode on http://0.0.0.0:{port}")
        socketio.run(app, host='0.0.0.0', port=port, debug=True, allow_unsafe_werkzeug=True)
    else:
        # Production: app is run by gunicorn, not socketio.run()
        logger.info("Starting in PRODUCTION mode (use gunicorn)")
        logger.warning("If running locally without gunicorn, set FLASK_DEBUG=1")
