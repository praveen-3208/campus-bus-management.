"""
Android IP Webcam integration service.
Handles:
  - Connection testing with timeout and real error reporting
  - Automatic snapshot fetching on Entry/Exit events
  - Manual snapshot capture
  - Manual photo file uploads
  - Server-side image proxying to prevent CORS/mixed-content browser blocks
"""

import os
import time
import requests
from werkzeug.utils import secure_filename
from database import get_setting, set_setting

UPLOAD_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static', 'uploads', 'events')
os.makedirs(UPLOAD_DIR, exist_ok=True)

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp', 'bmp'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def get_camera_urls():
    """Returns normalized camera base URL, stream URL, and snapshot URL."""
    base_url = get_setting('camera_url', 'http://192.168.1.100:8080').strip().rstrip('/')
    stream_path = get_setting('camera_stream_path', '/video').strip()
    snapshot_path = get_setting('camera_snapshot_path', '/shot.jpg').strip()

    if not stream_path.startswith('/'):
        stream_path = '/' + stream_path
    if not snapshot_path.startswith('/'):
        snapshot_path = '/' + snapshot_path

    stream_url = f"{base_url}{stream_path}" if base_url else ""
    snapshot_url = f"{base_url}{snapshot_path}" if base_url else ""
    return base_url, stream_url, snapshot_url

def test_camera_connection(custom_url=None):
    """
    Tests actual connectivity to the IP Webcam server by requesting a snapshot.
    Returns: (is_connected: bool, message: str, latency_ms: int)
    """
    if custom_url:
        base_url = custom_url.strip().rstrip('/')
        snapshot_url = f"{base_url}/shot.jpg"
    else:
        base_url, _, snapshot_url = get_camera_urls()

    if not base_url:
        set_setting('camera_status', 'disconnected')
        return False, "Camera URL is not configured", 0

    # Ensure http:// or https:// prefix
    if not (snapshot_url.startswith('http://') or snapshot_url.startswith('https://')):
        snapshot_url = 'http://' + snapshot_url

    start_time = time.time()
    try:
        response = requests.get(snapshot_url, timeout=3.0)
        latency_ms = int((time.time() - start_time) * 1000)

        if response.status_code == 200 and 'image' in response.headers.get('Content-Type', '').lower():
            set_setting('camera_status', 'connected')
            set_setting('camera_last_tested', time.strftime('%Y-%m-%d %H:%M:%S'))
            return True, f"Connected to IP Webcam ({latency_ms}ms, {len(response.content)} bytes received)", latency_ms
        else:
            set_setting('camera_status', 'error')
            return False, f"Server responded with status {response.status_code} (Content-Type: {response.headers.get('Content-Type')})", latency_ms

    except requests.exceptions.ConnectTimeout:
        set_setting('camera_status', 'disconnected')
        return False, "Connection timed out (Check phone Wi-Fi IP and ensure IP Webcam app is running)", 0
    except requests.exceptions.ConnectionError:
        set_setting('camera_status', 'disconnected')
        return False, "Connection refused (Check IP address and port e.g. 8080)", 0
    except Exception as e:
        set_setting('camera_status', 'error')
        return False, f"Camera connection error: {str(e)}", 0

def capture_event_photo(bus_id, event_type):
    """
    Automatically captures a photo from the IP Webcam when an entry or exit event occurs.
    Returns: (photo_url or None, error_message or None)
    """
    enabled = get_setting('camera_enabled', 'true').lower() == 'true'
    if not enabled:
        return None, "Automatic camera capture is disabled in settings"

    _, _, snapshot_url = get_camera_urls()
    if not snapshot_url:
        return None, "Camera URL is not configured"

    try:
        response = requests.get(snapshot_url, timeout=3.5)
        if response.status_code == 200 and len(response.content) > 1000:
            timestamp_str = time.strftime('%Y%m%d_%H%M%S')
            safe_bus = "".join(c for c in bus_id if c.isalnum() or c in ('-', '_'))
            filename = f"event_{timestamp_str}_{safe_bus}_{event_type.lower()}.jpg"
            filepath = os.path.join(UPLOAD_DIR, filename)

            with open(filepath, 'wb') as f:
                f.write(response.content)

            photo_web_path = f"/static/uploads/events/{filename}"
            set_setting('camera_status', 'connected')
            return photo_web_path, None
        else:
            set_setting('camera_status', 'error')
            return None, f"Camera responded with status {response.status_code} during auto-capture"

    except requests.exceptions.Timeout:
        set_setting('camera_status', 'disconnected')
        return None, "Camera snapshot timed out (Device unreachable)"
    except requests.exceptions.ConnectionError:
        set_setting('camera_status', 'disconnected')
        return None, "Camera connection refused (Phone offline or app closed)"
    except Exception as e:
        set_setting('camera_status', 'error')
        return None, f"Failed to capture snapshot: {str(e)}"

def save_uploaded_photo(file_storage, bus_id, event_type):
    """
    Saves an uploaded photo file for a manual event or bus record.
    Returns: (photo_url, None) or (None, error_message)
    """
    if not file_storage or file_storage.filename == '':
        return None, "No file provided"

    if not allowed_file(file_storage.filename):
        return None, "Invalid file format. Allowed: JPG, PNG, WEBP, BMP"

    timestamp_str = time.strftime('%Y%m%d_%H%M%S')
    safe_bus = "".join(c for c in bus_id if c.isalnum() or c in ('-', '_'))
    ext = file_storage.filename.rsplit('.', 1)[1].lower()
    filename = f"upload_{timestamp_str}_{safe_bus}_{event_type.lower()}.{ext}"
    filepath = os.path.join(UPLOAD_DIR, filename)

    try:
        file_storage.save(filepath)
        photo_web_path = f"/static/uploads/events/{filename}"
        return photo_web_path, None
    except Exception as e:
        return None, f"Failed to save uploaded image: {str(e)}"

def fetch_live_snapshot():
    """
    Pulls a fresh snapshot frame directly from the camera to proxy to the client.
    Returns: (content_bytes, content_type) or (None, error_str)
    """
    _, _, snapshot_url = get_camera_urls()
    if not snapshot_url:
        return None, "Camera URL not configured"

    try:
        response = requests.get(snapshot_url, timeout=3.0)
        if response.status_code == 200:
            return response.content, response.headers.get('Content-Type', 'image/jpeg')
        return None, f"Camera status {response.status_code}"
    except Exception as e:
        return None, str(e)
