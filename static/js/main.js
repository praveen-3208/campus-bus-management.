/**
 * Global JavaScript utilities, hardware status polling, toasts, and modals.
 */

// Toast notification helper
function showToast(message, type = 'info') {
  const container = document.getElementById('toast-container');
  if (!container) return;

  const toast = document.createElement('div');
  toast.className = `toast toast-${type}`;
  
  let icon = 'info-circle';
  if (type === 'success') icon = 'check-circle';
  if (type === 'error') icon = 'exclamation-circle';
  if (type === 'warning') icon = 'exclamation-triangle';

  toast.innerHTML = `
    <i class="fas fa-${icon}" style="font-size: 16px;"></i>
    <div style="flex: 1;">${message}</div>
    <button onclick="this.parentElement.remove()" style="background: none; border: none; color: #94a3b8; cursor: pointer;">
      <i class="fas fa-times"></i>
    </button>
  `;

  container.appendChild(toast);

  setTimeout(() => {
    toast.style.opacity = '0';
    toast.style.transition = 'opacity 0.3s ease';
    setTimeout(() => toast.remove(), 300);
  }, 4000);
}

// Modal open/close helpers
function openModal(modalId) {
  const modal = document.getElementById(modalId);
  if (modal) {
    modal.classList.add('active');
    document.body.style.overflow = 'hidden';
  }
}

function closeModal(modalId) {
  const modal = document.getElementById(modalId);
  if (modal) {
    modal.classList.remove('active');
    document.body.style.overflow = '';
  }
}

// Global Image Preview Modal
function openImagePreview(src, title = 'Event Photo', busId = '', timestamp = '') {
  const modal = document.getElementById('global-image-modal');
  if (!modal) return;

  document.getElementById('global-modal-img').src = src;
  document.getElementById('global-modal-title').innerText = title;
  document.getElementById('global-modal-desc').innerText = `${busId ? 'Bus: ' + busId : ''} ${timestamp ? ' • ' + timestamp : ''}`;
  openModal('global-image-modal');
}

// Active Bus Switcher
async function openActiveBusSwitcher() {
  try {
    const res = await fetch('/api/buses');
    const buses = await res.json();
    const listContainer = document.getElementById('active-bus-options-list');
    if (!listContainer) return;

    listContainer.innerHTML = '';
    buses.forEach(b => {
      const item = document.createElement('div');
      item.style.padding = '12px 14px';
      item.style.border = '1px solid #e2e8f0';
      item.style.borderRadius = '8px';
      item.style.marginBottom = '8px';
      item.style.display = 'flex';
      item.style.justifyContent = 'space-between';
      item.style.alignItems = 'center';
      item.style.cursor = 'pointer';
      item.style.transition = 'all 0.2s';
      item.className = 'bus-select-row';

      const isInside = b.status === 'Inside';
      item.innerHTML = `
        <div>
          <div style="font-weight: 700; color: #0f172a;">${b.bus_id} <span style="font-weight: 500; font-size: 13px; color: #64748b;">(${b.registration_no})</span></div>
          <div style="font-size: 12px; color: #64748b;">${b.route_name} • Driver: ${b.driver_name}</div>
        </div>
        <div style="display: flex; align-items: center; gap: 10px;">
          <span class="badge ${isInside ? 'badge-inside' : 'badge-outside'}">${b.status}</span>
          <button class="btn btn-sm btn-primary" onclick="selectActiveBus('${b.bus_id}')">Select</button>
        </div>
      `;
      listContainer.appendChild(item);
    });

    openModal('active-bus-modal');
  } catch (err) {
    showToast('Failed to load buses: ' + err.message, 'error');
  }
}

async function selectActiveBus(busId) {
  try {
    const res = await fetch('/api/buses/set-active-by-code', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ bus_id: busId })
    });
    const data = await res.json();
    if (res.ok) {
      showToast(data.message, 'success');
      closeModal('active-bus-modal');
      updateGlobalStatus();
      if (typeof refreshMonitoringState === 'function') refreshMonitoringState();
    } else {
      showToast(data.error || 'Failed to set active bus', 'error');
    }
  } catch (err) {
    showToast('Error setting active bus: ' + err.message, 'error');
  }
}

// Global System Status Poller (every 4 seconds)
async function updateGlobalStatus() {
  try {
    const res = await fetch('/api/status');
    if (!res.ok) return;
    const data = await res.json();

    // Update Header Active Bus
    const headerActiveBusEl = document.getElementById('header-active-bus-name');
    if (headerActiveBusEl && data.active_bus) {
      headerActiveBusEl.innerText = `${data.active_bus.bus_id} (${data.active_bus.registration_no})`;
    }

    // Update ESP32 status pill
    const esp32Pill = document.getElementById('header-esp32-pill');
    const esp32Text = document.getElementById('header-esp32-text');
    if (esp32Pill && esp32Text) {
      const isOnline = data.hardware.esp32.status === 'online';
      esp32Pill.className = `status-pill ${isOnline ? 'online' : 'offline'}`;
      esp32Text.innerText = isOnline ? 'ESP32 Online' : 'ESP32 Offline';
    }

    // Update Camera status pill
    const camPill = document.getElementById('header-camera-pill');
    const camText = document.getElementById('header-camera-text');
    if (camPill && camText) {
      const isConnected = data.hardware.camera.status === 'connected';
      camPill.className = `status-pill ${isConnected ? 'online' : 'offline'}`;
      camText.innerText = isConnected ? 'Camera Live' : 'Camera Disconnected';
    }

    // Update live clock
    const clockEl = document.getElementById('header-clock');
    if (clockEl) {
      const now = new Date();
      clockEl.innerText = now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
    }

    // Dispatch event for page-specific hooks
    window.dispatchEvent(new CustomEvent('systemStatusUpdated', { detail: data }));
  } catch (err) {
    // Silent fail on network blip
  }
}

// Mobile sidebar toggle
document.addEventListener('DOMContentLoaded', () => {
  const toggleBtn = document.getElementById('mobile-menu-toggle');
  const sidebar = document.getElementById('app-sidebar');
  if (toggleBtn && sidebar) {
    toggleBtn.addEventListener('click', () => {
      sidebar.classList.toggle('mobile-open');
    });

    // Close on outside click
    document.addEventListener('click', (e) => {
      if (sidebar.classList.contains('mobile-open') && !sidebar.contains(e.target) && !toggleBtn.contains(e.target)) {
        sidebar.classList.remove('mobile-open');
      }
    });
  }

  // Start status polling
  updateGlobalStatus();
  setInterval(updateGlobalStatus, 4000);
});
