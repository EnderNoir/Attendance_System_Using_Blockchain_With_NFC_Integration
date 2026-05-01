const COLORS = { present: '#10b981', late: '#f59e0b', absent: '#ef4444', excused: '#60a5fa' };
let curPeriod = 'today';
let curParamStr = '';
let rawData = null;

const donutChart = new Chart(document.getElementById('donutChart'), {
  type: 'doughnut',
  data: {
    labels: ['Present', 'Late', 'Absent', 'Excused'],
    datasets: [{
      data: [0, 0, 0, 0],
      backgroundColor: [COLORS.present, COLORS.late, COLORS.absent, COLORS.excused],
      borderColor: '#1a1d24',
      borderWidth: 3,
      hoverOffset: 6
    }]
  },
  options: {
    responsive: true,
    cutout: '68%',
    plugins: {
      legend: { display: false },
      tooltip: {
        callbacks: {
          label: (ctx) => {
            const t = ctx.dataset.data.reduce((a, b) => a + b, 0);
            return ` ${ctx.label}: ${ctx.parsed} (${t ? Math.round((ctx.parsed / t) * 100) : 0}%)`;
          }
        }
      }
    }
  }
});

const trendChart = new Chart(document.getElementById('trendChart'), {
  type: 'bar',
  data: {
    labels: [],
    datasets: [
      { label: 'Present', data: [], backgroundColor: COLORS.present + 'cc', borderRadius: 3, borderSkipped: false },
      { label: 'Late', data: [], backgroundColor: COLORS.late + 'cc', borderRadius: 3, borderSkipped: false },
      { label: 'Absent', data: [], backgroundColor: COLORS.absent + 'cc', borderRadius: 3, borderSkipped: false },
      { label: 'Excused', data: [], backgroundColor: COLORS.excused + 'cc', borderRadius: 3, borderSkipped: false }
    ]
  },
  options: {
    responsive: true,
    plugins: {
      legend: { labels: { color: '#94a3b8', font: { family: 'DM Sans', size: 11 }, boxWidth: 10, boxHeight: 10 } },
      tooltip: { mode: 'index', intersect: false }
    },
    scales: {
      x: {
        stacked: true,
        ticks: { color: '#64748b', font: { family: 'Space Mono', size: 10 } },
        grid: { color: 'rgba(255,255,255,.04)' }
      },
      y: {
        stacked: true,
        ticks: { color: '#64748b', font: { family: 'Space Mono', size: 10 } },
        grid: { color: 'rgba(255,255,255,.06)' },
        beginAtZero: true
      }
    }
  }
});

const subjChart = new Chart(document.getElementById('subjChart'), {
  type: 'bar',
  data: {
    labels: [],
    datasets: [
      { label: 'Present', data: [], backgroundColor: COLORS.present + 'cc', borderRadius: 3, borderSkipped: false },
      { label: 'Late', data: [], backgroundColor: COLORS.late + 'cc', borderRadius: 3, borderSkipped: false },
      { label: 'Absent', data: [], backgroundColor: COLORS.absent + 'cc', borderRadius: 3, borderSkipped: false },
      { label: 'Excused', data: [], backgroundColor: COLORS.excused + 'cc', borderRadius: 3, borderSkipped: false }
    ]
  },
  options: {
    responsive: true,
    maintainAspectRatio: false,
    indexAxis: 'y',
    plugins: {
      legend: { labels: { color: '#94a3b8', font: { family: 'DM Sans', size: 11 }, boxWidth: 10, boxHeight: 10 } },
      tooltip: { mode: 'index', intersect: false }
    },
    scales: {
      x: {
        stacked: true,
        ticks: { color: '#64748b', font: { family: 'Space Mono', size: 10 } },
        grid: { color: 'rgba(255,255,255,.04)' },
        beginAtZero: true
      },
      y: {
        stacked: true,
        ticks: { color: '#64748b', font: { family: 'Space Mono', size: 10 } },
        grid: { color: 'rgba(255,255,255,.06)' }
      }
    }
  }
});

function setLoading(on) {
  ['donutLoading', 'trendLoading', 'subjLoading'].forEach((id) => {
    document.getElementById(id).style.display = on ? 'flex' : 'none';
  });
}

async function loadStats(period, extra) {
  setLoading(true);
  const params = new URLSearchParams({ period });
  const enr = document.getElementById('tf_enrollment')?.value;
  if (enr) params.append('enrollment_type', enr);
  if (extra) {
    for (const [k, v] of Object.entries(extra)) {
      if (v) {
        params.append(k, v);
      }
    }
  }
  curParamStr = params.toString();
  try {
    const r = await fetch(`/api/attendance/stats?${curParamStr}`);
    rawData = await r.json();
    renderAll(rawData);
  } catch (e) {
    console.warn(e);
  }
  setLoading(false);
}

function renderAll(data) {
  const d = data.donut;
  const total = d.present + d.late + d.absent + d.excused;
  document.getElementById('sc_present').textContent = d.present;
  document.getElementById('sc_late').textContent = d.late;
  document.getElementById('sc_absent').textContent = d.absent;
  document.getElementById('sc_excused').textContent = d.excused;
  document.getElementById('sessionCountBadge').textContent = `${data.session_count} session${data.session_count !== 1 ? 's' : ''} · ${data.period}`;
  document.getElementById('exportBtn').href = `/export/stats.csv?${curParamStr}`;

  if (!total) {
    document.getElementById('donutNoData').classList.add('show');
  } else {
    document.getElementById('donutNoData').classList.remove('show');
    donutChart.data.datasets[0].data = [d.present, d.late, d.absent, d.excused];
    donutChart.update('active');
    ['present', 'late', 'absent', 'excused'].forEach((k) => {
      document.getElementById('leg_' + k).textContent = d[k];
      document.getElementById('pct_' + k).textContent = total ? `(${Math.round((d[k] / total) * 100)}%)` : '';
    });
  }

  const sel = document.getElementById('tf_subject');
  const cur = sel.value;
  while (sel.options.length > 1) {
    sel.remove(1);
  }
  (data.all_subjects || []).forEach((s) => {
    sel.add(new Option(s.length > 38 ? s.substring(0, 36) + '…' : s, s));
  });
  if (cur) {
    sel.value = cur;
  }

  renderTrend(data);
  renderSubject(data);
}

function renderTrend(data) {
  const keys = Object.keys(data.trend || {});
  document.getElementById('trendNoData').classList.toggle('show', keys.length === 0);
  if (!keys.length) {
    return;
  }
  trendChart.data.labels = keys;
  ['present', 'late', 'absent', 'excused'].forEach((k, i) => {
    trendChart.data.datasets[i].data = keys.map((key) => (data.trend[key] || {})[k] || 0);
  });
  trendChart.update('active');
}

function applyTrendFilter() {
  const extra = {
    subject: document.getElementById('tf_subject').value,
    section_key: document.getElementById('tf_section').value,
    enrollment_type: document.getElementById('tf_enrollment').value,
    year_level: document.getElementById('tf_year').value,
    instructor: document.getElementById('tf_instructor').value
  };
  loadStats(curPeriod, extra);
}

function resetTrendFilter() {
  ['tf_subject', 'tf_section', 'tf_enrollment', 'tf_year', 'tf_instructor'].forEach((id) => {
    const el = document.getElementById(id);
    if (el) {
      el.value = '';
    }
  });
  loadStats(curPeriod);
}

function renderSubject(data) {
  let entries = Object.entries(data.subjects || {});
  const course = document.getElementById('sf_course').value;
  const status = document.getElementById('sf_status').value;
  const sortBy = document.getElementById('sf_sort').value;
  if (course === 'BS Computer Science') {
    entries = entries.filter(([k]) => k.toLowerCase().includes('cs') || k.toLowerCase().includes('computer'));
  } else if (course === 'BS Information Technology') {
    entries = entries.filter(([k]) => k.toLowerCase().includes('it') || k.toLowerCase().includes('info'));
  }
  if (sortBy === 'present_desc') entries.sort((a, b) => b[1].present - a[1].present);
  else if (sortBy === 'absent_desc') entries.sort((a, b) => b[1].absent - a[1].absent);
  else if (sortBy === 'sessions_desc') entries.sort((a, b) => b[1].sessions - a[1].sessions);
  else entries.sort((a, b) => a[0].localeCompare(b[0]));

  const keys = entries.map(([k]) => k);
  const vals = entries.map(([, v]) => v);
  const shortKeys = keys.map((k) => (k.length > 26 ? k.substring(0, 24) + '…' : k));
  document.getElementById('subjNoData').classList.toggle('show', keys.length === 0);
  if (!keys.length) {
    return;
  }

  const barH = 36;
  const canvasH = Math.max(160, keys.length * barH + 60);
  subjChart.canvas.style.height = canvasH + 'px';
  subjChart.canvas.height = canvasH;

  subjChart.data.labels = shortKeys;
  const idx = { present: 0, late: 1, absent: 2, excused: 3 };
  subjChart.data.datasets[0].data = vals.map((v) => v.present || 0);
  subjChart.data.datasets[1].data = vals.map((v) => v.late || 0);
  subjChart.data.datasets[2].data = vals.map((v) => v.absent || 0);
  subjChart.data.datasets[3].data = vals.map((v) => v.excused || 0);
  if (status !== 'all' && status) {
    subjChart.data.datasets.forEach((d, i) => {
      d.hidden = i !== idx[status];
    });
  } else {
    subjChart.data.datasets.forEach((d) => {
      d.hidden = false;
    });
  }
  subjChart.update('active');
}

function applySubjectFilter() {
  if (rawData) {
    renderSubject(rawData);
  }
}

function resetSubjectFilter() {
  ['sf_course', 'sf_status', 'sf_sort'].forEach((id) => {
    const el = document.getElementById(id);
    if (el) {
      el.value = id === 'sf_sort' ? 'name' : id === 'sf_status' ? 'all' : '';
    }
  });
  if (rawData) {
    renderSubject(rawData);
  }
}

function switchPeriod(p, btn) {
  curPeriod = p;
  document.querySelectorAll('.ptab').forEach((b) => b.classList.remove('active'));
  btn.classList.add('active');
  document.getElementById('monthPicker').classList.toggle('show', p === 'month');
  document.getElementById('yearPicker').classList.toggle('show', p === 'year');
  if (p !== 'month' && p !== 'year') {
    loadStats(p);
  }
}

function applyPeriodPick() {
  if (curPeriod === 'month') {
    const m = document.getElementById('pickMonth').value;
    const y = document.getElementById('pickMonthYear').value;
    loadStats('month', { month: m, year_num: y });
  } else if (curPeriod === 'year') {
    const y = document.getElementById('pickYear').value;
    loadStats('year', { year_num: y });
  }
}

(function initMonthPicker() {
  const now = new Date();
  document.getElementById('pickMonth').value = now.getMonth() + 1;
})();

function switchChart(id, btn) {
  document.querySelectorAll('.chart-pane').forEach((p) => p.classList.remove('active'));
  document.querySelectorAll('.ctab').forEach((b) => b.classList.remove('active'));
  document.getElementById('pane-' + id).classList.add('active');
  btn.classList.add('active');
  if (id === 'trend') {
    trendChart.resize();
  }
  if (id === 'subject') {
    subjChart.update();
  }
}

loadStats('today');
fetch('/api/block_number')
  .then((r) => r.json())
  .then((d) => {
    if (d.block !== undefined) {
      document.getElementById('blockNum').textContent = d.block;
    }
  })
  .catch(() => {});
setInterval(() => loadStats(curPeriod), 30000);
