// Clock
function tick() {
  const cd = document.getElementById('liveDate');
  if (cd) {
    cd.textContent = new Date().toLocaleDateString([], {
      weekday: 'long',
      month: 'long',
      day: 'numeric',
      year: 'numeric'
    });
  }
}
tick();

// Block height
async function fetchBlockHeight() {
  try {
    const r = await fetch('/api/block_number');
    const d = await r.json();
    const el = document.getElementById('blockHeightVal');
    if (el) {
      el.textContent = d.block !== null && d.block !== undefined ? d.block : '—';
    }
  } catch (e) {
    // silent
  }
}
fetchBlockHeight();
setInterval(fetchBlockHeight, 10000);

// Charts setup
const C = { present: '#10b981', late: '#f59e0b', absent: '#ef4444', excused: '#60a5fa' };
const donutChart = new Chart(document.getElementById('donutChart'), {
  type: 'doughnut',
  data: {
    labels: ['Present', 'Late', 'Absent', 'Excused'],
    datasets: [{
      data: [0, 0, 0, 0],
      backgroundColor: [C.present, C.late, C.absent, C.excused],
      borderColor: 'transparent',
      borderWidth: 2,
      hoverOffset: 6
    }]
  },
  options: {
    responsive: false,
    cutout: '65%',
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
      { label: 'Present', data: [], backgroundColor: C.present + 'cc', borderRadius: 3, borderSkipped: false },
      { label: 'Late', data: [], backgroundColor: C.late + 'cc', borderRadius: 3, borderSkipped: false },
      { label: 'Absent', data: [], backgroundColor: C.absent + 'cc', borderRadius: 3, borderSkipped: false },
      { label: 'Excused', data: [], backgroundColor: C.excused + 'cc', borderRadius: 3, borderSkipped: false }
    ]
  },
  options: {
    responsive: true,
    plugins: {
      legend: { labels: { color: '#94a3b8', font: { family: 'DM Sans', size: 11 }, boxWidth: 10 } },
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
      { label: 'Present', data: [], backgroundColor: C.present + 'cc', borderRadius: 3, borderSkipped: false },
      { label: 'Late', data: [], backgroundColor: C.late + 'cc', borderRadius: 3, borderSkipped: false },
      { label: 'Absent', data: [], backgroundColor: C.absent + 'cc', borderRadius: 3, borderSkipped: false },
      { label: 'Excused', data: [], backgroundColor: C.excused + 'cc', borderRadius: 3, borderSkipped: false }
    ]
  },
  options: {
    responsive: true,
    maintainAspectRatio: false,
    indexAxis: 'y',
    plugins: {
      legend: { labels: { color: '#94a3b8', font: { family: 'DM Sans', size: 11 }, boxWidth: 10 } },
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

// Period / filter state
let curPeriod = 'all';

// Stores exact params from the most recent apply, so export matches the current view.
let lastAppliedParams = null;

function switchPeriod(p, btn) {
  curPeriod = p;
  document.querySelectorAll('.pbtn').forEach((b) => b.classList.remove('active'));
  btn.classList.add('active');
  document.getElementById('monthPicker').classList.toggle('show', p === 'month');
  document.getElementById('yearPicker').classList.toggle('show', p === 'year');
}

function getPeriodParams() {
  const p = new URLSearchParams({ period: curPeriod });
  if (curPeriod === 'month') {
    p.append('month', document.getElementById('pickMonth').value);
    p.append('year_num', document.getElementById('pickMonthYear').value);
  } else if (curPeriod === 'year') {
    p.append('year_num', document.getElementById('pickYear').value);
  }
  return p;
}

const ssdValues = {};

function toggleSSD(id) {
  const drop = document.getElementById('drop_' + id);
  const disp = document.getElementById('disp_' + id);
  const isOpen = drop.classList.contains('open');
  document.querySelectorAll('.search-select-dropdown.open').forEach((d) => {
    d.classList.remove('open');
    const dd = document.getElementById('disp_' + d.id.replace('drop_', ''));
    if (dd) {
      dd.classList.remove('open');
    }
  });
  if (!isOpen) {
    drop.classList.add('open');
    disp.classList.add('open');
    const inp = drop.querySelector('.ssd-input');
    if (inp) {
      inp.value = '';
      inp.focus();
      filterSSDOpts(id, '');
    }
  }
}

function filterSSDOpts(id, query) {
  const q = query.toLowerCase();
  const opts = document.querySelectorAll('#opts_' + id + ' .ssd-opt');
  let any = false;
  opts.forEach((o) => {
    if (o.classList.contains('no-match')) {
      return;
    }
    const m = !q || o.textContent.toLowerCase().includes(q);
    o.style.display = m ? '' : 'none';
    if (m) {
      any = true;
    }
  });
  let nm = document.querySelector('#opts_' + id + ' .no-match');
  if (!any) {
    if (!nm) {
      nm = document.createElement('div');
      nm.className = 'ssd-opt no-match';
      nm.textContent = 'No matches found';
      document.getElementById('opts_' + id).appendChild(nm);
    }
    nm.style.display = '';
  } else if (nm) {
    nm.style.display = 'none';
  }
}

function selectSSD(id, value, label) {
  ssdValues[id] = value;
  const lbl = document.getElementById('label_' + id);
  if (lbl) {
    lbl.textContent = label;
  }
  document.querySelectorAll('#opts_' + id + ' .ssd-opt').forEach((o) => o.classList.toggle('selected', o.dataset.value === value));
  const drop = document.getElementById('drop_' + id);
  const disp = document.getElementById('disp_' + id);
  if (drop) {
    drop.classList.remove('open');
  }
  if (disp) {
    disp.classList.remove('open');
  }
}

document.addEventListener('click', function (e) {
  if (!e.target.closest('.search-select-wrap')) {
    document.querySelectorAll('.search-select-dropdown.open').forEach((d) => {
      d.classList.remove('open');
      const dd = document.getElementById('disp_' + d.id.replace('drop_', ''));
      if (dd) {
        dd.classList.remove('open');
      }
    });
  }
});

// Apply filters -> fetch stats -> render charts
async function applyFilters() {
  const params = getPeriodParams();
  const prog = ssdValues.f_program || '';
  const yr = ssdValues.f_year || '';
  const sec = ssdValues.f_section || '';
  const subj = ssdValues.f_subject || '';
  const sem = ssdValues.f_semester || '';
  if (prog) params.append('program', prog);
  if (yr) params.append('year', yr);
  if (sec) params.append('section_letter', sec);
  if (subj) params.append('subject', subj);
  if (sem) params.append('semester', sem);

  lastAppliedParams = params.toString();

  ['trendLoading', 'subjLoading'].forEach((id) => {
    const el = document.getElementById(id);
    if (el) {
      el.style.display = 'flex';
    }
  });
  document.getElementById('trendChart').style.display = 'none';
  document.getElementById('subjScroll').style.display = 'none';
  document.getElementById('donutContent').style.display = 'none';
  ['trendNoData', 'subjNoData', 'donutNoData'].forEach((id) => document.getElementById(id).classList.remove('show'));
  try {
    const r = await fetch('/api/attendance/stats?' + params.toString(), { credentials: 'same-origin' });
    const d = await r.json();
    renderAll(d, subj, sec, tod);
  } catch (e) {
    console.error(e);
  }
  ['trendLoading', 'subjLoading'].forEach((id) => {
    const el = document.getElementById(id);
    if (el) {
      el.style.display = 'none';
    }
  });
}

function resetFilters() {
  ['f_program', 'f_year', 'f_section', 'f_subject', 'f_semester'].forEach((id) => {
    ssdValues[id] = '';
    const lbl = document.getElementById('label_' + id);
    if (lbl) {
      lbl.textContent = {
        f_program: 'All Programs',
        f_year: 'All Years',
        f_section: 'All Sections',
        f_subject: 'All Subjects',
        f_semester: 'All Semesters'
      }[id];
    }
    document.querySelectorAll('#opts_' + id + ' .ssd-opt').forEach((o) => o.classList.toggle('selected', o.dataset.value === ''));
  });
  applyFilters();
}

// Uses the most recent applied params so export matches the visible charts.
function exportDashboard() {
  const btn = document.getElementById('btnExport');
  btn.disabled = true;
  btn.innerHTML = '<i class="bi bi-hourglass-split"></i> Exporting…';

  const qs = lastAppliedParams || (() => {
    const p = getPeriodParams();
    const prog = ssdValues.f_program || '';
    const yr = ssdValues.f_year || '';
    const sec = ssdValues.f_section || '';
    const subj = ssdValues.f_subject || '';
    const sem = ssdValues.f_semester || '';
    if (prog) p.append('program', prog);
    if (yr) p.append('year', yr);
    if (sec) p.append('section_letter', sec);
    if (subj) p.append('subject', subj);
    if (sem) p.append('semester', sem);
    return p.toString();
  })();

  const a = document.createElement('a');
  a.href = '/export/stats.xlsx?' + qs;
  a.style.display = 'none';
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);

  setTimeout(() => {
    btn.disabled = false;
    btn.innerHTML = '<i class="bi bi-file-earmark-excel"></i> Export';
  }, 2000);
}

// Render all charts with data from API
function renderAll(data, subj, sec, tod) {
  const d = data.donut;
  const total = d.present + d.late + d.absent + d.excused;
  const pct = (v) => (total ? Math.round((v / total) * 100) + '%' : '0%');
  document.getElementById('sc_present').textContent = d.present;
  document.getElementById('sc_late').textContent = d.late;
  document.getElementById('sc_absent').textContent = d.absent;
  document.getElementById('sc_excused').textContent = d.excused;
  const cnt = data.session_count;
  document.getElementById('sessCountLabel').textContent = cnt + ' session' + (cnt !== 1 ? 's' : '') + ' found';
  document.getElementById('sb_num').textContent = cnt;
  const periods = { today: 'Today', month: 'This Month', year: 'This Year', all: 'All Time' };
  const parts = [];
  if (subj) parts.push('Subject: ' + subj);
  if (sec) parts.push('Section: ' + sec.split('|').pop());
  if (tod) parts.push('Semester: ' + tod);
  document.getElementById('sb_main').textContent = (periods[curPeriod] || curPeriod) + (parts.length ? ' — Filtered' : '');
  document.getElementById('sb_sub').textContent = parts.length ? parts.join(' · ') : 'Showing all your sessions';
  document.getElementById('showingBar').style.display = 'flex';
  document.getElementById('showingSub').textContent = cnt + ' session' + (cnt !== 1 ? 's' : '') + ' · ' + document.getElementById('sb_sub').textContent;

  if (!total) {
    document.getElementById('donutNoData').classList.add('show');
  } else {
    document.getElementById('donutNoData').classList.remove('show');
    document.getElementById('donutContent').style.display = 'block';
    donutChart.data.datasets[0].data = [d.present, d.late, d.absent, d.excused];
    donutChart.update('active');
    ['present', 'late', 'absent', 'excused'].forEach((k) => {
      document.getElementById('leg_' + k).textContent = d[k];
      document.getElementById('pct_' + k).textContent = '(' + pct(d[k]) + ')';
    });
  }

  const keys = Object.keys(data.trend || {});
  if (!keys.length) {
    document.getElementById('trendNoData').classList.add('show');
  } else {
    const tc = document.getElementById('trendChart');
    tc.style.display = 'block';
    trendChart.data.labels = keys;
    ['present', 'late', 'absent', 'excused'].forEach((k, i) => {
      trendChart.data.datasets[i].data = keys.map((key) => (data.trend[key] || {})[k] || 0);
    });
    trendChart.update('active');
  }

  const entries = Object.entries(data.subjects || {}).sort((a, b) => a[0].localeCompare(b[0]));
  if (!entries.length) {
    document.getElementById('subjNoData').classList.add('show');
  } else {
    const sc = document.getElementById('subjScroll');
    sc.style.display = 'block';
    const labels = entries.map(([k]) => (k.length > 28 ? k.substring(0, 26) + '…' : k));
    const vals = entries.map(([, v]) => v);
    const h = Math.max(180, entries.length * 40 + 60);
    subjChart.canvas.style.height = h + 'px';
    subjChart.canvas.height = h;
    subjChart.data.labels = labels;
    subjChart.data.datasets[0].data = vals.map((v) => v.present || 0);
    subjChart.data.datasets[1].data = vals.map((v) => v.late || 0);
    subjChart.data.datasets[2].data = vals.map((v) => v.absent || 0);
    subjChart.data.datasets[3].data = vals.map((v) => v.excused || 0);
    subjChart.update('active');
  }
}

function switchChart(id, btn) {
  document.querySelectorAll('.cpane').forEach((p) => p.classList.remove('active'));
  document.querySelectorAll('.ctab').forEach((b) => b.classList.remove('active'));
  document.getElementById('pane-' + id).classList.add('active');
  btn.classList.add('active');
  if (id === 'trend') trendChart.resize();
  if (id === 'subject') subjChart.update();
}

(function initPeriodDefaults() {
  document.getElementById('pickMonth').value = new Date().getMonth() + 1;
})();

applyFilters();
