"""
Database configuration, schema management, and sample data seeding for
Automated Bus Entry & Exit Management System.
"""
import sqlite3
import os
from datetime import datetime, timedelta

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'bus_system.db')

def get_db_connection():
    """Returns a SQLite connection with row factory enabled."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def init_db(seed_if_empty=True):
    """Initializes tables and seeds initial data if needed."""
    conn = get_db_connection()
    cursor = conn.cursor()

    # Buses Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS buses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        bus_id TEXT UNIQUE NOT NULL,
        registration_no TEXT NOT NULL,
        route_name TEXT NOT NULL,
        driver_name TEXT NOT NULL,
        driver_contact TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'Inside' CHECK(status IN ('Inside', 'Outside')),
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )
    """)

    # Events Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        bus_id TEXT NOT NULL,
        bus_registration TEXT,
        route_name TEXT,
        driver_name TEXT,
        event_type TEXT NOT NULL CHECK(event_type IN ('ENTRY', 'EXIT')),
        timestamp TEXT NOT NULL,
        sensor_trigger TEXT,
        confidence TEXT DEFAULT 'Normal',
        photo_path TEXT,
        notes TEXT
    )
    """)

    # Settings Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL
    )
    """)

    # Raw Sensor Triggers Log (for debugging & analytics)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS sensor_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        sensor_name TEXT NOT NULL,
        distance_cm REAL,
        timestamp TEXT NOT NULL,
        result TEXT
    )
    """)

    conn.commit()

    # Default Settings
    default_settings = {
        'camera_url': 'http://10.182.220.107:8080',
        'camera_stream_path': '/video',
        'camera_snapshot_path': '/shot.jpg',
        'camera_enabled': 'true',
        'camera_status': 'disconnected',
        'camera_last_tested': '',
        'active_bus_id': 'BUS-01',
        'distance_threshold_cm': '50',
        'max_sensor_gap_ms': '3500',
        'cooldown_seconds': '6',
        'esp32_status': 'offline',
        'esp32_last_seen': '',
        'esp32_device_ip': 'Not Connected'
    }

    for key, value in default_settings.items():
        cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", (key, value))

    conn.commit()

    # Check if buses table is empty
    cursor.execute("SELECT COUNT(*) FROM buses")
    bus_count = cursor.fetchone()[0]

    if seed_if_empty and bus_count == 0:
        seed_sample_data(conn)

    conn.close()

def get_setting(key, default=''):
    conn = get_db_connection()
    row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
    conn.close()
    return row['value'] if row else default

def set_setting(key, value):
    conn = get_db_connection()
    conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, str(value)))
    conn.commit()
    conn.close()

def get_all_settings():
    conn = get_db_connection()
    rows = conn.execute("SELECT key, value FROM settings").fetchall()
    conn.close()
    return {row['key']: row['value'] for row in rows}

def seed_sample_data(conn=None):
    """Populates initial sample buses and realistic gate events for preview."""
    close_at_end = False
    if conn is None:
        conn = get_db_connection()
        close_at_end = True

    cursor = conn.cursor()

    # Clear existing data for fresh seed if called explicitly
    cursor.execute("DELETE FROM buses")
    cursor.execute("DELETE FROM events")
    cursor.execute("DELETE FROM sensor_logs")

    now = datetime.now()
    now_str = now.strftime('%Y-%m-%d %H:%M:%S')

    sample_buses = [
        ('BUS-01', 'KA-05-AA-1001', 'Route 1 - North Campus / Hebbal', 'Ramesh Sharma', '+91 98450 12345', 'Inside', now_str, now_str),
        ('BUS-02', 'KA-05-AA-1002', 'Route 2 - Central City / MG Road', 'Sunil Kumar', '+91 98450 23456', 'Outside', now_str, now_str),
        ('BUS-03', 'KA-05-AA-1003', 'Route 3 - West Suburbs / Rajajinagar', 'Anand Patil', '+91 98450 34567', 'Inside', now_str, now_str),
        ('BUS-04', 'KA-05-AA-1004', 'Route 4 - Tech Park / Electronic City', 'Mohammed Rafiq', '+91 98450 45678', 'Inside', now_str, now_str),
        ('BUS-05', 'KA-05-AA-1005', 'Route 5 - South Campus / Bannerghatta', 'Deepak Verma', '+91 98450 56789', 'Outside', now_str, now_str),
        ('BUS-06', 'KA-05-AA-1006', 'Route 6 - East Extension / Whitefield', 'Gurpreet Singh', '+91 98450 67890', 'Inside', now_str, now_str),
        ('BUS-07', 'KA-05-AA-1007', 'Route 7 - Airport Road / Yelahanka', 'Vikram Gowda', '+91 98450 78901', 'Inside', now_str, now_str),
        ('BUS-08', 'KA-05-AA-1008', 'Route 8 - Special Staff Shuttle', 'Karthik Nair', '+91 98450 89012', 'Outside', now_str, now_str)
    ]

    cursor.executemany("""
    INSERT INTO buses (bus_id, registration_no, route_name, driver_name, driver_contact, status, created_at, updated_at)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, sample_buses)

    # Realistic sample events for today
    today = now.date()
    sample_events = [
        ('BUS-01', 'KA-05-AA-1001', 'Route 1 - North Campus / Hebbal', 'Ramesh Sharma', 'ENTRY',
         (now - timedelta(hours=2, minutes=15)).strftime('%Y-%m-%d %H:%M:%S'),
         'Sensor 1 -> Sensor 2 (Entry pattern)', 'Hardware (HC-SR04)', '/static/img/sample_bus_1.svg', 'Morning arrival from Route 1'),

        ('BUS-02', 'KA-05-AA-1002', 'Route 2 - Central City / MG Road', 'Sunil Kumar', 'EXIT',
         (now - timedelta(hours=1, minutes=40)).strftime('%Y-%m-%d %H:%M:%S'),
         'Sensor 2 -> Sensor 1 (Exit pattern)', 'Hardware (HC-SR04)', '/static/img/sample_bus_2.svg', 'Departed for afternoon student pickup'),

        ('BUS-03', 'KA-05-AA-1003', 'Route 3 - West Suburbs / Rajajinagar', 'Anand Patil', 'ENTRY',
         (now - timedelta(hours=1, minutes=10)).strftime('%Y-%m-%d %H:%M:%S'),
         'Sensor 1 -> Sensor 2 (Entry pattern)', 'Hardware (HC-SR04)', '/static/img/sample_bus_1.svg', 'Routine entry verified at Main Gate'),

        ('BUS-04', 'KA-05-AA-1004', 'Route 4 - Tech Park / Electronic City', 'Mohammed Rafiq', 'ENTRY',
         (now - timedelta(minutes=45)).strftime('%Y-%m-%d %H:%M:%S'),
         'Manual Gate Trigger', 'Manual Verification', '/static/img/sample_bus_2.svg', 'Gate supervisor manual log'),

        ('BUS-05', 'KA-05-AA-1005', 'Route 5 - South Campus / Bannerghatta', 'Deepak Verma', 'EXIT',
         (now - timedelta(minutes=20)).strftime('%Y-%m-%d %H:%M:%S'),
         'Sensor 2 -> Sensor 1 (Exit pattern)', 'Hardware (HC-SR04)', '/static/img/sample_bus_1.svg', 'Maintenance check route departure')
    ]

    cursor.executemany("""
    INSERT INTO events (bus_id, bus_registration, route_name, driver_name, event_type, timestamp, sensor_trigger, confidence, photo_path, notes)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, sample_events)

    # Set default active bus to BUS-01
    cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('active_bus_id', 'BUS-01')")

    conn.commit()
    if close_at_end:
        conn.close()
