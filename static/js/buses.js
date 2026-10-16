/**
 * Bus Management: CRUD, Search, Filter, and Gate Activation.
 */

let allBuses = [];
let currentActiveBusId = '';

async function fetchBuses() {
  try {
    // Get current status to know active bus
    const statusRes = await fetch('/api/status');
    if (statusRes.ok) {
      const statusData = await statusRes.json();
      currentActiveBusId = statusData.active_bus ? statusData.active_bus.bus_id : '';
    }

    const res = await fetch('/api/buses');
    allBuses = await res.json();
    renderBuses(allBuses);
    document.getElementById('bus-count-badge').innerText = allBuses.length;
  } catch (err) {
    showToast('Failed to load bus records: ' + err.message, 'error');
  }
}

function renderBuses(buses) {
  const tbody = document.getElementById('buses-table-body');
  if (!tbody) return;

  if (buses.length === 0) {
    tbody.innerHTML = `
      <tr>
        <td colspan="8" style="text-align: center; color: #64748b; padding: 40px;">
          No buses found matching your query.
        </td>
      </tr>
    `;
    return;
  }

  tbody.innerHTML = '';
  buses.forEach(b => {
    const isInside = b.status === 'Inside';
    const isActive = b.bus_id === currentActiveBusId;
    const tr = document.createElement('tr');

    tr.innerHTML = `
      <td>
        ${isActive ? 
          `<span class="badge" style="background: #eff6ff; color: #2563eb; border: 1px solid #bfdbfe;">
             <i class="fas fa-check-circle"></i> ACTIVE TARGET
           </span>` :
          `<button class="btn btn-sm btn-outline" style="padding: 3px 8px; font-size: 11px;" onclick="setActiveBusDirect(${b.id})" title="Set as target bus for sensor detections">
             <i class="fas fa-crosshairs"></i> Set Active
           </button>`
        }
      </td>
      <td>
        <strong style="color: #0f172a; font-size: 15px;">${b.bus_id}</strong>
      </td>
      <td>
        <span style="font-family: monospace; font-size: 13px; font-weight: 600; color: #334155;">
          ${b.registration_no}
        </span>
      </td>
      <td>
        <span style="color: #1e293b; font-weight: 500;">${b.route_name}</span>
      </td>
      <td>${b.driver_name}</td>
      <td>
        <a href="tel:${b.driver_contact}" style="color: var(--blue-primary); text-decoration: none; font-size: 13px;">
          <i class="fas fa-phone-alt" style="font-size: 11px;"></i> ${b.driver_contact}
        </a>
      </td>
      <td>
        <span class="badge ${isInside ? 'badge-inside' : 'badge-outside'}" style="cursor: pointer;" onclick="toggleBusStatus(${b.id})" title="Click to toggle status">
          <i class="fas fa-circle" style="font-size: 8px;"></i> ${b.status}
        </span>
      </td>
      <td style="text-align: right; white-space: nowrap;">
        <button class="btn btn-sm btn-outline" onclick="openEditBusModal(${b.id})" title="Edit Bus Details">
          <i class="fas fa-edit"></i>
        </button>
        <button class="btn btn-sm btn-outline" style="color: #ef4444;" onclick="openDeleteBusModal(${b.id}, '${b.bus_id}')" title="Delete Bus">
          <i class="fas fa-trash-alt"></i>
        </button>
      </td>
    `;
    tbody.appendChild(tr);
  });
}

function filterBuses() {
  const query = document.getElementById('bus-search-input').value.toLowerCase().trim();
  const statusFilter = document.getElementById('bus-status-filter').value;

  const filtered = allBuses.filter(b => {
    const matchesQuery = !query || 
      b.bus_id.toLowerCase().includes(query) ||
      b.registration_no.toLowerCase().includes(query) ||
      b.route_name.toLowerCase().includes(query) ||
      b.driver_name.toLowerCase().includes(query);

    const matchesStatus = !statusFilter || b.status === statusFilter;
    return matchesQuery && matchesStatus;
  });

  renderBuses(filtered);
}

function openAddBusModal() {
  document.getElementById('bus-modal-title').innerText = 'Register New Bus';
  document.getElementById('bus-form-submit-btn').innerText = 'Register Bus';
  document.getElementById('bus-edit-pk').value = '';
  document.getElementById('bus-id-input').value = '';
  document.getElementById('bus-id-input').disabled = false;
  document.getElementById('bus-reg-input').value = '';
  document.getElementById('bus-route-input').value = '';
  document.getElementById('bus-driver-input').value = '';
  document.getElementById('bus-contact-input').value = '';
  document.getElementById('bus-status-input').value = 'Inside';
  openModal('bus-form-modal');
}

function openEditBusModal(pkId) {
  const bus = allBuses.find(b => b.id === pkId);
  if (!bus) return;

  document.getElementById('bus-modal-title').innerText = `Edit Bus ${bus.bus_id}`;
  document.getElementById('bus-form-submit-btn').innerText = 'Save Changes';
  document.getElementById('bus-edit-pk').value = bus.id;
  document.getElementById('bus-id-input').value = bus.bus_id;
  document.getElementById('bus-id-input').disabled = true; // Bus ID is unique identifier
  document.getElementById('bus-reg-input').value = bus.registration_no;
  document.getElementById('bus-route-input').value = bus.route_name;
  document.getElementById('bus-driver-input').value = bus.driver_name;
  document.getElementById('bus-contact-input').value = bus.driver_contact;
  document.getElementById('bus-status-input').value = bus.status;
  openModal('bus-form-modal');
}

async function handleBusFormSubmit(e) {
  e.preventDefault();
  const pkId = document.getElementById('bus-edit-pk').value;
  const isEdit = Boolean(pkId);

  const payload = {
    bus_id: document.getElementById('bus-id-input').value.trim().toUpperCase(),
    registration_no: document.getElementById('bus-reg-input').value.trim().toUpperCase(),
    route_name: document.getElementById('bus-route-input').value.trim(),
    driver_name: document.getElementById('bus-driver-input').value.trim(),
    driver_contact: document.getElementById('bus-contact-input').value.trim(),
    status: document.getElementById('bus-status-input').value
  };

  try {
    let url = '/api/buses';
    let method = 'POST';

    if (isEdit) {
      url = `/api/buses/${pkId}`;
      method = 'PUT';
    }

    const res = await fetch(url, {
      method: method,
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });

    const data = await res.json();
    if (res.ok) {
      showToast(data.message || 'Bus saved successfully!', 'success');
      closeModal('bus-form-modal');
      fetchBuses();
      updateGlobalStatus();
    } else {
      showToast(data.error || 'Failed to save bus', 'error');
    }
  } catch (err) {
    showToast('Network error: ' + err.message, 'error');
  }
}

async function setActiveBusDirect(pkId) {
  try {
    const res = await fetch(`/api/buses/${pkId}/set-active`, { method: 'POST' });
    const data = await res.json();
    if (res.ok) {
      showToast(data.message, 'success');
      currentActiveBusId = data.active_bus_id;
      renderBuses(allBuses);
      updateGlobalStatus();
    } else {
      showToast(data.error || 'Failed to set active bus', 'error');
    }
  } catch (err) {
    showToast('Error: ' + err.message, 'error');
  }
}

async function toggleBusStatus(pkId) {
  try {
    const res = await fetch(`/api/buses/${pkId}/toggle-status`, { method: 'POST' });
    const data = await res.json();
    if (res.ok) {
      showToast(data.message, 'info');
      fetchBuses();
    } else {
      showToast(data.error || 'Failed to toggle status', 'error');
    }
  } catch (err) {
    showToast('Error: ' + err.message, 'error');
  }
}

function openDeleteBusModal(pkId, busCode) {
  document.getElementById('bus-delete-pk').value = pkId;
  document.getElementById('bus-delete-code').innerText = busCode;
  openModal('bus-delete-modal');
}

async function confirmDeleteBus() {
  const pkId = document.getElementById('bus-delete-pk').value;
  try {
    const res = await fetch(`/api/buses/${pkId}`, { method: 'DELETE' });
    const data = await res.json();
    if (res.ok) {
      showToast(data.message, 'success');
      closeModal('bus-delete-modal');
      fetchBuses();
      updateGlobalStatus();
    } else {
      showToast(data.error || 'Failed to delete bus', 'error');
    }
  } catch (err) {
    showToast('Error: ' + err.message, 'error');
  }
}

document.addEventListener('DOMContentLoaded', () => {
  fetchBuses();
});
