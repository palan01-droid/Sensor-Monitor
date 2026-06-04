# Multi-Sensor Monitor

A real-time IoT sensor monitoring dashboard with AI-powered analysis and interactive chat. Monitor temperature, humidity, gas, light, distance, vibration, and IMU data with live charts and Groq AI insights.

## Features

- 🎯 **Real-time Metrics** — Temperature, humidity, gas (MQ-2), alcohol (MQ-3), light, distance
- 📊 **Live Charts** — Streaming data visualization with threshold indicators
- 🤖 **AI Chat** — Ask questions about sensor data; get intelligent analysis from Groq
- 🚨 **Alert System** — Automatic detection and history of anomalies
- 📱 **Responsive UI** — Dark-themed dashboard that works on desktop and mobile
- 🔄 **Simulation Mode** — Test without hardware
- 🛠️ **Real Hardware Support** — Arduino/ESP32 with DHT11, MPU-6050, HC-SR04, and more

## Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure API Key

Copy `.env.example` to `.env` and add your Groq API key:

```bash
cp .env.example .env
# Edit .env and add your GROQ_API_KEY
```

### 3. Run Server

**Simulation mode (no hardware needed):**
```bash
cd python
python app.py
```

**With real Arduino/ESP32 hardware:**
```bash
cd python
SERIAL_PORT=/dev/cu.usbserial-XXXXX python app.py
```

Find your port:
- **macOS**: `ls /dev/cu.usb*`
- **Linux**: `ls /dev/ttyUSB*`
- **Windows**: Check Device Manager for COM ports

### 4. Open Dashboard

Navigate to `http://localhost:5000` in your browser.

---

## Hardware Setup (Optional)

### Arduino/ESP32 Firmware

1. **For Standard Arduino Uno/Nano:**
   - Use pin definitions in `arduino/sensor_monitor.ino`
   - Set `#define SIMULATE 0`

2. **For ESP32/ESP32-CAM:**
   - Pins are pre-configured for ESP32 in the sketch
   - Set `#define SIMULATE 0`

### Sensor Pinout (ESP32)

| Sensor | Pin | Notes |
|--------|-----|-------|
| DHT11 | GPIO 4 | Temperature & humidity |
| MPU-6050 | GPIO 21 (SDA), GPIO 22 (SCL) | I2C accelerometer/gyroscope |
| HC-SR04 TRIG | GPIO 13 | Ultrasonic distance |
| HC-SR04 ECHO | GPIO 12 | Ultrasonic distance |
| MQ-2 (Gas) | GPIO 34 (ADC) | Analog gas sensor |
| MQ-3 (Alcohol) | GPIO 35 (ADC) | Analog alcohol sensor |
| LDR (Light) | GPIO 32 (ADC) | Analog light sensor |
| Vibration | GPIO 14 | Digital vibration switch |
| IR Obstacle | GPIO 15 | Digital IR sensor |

### Required Arduino Libraries

1. DHT sensor library (Adafruit)
2. MPU6050 library (InvenSense)

Install via Arduino IDE → Sketch → Include Library → Manage Libraries

---

## Environment Variables

Create a `.env` file (copy from `.env.example`):

```
GROQ_API_KEY=your_key_here     # Required for AI features
SERIAL_PORT=/dev/ttyUSB0       # Optional, for real hardware
BAUD_RATE=115200               # Optional, default 115200
PORT=5000                       # Optional, default 5000
```

---

## Dashboard Features

### Metric Cards
Live readings with color-coded thresholds:
- **Temperature** (°C) — Alert if > 32°C
- **Humidity** (%) — Alert if > 75%
- **Gas** (ADC) — Alert if > 400
- **Alcohol** (ADC) — Alert if > 250
- **Light** (/1023) — Percentage brightness
- **Distance** (cm) — Alert if < 10 cm

### Charts
Real-time scrolling line charts:
- Temperature & Humidity with threshold overlays
- Gas & Alcohol levels with threshold overlays
- Light level trends
- Distance trends

### Boolean Sensors
- 📳 Vibration detection
- 🔴 IR obstacle detection

### IMU Data
- **Accelerometer** — X, Y, Z axes (g)
- **Gyroscope** — X, Y, Z rotation (°/s)

### Alert History
Timestamped log of all triggered anomalies with clear button.

### AI Chat
Ask natural language questions about your sensor data:
- "Why is temperature spiking?"
- "What should I do about high gas levels?"
- "Is this vibration pattern normal?"

The AI maintains conversation history and provides context-aware insights.

---

## Troubleshooting

### Chat not working?
- Ensure `GROQ_API_KEY` is set in `.env`
- Check browser console for WebSocket errors
- Verify Flask server is running

### Serial connection issues?
- Use correct port: `ls /dev/cu.usb*` (macOS) or check Device Manager (Windows)
- Check baud rate matches your board (default: 115200)
- Verify RX/TX wiring if using real hardware

### No sensor data appearing?
- Confirm simulation mode is enabled (`#define SIMULATE 1`) for testing
- Check browser DevTools → Network → WS for WebSocket connection
- Verify Flask server is outputting `[sensor]` messages

### High latency?
- For cloud deployment, ensure low-latency network
- Consider caching historical data in browser
- Monitor server CPU usage with `top` or `htop`

---

## Deployment

### Local Network
```bash
python app.py  # Accessible at http://[your-ip]:5000
```

### Cloud (Heroku)
```bash
heroku create your-app-name
git push heroku main
heroku config:set GROQ_API_KEY=your_key
```

### Docker (if needed)
```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
CMD ["python", "python/app.py"]
```

---

## Project Structure

```
sensor_monitor/
├── python/
│   ├── app.py              # Flask WebSocket server
│   └── templates/
│       └── index.html      # Web dashboard
├── arduino/
│   └── sensor_monitor.ino  # Arduino/ESP32 firmware
├── requirements.txt        # Python dependencies
├── .env.example            # Environment template
└── README.md              # This file
```

---

## License

MIT — Use freely for personal/educational projects.
