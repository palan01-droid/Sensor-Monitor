import os
import json
import math
import random
import time
from flask import Flask, render_template
from flask_socketio import SocketIO, emit

app = Flask(__name__)
app.config['SECRET_KEY'] = os.urandom(24)
socketio = SocketIO(app, cors_allowed_origins='*', async_mode='threading')

SERIAL_PORT = os.environ.get('SERIAL_PORT')
BAUD_RATE = int(os.environ.get('BAUD_RATE', '115200'))
GROQ_API_KEY = os.environ.get('GROQ_API_KEY', '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')
GROQ_COOLDOWN = 30  # seconds between AI calls

groq_client = None
if GROQ_API_KEY:
    from groq import Groq
    groq_client = Groq(api_key=GROQ_API_KEY)

last_flags: set = set()
last_groq_time: float = 0.0
alert_history: list = []  # [{ts, flags}], capped at 50
chat_history: list = []  # [{role, content, ts}], capped at 100
last_sensor_data: dict = {}


def chat_with_groq(user_message: str) -> str | None:
    global chat_history
    if not groq_client:
        return None

    system_prompt = (
        "You are an IoT sensor monitoring assistant. You help users understand "
        "real-time sensor data from multiple sensors. Be concise and helpful. "
        "Current sensor readings: "
    )
    if last_sensor_data:
        system_prompt += (
            f"Temperature: {last_sensor_data.get('temp', 'N/A')}°C, "
            f"Humidity: {last_sensor_data.get('humidity', 'N/A')}%, "
            f"Gas: {last_sensor_data.get('gas', 'N/A')}, "
            f"Distance: {last_sensor_data.get('distance', 'N/A')} cm. "
        )

    try:
        messages = [{"role": "system", "content": system_prompt}]
        for entry in chat_history[-10:]:
            messages.append({"role": entry["role"], "content": entry["content"]})
        messages.append({"role": "user", "content": user_message})

        resp = groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=messages,
            max_tokens=500,
            temperature=0.7,
        )
        return resp.choices[0].message.content.strip()
    except Exception as exc:
        return f"Error: {exc}"


def analyze_with_groq(data: dict, flags: list) -> str | None:
    global last_groq_time
    if not groq_client or not flags:
        return None
    now = time.time()
    if now - last_groq_time < GROQ_COOLDOWN:
        return None
    last_groq_time = now
    prompt = (
        "You are an IoT sensor monitoring AI. Analyze these real-time readings "
        "and active alerts, then give a concise 2–3 sentence assessment with any "
        "recommended actions.\n\n"
        f"Temperature: {data['temp']}°C  |  Humidity: {data['humidity']}%\n"
        f"Gas (MQ-2): {data['gas']}  |  Alcohol (MQ-3): {data['alcohol']}\n"
        f"Light: {data['light']}/1023  |  Distance: {data['distance']} cm\n"
        f"Vibration: {data['vibration']}  |  IR Obstacle: {data['ir_obstacle']}\n"
        f"Accel (g): x={data['accel_x']}, y={data['accel_y']}, z={data['accel_z']}\n"
        f"Gyro (°/s): x={data['gyro_x']}, y={data['gyro_y']}, z={data['gyro_z']}\n"
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


def simulate_data(t: float) -> dict:
    temp = 25.0 + 5.0 * math.sin(t / 60.0) + random.uniform(-0.3, 0.3)
    humidity = 60.0 + 10.0 * math.cos(t / 90.0) + random.uniform(-0.5, 0.5)
    gas = int(200 + 100 * abs(math.sin(t / 45.0)) + random.uniform(-10, 10))
    alcohol = int(150 + 80 * abs(math.cos(t / 50.0)) + random.uniform(-5, 5))
    light = int(max(0, min(1023, 512 + 400 * math.sin(t / 30.0) + random.uniform(-10, 10))))
    distance = max(2.0, 50.0 + 30.0 * abs(math.sin(t / 20.0)) + random.uniform(-1, 1))
    vibration = random.random() > 0.9
    ir_obstacle = random.random() > 0.85
    ax = 0.1 * math.sin(t / 5.0) + random.uniform(-0.02, 0.02)
    ay = 0.1 * math.cos(t / 7.0) + random.uniform(-0.02, 0.02)
    az = 9.8 + random.uniform(-0.05, 0.05)
    gx = 2.0 * math.sin(t / 3.0) + random.uniform(-0.2, 0.2)
    gy = 2.0 * math.cos(t / 4.0) + random.uniform(-0.2, 0.2)
    gz = random.uniform(-0.3, 0.3)

    flags = []
    if temp > 32.0:                       flags.append("HIGH_TEMP")
    if humidity > 75.0:                   flags.append("HIGH_HUMIDITY")
    if gas > 400:                         flags.append("HIGH_GAS")
    if alcohol > 250:                     flags.append("HIGH_ALCOHOL")
    if distance < 10.0:                   flags.append("CLOSE_OBJECT")
    if vibration:                         flags.append("VIBRATION_DETECTED")
    if ir_obstacle:                       flags.append("IR_OBSTACLE")
    if abs(ax) > 1.5 or abs(ay) > 1.5:   flags.append("TILT_DETECTED")

    return {
        "temp": round(temp, 2), "humidity": round(humidity, 2),
        "gas": gas, "alcohol": alcohol, "light": light,
        "distance": round(distance, 2), "vibration": vibration,
        "ir_obstacle": ir_obstacle,
        "accel_x": round(ax, 4), "accel_y": round(ay, 4), "accel_z": round(az, 4),
        "gyro_x": round(gx, 3), "gyro_y": round(gy, 3), "gyro_z": round(gz, 3),
        "flags": flags,
    }


def serial_reader():
    global last_flags, last_sensor_data
    ser = None

    if SERIAL_PORT:
        try:
            import serial as pyserial
            ser = pyserial.Serial(SERIAL_PORT, BAUD_RATE, timeout=2)
            print(f"[serial] Connected to {SERIAL_PORT} @ {BAUD_RATE} baud")
        except Exception as exc:
            print(f"[serial] Could not open port: {exc}. Falling back to simulation.")

    if not ser:
        print("[serial] Running in simulation mode (set SERIAL_PORT to use real hardware)")

    start = time.time()
    while True:
        try:
            if ser:
                raw = ser.readline().decode('utf-8', errors='ignore').strip()
                if not raw:
                    continue
                data = json.loads(raw)
            else:
                data = simulate_data(time.time() - start)
                time.sleep(1)

            flags = set(data.get('flags', []))
            last_sensor_data = data
            payload: dict = {
                'sensor': data,
                'ts': time.time(),
                'simulated': ser is None,
            }

            # Track new alerts and request Groq analysis when alert set changes
            if flags != last_flags and flags:
                entry = {'ts': time.time(), 'flags': sorted(flags)}
                alert_history.append(entry)
                if len(alert_history) > 50:
                    alert_history.pop(0)
                socketio.emit('new_alert', entry)
                analysis = analyze_with_groq(data, list(flags))
                if analysis:
                    payload['groq_analysis'] = analysis
            last_flags = flags

            socketio.emit('sensor_data', payload)

        except (json.JSONDecodeError, UnicodeDecodeError):
            continue
        except Exception as exc:
            print(f"[reader] {exc}")
            time.sleep(1)


@app.route('/')
def index():
    return render_template('index.html')


@socketio.on('connect')
def on_connect():
    emit('config', {
        'groq_available': groq_client is not None,
        'alert_history': alert_history,
        'chat_history': chat_history,
    })


@socketio.on('request_analysis')
def on_request_analysis(data):
    """Client can request an on-demand Groq analysis."""
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
    """Handle chat messages from the client."""
    if not groq_client:
        emit('chat_response', {'error': 'Groq API not configured'})
        return

    user_msg = data.get('message', '').strip()
    if not user_msg:
        return

    user_entry = {'role': 'user', 'content': user_msg, 'ts': time.time()}
    chat_history.append(user_entry)
    if len(chat_history) > 100:
        chat_history.pop(0)

    socketio.emit('chat_message_received', {'message': user_msg, 'ts': user_entry['ts']})

    response = chat_with_groq(user_msg)
    if response:
        assist_entry = {'role': 'assistant', 'content': response, 'ts': time.time()}
        chat_history.append(assist_entry)
        if len(chat_history) > 100:
            chat_history.pop(0)
        socketio.emit('chat_response', {'message': response, 'ts': assist_entry['ts']})
    else:
        socketio.emit('chat_response', {'error': 'No response from AI'})


if __name__ == '__main__':
    socketio.start_background_task(serial_reader)
    port = int(os.environ.get('PORT', 5000))
    print(f"[app] Starting on http://0.0.0.0:{port}")
    socketio.run(app, host='0.0.0.0', port=port, debug=False, allow_unsafe_werkzeug=True)
