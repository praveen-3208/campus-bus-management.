/**
 * Dashboard Page Logic: KPI cards, Charts, and Recent Activity Feed.
 */

let hourlyChartInstance = null;
let donutChartInstance = null;

async function loadDashboardData() {
  try {
    const res = await fetch('/api/status');
    if (!res.ok) throw new Error('Status endpoint error');
    const data = await res.json();

    // Populate KPIs
    document.getElementById('kpi-total-buses').innerText = data.counts.total_buses;
    document.getElementById('kpi-inside-buses').innerText = data.counts.buses_inside;
    document.getElementById('kpi-outside-buses').innerText = data.counts.buses_outside;
    document.getElementById('kpi-today-entries').innerText = data.counts.today_entries;
    document.getElementById('kpi-today-exits').innerText = data.counts.today_exits;

    // Occupancy donut counters
    document.getElementById('donut-inside-count').innerText = data.counts.buses_inside;
    document.getElementById('donut-outside-count').innerText = data.counts.buses_outside;

    // Active bus card
    if (data.active_bus) {
      document.getElementById('dash-active-bus-code').innerText = data.active_bus.bus_id;
      document.getElementById('dash-active-bus-details').innerText = 
        `(${data.active_bus.registration_no} • ${data.active_bus.route_name})`;
    }

    // Render Recent Events
    renderRecentEvents(data.recent_events);

    // Initialize or Update Charts
    updateOccupancyChart(data.counts.buses_inside, data.counts.buses_outside);
    fetchAndRenderHourlyChart();

  } catch (err) {
    console.error('Error loading dashboard:', err);
  }
}

function renderRecentEvents(events) {
  const tbody = document.getElementById('recent-activity-tbody');
  if (!tbody) return;

  if (!events || events.length === 0) {
    tbody.innerHTML = `
      <tr>
        <td colspan="8" style="text-align: center; color: #64748b; padding: 30px;">
          No movements recorded yet today. Use the buttons above or test sensors to log an event.
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
    const hasPhoto = Boolean(ev.photo_path);

    tr.innerHTML = `
      <td>
        <img src="${photoSrc}" alt="Snap" class="table-photo-thumb" 
             onclick="openImagePreview('${photoSrc}', '${ev.event_type} Snapshot', '${ev.bus_id}', '${ev.timestamp}')"
             title="${hasPhoto ? 'Click to inspect snapshot' : 'No photo captured'}">
      </td>
      <td><strong style="color: #0f172a;">${ev.bus_id}</strong></td>
      <td><span style="font-family: monospace; font-size: 13px; color: #334155;">${ev.bus_registration || '-'}</span></td>
      <td><span style="font-size: 13px; color: #475569;">${ev.route_name || '-'}</span></td>
      <td><span style="font-size: 13px;">${ev.driver_name || '-'}</span></td>
      <td>
        <span class="badge ${isEntry ? 'badge-entry' : 'badge-exit'}">
          <i class="fas fa-arrow-${isEntry ? 'down' : 'up'}"></i> ${ev.event_type}
        </span>
      </td>
      <td><span style="font-size: 13px; color: #64748b;">${ev.timestamp}</span></td>
      <td>
        <span style="font-size: 12px; color: #475569; background: #f1f5f9; padding: 3px 8px; border-radius: 4px;">
          ${ev.confidence || 'Sensor'}
        </span>
      </td>
    `;
    tbody.appendChild(tr);
  });
}

function updateOccupancyChart(inside, outside) {
  const ctx = document.getElementById('occupancyDonutChart');
  if (!ctx) return;

  const data = {
    labels: ['Inside Campus', 'Outside Campus'],
    datasets: [{
      data: [inside, outside],
      backgroundColor: ['#10b981', '#f59e0b'],
      borderWidth: 2,
      borderColor: '#ffffff'
    }]
  };

  if (donutChartInstance) {
    donutChartInstance.data = data;
    donutChartInstance.update();
  } else {
    donutChartInstance = new Chart(ctx, {
      type: 'doughnut',
      data: data,
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { display: false }
        },
        cutout: '72%'
      }
    });
  }
}

async function fetchAndRenderHourlyChart() {
  const ctx = document.getElementById('hourlyActivityChart');
  if (!ctx) return;

  try {
    const res = await fetch('/api/events?limit=200');
    const events = await res.json();

    // Group by hour
    const hours = ['06:00', '07:00', '08:00', '09:00', '10:00', '11:00', '12:00', '13:00', '14:00', '15:00', '16:00', '17:00', '18:00', '19:00'];
    const entriesByHour = Array(hours.length).fill(0);
    const exitsByHour = Array(hours.length).fill(0);

    const todayStr = new Date().toISOString().slice(0, 10);

    events.forEach(ev => {
      if (ev.timestamp && ev.timestamp.startsWith(todayStr)) {
        const timePart = ev.timestamp.split(' ')[1];
        if (timePart) {
          const hour = parseInt(timePart.split(':')[0], 10);
          const index = hour - 6; // 6 AM = index 0
          if (index >= 0 && index < hours.length) {
            if (ev.event_type === 'ENTRY') entriesByHour[index]++;
            if (ev.event_type === 'EXIT') exitsByHour[index]++;
          }
        }
      }
    });

    const chartData = {
      labels: hours,
      datasets: [
        {
          label: 'Entries',
          data: entriesByHour,
          backgroundColor: 'rgba(16, 185, 129, 0.75)',
          borderColor: '#10b981',
          borderRadius: 6
        },
        {
          label: 'Exits',
          data: exitsByHour,
          backgroundColor: 'rgba(239, 68, 68, 0.75)',
          borderColor: '#ef4444',
          borderRadius: 6
        }
      ]
    };

    if (hourlyChartInstance) {
      hourlyChartInstance.data = chartData;
      hourlyChartInstance.update();
    } else {
      hourlyChartInstance = new Chart(ctx, {
        type: 'bar',
        data: chartData,
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: {
            legend: {
              position: 'top',
              labels: { boxWidth: 12, font: { size: 12 } }
            }
          },
          scales: {
            x: {
              grid: { display: false }
            },
            y: {
              beginAtZero: true,
              ticks: { stepSize: 1 }
            }
          }
        }
      });
    }
  } catch (err) {
    console.error('Error fetching hourly chart:', err);
  }
}

// Quick Gate Action Trigger
async function quickLogEvent(eventType) {
  try {
    const res = await fetch('/api/events', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        event_type: eventType,
        notes: 'Dashboard quick-action button'
      })
    });

    const data = await res.json();
    if (res.ok) {
      showToast(`Logged ${eventType} for ${data.event.bus_id}!`, 'success');
      loadDashboardData();
      updateGlobalStatus();
    } else {
      showToast(data.error || 'Failed to record event', 'error');
    }
  } catch (err) {
    showToast('Network error: ' + err.message, 'error');
  }
}

// Listen to custom background update
window.addEventListener('systemStatusUpdated', (e) => {
  const data = e.detail;
  if (!data) return;

  document.getElementById('kpi-total-buses').innerText = data.counts.total_buses;
  document.getElementById('kpi-inside-buses').innerText = data.counts.buses_inside;
  document.getElementById('kpi-outside-buses').innerText = data.counts.buses_outside;
  document.getElementById('kpi-today-entries').innerText = data.counts.today_entries;
  document.getElementById('kpi-today-exits').innerText = data.counts.today_exits;
});

document.addEventListener('DOMContentLoaded', () => {
  loadDashboardData();
});
