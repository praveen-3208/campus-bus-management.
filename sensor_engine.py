"""
Sensor Engine for Ultrasonic Direction Detection and Debounce Management.
Infers Entry/Exit direction based on two HC-SR04 ultrasonic sensors:
  - Sensor 1 (S1): Outer gate sensor (facing road / exterior)
  - Sensor 2 (S2): Inner gate sensor (facing campus / interior)

Direction Logic:
  - S1 triggered -> S2 triggered within max_gap: ENTRY
  - S2 triggered -> S1 triggered within max_gap: EXIT
Includes duplicate-event protection (cooldown debounce).
"""

import time
import threading
from database import get_setting, get_db_connection

class SensorEngine:
    def __init__(self):
        self.lock = threading.Lock()
        self.last_s1_time = 0.0
        self.last_s2_time = 0.0
        self.last_event_time = 0.0
        self.last_event_type = None
        self.last_event_info = None

    def get_config(self):
        """Fetches dynamic thresholds from database settings."""
        try:
            threshold_cm = float(get_setting('distance_threshold_cm', 50))
            max_gap_sec = float(get_setting('max_sensor_gap_ms', 3500)) / 1000.0
            cooldown_sec = float(get_setting('cooldown_seconds', 6))
        except Exception:
            threshold_cm = 50.0
            max_gap_sec = 3.5
            cooldown_sec = 6.0
        return threshold_cm, max_gap_sec, cooldown_sec

    def process_raw_sensor(self, sensor_name, distance_cm):
        """
        Processes a raw distance reading from S1 or S2.
        Returns a dict describing result and any triggered direction.
        """
        with self.lock:
            now = time.time()
            threshold_cm, max_gap_sec, cooldown_sec = self.get_config()

            sensor_id = str(sensor_name).lower().strip()
            # Log raw trigger
            self._log_raw_sensor(sensor_id, distance_cm)

            # Check distance threshold: distance must be <= threshold to count as obstacle/bus present
            if distance_cm > threshold_cm:
                return {
                    'status': 'clear',
                    'message': f'{sensor_id.upper()} distance {distance_cm:.1f}cm above threshold {threshold_cm}cm (no vehicle detected)',
                    'direction': None,
                    'cooldown_active': (now - self.last_event_time) < cooldown_sec
                }

            # Check debounce cooldown
            cooldown_remaining = cooldown_sec - (now - self.last_event_time)
            if cooldown_remaining > 0:
                return {
                    'status': 'debounced',
                    'message': f'Vehicle detected on {sensor_id.upper()} but gate is in cooldown ({cooldown_remaining:.1f}s remaining)',
                    'direction': None,
                    'cooldown_active': True,
                    'cooldown_remaining': round(cooldown_remaining, 1)
                }

            direction = None
            delta_ms = 0

            if sensor_id in ('s1', 'sensor1', 'outer'):
                self.last_s1_time = now
                # Check if S2 was triggered recently
                if self.last_s2_time > 0 and (now - self.last_s2_time) <= max_gap_sec:
                    delta_ms = int((now - self.last_s2_time) * 1000)
                    direction = 'EXIT'
                    # Reset triggers
                    self.last_s1_time = 0.0
                    self.last_s2_time = 0.0
                    self.last_event_time = now
                    self.last_event_type = 'EXIT'
                    self.last_event_info = f'S2 -> S1 sequence ({delta_ms}ms gap)'
                else:
                    return {
                        'status': 'pending',
                        'message': 'Sensor 1 (Outer) triggered. Waiting for Sensor 2 to confirm ENTRY...',
                        'direction': None,
                        'pending_sensor': 'S1',
                        'cooldown_active': False
                    }

            elif sensor_id in ('s2', 'sensor2', 'inner'):
                self.last_s2_time = now
                # Check if S1 was triggered recently
                if self.last_s1_time > 0 and (now - self.last_s1_time) <= max_gap_sec:
                    delta_ms = int((now - self.last_s1_time) * 1000)
                    direction = 'ENTRY'
                    # Reset triggers
                    self.last_s1_time = 0.0
                    self.last_s2_time = 0.0
                    self.last_event_time = now
                    self.last_event_type = 'ENTRY'
                    self.last_event_info = f'S1 -> S2 sequence ({delta_ms}ms gap)'
                else:
                    return {
                        'status': 'pending',
                        'message': 'Sensor 2 (Inner) triggered. Waiting for Sensor 1 to confirm EXIT...',
                        'direction': None,
                        'pending_sensor': 'S2',
                        'cooldown_active': False
                    }
            else:
                return {
                    'status': 'error',
                    'message': f'Unknown sensor ID: {sensor_name}. Use "s1" or "s2".',
                    'direction': None
                }

            if direction:
                return {
                    'status': 'detected',
                    'direction': direction,
                    'message': f'{direction} detected via dual HC-SR04 sensors ({delta_ms}ms gap)',
                    'delta_ms': delta_ms,
                    'sequence': self.last_event_info,
                    'cooldown_sec': cooldown_sec
                }

    def process_direct_direction(self, direction_type, trigger_info="ESP32 Direction Protocol"):
        """
        Processes a pre-computed direction event sent directly by the ESP32 firmware.
        Applies duplicate protection / debounce window.
        """
        with self.lock:
            now = time.time()
            _, _, cooldown_sec = self.get_config()
            direction = str(direction_type).upper().strip()

            if direction not in ('ENTRY', 'EXIT'):
                return {
                    'status': 'error',
                    'message': f'Invalid direction "{direction_type}". Must be "ENTRY" or "EXIT".',
                    'direction': None
                }

            # Check cooldown
            cooldown_remaining = cooldown_sec - (now - self.last_event_time)
            if cooldown_remaining > 0:
                return {
                    'status': 'debounced',
                    'message': f'{direction} ignored: duplicate trigger within debounce window ({cooldown_remaining:.1f}s remaining)',
                    'direction': None,
                    'cooldown_active': True,
                    'cooldown_remaining': round(cooldown_remaining, 1)
                }

            self.last_event_time = now
            self.last_event_type = direction
            self.last_event_info = trigger_info
            self.last_s1_time = 0.0
            self.last_s2_time = 0.0

            return {
                'status': 'detected',
                'direction': direction,
                'message': f'{direction} event confirmed ({trigger_info})',
                'cooldown_sec': cooldown_sec
            }

    def get_live_state(self):
        """Returns the current state for frontend gate visualization."""
        with self.lock:
            now = time.time()
            threshold_cm, max_gap_sec, cooldown_sec = self.get_config()

            s1_active = (now - self.last_s1_time) <= max_gap_sec if self.last_s1_time > 0 else False
            s2_active = (now - self.last_s2_time) <= max_gap_sec if self.last_s2_time > 0 else False

            cooldown_remaining = max(0.0, cooldown_sec - (now - self.last_event_time))
            in_cooldown = cooldown_remaining > 0

            # Compute gate status
            if in_cooldown:
                gate_status = 'COOLDOWN'
                status_text = f'Cooldown Active ({cooldown_remaining:.1f}s)'
            elif s1_active and not s2_active:
                gate_status = 'S1_WAITING'
                status_text = 'Outer Beam Broken (Waiting for Inner...)'
            elif s2_active and not s1_active:
                gate_status = 'S2_WAITING'
                status_text = 'Inner Beam Broken (Waiting for Outer...)'
            elif s1_active and s2_active:
                gate_status = 'BOTH_DETECTED'
                status_text = 'Vehicle In Transition'
            else:
                gate_status = 'IDLE'
                status_text = 'Gate Clear / Monitoring'

            return {
                'gate_status': gate_status,
                'status_text': status_text,
                's1_active': s1_active,
                's2_active': s2_active,
                'in_cooldown': in_cooldown,
                'cooldown_remaining': round(cooldown_remaining, 1),
                'threshold_cm': threshold_cm,
                'max_gap_sec': max_gap_sec,
                'last_event_type': self.last_event_type,
                'last_event_info': self.last_event_info
            }

    def _log_raw_sensor(self, sensor_name, distance_cm):
        """Internal helper to log raw sensor readings into SQLite."""
        try:
            conn = get_db_connection()
            now_str = time.strftime('%Y-%m-%d %H:%M:%S')
            conn.execute(
                "INSERT INTO sensor_logs (sensor_name, distance_cm, timestamp, result) VALUES (?, ?, ?, ?)",
                (sensor_name, distance_cm, now_str, 'received')
            )
            # Prune old logs keeping last 200
            conn.execute("DELETE FROM sensor_logs WHERE id NOT IN (SELECT id FROM sensor_logs ORDER BY id DESC LIMIT 200)")
            conn.commit()
            conn.close()
        except Exception:
            pass

sensor_engine = SensorEngine()
