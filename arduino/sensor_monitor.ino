// ============================================================
// Multi-Sensor Arduino Monitor
// Set SIMULATE to 1 to run without hardware (no libraries needed)
// Set SIMULATE to 0 for real sensors (requires DHT, MPU6050, Wire libs)
// ============================================================

#define SIMULATE 1

// --- Pin Definitions (ESP32) ---
#define DHT_PIN      4
#define DHT_TYPE     DHT11
#define VIBRATION_PIN 14
#define IR_PIN       15
#define TRIG_PIN     13
#define ECHO_PIN     12
#define MQ2_PIN      34  // ADC1_CH6
#define MQ3_PIN      35  // ADC1_CH7
#define LDR_PIN      32  // ADC1_CH4
// I2C: SDA=21, SCL=22 (default)

#if !SIMULATE
  #include <DHT.h>
  #include <Wire.h>
  #include <MPU6050.h>
  DHT dht(DHT_PIN, DHT_TYPE);
  MPU6050 mpu;
#endif

// --- Anomaly thresholds ---
#define TEMP_HIGH       32.0
#define HUMIDITY_HIGH   75.0
#define GAS_HIGH        400
#define ALCOHOL_HIGH    250
#define DIST_CLOSE      10.0
#define TILT_THRESHOLD  1.5

unsigned long lastMillis = 0;

void setup() {
  Serial.begin(115200);
  randomSeed(analogRead(A5));

#if !SIMULATE
  dht.begin();
  Wire.begin();
  mpu.initialize();
  pinMode(TRIG_PIN, OUTPUT);
  pinMode(ECHO_PIN, INPUT);
  pinMode(VIBRATION_PIN, INPUT);
  pinMode(IR_PIN, INPUT);
#endif
}

// --- Helpers for simulate ---
float frand(float lo, float hi) {
  return lo + (float)random(0, 10000) / 10000.0 * (hi - lo);
}

// --- JSON builder (no external library needed) ---
void printJson(float temp, float humidity, int gas, int alcohol,
               int light, float distance, bool vibration, bool ir_obs,
               float ax, float ay, float az,
               float gx, float gy, float gz,
               String flags) {
  Serial.print(F("{"));
  Serial.print(F("\"temp\":")); Serial.print(temp, 2); Serial.print(F(","));
  Serial.print(F("\"humidity\":")); Serial.print(humidity, 2); Serial.print(F(","));
  Serial.print(F("\"gas\":")); Serial.print(gas); Serial.print(F(","));
  Serial.print(F("\"alcohol\":")); Serial.print(alcohol); Serial.print(F(","));
  Serial.print(F("\"light\":")); Serial.print(light); Serial.print(F(","));
  Serial.print(F("\"distance\":")); Serial.print(distance, 2); Serial.print(F(","));
  Serial.print(F("\"vibration\":")); Serial.print(vibration ? "true" : "false"); Serial.print(F(","));
  Serial.print(F("\"ir_obstacle\":")); Serial.print(ir_obs ? "true" : "false"); Serial.print(F(","));
  Serial.print(F("\"accel_x\":")); Serial.print(ax, 4); Serial.print(F(","));
  Serial.print(F("\"accel_y\":")); Serial.print(ay, 4); Serial.print(F(","));
  Serial.print(F("\"accel_z\":")); Serial.print(az, 4); Serial.print(F(","));
  Serial.print(F("\"gyro_x\":")); Serial.print(gx, 3); Serial.print(F(","));
  Serial.print(F("\"gyro_y\":")); Serial.print(gy, 3); Serial.print(F(","));
  Serial.print(F("\"gyro_z\":")); Serial.print(gz, 3); Serial.print(F(","));
  Serial.print(F("\"flags\":")); Serial.print(flags);
  Serial.println(F("}"));
}

// --- Collect active flag strings into JSON array ---
String buildFlags(float temp, float humidity, int gas, int alcohol,
                  float distance, bool vibration, bool ir_obs,
                  float ax, float ay) {
  String arr = "[";
  bool first = true;
  auto add = [&](const char* s) {
    if (!first) arr += ",";
    arr += "\""; arr += s; arr += "\"";
    first = false;
  };
  if (temp > TEMP_HIGH)       add("HIGH_TEMP");
  if (humidity > HUMIDITY_HIGH) add("HIGH_HUMIDITY");
  if (gas > GAS_HIGH)         add("HIGH_GAS");
  if (alcohol > ALCOHOL_HIGH) add("HIGH_ALCOHOL");
  if (distance < DIST_CLOSE)  add("CLOSE_OBJECT");
  if (vibration)              add("VIBRATION_DETECTED");
  if (ir_obs)                 add("IR_OBSTACLE");
  if (abs(ax) > TILT_THRESHOLD || abs(ay) > TILT_THRESHOLD) add("TILT_DETECTED");
  arr += "]";
  return arr;
}

void loop() {
  if (millis() - lastMillis < 1000) return;
  lastMillis = millis();

#if SIMULATE
  // --- Simulated readings with realistic variation ---
  float t = millis() / 1000.0;
  float temp     = 25.0 + 5.0 * sin(t / 60.0) + frand(-0.3, 0.3);
  float humidity = 60.0 + 10.0 * cos(t / 90.0) + frand(-0.5, 0.5);
  int   gas      = (int)(200 + 100 * abs(sin(t / 45.0)) + frand(-10, 10));
  int   alcohol  = (int)(150 + 80  * abs(cos(t / 50.0)) + frand(-5, 5));
  int   light    = (int)constrain(512 + 400 * sin(t / 30.0) + frand(-10, 10), 0, 1023);
  float distance = max(2.0, 50.0 + 30.0 * abs(sin(t / 20.0)) + frand(-1, 1));
  bool  vibration  = (random(0, 100) > 90);
  bool  ir_obstacle = (random(0, 100) > 85);
  float ax = 0.1 * sin(t / 5.0)  + frand(-0.02, 0.02);
  float ay = 0.1 * cos(t / 7.0)  + frand(-0.02, 0.02);
  float az = 9.8 + frand(-0.05, 0.05);
  float gx = 2.0 * sin(t / 3.0)  + frand(-0.2, 0.2);
  float gy = 2.0 * cos(t / 4.0)  + frand(-0.2, 0.2);
  float gz = frand(-0.3, 0.3);

#else
  // --- Real sensor reads ---
  float temp     = dht.readTemperature();
  float humidity = dht.readHumidity();
  int   gas      = analogRead(MQ2_PIN);
  int   alcohol  = analogRead(MQ3_PIN);
  int   light    = analogRead(LDR_PIN);
  bool  vibration  = digitalRead(VIBRATION_PIN);
  bool  ir_obstacle = !digitalRead(IR_PIN);  // active LOW

  // HC-SR04
  digitalWrite(TRIG_PIN, LOW);
  delayMicroseconds(2);
  digitalWrite(TRIG_PIN, HIGH);
  delayMicroseconds(10);
  digitalWrite(TRIG_PIN, LOW);
  long dur = pulseIn(ECHO_PIN, HIGH, 30000UL);
  float distance = dur * 0.034 / 2.0;

  // MPU-6050
  int16_t ax_r, ay_r, az_r, gx_r, gy_r, gz_r;
  mpu.getMotion6(&ax_r, &ay_r, &az_r, &gx_r, &gy_r, &gz_r);
  float ax = ax_r / 16384.0;
  float ay = ay_r / 16384.0;
  float az = az_r / 16384.0;
  float gx = gx_r / 131.0;
  float gy = gy_r / 131.0;
  float gz = gz_r / 131.0;
#endif

  String flags = buildFlags(temp, humidity, gas, alcohol, distance,
                            vibration, ir_obstacle, ax, ay);
  printJson(temp, humidity, gas, alcohol, light, distance,
            vibration, ir_obstacle, ax, ay, az, gx, gy, gz, flags);
}
