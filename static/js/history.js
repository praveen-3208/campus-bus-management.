/**
 * Movement History Page Logic: Search, Filters, CSV Export, and Delete Actions.
 */

let searchTimeout = null;

async function fetchHistory() {
  const query = document.getElementById('history-search-input').value.trim();
  const eventType = document.getElementById('history-type-filter').value;
  const dateVal = document.getElementById('history-date-filter').value;
  const limit = document.getElementById('history-limit-filter').value;

  let url = `/api/events?limit=${limit}`;
  if (query) url += `&bus_id=${encodeURIComponent(query)}`;
  if (eventType) url += `&event_type=${encodeURIComponent(eventType)}`;
  if (dateVal) url += `&date=${encodeURIComponent(dateVal)}`;

  try {
    const res = await fetch(url);
    const events = await res.json();
    renderHistoryTable(events);
    document.getElementById('history-count-badge').innerText = events.length;
  } catch (err) {
    showToast('Failed to load history: ' + err.message, 'error');
  }
}

function renderHistoryTable(events) {
  const tbody = document.getElementById('history-table-body');
  if (!tbody) return;

  if (events.length === 0) {
    tbody.innerHTML = `
      <tr>
        <td colspan="11" style="text-align: center; color: #64748b; padding: 40px;">
          No transit records found matching current filters.
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
      <td><span style="font-family: monospace; color: #64748b; font-size: 12px;">#${ev.id}</span></td>
      <td>
        <img src="${photoSrc}" alt="Snap" class="table-photo-thumb"
             onclick="openImagePreview('${photoSrc}', '${ev.event_type} Snapshot', '${ev.bus_id}', '${ev.timestamp}')"
             title="Click to view full photo">
      </td>
      <td><strong style="color: #0f172a; font-size: 14px;">${ev.bus_id}</strong></td>
      <td><span style="font-family: monospace; color: #334155; font-size: 13px;">${ev.bus_registration || '-'}</span></td>
      <td>
        <span class="badge ${isEntry ? 'badge-entry' : 'badge-exit'}">
          <i class="fas fa-arrow-${isEntry ? 'down' : 'up'}"></i> ${ev.event_type}
        </span>
      </td>
      <td><span style="font-size: 13px;">${ev.route_name || '-'}</span></td>
      <td><span style="font-size: 13px;">${ev.driver_name || '-'}</span></td>
      <td>
        <div style="font-size: 12px; font-weight: 600; color: #1e293b;">${ev.sensor_trigger || '-'}</div>
        <div style="font-size: 11px; color: #64748b;">${ev.confidence || ''}</div>
      </td>
      <td><span style="font-size: 13px; color: #64748b; white-space: nowrap;">${ev.timestamp}</span></td>
      <td><span style="font-size: 12px; color: #64748b;">${ev.notes || '-'}</span></td>
      <td style="text-align: right;">
        <button class="btn btn-sm btn-outline" style="color: #ef4444; padding: 4px 8px;" onclick="deleteSingleEvent(${ev.id})" title="Delete Record">
          <i class="fas fa-trash-alt"></i>
        </button>
      </td>
    `;
    tbody.appendChild(tr);
  });
}

function debouncedHistorySearch() {
  clearTimeout(searchTimeout);
  searchTimeout = setTimeout(() => {
    fetchHistory();
  }, 300);
}

function resetHistoryFilters() {
  document.getElementById('history-search-input').value = '';
  document.getElementById('history-type-filter').value = '';
  document.getElementById('history-date-filter').value = '';
  document.getElementById('history-limit-filter').value = '100';
  fetchHistory();
}

async function deleteSingleEvent(eventId) {
  if (!confirm(`Delete transit record #${eventId}?`)) return;

  try {
    const res = await fetch(`/api/events/${eventId}`, { method: 'DELETE' });
    const data = await res.json();
    if (res.ok) {
      showToast(data.message, 'success');
      fetchHistory();
    } else {
      showToast(data.error || 'Failed to delete record', 'error');
    }
  } catch (err) {
    showToast('Error: ' + err.message, 'error');
  }
}

function openClearHistoryModal() {
  openModal('clear-history-modal');
}

async function confirmClearHistory() {
  try {
    const res = await fetch('/api/events/clear', { method: 'POST' });
    const data = await res.json();
    if (res.ok) {
      showToast(data.message, 'success');
      closeModal('clear-history-modal');
      fetchHistory();
      updateGlobalStatus();
    } else {
      showToast(data.error || 'Failed to clear logs', 'error');
    }
  } catch (err) {
    showToast('Error: ' + err.message, 'error');
  }
}

document.addEventListener('DOMContentLoaded', () => {
  fetchHistory();
});
