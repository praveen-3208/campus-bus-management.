/**
 * Settings & Hardware Diagnostics JavaScript Logic.
 */

const ESP32_SKETCH_CODE = `/*
 * Automated Bus Entry & Exit Management System
 * Firmware for ESP32 + Dual HC-SR04 Ultrasonic Sensors
 * 
 * Hardware Connections:
 *   Sensor 1 (Outer - Road): TRIG -> GPIO 5,  ECHO -> GPIO 18
 *   Sensor 2 (Inner - Campus): TRIG -> GPIO 19, ECHO -> GPIO 21
 *   Status LED: GPIO 2
 */

#include <WiFi.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>

// Wi-Fi Credentials (replace with your local Wi-Fi)
const char* WIFI_SSID = "YOUR_WIFI_SSID";
const char* WIFI_PASSWORD = "YOUR_WIFI_PASSWORD";

// Flask Server URL (replace with your PC's IP address on local network)
const char* SERVER_URL = "http://192.168.1.50:5000/api/sensor-event";
const char* PING_URL   = "http://192.168.1.50:5000/api/esp32/ping";
const char* DEVICE_ID  = "ESP32-GATE-01";

// Sensor 1 Pins (Outer / Road side)
const int TRIG_PIN_1 = 5;
const int ECHO_PIN_1 = 18;

// Sensor 2 Pins (Inner / Campus side)
const int TRIG_PIN_2 = 19;
const int ECHO_PIN_2 = 21;

// Status LED
const int LED_PIN = 2;

// Detection Parameters
const float DISTANCE_THRESHOLD_CM = 50.0; // Distance below which vehicle is detected
const unsigned long MAX_GAP_MS    = 3500; // Max time allowed between S1 and S2
const unsigned long COOLDOWN_MS   = 6000; // Cooldown to debounce same vehicle

unsigned long lastS1Time = 0;
unsigned long lastS2Time = 0;
unsigned long lastEventTime = 0;
unsigned long lastHeartbeatTime = 0;

float readDistanceCM(int trigPin, int echoPin) {
  digitalWrite(trigPin, LOW);
  delayMicroseconds(2);
  digitalWrite(trigPin, HIGH);
  delayMicroseconds(10);
  digitalWrite(trigPin, LOW);

  long duration = pulseIn(echoPin, HIGH, 30000); // 30ms timeout (~5m)
  if (duration == 0) return 999.0;
  return (duration * 0.0343) / 2.0;
}

void sendHeartbeat() {
  if (WiFi.status() != WL_CONNECTED) return;
  HTTPClient http;
  http.begin(PING_URL);
  http.addHeader("Content-Type", "application/json");

  String payload = "{\\"device_id\\":\\"" + String(DEVICE_ID) + "\\"}";
  int code = http.POST(payload);
  http.end();
}

void sendEventToServer(const char* direction, unsigned long durationMs) {
  if (WiFi.status() != WL_CONNECTED) return;

  HTTPClient http;
  http.begin(SERVER_URL);
  http.addHeader("Content-Type", "application/json");

  StaticJsonDocument<200> doc;
  doc["device_id"] = DEVICE_ID;
  doc["direction"] = direction;
  doc["duration_ms"] = durationMs;

  String jsonPayload;
  serializeJson(doc, jsonPayload);

  digitalWrite(LED_PIN, HIGH);
  int httpResponseCode = http.POST(jsonPayload);
  digitalWrite(LED_PIN, LOW);

  Serial.print("Event sent [");
  Serial.print(direction);
  Serial.print("]. Response code: ");
  Serial.println(httpResponseCode);

  http.end();
}

void setup() {
  Serial.begin(115200);
  pinMode(TRIG_PIN_1, OUTPUT);
  pinMode(ECHO_PIN_1, INPUT);
  pinMode(TRIG_PIN_2, OUTPUT);
  pinMode(ECHO_PIN_2, INPUT);
  pinMode(LED_PIN, OUTPUT);

  Serial.println("Starting Gate Sensor Node...");
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);

  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
    digitalWrite(LED_PIN, !digitalRead(LED_PIN));
  }

  digitalWrite(LED_PIN, HIGH);
  Serial.println("\\nWiFi Connected. IP: " + WiFi.localIP().toString());
  sendHeartbeat();
}

void loop() {
  unsigned long now = millis();

  // Periodic heartbeat every 15 seconds
  if (now - lastHeartbeatTime > 15000) {
    lastHeartbeatTime = now;
    sendHeartbeat();
  }

  // Check debounce cooldown
  if (now - lastEventTime < COOLDOWN_MS) {
    delay(50);
    return;
  }

  // Read both sensors
  float d1 = readDistanceCM(TRIG_PIN_1, ECHO_PIN_1);
  delay(15);
  float d2 = readDistanceCM(TRIG_PIN_2, ECHO_PIN_2);

  // Check Sensor 1 trigger (Outer)
  if (d1 > 0 && d1 <= DISTANCE_THRESHOLD_CM) {
    lastS1Time = now;
    // Check if S2 was triggered within MAX_GAP_MS -> EXIT
    if (lastS2Time > 0 && (now - lastS2Time) <= MAX_GAP_MS) {
      unsigned long delta = now - lastS2Time;
      Serial.println(">>> EXIT DETECTED (S2 -> S1) <<<");
      sendEventToServer("EXIT", delta);
      lastEventTime = now;
      lastS1Time = 0;
      lastS2Time = 0;
    }
  }

  // Check Sensor 2 trigger (Inner)
  if (d2 > 0 && d2 <= DISTANCE_THRESHOLD_CM) {
    lastS2Time = now;
    // Check if S1 was triggered within MAX_GAP_MS -> ENTRY
    if (lastS1Time > 0 && (now - lastS1Time) <= MAX_GAP_MS) {
      unsigned long delta = now - lastS1Time;
      Serial.println(">>> ENTRY DETECTED (S1 -> S2) <<<");
      sendEventToServer("ENTRY", delta);
      lastEventTime = now;
      lastS1Time = 0;
      lastS2Time = 0;
    }
  }

  delay(60);
}`;

async function loadSettings() {
  try {
    const res = await fetch('/api/status');
    const data = await res.json();

    // ESP32 Health
    const isOnline = data.hardware.esp32.status === 'online';
    const pill = document.getElementById('settings-esp32-pill');
    pill.className = `status-pill ${isOnline ? 'online' : 'offline'}`;
    document.getElementById('settings-esp32-status-text').innerText = isOnline ? 'Online' : 'Offline';
    document.getElementById('settings-esp-ip').innerText = data.hardware.esp32.device_ip || 'Not Connected';
    document.getElementById('settings-esp-last-seen').innerText = data.hardware.esp32.last_seen || 'Never';

    // Sensor Calibration form
    const settingsRes = await fetch('/api/settings');
    const settings = await settingsRes.json();

    document.getElementById('setting-threshold-cm').value = settings.distance_threshold_cm || '50';
    document.getElementById('setting-max-gap-ms').value = settings.max_sensor_gap_ms || '3500';
    document.getElementById('setting-cooldown-sec').value = settings.cooldown_seconds || '6';

  } catch (err) {
    console.error('Error loading settings:', err);
  }
}

async function saveCalibrationSettings(e) {
  e.preventDefault();

  const payload = {
    distance_threshold_cm: document.getElementById('setting-threshold-cm').value,
    max_sensor_gap_ms: document.getElementById('setting-max-gap-ms').value,
    cooldown_seconds: document.getElementById('setting-cooldown-sec').value
  };

  try {
    const res = await fetch('/api/settings', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });

    const data = await res.json();
    if (res.ok) {
      showToast('Sensor calibration parameters saved!', 'success');
      loadSettings();
    } else {
      showToast(data.error || 'Failed to save settings', 'error');
    }
  } catch (err) {
    showToast('Error: ' + err.message, 'error');
  }
}

async function sendEsp32SimulatedPing() {
  try {
    const res = await fetch('/api/esp32/ping', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ device_id: 'ESP32-DIAGNOSTIC-PING' })
    });

    const data = await res.json();
    if (res.ok) {
      showToast('ESP32 heartbeat acknowledged by server!', 'success');
      loadSettings();
      updateGlobalStatus();
    }
  } catch (err) {
    showToast('Ping error: ' + err.message, 'error');
  }
}

async function restoreSampleData() {
  if (!confirm('Restore default fleet buses and realistic sample events?')) return;

  try {
    const res = await fetch('/api/settings/seed-sample-data', { method: 'POST' });
    const data = await res.json();
    if (res.ok) {
      showToast(data.message, 'success');
      updateGlobalStatus();
    } else {
      showToast(data.error || 'Failed to seed sample data', 'error');
    }
  } catch (err) {
    showToast('Error: ' + err.message, 'error');
  }
}

function copyFirmwareCode() {
  navigator.clipboard.writeText(ESP32_SKETCH_CODE).then(() => {
    showToast('ESP32 Arduino C++ firmware code copied to clipboard!', 'success');
  }).catch(() => {
    showToast('Please select and copy the code manually', 'warning');
  });
}

document.addEventListener('DOMContentLoaded', () => {
  loadSettings();
  const codeBlock = document.getElementById('firmware-code-block');
  if (codeBlock) {
    codeBlock.innerText = ESP32_SKETCH_CODE;
  }
});
