/**
 * Live Gate Monitoring Logic: Ultrasonic Visualizer, Simulator, and Events Stream.
 */

let pollInterval = null;
let currentCooldownTotal = 6.0;

async function refreshMonitoringState() {
  try {
    const res = await fetch('/api/status');
    if (!res.ok) return;
    const data = await res.json();

    // 1. Update Active Bus Card
    if (data.active_bus) {
      document.getElementById('mon-bus-code').innerText = data.active_bus.bus_id;
      document.getElementById('mon-bus-reg').innerText = data.active_bus.registration_no;
      document.getElementById('mon-bus-route').innerText = data.active_bus.route_name;
      document.getElementById('mon-bus-driver').innerText = data.active_bus.driver_name;
      document.getElementById('mon-bus-phone').innerText = data.active_bus.driver_contact;

      const isInside = data.active_bus.status === 'Inside';
      const statusBadge = document.getElementById('mon-bus-status');
      statusBadge.className = `badge ${isInside ? 'badge-inside' : 'badge-outside'}`;
      statusBadge.innerText = data.active_bus.status;
    }

    // 2. Update Sensor Gate Visualizer
    const gate = data.gate_sensor;
    if (gate) {
      // Sensor 1 visual state
      const s1Box = document.getElementById('sensor-1-box');
      const s1Status = document.getElementById('sensor-1-status');
      if (gate.s1_active) {
        s1Box.classList.add('active');
        s1Status.className = 'badge badge-entry';
        s1Status.innerText = 'TRIGGERED';
      } else {
        s1Box.classList.remove('active');
        s1Status.className = 'badge badge-neutral';
        s1Status.innerText = 'IDLE';
      }

      // Sensor 2 visual state
      const s2Box = document.getElementById('sensor-2-box');
      const s2Status = document.getElementById('sensor-2-status');
      if (gate.s2_active) {
        s2Box.classList.add('active');
        s2Status.className = 'badge badge-entry';
        s2Status.innerText = 'TRIGGERED';
      } else {
        s2Box.classList.remove('active');
        s2Status.className = 'badge badge-neutral';
        s2Status.innerText = 'IDLE';
      }

      // Gate Master Status Badge
      const masterBadge = document.getElementById('gate-main-status-badge');
      masterBadge.className = 'direction-badge-live';
      if (gate.gate_status === 'COOLDOWN') {
        masterBadge.innerText = `COOLDOWN • ${gate.cooldown_remaining}s`;
        masterBadge.style.background = '#f59e0b';
        masterBadge.style.color = '#fff';
      } else if (gate.gate_status === 'S1_WAITING') {
        masterBadge.innerText = 'BEAM 1 BROKEN • WAITING S2';
        masterBadge.style.background = '#0284c7';
        masterBadge.style.color = '#fff';
      } else if (gate.gate_status === 'S2_WAITING') {
        masterBadge.innerText = 'BEAM 2 BROKEN • WAITING S1';
        masterBadge.style.background = '#0284c7';
        masterBadge.style.color = '#fff';
      } else if (gate.last_event_type === 'ENTRY' && gate.in_cooldown) {
        masterBadge.className = 'direction-badge-live entry-active';
        masterBadge.innerText = 'ENTRY CONFIRMED';
      } else if (gate.last_event_type === 'EXIT' && gate.in_cooldown) {
        masterBadge.className = 'direction-badge-live exit-active';
        masterBadge.innerText = 'EXIT CONFIRMED';
      } else {
        masterBadge.innerText = 'IDLE • GATE CLEAR';
        masterBadge.style.background = '#334155';
        masterBadge.style.color = '#94a3b8';
      }

      // Cooldown Progress Bar
      const cooldownText = document.getElementById('cooldown-status-text');
      const cooldownSeconds = document.getElementById('cooldown-timer-seconds');
      const cooldownBar = document.getElementById('cooldown-progress-bar');

      if (gate.in_cooldown) {
        cooldownText.innerText = 'Debouncing Duplicate Triggers';
        cooldownText.style.color = '#f59e0b';
        cooldownSeconds.innerText = `${gate.cooldown_remaining}s`;
        const percent = Math.min(100, (gate.cooldown_remaining / currentCooldownTotal) * 100);
        cooldownBar.style.width = `${percent}%`;
      } else {
        cooldownText.innerText = 'Gate Ready For Detection';
        cooldownText.style.color = '#10b981';
        cooldownSeconds.innerText = '0.0s';
        cooldownBar.style.width = '0%';
      }

      // Config stats
      document.getElementById('info-max-gap').innerText = gate.max_gap_sec;
      document.getElementById('info-threshold').innerText = gate.threshold_cm;
    }

    // 3. Update Recent Events Table
    renderMonitoringEvents(data.recent_events);

  } catch (err) {
    console.error('Monitoring refresh error:', err);
  }
}

function renderMonitoringEvents(events) {
  const tbody = document.getElementById('live-monitoring-events-tbody');
  if (!tbody) return;

  if (!events || events.length === 0) {
    tbody.innerHTML = `
      <tr>
        <td colspan="8" style="text-align: center; color: #64748b; padding: 24px;">
          No events recorded yet.
        </td>
      </tr>
    `;
    return;
  }

  tbody.innerHTML = '';
  events.forEach(ev => {
    const isEntry = ev.event_type === 'ENTRY';
    const tr = document.createElement('tr');
    const photoSrc = ev.photo_path || '/static/img/bus_logo.svg';

    tr.innerHTML = `
      <td>
        <img src="${photoSrc}" alt="Snap" class="table-photo-thumb"
             onclick="openImagePreview('${photoSrc}', '${ev.event_type} Photo', '${ev.bus_id}', '${ev.timestamp}')"
             title="Click to inspect snapshot">
      </td>
      <td><strong>${ev.bus_id}</strong></td>
      <td><span style="font-family: monospace; color: #334155;">${ev.bus_registration || '-'}</span></td>
      <td>
        <span class="badge ${isEntry ? 'badge-entry' : 'badge-exit'}">
          <i class="fas fa-arrow-${isEntry ? 'down' : 'up'}"></i> ${ev.event_type}
        </span>
      </td>
      <td><span style="font-size: 12px; color: #475569;">${ev.sensor_trigger || '-'}</span></td>
      <td>${ev.driver_name || '-'}</td>
      <td><span style="font-size: 13px; color: #64748b;">${ev.timestamp}</span></td>
      <td><span style="font-size: 12px; color: #64748b;">${ev.notes || '-'}</span></td>
    `;
    tbody.appendChild(tr);
  });
}

// Simulation: Send Raw Distance reading to backend
async function simulateRawSensor(sensorName, distance) {
  try {
    const res = await fetch('/api/sensor-event', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        sensor: sensorName,
        distance: distance,
        device_id: 'WEB-SIMULATOR'
      })
    });
    const data = await res.json();
    if (data.status === 'detected') {
      showToast(`${data.direction} detected! Recorded for active bus.`, 'success');
    } else if (data.status === 'debounced') {
      showToast(data.message, 'warning');
    } else {
      showToast(data.message || 'Sensor reading received', 'info');
    }
    refreshMonitoringState();
  } catch (err) {
    showToast('Simulation error: ' + err.message, 'error');
  }
}

// Simulation: Full transit sequence (S1 -> S2 for Entry, S2 -> S1 for Exit)
async function simulateFullSequence(direction) {
  const isEntry = direction === 'ENTRY';
  const firstSensor = isEntry ? 's1' : 's2';
  const secondSensor = isEntry ? 's2' : 's1';

  showToast(`Simulating ${direction} transit: vehicle approaching ${isEntry ? 'Outer' : 'Inner'} sensor...`, 'info');

  // Trigger first sensor
  await simulateRawSensor(firstSensor, 32.0);

  // Wait 750ms and trigger second sensor
  setTimeout(async () => {
    await simulateRawSensor(secondSensor, 30.0);
    refreshMonitoringState();
  }, 750);
}

// Manual Event Trigger (supervisor override)
async function triggerDirectManual(direction) {
  try {
    const res = await fetch('/api/events', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        event_type: direction,
        notes: 'Manual supervisor trigger on Live Gate'
      })
    });
    const data = await res.json();
    if (res.ok) {
      showToast(`Manual ${direction} logged for ${data.event.bus_id}`, 'success');
      refreshMonitoringState();
      updateGlobalStatus();
    } else {
      showToast(data.error || 'Failed to record event', 'error');
    }
  } catch (err) {
    showToast('Error: ' + err.message, 'error');
  }
}

// Camera mini-preview helpers
function refreshMiniCamSnapshot() {
  const img = document.getElementById('mini-cam-feed');
  if (img) {
    img.src = `/api/camera/proxy-snapshot?t=${Date.now()}`;
  }
}

function handleMiniCamError() {
  const label = document.getElementById('mini-cam-status-label');
  if (label) label.innerText = 'Camera Offline / Placeholder Shown';
}

document.addEventListener('DOMContentLoaded', () => {
  refreshMonitoringState();
  pollInterval = setInterval(refreshMonitoringState, 1500);

  // Refresh camera mini snapshot every 4s
  setInterval(refreshMiniCamSnapshot, 4000);
});
