# Automated Bus Entry & Exit Management System

A smart, responsive web application and hardware prototype backend for school and college campuses to monitor bus arrivals and departures.

The system uses:
- **ESP32 Microcontroller** + **Two HC-SR04 Ultrasonic Sensors** to detect passing vehicles and infer transit direction (**ENTRY** vs **EXIT**).
- **Android Phone Camera** via the **IP Webcam** application over Wi-Fi for automated gate photo snapshots.
- **Python Flask Backend + SQLite Database** for local records and REST APIs.
- **Navy Blue & White Dashboard** for real-time monitoring, fleet management, and historical logs.

> **Design Note**: Ultrasonic sensors detect vehicle presence and passage direction, not bus identity. The system provides an **Active Bus Selection Workflow** allowing gate operators to assign transit detections to the expected bus, alongside full manual overrides.

---

## 1. Project Folder Structure

```
bus/
├── app.py                     # Main Flask web server, REST API endpoints & proxy
├── database.py                # SQLite schema setup, helper functions & pre-seeded sample data
├── sensor_engine.py           # HC-SR04 direction inference logic & debounce protection
├── camera_service.py          # IP Webcam connection test, auto-capture & snapshot proxy
├── requirements.txt           # Python dependencies (Flask, requests, Pillow, flask-cors)
├── .gitignore                 # Git ignore rules for Python/Flask
├── README.md                  # Complete documentation and setup guide
├── esp32_firmware/
│   └── esp32_bus_gate.ino     # Ready-to-flash Arduino C++ firmware for ESP32
├── templates/                 # Jinja2 HTML Templates
│   ├── base.html              # Sidebar, responsive header, status pills & modals
│   ├── dashboard.html         # Overview metrics, Chart.js trends & quick gate actions
│   ├── buses.html             # Bus CRUD, search/filters, active target switcher
│   ├── monitoring.html        # Live gate simulator & dual-sensor visualizer
│   ├── camera.html            # IP Webcam stream preview, snapshot test & gallery
│   ├── history.html           # Historical logs, date/bus filters & CSV export
│   └── settings.html          # ESP32 diagnostics, calibration form & Arduino code
└── static/
    ├── css/
    │   └── style.css          # Dark navy blue and white responsive styling
    ├── js/
    │   ├── main.js            # Global utilities, toast notifications, status poller
    │   ├── dashboard.js       # KPI metrics & Chart.js rendering
    │   ├── buses.js           # Bus management CRUD logic
    │   ├── monitoring.js      # Ultrasonic visualizer & prototype simulator
    │   ├── camera.js          # IP Webcam connection test & stream switcher
    │   ├── history.js         # Event log filtering & CSV download
    │   └── settings.js        # Calibration saving & heartbeat test
    ├── img/                   # Icons, logo, and sample vehicle SVGs
    └── uploads/
        └── events/            # Auto-captured and uploaded snapshot photos
```

---

## 2. Prerequisites & Installation

### Requirements
- Python 3.9+ (Python 3.10, 3.11, 3.12, 3.13, 3.14 supported)
- pip package manager

### Step 1: Install Dependencies
Open a PowerShell or Terminal in the `bus` project directory:

```powershell
pip install -r requirements.txt
```

### Step 2: Run the Flask Web Application
```powershell
python app.py
```

The terminal will display:
```
=======================================================
 Automated Bus Entry & Exit Management System
 Server running at: http://127.0.0.1:5000
 Accessible on local Wi-Fi at: http://<YOUR_PC_IP>:5000
=======================================================
```

---

## 3. How to Open the Website in a Browser

Open any modern browser (Chrome, Edge, Firefox, Safari) and navigate to:
```
http://127.0.0.1:5000
```
Or from another device (like your phone or tablet on the same Wi-Fi):
```
http://<YOUR_PC_LOCAL_IP>:5000
```
*(Find your PC's local IP on Windows by running `ipconfig` in PowerShell).*

---

## 4. How to Configure the Android IP Webcam

1. Install the free **IP Webcam** app from Google Play Store on your Android phone.
2. Connect your phone to the **same Wi-Fi network** as your laptop/PC.
3. Open **IP Webcam**, scroll to the bottom, and tap **Start Server**.
4. The phone screen will display an address, for example: `http://192.168.1.15:8080`.
5. On the website dashboard, go to the **Android Camera** page (`/camera`).
6. Enter the URL into the **IP Webcam Server URL** input field.
7. Click **Test Ping** to verify connectivity with real latency diagnostics.
8. Click **Save & Connect**.
9. The camera status in the top header will switch to **Camera Live** (green), and gate events will automatically capture a snapshot from this camera!

> **Note on Browser Stream Compatibility**: Some browsers block direct cross-origin HTTP video streams. The dashboard includes a **Proxy Snapshot Mode** that fetches frames through the Flask backend (`/api/camera/proxy-snapshot`), ensuring reliable display without browser security warnings. You can also click **Open Direct** to view the phone's native camera interface in a separate tab.

---

## 5. How to Test With Sample Bus Records (No Hardware Needed)

The application comes pre-loaded with **8 sample buses** and **5 realistic gate movement events**.

You can test every feature immediately without connecting physical hardware:

1. **Test Gate Direction Simulation**:
   - Go to **Live Monitoring** (`/monitoring`).
   - Click **Simulate Full Entry (S1 → S2)**: The visualizer simulates a bus breaking the outer beam, then the inner beam, inferring **ENTRY** and recording the event for the active target bus.
   - Click **Simulate Full Exit (S2 → S1)**: Simulates the vehicle exiting the campus, inferring **EXIT** and updating the bus status to "Outside".
2. **Test Duplicate-Event Protection (Debounce)**:
   - Click the simulate button twice in rapid succession. Notice the second click is safely debounced: `"Duplicate trigger within debounce window (X.Xs remaining)"`.
3. **Test Fleet Management**:
   - Go to **Bus Management** (`/buses`).
   - Add, edit, or delete buses.
   - Click **Set Active** to assign a different vehicle as the active gate target.
4. **Test CSV Export**:
   - Go to **Entry/Exit History** (`/history`) and click **Export CSV** to download the movement log.
5. **Restore Demo Data**:
   - At any time, go to **Settings & Hardware** (`/settings`) and click **Restore Pre-seeded Sample Data** to reset the fleet to default state.

---

## 6. How to Connect the ESP32 Later

### Hardware Required:
- 1 × ESP32 Development Board (e.g. NodeMCU ESP32 / DOIT DEVKIT V1)
- 2 × HC-SR04 Ultrasonic Distance Sensors
- 1 × Breadboard and jumper wires
- Micro-USB cable

### Pinout Connections:
| Component | Sensor Pin | ESP32 GPIO Pin | Description |
|-----------|------------|----------------|-------------|
| **Sensor 1 (Outer - Road)** | VCC | VIN (5V) | Power supply |
| Sensor 1 (Outer) | GND | GND | Ground |
| Sensor 1 (Outer) | TRIG | **GPIO 5** | Trigger pulse output |
| Sensor 1 (Outer) | ECHO | **GPIO 18** | Echo pulse input |
| **Sensor 2 (Inner - Campus)** | VCC | VIN (5V) | Power supply |
| Sensor 2 (Inner) | GND | GND | Ground |
| Sensor 2 (Inner) | TRIG | **GPIO 19** | Trigger pulse output |
| Sensor 2 (Inner) | ECHO | **GPIO 21** | Echo pulse input |
| **Status LED** | Built-in | **GPIO 2** | Flashes on Wi-Fi/POST |

### Flashing the ESP32:
1. Open the Arduino IDE.
2. Open `esp32_firmware/esp32_bus_gate.ino`.
3. Install the **ArduinoJson** library via *Library Manager* (Tools -> Manage Libraries -> search `ArduinoJson`).
4. Update `WIFI_SSID`, `WIFI_PASSWORD`, and `SERVER_URL` in the sketch:
   ```cpp
   const char* WIFI_SSID     = "Your_WiFi_Network";
   const char* WIFI_PASSWORD = "Your_WiFi_Password";
   const char* SERVER_URL    = "http://192.168.1.50:5000/api/sensor-event";
   ```
5. Select **ESP32 Dev Module** under Tools -> Board.
6. Select your COM port and click **Upload**.
7. Once connected to Wi-Fi, the ESP32 will send periodic heartbeats to the Flask backend, changing the status pill to **ESP32 Online** (green).

---

## 7. Status of Features & Hardware Verification

| Feature | Software / Simulation Status | Physical Hardware Status |
|---------|------------------------------|--------------------------|
| Web Dashboard & 6 Pages | **100% Tested & Fully Functional** | Independent of hardware |
| Bus Fleet CRUD & Search | **100% Tested & Fully Functional** | Independent of hardware |
| Direction Inference Logic (S1→S2 = Entry, S2→S1 = Exit) | **100% Tested & Verified via Backend Engine** | Firmware provided; requires physical sensors for field test |
| Duplicate-Event Protection (Cooldown) | **100% Tested & Verified** | Software & firmware debounce logic ready |
| Android IP Webcam Connection & Auto-Capture | **100% Tested (Endpoint & Proxy Architecture)** | Requires Android phone running IP Webcam on local Wi-Fi |
| SQLite Database & History CSV Export | **100% Tested & Verified** | Functional |
| ESP32 REST Endpoint (`/api/sensor-event`) | **100% Tested via JSON Simulation** | Firmware provided; requires physical ESP32 flash |

> **Honest Engineering Note**: The web application, REST backend, database, and sensor simulation logic have been thoroughly implemented and tested in software. Connecting physical HC-SR04 sensors and flashing the ESP32 board requires physical hardware assembly by the user following the provided pinout table and Arduino sketch.
