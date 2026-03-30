const COLORS = { present: '#10b981', late: '#f59e0b', absent: '#ef4444', excused: '#60a5fa' };
let curPeriod = 'today';
let curFilters = {};
let rawData = null;
const ssdValues = {};

// Chart instances
const donutChart = new Chart(document.getElementById('donutChart'), {
  type: 'doughnut',
  data: {
    labels: ['Present', 'Late', 'Absent', 'Excused'],
    datasets: [{
      data: [0, 0, 0, 0],
      backgroundColor: [COLORS.present, COLORS.late, COLORS.absent, COLORS.excused],
      borderColor: 'transparent',
      borderWidth: 2,
      hoverOffset: 6,
    }],
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
            return ` ${ctx.label}: ${ctx.parsed} (${t ? Math.round((ctx.parsed / t * 100)) : 0}%)`;
          },
        },
      },
    },
  },
});

const trendChart = new Chart(document.getElementById('trendChart'), {
  type: 'bar',
  data: {
    labels: [],
    datasets: [
      { label: 'Present', data: [], backgroundColor: COLORS.present + 'cc', borderRadius: 3, borderSkipped: false },
      { label: 'Late', data: [], backgroundColor: COLORS.late + 'cc', borderRadius: 3, borderSkipped: false },
      { label: 'Absent', data: [], backgroundColor: COLORS.absent + 'cc', borderRadius: 3, borderSkipped: false },
      { label: 'Excused', data: [], backgroundColor: COLORS.excused + 'cc', borderRadius: 3, borderSkipped: false },
    ],
  },
  options: {
    responsive: true,
    plugins: {
      legend: { labels: { color: '#94a3b8', font: { family: 'DM Sans', size: 11 }, boxWidth: 10 } },
      tooltip: { mode: 'index', intersect: false },
    },
    scales: {
      x: { stacked: true, ticks: { color: '#64748b', font: { family: 'Space Mono', size: 10 } }, grid: { color: 'rgba(255,255,255,.04)' } },
      y: { stacked: true, ticks: { color: '#64748b', font: { family: 'Space Mono', size: 10 } }, grid: { color: 'rgba(255,255,255,.06)' }, beginAtZero: true },
    },
  },
});

const subjChart = new Chart(document.getElementById('subjChart'), {
  type: 'bar',
  data: {
    labels: [],
    datasets: [
      { label: 'Present', data: [], backgroundColor: COLORS.present + 'cc', borderRadius: 3, borderSkipped: false },
      { label: 'Late', data: [], backgroundColor: COLORS.late + 'cc', borderRadius: 3, borderSkipped: false },
      { label: 'Absent', data: [], backgroundColor: COLORS.absent + 'cc', borderRadius: 3, borderSkipped: false },
      { label: 'Excused', data: [], backgroundColor: COLORS.excused + 'cc', borderRadius: 3, borderSkipped: false },
    ],
  },
  options: {
    responsive: true,
    maintainAspectRatio: false,
    indexAxis: 'y',
    plugins: {
      legend: { labels: { color: '#94a3b8', font: { family: 'DM Sans', size: 11 }, boxWidth: 10 } },
      tooltip: { mode: 'index', intersect: false },
    },
    scales: {
      x: { stacked: true, ticks: { color: '#64748b', font: { family: 'Space Mono', size: 10 } }, grid: { color: 'rgba(255,255,255,.04)' }, beginAtZero: true },
      y: { stacked: true, ticks: { color: '#64748b', font: { family: 'Space Mono', size: 10 } }, grid: { color: 'rgba(255,255,255,.06)' } },
    },
  },
});

function setLoading(on) {
  ['donutLoading', 'trendLoading', 'subjLoading'].forEach((id) => {
    document.getElementById(id).style.display = on ? 'flex' : 'none';
  });
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

async function loadStats() {
  setLoading(true);
  document.getElementById('donutContent').style.display = 'none';
  document.getElementById('donutNoData').classList.remove('show');
  document.getElementById('trendChart').style.display = 'none';
  document.getElementById('trendNoData').classList.remove('show');
  document.getElementById('subjChartScroll').style.display = 'none';
  document.getElementById('subjNoData').classList.remove('show');

  const params = getPeriodParams();
  const prog = ssdValues.gf_program || '';
  const yr = ssdValues.gf_year || '';
  const sec = ssdValues.gf_section || '';
  const tod = ssdValues.gf_timeofday || '';
  const subj = ssdValues.gf_subject || '';
  const instr = ssdValues.gf_instructor || '';

  if (prog && yr && sec) {
    params.append('section_key', `${prog}|${yr}|${sec}`);
  } else {
    if (prog) params.append('program', prog);
    if (yr) params.append('year', yr);
    if (sec) params.append('section_letter', sec);
  }
  if (subj) params.append('subject', subj);
  if (instr) params.append('instructor', instr);
  if (tod) params.append('time_of_day', tod);

  const expLink = document.getElementById('exportBtn');
  expLink.href = `/export/stats.xlsx?${params.toString()}&filename=${encodeURIComponent(buildExportFilename())}`;

  try {
    const r = await fetch(`/api/attendance/stats?${params.toString()}`);
    rawData = await r.json();
    renderAll(rawData);
  } catch (e) {
    console.warn(e);
  }
  setLoading(false);
}

function buildExportFilename() {
  const periods = { today: 'today', month: 'month', year: 'year', all: 'alltime' };
  const pLabel = periods[curPeriod] || curPeriod;
  const parts = ['attendance_analytics', pLabel];
  const prog = ssdValues.gf_program || '';
  const yr = ssdValues.gf_year || '';
  const sec = ssdValues.gf_section || '';
  const subj = ssdValues.gf_subject || '';
  const instr = ssdValues.gf_instructor || '';
  if (prog) parts.push(prog.replace(/[^a-zA-Z0-9]/g, '_').toLowerCase().substring(0, 10));
  if (yr) parts.push(yr.replace(' ', '').toLowerCase());
  if (sec) parts.push('sec' + sec.toLowerCase());
  if (subj) parts.push(subj.replace(/[^a-z0-9]/gi, '').toLowerCase().substring(0, 12));
  if (instr) parts.push(instr.split(' ')[0].toLowerCase());
  const now = new Date();
  parts.push(`exported_${now.getFullYear()}${String(now.getMonth() + 1).padStart(2, '0')}${String(now.getDate()).padStart(2, '0')}`);
  return parts.join('_') + '.xlsx';
}

function renderAll(data) {
  const d = data.donut;
  const total = d.present + d.late + d.absent + d.excused;
  const pct = (v) => (total ? Math.round((v / total * 100)) + '%' : '0%');
  document.getElementById('sc_present').textContent = d.present;
  document.getElementById('sc_late').textContent = d.late;
  document.getElementById('sc_absent').textContent = d.absent;
  document.getElementById('sc_excused').textContent = d.excused;
  document.getElementById('pct_present_box').textContent = pct(d.present) + ' of total';
  document.getElementById('pct_late_box').textContent = pct(d.late) + ' of total';
  document.getElementById('pct_absent_box').textContent = pct(d.absent) + ' of total';
  document.getElementById('pct_excused_box').textContent = pct(d.excused) + ' of total';
  const cnt = data.session_count;
  document.getElementById('sessionCountNum').textContent = cnt;
  document.getElementById('sessionCountNum_label').textContent = `${cnt} session${cnt !== 1 ? 's' : ''} found`;

  const periods = { today: 'Today', month: 'This Month', year: 'This Year', all: 'All Time' };
  const hasFilter = Object.values(ssdValues).some((v) => v);
  document.getElementById('showingMain').textContent = (periods[curPeriod] || curPeriod) + (hasFilter ? ' - Filtered' : ' - All Data');
  const parts = [];
  const prog = ssdValues.gf_program || '';
  const yr = ssdValues.gf_year || '';
  const sec = ssdValues.gf_section || '';
  const subj = ssdValues.gf_subject || '';
  const instr = ssdValues.gf_instructor || '';
  const tod = ssdValues.gf_timeofday || '';
  if (prog) parts.push('Program: ' + prog);
  if (yr) parts.push(yr);
  if (sec) parts.push('Section ' + sec);
  if (subj) parts.push('Subject: ' + subj);
  if (instr) parts.push('Instructor: ' + instr);
  if (tod) parts.push(tod.charAt(0).toUpperCase() + tod.slice(1));
  document.getElementById('showingDetail').textContent = parts.length ? parts.join(' - ') : 'Showing all data across every subject, section, and instructor.';

  const badge = document.getElementById('activeFilterBadge');
  if (badge) badge.textContent = parts.length ? `${parts.length} filter${parts.length > 1 ? 's' : ''} active` : '';

  if (!total) {
    document.getElementById('donutNoData').classList.add('show');
    document.getElementById('donutContent').style.display = 'none';
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
  renderTrend(data);
  renderSubject(data);
}

function renderTrend(data) {
  const keys = Object.keys(data.trend || {});
  const tc = document.getElementById('trendChart');
  if (!keys.length) {
    document.getElementById('trendNoData').classList.add('show');
    tc.style.display = 'none';
    return;
  }
  document.getElementById('trendNoData').classList.remove('show');
  tc.style.display = 'block';
  trendChart.data.labels = keys;
  ['present', 'late', 'absent', 'excused'].forEach((k, i) => {
    trendChart.data.datasets[i].data = keys.map((key) => (data.trend[key] || {})[k] || 0);
  });
  trendChart.update('active');
}

function renderSubject(data) {
  const entries = Object.entries(data.subjects || {}).sort((a, b) => a[0].localeCompare(b[0]));
  const keys = entries.map(([k]) => k);
  const vals = entries.map(([, v]) => v);
  const labels = keys.map((k) => (k.length > 26 ? k.substring(0, 24) + '...' : k));
  const sc = document.getElementById('subjChartScroll');
  if (!keys.length) {
    document.getElementById('subjNoData').classList.add('show');
    sc.style.display = 'none';
    return;
  }
  document.getElementById('subjNoData').classList.remove('show');
  sc.style.display = 'block';
  const canvasH = Math.max(180, keys.length * 38 + 60);
  subjChart.canvas.style.height = canvasH + 'px';
  subjChart.canvas.height = canvasH;
  subjChart.data.labels = labels;
  subjChart.data.datasets[0].data = vals.map((v) => v.present || 0);
  subjChart.data.datasets[1].data = vals.map((v) => v.late || 0);
  subjChart.data.datasets[2].data = vals.map((v) => v.absent || 0);
  subjChart.data.datasets[3].data = vals.map((v) => v.excused || 0);
  subjChart.update('active');
}

function switchPeriod(p, btn) {
  curPeriod = p;
  document.querySelectorAll('.pbtn').forEach((b) => b.classList.remove('active'));
  btn.classList.add('active');
  document.getElementById('monthPicker').classList.toggle('show', p === 'month');
  document.getElementById('yearPicker').classList.toggle('show', p === 'year');
}

function applyFilters() {
  curFilters = { ...ssdValues };
  loadStats();
}

function resetFilters() {
  ['gf_program', 'gf_year', 'gf_section', 'gf_subject', 'gf_instructor', 'gf_timeofday'].forEach((id) => {
    const defaults = {
      gf_program: 'All Programs',
      gf_year: 'All Years',
      gf_section: 'All Sections',
      gf_subject: 'All Subjects',
      gf_instructor: 'All Instructors',
      gf_timeofday: 'Any Time',
    };
    selectSSD(id, '', defaults[id]);
  });
  curFilters = {};
  loadStats();
}

function switchChart(id, btn) {
  document.querySelectorAll('.cpane').forEach((p) => p.classList.remove('active'));
  document.querySelectorAll('.ctab').forEach((b) => b.classList.remove('active'));
  document.getElementById('pane-' + id).classList.add('active');
  btn.classList.add('active');
  if (id === 'trend') trendChart.resize();
  if (id === 'subject') subjChart.update();
}

(function initMonthPicker() {
  document.getElementById('pickMonth').value = new Date().getMonth() + 1;
})();

applyFilters();

fetch('/api/block_number').then((r) => r.json()).then((d) => {
  if (d.block !== undefined) document.getElementById('blockNum').textContent = d.block;
}).catch(() => {});
setInterval(() => { if (rawData) loadStats(); }, 60000);

// Custom searchable dropdown engine
function toggleSSD(id) {
  const drop = document.getElementById('drop_' + id);
  const disp = document.getElementById('disp_' + id);
  const isOpen = drop.classList.contains('open');
  document.querySelectorAll('.search-select-dropdown.open').forEach((d) => {
    d.classList.remove('open');
    const dId = d.id.replace('drop_', '');
    const dd = document.getElementById('disp_' + dId);
    if (dd) dd.classList.remove('open');
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
  const opts = document.querySelectorAll(`#opts_${id} .ssd-opt`);
  let any = false;
  opts.forEach((o) => {
    if (o.classList.contains('no-match')) return;
    const m = !q || o.textContent.toLowerCase().includes(q);
    o.style.display = m ? '' : 'none';
    if (m) any = true;
  });
  let nm = document.querySelector(`#opts_${id} .no-match`);
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
  if (lbl) lbl.textContent = label;
  document.querySelectorAll(`#opts_${id} .ssd-opt`).forEach((o) => {
    o.classList.toggle('selected', o.dataset.value === value);
  });
  const drop = document.getElementById('drop_' + id);
  const disp = document.getElementById('disp_' + id);
  if (drop) drop.classList.remove('open');
  if (disp) disp.classList.remove('open');

  if (id === 'gf_program') {
    updateSectionLabel(value);
  }
}

function updateSectionLabel(program) {
  const hint = document.getElementById('label_gf_section');
  if (!hint) return;
  selectSSD('gf_section', '', 'All Sections');
}

document.addEventListener('click', (e) => {
  if (!e.target.closest('.search-select-wrap')) {
    document.querySelectorAll('.search-select-dropdown.open').forEach((d) => {
      d.classList.remove('open');
      const dId = d.id.replace('drop_', '');
      const dd = document.getElementById('disp_' + dId);
      if (dd) dd.classList.remove('open');
    });
  }
});
