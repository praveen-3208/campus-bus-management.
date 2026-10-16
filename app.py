"""
Automated Bus Entry & Exit Management System - Flask Application
"""

import os
import time
import io
import csv
from datetime import datetime
from flask import (
    Flask, render_template, request, jsonify, Response, send_file, redirect, url_for
)
from flask_cors import CORS
from database import (
    init_db, get_db_connection, get_setting, set_setting, get_all_settings, seed_sample_data
)
from sensor_engine import sensor_engine
from camera_service import (
    test_camera_connection, capture_event_photo, save_uploaded_photo,
    fetch_live_snapshot, get_camera_urls
)

app = Flask(__name__)
app.config['SECRET_KEY'] = 'bus-gate-management-secret-key-2026'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16 MB max upload
CORS(app)

# Initialize database on startup
init_db(seed_if_empty=True)

# -------------------------------------------------------------
# HELPER FUNCTIONS
# -------------------------------------------------------------

def get_active_bus():
    """Retrieves the currently active bus record for gate tracking."""
    conn = get_db_connection()
    active_bus_id = get_setting('active_bus_id', 'BUS-01')
    row = conn.execute("SELECT * FROM buses WHERE bus_id = ?", (active_bus_id,)).fetchone()
    if not row:
        # Fallback to first bus in database
        row = conn.execute("SELECT * FROM buses ORDER BY bus_id ASC LIMIT 1").fetchone()
        if row:
            set_setting('active_bus_id', row['bus_id'])
    conn.close()
    return dict(row) if row else None

def record_gate_event(bus_dict, event_type, sensor_trigger, confidence='Normal', notes=''):
    """
    Creates an event record, attempts photo capture, and updates bus status in database.
    """
    bus_id = bus_dict['bus_id']
    bus_reg = bus_dict.get('registration_no', '')
    route = bus_dict.get('route_name', '')
    driver = bus_dict.get('driver_name', '')

    # Attempt automatic photo capture
    photo_path, photo_error = capture_event_photo(bus_id, event_type)
    if photo_error:
        event_notes = f"{notes} [Photo note: {photo_error}]".strip()
    else:
        event_notes = notes

    # Update bus status
    new_status = 'Inside' if event_type == 'ENTRY' else 'Outside'
    now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE buses 
        SET status = ?, updated_at = ? 
        WHERE bus_id = ?
    """, (new_status, now_str, bus_id))

    cursor.execute("""
        INSERT INTO events (bus_id, bus_registration, route_name, driver_name, event_type, timestamp, sensor_trigger, confidence, photo_path, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (bus_id, bus_reg, route, driver, event_type, now_str, sensor_trigger, confidence, photo_path, event_notes))

    event_id = cursor.lastrowid
    conn.commit()
    conn.close()

    return {
        'event_id': event_id,
        'bus_id': bus_id,
        'registration_no': bus_reg,
        'event_type': event_type,
        'timestamp': now_str,
        'new_status': new_status,
        'sensor_trigger': sensor_trigger,
        'photo_path': photo_path,
        'photo_captured': photo_path is not None,
        'photo_error': photo_error
    }

# -------------------------------------------------------------
# PAGE ROUTES
# -------------------------------------------------------------

@app.route('/')
@app.route('/dashboard')
def dashboard_page():
    return render_template('dashboard.html', active_page='dashboard')

@app.route('/buses')
def buses_page():
    return render_template('buses.html', active_page='buses')

@app.route('/monitoring')
def monitoring_page():
    return render_template('monitoring.html', active_page='monitoring')

@app.route('/camera')
def camera_page():
    return render_template('camera.html', active_page='camera')

@app.route('/history')
def history_page():
    return render_template('history.html', active_page='history')

@app.route('/settings')
def settings_page():
    return render_template('settings.html', active_page='settings')

# -------------------------------------------------------------
# BUSES API
# -------------------------------------------------------------

@app.route('/api/buses', methods=['GET'])
def list_buses():
    query = request.args.get('q', '').strip()
    status_filter = request.args.get('status', '').strip()

    conn = get_db_connection()
    sql = "SELECT * FROM buses WHERE 1=1"
    params = []

    if query:
        sql += " AND (bus_id LIKE ? OR registration_no LIKE ? OR route_name LIKE ? OR driver_name LIKE ?)"
        wildcard = f"%{query}%"
        params.extend([wildcard, wildcard, wildcard, wildcard])

    if status_filter in ('Inside', 'Outside'):
        sql += " AND status = ?"
        params.append(status_filter)

    sql += " ORDER BY bus_id ASC"
    rows = conn.execute(sql, params).fetchall()
    conn.close()

    return jsonify([dict(row) for row in rows])

@app.route('/api/buses', methods=['POST'])
def add_bus():
    data = request.get_json() or {}
    bus_id = data.get('bus_id', '').strip().upper()
    registration_no = data.get('registration_no', '').strip().upper()
    route_name = data.get('route_name', '').strip()
    driver_name = data.get('driver_name', '').strip()
    driver_contact = data.get('driver_contact', '').strip()
    status = data.get('status', 'Inside').capitalize()

    if not bus_id or not registration_no or not route_name or not driver_name:
        return jsonify({'error': 'Bus ID, Registration No, Route, and Driver Name are required fields.'}), 400

    if status not in ('Inside', 'Outside'):
        status = 'Inside'

    now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    try:
        conn = get_db_connection()
        conn.execute("""
            INSERT INTO buses (bus_id, registration_no, route_name, driver_name, driver_contact, status, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (bus_id, registration_no, route_name, driver_name, driver_contact, status, now_str, now_str))
        conn.commit()
        conn.close()
        return jsonify({'message': f'Bus {bus_id} added successfully!', 'bus_id': bus_id}), 201
    except Exception as e:
        if 'UNIQUE' in str(e).upper():
            return jsonify({'error': f'A bus with ID "{bus_id}" already exists.'}), 409
        return jsonify({'error': f'Database error: {str(e)}'}), 500

@app.route('/api/buses/<int:bus_id_pk>', methods=['GET'])
def get_bus(bus_id_pk):
    conn = get_db_connection()
    row = conn.execute("SELECT * FROM buses WHERE id = ?", (bus_id_pk,)).fetchone()
    conn.close()
    if not row:
        return jsonify({'error': 'Bus not found'}), 404
    return jsonify(dict(row))

@app.route('/api/buses/<int:bus_id_pk>', methods=['PUT'])
def update_bus(bus_id_pk):
    data = request.get_json() or {}
    registration_no = data.get('registration_no', '').strip().upper()
    route_name = data.get('route_name', '').strip()
    driver_name = data.get('driver_name', '').strip()
    driver_contact = data.get('driver_contact', '').strip()
    status = data.get('status', '').capitalize()

    if not registration_no or not route_name or not driver_name:
        return jsonify({'error': 'Registration No, Route, and Driver Name are required.'}), 400

    now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    conn = get_db_connection()
    cursor = conn.cursor()
    row = cursor.execute("SELECT * FROM buses WHERE id = ?", (bus_id_pk,)).fetchone()
    if not row:
        conn.close()
        return jsonify({'error': 'Bus not found'}), 404

    current_status = status if status in ('Inside', 'Outside') else row['status']

    cursor.execute("""
        UPDATE buses 
        SET registration_no = ?, route_name = ?, driver_name = ?, driver_contact = ?, status = ?, updated_at = ?
        WHERE id = ?
    """, (registration_no, route_name, driver_name, driver_contact, current_status, now_str, bus_id_pk))
    conn.commit()
    conn.close()

    return jsonify({'message': 'Bus details updated successfully!'})

@app.route('/api/buses/<int:bus_id_pk>', methods=['DELETE'])
def delete_bus(bus_id_pk):
    conn = get_db_connection()
    cursor = conn.cursor()
    row = cursor.execute("SELECT * FROM buses WHERE id = ?", (bus_id_pk,)).fetchone()
    if not row:
        conn.close()
        return jsonify({'error': 'Bus not found'}), 404

    bus_id = row['bus_id']
    cursor.execute("DELETE FROM buses WHERE id = ?", (bus_id_pk,))
    conn.commit()

    # If the deleted bus was active, reset active bus
    active_bus = get_setting('active_bus_id', '')
    if active_bus == bus_id:
        new_active = cursor.execute("SELECT bus_id FROM buses LIMIT 1").fetchone()
        set_setting('active_bus_id', new_active['bus_id'] if new_active else '')

    conn.close()
    return jsonify({'message': f'Bus {bus_id} deleted successfully.'})

@app.route('/api/buses/<int:bus_id_pk>/set-active', methods=['POST'])
def set_active_bus_endpoint(bus_id_pk):
    conn = get_db_connection()
    row = conn.execute("SELECT bus_id FROM buses WHERE id = ?", (bus_id_pk,)).fetchone()
    conn.close()
    if not row:
        return jsonify({'error': 'Bus not found'}), 404

    set_setting('active_bus_id', row['bus_id'])
    return jsonify({'message': f'Active gate bus set to {row["bus_id"]}', 'active_bus_id': row['bus_id']})

@app.route('/api/buses/set-active-by-code', methods=['POST'])
def set_active_bus_by_code():
    data = request.get_json() or {}
    bus_id = data.get('bus_id', '').strip().upper()
    conn = get_db_connection()
    row = conn.execute("SELECT * FROM buses WHERE bus_id = ?", (bus_id,)).fetchone()
    conn.close()
    if not row:
        return jsonify({'error': f'Bus ID "{bus_id}" not found'}), 404

    set_setting('active_bus_id', bus_id)
    return jsonify({'message': f'Active gate bus updated to {bus_id}', 'active_bus': dict(row)})

@app.route('/api/buses/<int:bus_id_pk>/toggle-status', methods=['POST'])
def toggle_bus_status(bus_id_pk):
    conn = get_db_connection()
    cursor = conn.cursor()
    row = cursor.execute("SELECT * FROM buses WHERE id = ?", (bus_id_pk,)).fetchone()
    if not row:
        conn.close()
        return jsonify({'error': 'Bus not found'}), 404

    new_status = 'Outside' if row['status'] == 'Inside' else 'Inside'
    now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    cursor.execute("UPDATE buses SET status = ?, updated_at = ? WHERE id = ?", (new_status, now_str, bus_id_pk))
    conn.commit()
    conn.close()

    return jsonify({'message': f'Status toggled to {new_status}', 'new_status': new_status})

# -------------------------------------------------------------
# EVENTS API
# -------------------------------------------------------------

@app.route('/api/events', methods=['GET'])
def list_events():
    limit = request.args.get('limit', 100, type=int)
    date_filter = request.args.get('date', '').strip()
    bus_filter = request.args.get('bus_id', '').strip()
    type_filter = request.args.get('event_type', '').strip().upper()

    conn = get_db_connection()
    sql = "SELECT * FROM events WHERE 1=1"
    params = []

    if date_filter:
        sql += " AND date(timestamp) = date(?)"
        params.append(date_filter)

    if bus_filter:
        sql += " AND (bus_id LIKE ? OR bus_registration LIKE ?)"
        wildcard = f"%{bus_filter}%"
        params.extend([wildcard, wildcard])

    if type_filter in ('ENTRY', 'EXIT'):
        sql += " AND event_type = ?"
        params.append(type_filter)

    sql += " ORDER BY id DESC LIMIT ?"
    params.append(limit)

    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return jsonify([dict(row) for row in rows])

@app.route('/api/events', methods=['POST'])
def create_manual_event():
    """Manual entry/exit event trigger via web dashboard."""
    # Check if form data or JSON
    if request.content_type and 'multipart/form-data' in request.content_type:
        bus_id = request.form.get('bus_id', '').strip().upper()
        event_type = request.form.get('event_type', '').strip().upper()
        notes = request.form.get('notes', 'Manual dashboard action').strip()
        photo_file = request.files.get('photo')
    else:
        data = request.get_json() or {}
        bus_id = data.get('bus_id', '').strip().upper()
        event_type = data.get('event_type', '').strip().upper()
        notes = data.get('notes', 'Manual dashboard action').strip()
        photo_file = None

    if event_type not in ('ENTRY', 'EXIT'):
        return jsonify({'error': 'Event type must be ENTRY or EXIT'}), 400

    conn = get_db_connection()
    if not bus_id:
        active_bus_id = get_setting('active_bus_id', '')
        row = conn.execute("SELECT * FROM buses WHERE bus_id = ?", (active_bus_id,)).fetchone()
    else:
        row = conn.execute("SELECT * FROM buses WHERE bus_id = ?", (bus_id,)).fetchone()
    conn.close()

    if not row:
        return jsonify({'error': 'Selected bus not found'}), 404

    bus_dict = dict(row)

    # If user uploaded a photo directly, save it
    if photo_file:
        photo_path, upload_err = save_uploaded_photo(photo_file, bus_dict['bus_id'], event_type)
        if upload_err:
            return jsonify({'error': upload_err}), 400

        # Record directly with uploaded photo
        new_status = 'Inside' if event_type == 'ENTRY' else 'Outside'
        now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        conn = get_db_connection()
        conn.execute("UPDATE buses SET status = ?, updated_at = ? WHERE bus_id = ?", (new_status, now_str, bus_dict['bus_id']))
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO events (bus_id, bus_registration, route_name, driver_name, event_type, timestamp, sensor_trigger, confidence, photo_path, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (bus_dict['bus_id'], bus_dict.get('registration_no', ''), bus_dict.get('route_name', ''),
              bus_dict.get('driver_name', ''), event_type, now_str, 'Manual Upload', 'Manual Verification', photo_path, notes))
        conn.commit()
        conn.close()

        result = {
            'event_id': cursor.lastrowid,
            'bus_id': bus_dict['bus_id'],
            'registration_no': bus_dict.get('registration_no', ''),
            'event_type': event_type,
            'timestamp': now_str,
            'new_status': new_status,
            'sensor_trigger': 'Manual Upload',
            'photo_path': photo_path,
            'photo_captured': True,
            'notes': notes
        }
    else:
        # Standard flow (calls automatic snapshot capture from IP Webcam)
        result = record_gate_event(
            bus_dict,
            event_type,
            sensor_trigger='Manual Gate Trigger',
            confidence='Manual Test',
            notes=notes
        )

    return jsonify({'message': f'{event_type} event recorded for {bus_dict["bus_id"]}', 'event': result})

@app.route('/api/events/<int:event_id>', methods=['DELETE'])
def delete_event(event_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM events WHERE id = ?", (event_id,))
    conn.commit()
    conn.close()
    return jsonify({'message': f'Event #{event_id} deleted.'})

@app.route('/api/events/clear', methods=['POST'])
def clear_events():
    conn = get_db_connection()
    conn.execute("DELETE FROM events")
    conn.commit()
    conn.close()
    return jsonify({'message': 'All event history cleared.'})

@app.route('/api/events/export')
def export_events_csv():
    """Exports events log to CSV for reporting."""
    conn = get_db_connection()
    rows = conn.execute("SELECT * FROM events ORDER BY id DESC").fetchall()
    conn.close()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Event ID', 'Bus ID', 'Registration No', 'Route', 'Driver', 'Event Type', 'Timestamp', 'Sensor Trigger', 'Confidence', 'Photo Path', 'Notes'])

    for row in rows:
        writer.writerow([
            row['id'], row['bus_id'], row['bus_registration'], row['route_name'],
            row['driver_name'], row['event_type'], row['timestamp'],
            row['sensor_trigger'], row['confidence'], row['photo_path'], row['notes']
        ])

    output.seek(0)
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-disposition": f"attachment; filename=bus_gate_history_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"}
    )

# -------------------------------------------------------------
# SENSOR & HARDWARE INTEGRATION ENDPOINTS
# -------------------------------------------------------------

@app.route('/api/sensor-event', methods=['POST'])
def handle_sensor_event():
    """
    ESP32 integration endpoint over Wi-Fi.
    Accepts:
      Option A (raw reading): {"sensor": "s1"|"s2", "distance": 45.0, "device_id": "ESP32-GATE-01"}
      Option B (direction):   {"direction": "ENTRY"|"EXIT", "duration_ms": 1200, "device_id": "ESP32-GATE-01"}
    """
    data = request.get_json(silent=True)
    if not data:
        return jsonify({'error': 'Invalid JSON body'}), 400

    now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    # Update ESP32 Heartbeat info
    client_ip = request.remote_addr or 'Local'
    device_id = data.get('device_id', 'ESP32-GATE-01')
    set_setting('esp32_status', 'online')
    set_setting('esp32_last_seen', now_str)
    set_setting('esp32_device_ip', f"{client_ip} ({device_id})")

    # Mode 1: ESP32 sends direct direction
    if 'direction' in data:
        direction = str(data['direction']).upper()
        trigger_desc = f"ESP32 Inferred ({device_id})"
        engine_result = sensor_engine.process_direct_direction(direction, trigger_desc)
    # Mode 2: ESP32 sends raw sensor distance reading
    elif 'sensor' in data:
        sensor_name = data['sensor']
        try:
            distance = float(data.get('distance', 999.0))
        except (ValueError, TypeError):
            return jsonify({'error': 'Distance must be a numeric value in cm'}), 400
        engine_result = sensor_engine.process_raw_sensor(sensor_name, distance)
    else:
        return jsonify({'error': 'Payload must contain either "sensor" + "distance" or "direction"'}), 400

    # If a full vehicle movement direction was triggered!
    if engine_result.get('status') == 'detected' and engine_result.get('direction'):
        direction = engine_result['direction']
        trigger_info = engine_result.get('sequence', f"Dual HC-SR04 Sequence")

        # Get active bus for gate
        active_bus = get_active_bus()
        if not active_bus:
            return jsonify({
                'status': 'detected_but_no_bus',
                'message': f'{direction} detected, but no buses are registered in system.',
                'direction': direction
            }), 200

        # Record event, capture snapshot, and update status
        event_record = record_gate_event(
            bus_dict=active_bus,
            event_type=direction,
            sensor_trigger=trigger_info,
            confidence='Hardware (Dual HC-SR04)',
            notes=f"Auto-detected via ESP32 {device_id}"
        )

        return jsonify({
            'status': 'success',
            'action': 'event_recorded',
            'direction': direction,
            'bus': active_bus['bus_id'],
            'event': event_record,
            'engine': engine_result
        }), 201

    return jsonify({
        'status': engine_result.get('status', 'ok'),
        'message': engine_result.get('message', 'Sensor reading processed'),
        'engine': engine_result
    }), 200

@app.route('/api/esp32/ping', methods=['POST', 'GET'])
def esp32_ping():
    """Lightweight heartbeat endpoint for ESP32 connectivity checks."""
    now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    client_ip = request.remote_addr or 'Local'
    data = request.get_json(silent=True) or {}
    device_id = data.get('device_id', 'ESP32-GATE-01')

    set_setting('esp32_status', 'online')
    set_setting('esp32_last_seen', now_str)
    set_setting('esp32_device_ip', f"{client_ip} ({device_id})")

    return jsonify({
        'status': 'online',
        'server_time': now_str,
        'message': 'ESP32 heartbeat acknowledged'
    })

# -------------------------------------------------------------
# CAMERA API & PROXY
# -------------------------------------------------------------

@app.route('/api/camera/test', methods=['POST'])
def test_camera():
    data = request.get_json(silent=True) or {}
    custom_url = data.get('camera_url')
    connected, message, latency = test_camera_connection(custom_url)
    return jsonify({
        'connected': connected,
        'message': message,
        'latency_ms': latency,
        'status': 'connected' if connected else 'disconnected'
    })

@app.route('/api/camera/configure', methods=['POST'])
def configure_camera():
    data = request.get_json() or {}
    camera_url = data.get('camera_url', '').strip()
    stream_path = data.get('camera_stream_path', '/video').strip()
    snapshot_path = data.get('camera_snapshot_path', '/shot.jpg').strip()
    enabled = str(data.get('camera_enabled', 'true')).lower()

    if camera_url and not (camera_url.startswith('http://') or camera_url.startswith('https://')):
        camera_url = 'http://' + camera_url

    set_setting('camera_url', camera_url)
    set_setting('camera_stream_path', stream_path)
    set_setting('camera_snapshot_path', snapshot_path)
    set_setting('camera_enabled', enabled)

    # Test the newly saved connection
    connected, message, latency = test_camera_connection()

    return jsonify({
        'message': 'Camera settings saved successfully',
        'connected': connected,
        'test_result': message,
        'camera_url': camera_url,
        'stream_url': f"{camera_url}{stream_path}",
        'snapshot_url': f"{camera_url}{snapshot_path}"
    })

@app.route('/api/camera/capture', methods=['POST'])
def manual_camera_capture():
    """Triggers instant photo capture from the IP Webcam without requiring a sensor trigger."""
    data = request.get_json(silent=True) or {}
    bus_id = data.get('bus_id') or get_setting('active_bus_id', 'BUS-01')
    event_type = data.get('event_type', 'MANUAL').upper()

    photo_path, error = capture_event_photo(bus_id, event_type)
    if error:
        return jsonify({'error': error, 'captured': False}), 502

    return jsonify({
        'message': 'Snapshot captured successfully from IP Webcam',
        'captured': True,
        'photo_path': photo_path,
        'bus_id': bus_id,
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    })

@app.route('/api/camera/proxy-snapshot')
def proxy_snapshot():
    """
    Proxies live snapshot from IP Webcam to the browser.
    Eliminates CORS, mixed-content, and local network browser blocking issues.
    """
    content, content_type = fetch_live_snapshot()
    if not content:
        # Return fallback placeholder SVG
        return redirect(url_for('static', filename='img/sample_bus_1.svg'))
    return Response(content, mimetype=content_type)

@app.route('/api/camera/upload', methods=['POST'])
def manual_upload_photo():
    """Manual photo file upload fallback."""
    if 'photo' not in request.files:
        return jsonify({'error': 'No photo file provided'}), 400

    photo_file = request.files['photo']
    bus_id = request.form.get('bus_id', 'MANUAL')
    event_type = request.form.get('event_type', 'SNAP')

    photo_path, error = save_uploaded_photo(photo_file, bus_id, event_type)
    if error:
        return jsonify({'error': error}), 400

    return jsonify({
        'message': 'Photo uploaded successfully',
        'photo_path': photo_path
    })

# -------------------------------------------------------------
# SYSTEM STATUS & DASHBOARD API
# -------------------------------------------------------------

@app.route('/api/status')
def get_system_status():
    conn = get_db_connection()

    # Bus counts
    total_buses = conn.execute("SELECT COUNT(*) FROM buses").fetchone()[0]
    buses_inside = conn.execute("SELECT COUNT(*) FROM buses WHERE status = 'Inside'").fetchone()[0]
    buses_outside = conn.execute("SELECT COUNT(*) FROM buses WHERE status = 'Outside'").fetchone()[0]

    # Today's entries & exits
    today_str = datetime.now().strftime('%Y-%m-%d')
    today_entries = conn.execute(
        "SELECT COUNT(*) FROM events WHERE event_type = 'ENTRY' AND date(timestamp) = date(?)",
        (today_str,)
    ).fetchone()[0]
    today_exits = conn.execute(
        "SELECT COUNT(*) FROM events WHERE event_type = 'EXIT' AND date(timestamp) = date(?)",
        (today_str,)
    ).fetchone()[0]

    # Recent 6 events
    recent_events_rows = conn.execute(
        "SELECT * FROM events ORDER BY id DESC LIMIT 6"
    ).fetchall()
    recent_events = [dict(r) for r in recent_events_rows]

    conn.close()

    # Hardware connection health checks
    esp32_last_seen = get_setting('esp32_last_seen', '')
    esp32_online = False
    if esp32_last_seen:
        try:
            last_dt = datetime.strptime(esp32_last_seen, '%Y-%m-%d %H:%M:%S')
            # If heard from within last 30 seconds, treat as online
            if (datetime.now() - last_dt).total_seconds() < 30:
                esp32_online = True
        except Exception:
            pass

    camera_status = get_setting('camera_status', 'disconnected')
    active_bus = get_active_bus()
    gate_state = sensor_engine.get_live_state()
    base_url, stream_url, snapshot_url = get_camera_urls()

    return jsonify({
        'counts': {
            'total_buses': total_buses,
            'buses_inside': buses_inside,
            'buses_outside': buses_outside,
            'today_entries': today_entries,
            'today_exits': today_exits
        },
        'hardware': {
            'esp32': {
                'status': 'online' if esp32_online else 'offline',
                'last_seen': esp32_last_seen or 'Never',
                'device_ip': get_setting('esp32_device_ip', 'Not Connected')
            },
            'camera': {
                'status': camera_status,
                'base_url': base_url,
                'stream_url': stream_url,
                'snapshot_url': snapshot_url,
                'enabled': get_setting('camera_enabled', 'true').lower() == 'true',
                'last_tested': get_setting('camera_last_tested', '')
            }
        },
        'gate_sensor': gate_state,
        'active_bus': active_bus,
        'recent_events': recent_events,
        'server_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    })

# -------------------------------------------------------------
# SETTINGS & DATA SEEDING API
# -------------------------------------------------------------

@app.route('/api/settings', methods=['GET'])
def get_settings():
    return jsonify(get_all_settings())

@app.route('/api/settings', methods=['POST'])
def save_settings():
    data = request.get_json() or {}
    allowed_keys = {
        'camera_url', 'camera_stream_path', 'camera_snapshot_path', 'camera_enabled',
        'active_bus_id', 'distance_threshold_cm', 'max_sensor_gap_ms', 'cooldown_seconds'
    }
    for key, value in data.items():
        if key in allowed_keys:
            set_setting(key, str(value))

    return jsonify({'message': 'Settings saved successfully', 'settings': get_all_settings()})

@app.route('/api/settings/seed-sample-data', methods=['POST'])
def seed_data_endpoint():
    """Resets database and loads sample buses and event movements."""
    seed_sample_data()
    return jsonify({'message': 'Sample data successfully restored!'})

# -------------------------------------------------------------
# APPLICATION ENTRYPOINT
# -------------------------------------------------------------

if __name__ == '__main__':
    # Default host 0.0.0.0 makes it accessible to ESP32 & Android phone on local Wi-Fi
    port = int(os.environ.get('PORT', 5000))
    print(f"\n=======================================================")
    print(f" Automated Bus Entry & Exit Management System")
    print(f" Server running at: http://127.0.0.1:{port}")
    print(f" Accessible on local Wi-Fi at: http://<YOUR_PC_IP>:{port}")
    print(f"=======================================================\n")
    app.run(host='0.0.0.0', port=port, debug=False)
