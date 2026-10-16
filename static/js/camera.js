/**
 * Android IP Webcam Integration: Connection tester, stream player, snapshot gallery.
 */

let streamMode = 'proxy'; // 'proxy' or 'direct'
let proxyStreamTimer = null;
let currentBaseUrl = '';
let currentStreamUrl = '';

async function loadCameraSettings() {
  try {
    const res = await fetch('/api/status');
    const data = await res.json();
    const cam = data.hardware.camera;

    currentBaseUrl = cam.base_url || 'http://192.168.1.100:8080';
    currentStreamUrl = cam.stream_url;

    document.getElementById('cam-url-input').value = currentBaseUrl;
    document.getElementById('cam-stream-path').value = cam.stream_url.replace(currentBaseUrl, '') || '/video';
    document.getElementById('cam-snapshot-path').value = cam.snapshot_url.replace(currentBaseUrl, '') || '/shot.jpg';
    document.getElementById('cam-enabled-checkbox').checked = cam.enabled;

    // External link
    const extLink = document.getElementById('external-camera-link');
    extLink.href = currentBaseUrl || '#';

    // Update connection indicator
    updateCameraStatusUI(cam.status === 'connected', cam.last_tested);

    // Load gallery
    loadSnapshotGallery();

    // Start stream display
    applyStreamMode();

  } catch (err) {
    console.error('Error loading camera settings:', err);
  }
}

function updateCameraStatusUI(isConnected, detailText = '') {
  const overlayDot = document.getElementById('cam-overlay-dot');
  const overlayText = document.getElementById('cam-overlay-text');
  const statusText = document.getElementById('cam-current-status-text');

  if (isConnected) {
    overlayDot.style.background = 'var(--status-green)';
    overlayText.innerText = 'CAMERA LIVE (IP WEBCAM)';
    statusText.innerText = 'Connected';
    statusText.style.color = '#10b981';
  } else {
    overlayDot.style.background = 'var(--status-red)';
    overlayText.innerText = 'CAMERA DISCONNECTED';
    statusText.innerText = 'Disconnected';
    statusText.style.color = '#ef4444';
  }
}

async function testCameraDirect() {
  const url = document.getElementById('cam-url-input').value.trim();
  if (!url) {
    showToast('Please enter an IP Webcam URL to test', 'warning');
    return;
  }

  showToast('Testing camera connection to ' + url + '...', 'info');

  try {
    const res = await fetch('/api/camera/test', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ camera_url: url })
    });

    const data = await res.json();
    if (data.connected) {
      showToast(data.message, 'success');
      updateCameraStatusUI(true);
      document.getElementById('cam-latency-tag').innerText = `(${data.latency_ms}ms)`;
      forceSnapshotRefresh();
    } else {
      showToast(data.message || 'Could not connect to camera', 'error');
      updateCameraStatusUI(false);
      document.getElementById('cam-latency-tag').innerText = '(Failed)';
    }
  } catch (err) {
    showToast('Test failed: ' + err.message, 'error');
    updateCameraStatusUI(false);
  }
}

async function saveCameraConfig(e) {
  e.preventDefault();
  const url = document.getElementById('cam-url-input').value.trim();
  const streamPath = document.getElementById('cam-stream-path').value.trim();
  const snapshotPath = document.getElementById('cam-snapshot-path').value.trim();
  const enabled = document.getElementById('cam-enabled-checkbox').checked;

  try {
    const res = await fetch('/api/camera/configure', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        camera_url: url,
        camera_stream_path: streamPath,
        camera_snapshot_path: snapshotPath,
        camera_enabled: enabled
      })
    });

    const data = await res.json();
    if (res.ok) {
      showToast('Camera settings saved! ' + (data.test_result || ''), data.connected ? 'success' : 'warning');
      currentBaseUrl = data.camera_url;
      currentStreamUrl = data.stream_url;
      document.getElementById('external-camera-link').href = currentBaseUrl;
      updateCameraStatusUI(data.connected);
      applyStreamMode();
      updateGlobalStatus();
    } else {
      showToast(data.error || 'Failed to save camera settings', 'error');
    }
  } catch (err) {
    showToast('Error saving camera settings: ' + err.message, 'error');
  }
}

function toggleStreamMode() {
  if (streamMode === 'proxy') {
    streamMode = 'direct';
    document.getElementById('stream-mode-label').innerText = 'Direct Stream';
  } else {
    streamMode = 'proxy';
    document.getElementById('stream-mode-label').innerText = 'Proxy Snapshot';
  }
  applyStreamMode();
  showToast(`Switched to ${streamMode.toUpperCase()} mode`, 'info');
}

function applyStreamMode() {
  const feed = document.getElementById('main-camera-feed');
  if (!feed) return;

  if (proxyStreamTimer) {
    clearInterval(proxyStreamTimer);
    proxyStreamTimer = null;
  }

  if (streamMode === 'direct' && currentStreamUrl) {
    // Direct MJPEG stream from Android phone
    feed.src = currentStreamUrl;
  } else {
    // Proxy snapshot mode through Flask backend
    forceSnapshotRefresh();
    proxyStreamTimer = setInterval(forceSnapshotRefresh, 2000);
  }
}

function forceSnapshotRefresh() {
  const feed = document.getElementById('main-camera-feed');
  if (feed) {
    feed.src = `/api/camera/proxy-snapshot?t=${Date.now()}`;
  }
}

function handleMainCamError() {
  updateCameraStatusUI(false);
}

// Instant Photo Capture
async function triggerInstantCapture() {
  showToast('Requesting instant snapshot from Android camera...', 'info');

  try {
    const res = await fetch('/api/camera/capture', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ event_type: 'MANUAL_SNAP' })
    });

    const data = await res.json();
    if (res.ok && data.captured) {
      showToast('Photo captured and saved!', 'success');
      
      // Show latest capture preview
      const card = document.getElementById('latest-capture-card');
      card.style.display = 'block';
      document.getElementById('latest-capture-img').src = data.photo_path;
      document.getElementById('latest-capture-bus').innerText = `Bus: ${data.bus_id}`;
      document.getElementById('latest-capture-time').innerText = data.timestamp;

      loadSnapshotGallery();
      updateGlobalStatus();
    } else {
      showToast(data.error || 'Failed to capture photo (Is camera connected?)', 'error');
    }
  } catch (err) {
    showToast('Capture error: ' + err.message, 'error');
  }
}

// Manual File Upload
async function handleManualUpload(e) {
  e.preventDefault();
  const fileInput = document.getElementById('manual-photo-file');
  if (!fileInput.files || fileInput.files.length === 0) {
    showToast('Please select a photo file to upload', 'warning');
    return;
  }

  const formData = new FormData();
  formData.append('photo', fileInput.files[0]);
  formData.append('bus_id', 'MANUAL');
  formData.append('event_type', 'UPLOAD');

  try {
    const res = await fetch('/api/camera/upload', {
      method: 'POST',
      body: formData
    });

    const data = await res.json();
    if (res.ok) {
      showToast('Photo uploaded successfully!', 'success');
      fileInput.value = '';
      loadSnapshotGallery();
    } else {
      showToast(data.error || 'Upload failed', 'error');
    }
  } catch (err) {
    showToast('Upload error: ' + err.message, 'error');
  }
}

// Gallery Loader
async function loadSnapshotGallery() {
  const container = document.getElementById('camera-gallery-grid');
  if (!container) return;

  try {
    const res = await fetch('/api/events?limit=24');
    const events = await res.json();
    const photos = events.filter(e => e.photo_path);

    if (photos.length === 0) {
      container.innerHTML = `
        <div style="text-align: center; color: #64748b; padding: 40px; grid-column: 1 / -1;">
          No snapshots recorded yet. Capture a photo or trigger gate entries to build gallery.
        </div>
      `;
      return;
    }

    container.innerHTML = '';
    photos.forEach(item => {
      const card = document.createElement('div');
      card.style.background = '#ffffff';
      card.style.border = '1px solid #e2e8f0';
      card.style.borderRadius = '8px';
      card.style.overflow = 'hidden';
      card.style.boxShadow = '0 2px 4px rgba(0,0,0,0.05)';

      const isEntry = item.event_type === 'ENTRY';
      card.innerHTML = `
        <div style="height: 130px; background: #000; overflow: hidden; cursor: pointer;"
             onclick="openImagePreview('${item.photo_path}', '${item.event_type} Snapshot', '${item.bus_id}', '${item.timestamp}')">
          <img src="${item.photo_path}" alt="Snap" style="width: 100%; height: 100%; object-fit: cover; transition: transform 0.2s;" onmouseover="this.style.transform='scale(1.05)'" onmouseout="this.style.transform='scale(1)'">
        </div>
        <div style="padding: 10px 12px; font-size: 12px;">
          <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 4px;">
            <strong style="font-size: 13px; color: #0f172a;">${item.bus_id}</strong>
            <span class="badge ${isEntry ? 'badge-entry' : 'badge-exit'}" style="font-size: 9px;">${item.event_type}</span>
          </div>
          <div style="color: #64748b; font-size: 11px;">${item.timestamp}</div>
        </div>
      `;
      container.appendChild(card);
    });
  } catch (err) {
    console.error('Error loading gallery:', err);
  }
}

document.addEventListener('DOMContentLoaded', () => {
  loadCameraSettings();
});
