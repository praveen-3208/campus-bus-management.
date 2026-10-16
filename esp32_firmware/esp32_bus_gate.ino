/*
 * =====================================================================================
 * Automated Bus Entry & Exit Management System - ESP32 Firmware
 * Hardware Prototype: ESP32 + Dual HC-SR04 Ultrasonic Sensors + Wi-Fi HTTP Client
 * =====================================================================================
 * 
 * Hardware Connections:
 *   Sensor 1 (Outer Gate - Facing Road / Exterior):
 *     - VCC  -> ESP32 VIN (5V)
 *     - GND  -> ESP32 GND
 *     - TRIG -> ESP32 GPIO 5
 *     - ECHO -> ESP32 GPIO 18 (use voltage divider or 1k resistor if desired for 5V -> 3.3V)
 *
 *   Sensor 2 (Inner Gate - Facing Campus / Interior):
 *     - VCC  -> ESP32 VIN (5V)
 *     - GND  -> ESP32 GND
 *     - TRIG -> ESP32 GPIO 19
 *     - ECHO -> ESP32 GPIO 21
 *
 *   Indicator LED:
 *     - Built-in LED on GPIO 2
 *
 * Direction Inference Logic:
 *   - S1 interrupted first, then S2 interrupted within MAX_GAP_MS => ENTRY
 *   - S2 interrupted first, then S1 interrupted within MAX_GAP_MS => EXIT
 *   - Debounce window: COOLDOWN_MS prevents re-triggering for the same long vehicle body.
 * =====================================================================================
 */

#include <WiFi.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>

// 1. Wi-Fi Configuration (Replace with your local Wi-Fi SSID and password)
const char* WIFI_SSID     = "YOUR_WIFI_SSID";
const char* WIFI_PASSWORD = "YOUR_WIFI_PASSWORD";

// 2. Flask Server Configuration (Replace with your laptop/PC IP on the local Wi-Fi)
const char* SERVER_URL = "http://10.182.220.40:5000/api/sensor-event";
const char* PING_URL   = "http://10.182.220.40:5000/api/esp32/ping";
const char* DEVICE_ID  = "ESP32-GATE-01";

// 3. Pin Definitions
const int TRIG_PIN_1 = 5;
const int ECHO_PIN_1 = 18;
const int TRIG_PIN_2 = 19;
const int ECHO_PIN_2 = 21;
const int LED_PIN    = 2;

// 4. Calibration Parameters
const float DISTANCE_THRESHOLD_CM = 50.0; // Distance below which vehicle is detected
const unsigned long MAX_GAP_MS    = 3500; // Max time between S1 and S2 triggers
const unsigned long COOLDOWN_MS   = 6000; // Debounce cooldown for long bus body

// State Variables
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

  // Read echo pulse with 30ms timeout (~5 meters max)
  long duration = pulseIn(echoPin, HIGH, 30000);
  if (duration == 0) {
    return 999.0; // No obstacle / timeout
  }
  // Speed of sound = 343 m/s = 0.0343 cm/us (divide by 2 for round-trip)
  return (duration * 0.0343) / 2.0;
}

void sendHeartbeat() {
  if (WiFi.status() != WL_CONNECTED) return;

  HTTPClient http;
  http.begin(PING_URL);
  http.addHeader("Content-Type", "application/json");

  String payload = "{\"device_id\":\"" + String(DEVICE_ID) + "\"}";
  int code = http.POST(payload);
  http.end();
}

void sendEventToServer(const char* direction, unsigned long durationMs) {
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("Wi-Fi not connected! Cannot post event.");
    return;
  }

  HTTPClient http;
  http.begin(SERVER_URL);
  http.addHeader("Content-Type", "application/json");

  StaticJsonDocument<250> doc;
  doc["device_id"]   = DEVICE_ID;
  doc["direction"]   = direction;
  doc["duration_ms"] = durationMs;

  String jsonPayload;
  serializeJson(doc, jsonPayload);

  digitalWrite(LED_PIN, HIGH);
  int httpResponseCode = http.POST(jsonPayload);
  digitalWrite(LED_PIN, LOW);

  Serial.print("Event [");
  Serial.print(direction);
  Serial.print("] sent to Flask server. HTTP Code: ");
  Serial.println(httpResponseCode);

  if (httpResponseCode > 0) {
    String response = http.getString();
    Serial.println("Server Response: " + response);
  } else {
    Serial.print("Error sending POST: ");
    Serial.println(http.errorToString(httpResponseCode).c_str());
  }

  http.end();
}

void setup() {
  Serial.begin(115200);
  delay(1000);
  Serial.println("\n--- Automated Campus Bus Gate ESP32 Controller ---");

  pinMode(TRIG_PIN_1, OUTPUT);
  pinMode(ECHO_PIN_1, INPUT);
  pinMode(TRIG_PIN_2, OUTPUT);
  pinMode(ECHO_PIN_2, INPUT);
  pinMode(LED_PIN, OUTPUT);

  // Connect to Wi-Fi
  Serial.print("Connecting to Wi-Fi: ");
  Serial.println(WIFI_SSID);
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);

  while (WiFi.status() != WL_CONNECTED) {
    delay(400);
    digitalWrite(LED_PIN, !digitalRead(LED_PIN));
    Serial.print(".");
  }

  digitalWrite(LED_PIN, HIGH);
  Serial.println("\nWi-Fi Connected successfully!");
  Serial.print("ESP32 Assigned IP: ");
  Serial.println(WiFi.localIP());

  // Send initial ping
  sendHeartbeat();
}

void loop() {
  unsigned long now = millis();

  // Send periodic heartbeat every 15 seconds
  if (now - lastHeartbeatTime > 15000) {
    lastHeartbeatTime = now;
    sendHeartbeat();
  }

  // If in debounce cooldown, skip detection checks
  if (now - lastEventTime < COOLDOWN_MS) {
    delay(50);
    return;
  }

  // Read both HC-SR04 sensors
  float d1 = readDistanceCM(TRIG_PIN_1, ECHO_PIN_1);
  delay(15);
  float d2 = readDistanceCM(TRIG_PIN_2, ECHO_PIN_2);

  // Check Sensor 1 (Outer) Trigger
  if (d1 > 0 && d1 <= DISTANCE_THRESHOLD_CM) {
    lastS1Time = now;
    // If Sensor 2 was triggered first within MAX_GAP_MS -> EXIT
    if (lastS2Time > 0 && (now - lastS2Time) <= MAX_GAP_MS) {
      unsigned long delta = now - lastS2Time;
      Serial.println(">>> EXIT DETECTED (S2 -> S1) <<<");
      sendEventToServer("EXIT", delta);
      lastEventTime = now;
      lastS1Time = 0;
      lastS2Time = 0;
    }
  }

  // Check Sensor 2 (Inner) Trigger
  if (d2 > 0 && d2 <= DISTANCE_THRESHOLD_CM) {
    lastS2Time = now;
    // If Sensor 1 was triggered first within MAX_GAP_MS -> ENTRY
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
}
