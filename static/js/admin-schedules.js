/* -- DATA -- */
  const SCHEDULE_BOOTSTRAP = window.ADMIN_SCHEDULES_BOOTSTRAP || {};
  const ALL_SCHEDULES = Array.isArray(SCHEDULE_BOOTSTRAP.schedules) ? SCHEDULE_BOOTSTRAP.schedules : [];
  const ALL_SUBJECTS = SCHEDULE_BOOTSTRAP.subjects || {};
  const ALL_TEACHERS = SCHEDULE_BOOTSTRAP.teachers || {};
  const DOW_NAMES = Array.isArray(SCHEDULE_BOOTSTRAP.dowList)
    ? SCHEDULE_BOOTSTRAP.dowList
    : ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'];
  const IS_SUPER = !!SCHEDULE_BOOTSTRAP.canManageSchedules;
  const TEACHER_VIEW = !!SCHEDULE_BOOTSTRAP.teacherView;

  /* -- TIME UTILS -- */
  function to24h(t) {
    if (!t) return '00:00';
    if (t.includes(':') && !t.toLowerCase().includes('m')) return t.substring(0, 5);
    const m = t.match(/(\d{1,2}):(\d{2})\s*([ap]m?)/i);
    if (!m) return t.substring(0, 5);
    let h = parseInt(m[1]), mn = m[2], pm = m[3].toLowerCase().startsWith('p');
    if (pm && h !== 12) h += 12; if (!pm && h === 12) h = 0;
    return (h < 10 ? '0' : '') + h + ':' + mn;
  }
  function fmtTime(t) {
    if (!t) return '';
    const [h, m] = t.split(':').map(Number);
    const ap = h >= 12 ? 'PM' : 'AM'; const hh = h % 12 || 12;
    return hh + ':' + (m < 10 ? '0' + m : m) + ' ' + ap;
  }
  function timeToMins(t) { const p = to24h(t).split(':'); return parseInt(p[0]) * 60 + parseInt(p[1] || 0); }
  function nowMins() { const d = new Date(); return d.getHours() * 60 + d.getMinutes(); }
  function todayDow() { const d = new Date().getDay(); return d === 0 ? 6 : d - 1; }
  let activeSessions = {};

  async function refreshActiveSessions() {
    try {
      const resp = await fetch('/api/active_sessions_info');
      if (!resp.ok) return;
      activeSessions = await resp.json();
    } catch (e) {
      console.warn('Could not fetch active sessions:', e);
    }
  }

  function getSessionForSchedule(s) {
    const targetSection = (s.section_key || '').trim();
    for (const sid in activeSessions) {
      const live = activeSessions[sid] || {};
      if (!live.is_active) continue;
      if (live.schedule_id && live.schedule_id === s.schedule_id) {
        return live;
      }
      if (
        (live.subject_id || '') === (s.subject_id || '') &&
        (live.section_key || '') === targetSection &&
        (live.teacher_username || '') === (s.teacher_username || '')
      ) {
        return live;
      }
    }
    return null;
  }

  function isSessionActive(s) {
    return !!getSessionForSchedule(s);
  }

  function isLive(s) {
    const inScheduleWindow =
      s.day_of_week === todayDow() &&
      nowMins() >= timeToMins(s.start_time) &&
      nowMins() < timeToMins(s.end_time);
    return inScheduleWindow && isSessionActive(s);
  }
  function isUpcoming(s) { const diff = timeToMins(s.start_time) - nowMins(); return s.day_of_week === todayDow() && diff > 0 && diff <= 10; }
  function minsUntil(s) { return timeToMins(s.start_time) - nowMins(); }

  /* -- HIGHLIGHT TODAY -- */
  (function () {
    const th = document.getElementById('th_dow_' + todayDow());
    if (th) th.classList.add('today-col');
  })();

  /* -- BUILD CALENDAR -- */
  const TIME_SLOTS = ['07:00', '07:30', '08:00', '08:30', '09:00', '09:30', '10:00', '10:30',
    '11:00', '11:30', '12:00', '12:30', '13:00', '13:30', '14:00', '14:30',
    '15:00', '15:30', '16:00', '16:30', '17:00', '17:30', '18:00'];

  function esc(s) { return String(s || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;'); }

  function buildCalendar(filtered) {
    const body = document.getElementById('calBody'); if (!body) return;
    body.innerHTML = '';
    const grid = {}; for (let d = 0; d < 7; d++) grid[d] = [];
    (filtered || ALL_SCHEDULES).forEach(s => grid[s.day_of_week].push(s));
    TIME_SLOTS.forEach((slot, idx) => {
      const tr = document.createElement('tr');
      const tc = document.createElement('td');
      tc.className = 'time-cell'; tc.textContent = fmtTime(slot);
      tr.appendChild(tc);
      for (let d = 0; d < 7; d++) {
        const td = document.createElement('td');
        grid[d].filter(s => {
          const st = to24h(s.start_time);
          return st >= slot && st < (TIME_SLOTS[idx + 1] || '23:59');
        }).forEach(s => {
          const div = document.createElement('div');
          div.className = 'sched-block';
          div.dataset.teacher = s.teacher_username || '';
          div.dataset.subject = s.subject_id || '';
          if (isLive(s)) div.classList.add('live-now');
          else if (isUpcoming(s)) div.classList.add('upcoming-block');
          div.onclick = () => openSchedModal(s);
          const liveHtml = isLive(s)
            ? '<div class="live-badge-block"><span class="live-dot-s"></span> LIVE</div>'
            : (isUpcoming(s) ? '<div style="font-size:9px;color:#f59e0b;margin-top:2px;font-weight:700;">IN ' + minsUntil(s) + 'm</div>' : '');
          // DEFAULT: show SUBJECT NAME ONLY (clean view)
          div.innerHTML = '<div class="sb-subject">' + esc(s.subject_name) + '</div>' + liveHtml;
          td.appendChild(div);
        });
        tr.appendChild(td);
      }
      body.appendChild(tr);
    });
    applyFilter();
  }

  /* -- FILTER -- */
  let activeFilters = {};
  function applyFilter() {
    const tf = Object.values(activeFilters).filter(f => f.type === 'teacher').map(f => f.value);
    const sf = Object.values(activeFilters).filter(f => f.type === 'subject').map(f => f.value);
    document.querySelectorAll('.sched-block').forEach(b => {
      const mT = !tf.length || tf.includes(b.dataset.teacher);
      const mS = !sf.length || sf.includes(b.dataset.subject);
      b.classList.toggle('filtered-out', !(mT && mS));
    });
  }
  function addFilter(type, value, label) {
    const key = type + '_' + value; if (activeFilters[key]) return;
    activeFilters[key] = { type, value, label }; renderFilterChips(); applyFilter();
  }
  function removeFilter(key) { delete activeFilters[key]; renderFilterChips(); applyFilter(); }
  function renderFilterChips() {
    const c = document.getElementById('activeFilters'); if (!c) return;
    c.innerHTML = '';
    Object.keys(activeFilters).forEach(key => {
      const f = activeFilters[key];
      const chip = document.createElement('div'); chip.className = 'filter-chip';
      chip.innerHTML = '<i class="bi bi-funnel-fill" style="font-size:9px;"></i> ' + esc(f.label) +
        '<button onclick="removeFilter(\'' + key + '\')"><i class="bi bi-x"></i></button>';
      c.appendChild(chip);
    });
  }

  /* -- SEARCH -- */
  let searchTm = null;
  function onSearchInput() { clearTimeout(searchTm); searchTm = setTimeout(doSearch, 180); }
  function doSearch() {
    const q = (document.getElementById('schedSearchInput').value || '').trim().toLowerCase();
    const drop = document.getElementById('schedSearchDrop'); if (!drop) return;
    if (!q) { drop.classList.remove('open'); return; }
    const teachers = Object.entries(ALL_TEACHERS).filter(e =>
      !q || (e[1].full_name || '').toLowerCase().includes(q) || e[0].toLowerCase().includes(q)
    ).slice(0, 8);
    const subjects = Object.entries(ALL_SUBJECTS).filter(e =>
      !q || (e[1].name || '').toLowerCase().includes(q) || (e[1].course_code || '').toLowerCase().includes(q)
    ).slice(0, 8);
    if (!teachers.length && !subjects.length) { drop.innerHTML = '<div class="ac-empty">No matches found.</div>'; drop.classList.add('open'); return; }
    let html = '';
    if (teachers.length) {
      html += '<div class="search-section-label">Teachers</div>';
      teachers.forEach(e => {
        html += '<div class="search-result-row" onclick="addFilter(\'teacher\',\'' + e[0] + '\',\'' + esc(e[1].full_name) + '\');closeSearch()">' +
          '<span class="search-result-name">' + esc(e[1].full_name) + '</span>' +
          '<span class="search-result-badge badge-teacher">' + esc(e[1].role) + '</span></div>';
      });
    }
    if (subjects.length) {
      html += '<div class="search-section-label">Subjects</div>';
      subjects.forEach(e => {
        const lbl = '[' + e[1].course_code + '] ' + e[1].name;
        html += '<div class="search-result-row" onclick="addFilter(\'subject\',\'' + e[0] + '\',\'' + esc(lbl) + '\');closeSearch()">' +
          '<span class="search-result-name">' + esc(lbl) + '</span>' +
          '<span class="search-result-badge badge-subject">Subject</span></div>';
      });
    }
    drop.innerHTML = html; drop.classList.add('open');
  }
  function closeSearch() { document.getElementById('schedSearchInput').value = ''; document.getElementById('schedSearchDrop').classList.remove('open'); }
  document.addEventListener('click', e => { if (!e.target.closest('.sched-search-wrap')) document.getElementById('schedSearchDrop')?.classList.remove('open'); });

  /* -- MODAL SYSTEM -- */
  let selectedSched = null;
  function openSchedModal(s) {
    selectedSched = s;
    // Info tab
    document.getElementById('infoSubjectName').textContent = s.subject_name;
    document.getElementById('infoCourseCode').textContent = s.course_code || '';
    document.getElementById('infoTeacherName').textContent = s.teacher_name || '-';
    document.getElementById('infoSectionName').textContent = (s.section_key || '').split('|').join(' - ');
    document.getElementById('infoDayTime').textContent = DOW_NAMES[s.day_of_week] + ' @ ' + fmtTime(to24h(s.start_time)) + ' - ' + fmtTime(to24h(s.end_time));
    document.getElementById('infoGrace').textContent = (s.grace_minutes || 15) + ' minutes';
    const liveBadge = document.getElementById('infoLiveBadge');
    if (liveBadge) liveBadge.style.display = isLive(s) ? 'block' : 'none';
    const monitorBtn = document.getElementById('infoMonitorBtn');
    const liveSession = getSessionForSchedule(s);
    if (monitorBtn) {
      if (liveSession && liveSession.sess_id) {
        monitorBtn.href = '/teacher/session/' + liveSession.sess_id;
        monitorBtn.style.display = 'inline-flex';
      } else {
        monitorBtn.href = '#';
        monitorBtn.style.display = 'none';
      }
    }

    // Next class
    let nextTxt = '-';
    if (isLive(s)) { nextTxt = 'Currently in session'; }
    else {
      const d = new Date(); let diff = (s.day_of_week - todayDow() + 7) % 7;
      if (diff === 0) diff = 7;
      const nd = new Date(d); nd.setDate(nd.getDate() + diff);
      nextTxt = DOW_NAMES[s.day_of_week] + ', ' + nd.toLocaleDateString('en-US', { month: 'short', day: 'numeric' }) + ' @ ' + fmtTime(to24h(s.start_time));
    }
    document.getElementById('infoNextClass').textContent = nextTxt;

    if (IS_SUPER) {
      document.getElementById('editForm').action = '/admin/schedules/' + s.schedule_id + '/edit';
      document.getElementById('editSubjInput').value = s.subject_name;
      document.getElementById('editSubjHidden').value = s.subject_id;
      document.getElementById('editTeacherInput').value = s.teacher_name;
      document.getElementById('editTeacherHidden').value = s.teacher_username;
      const sk = (s.section_key || '').split('|');
      document.getElementById('editProgram').value = sk[0] || '';
      document.getElementById('editYear').value = sk[1] || '1st Year';
      document.getElementById('editSection').value = sk[2] || '';
      document.getElementById('editDay').value = s.day_of_week;
      document.getElementById('editStartTime').value = to24h(s.start_time);
      document.getElementById('editEndTime').value = to24h(s.end_time);
      document.getElementById('editGrace').value = s.grace_minutes || 15;
    }
    switchSchedTab('info');
    document.getElementById('scheduleModal').classList.add('show');
  }
  function closeSchedModal() { document.getElementById('scheduleModal').classList.remove('show'); selectedSched = null; }

  function switchSchedTab(tabId) {
    document.querySelectorAll('.sched-pane').forEach(p => p.classList.remove('active'));
    document.querySelectorAll('.pm-tab').forEach(t => t.classList.remove('active-tab'));
    const p = document.getElementById('pane-' + tabId);
    const b = document.getElementById('tab-' + tabId + '-btn');
    if (p) p.classList.add('active');
    if (b) b.classList.add('active-tab');
  }

  function deleteCurrentSched() {
    if (!selectedSched || !confirm('Permanently delete this schedule?')) return;
    const f = document.getElementById('deleteForm');
    f.action = '/admin/schedules/' + selectedSched.schedule_id + '/delete';
    f.submit();
  }

  /* -- ADD MODAL -- */
  function openAddModal() { document.getElementById('addModal').classList.add('show'); }
  function closeAddModal() { document.getElementById('addModal').classList.remove('show'); }
  function applyPreset(prefix, st, et) {
    document.getElementById(prefix + 'StartTime').value = st;
    document.getElementById(prefix + 'EndTime').value = et;
  }

  /* -- AUTOCOMPLETE -- */
  function makeAC(inputId, hiddenId, bodyId, dropId, dataFn, colA, colB) {
    const inp = document.getElementById(inputId), hid = document.getElementById(hiddenId);
    const tbody = document.getElementById(bodyId), drop = document.getElementById(dropId);
    if (!inp || !tbody) return;
    inp.onfocus = inp.oninput = function () { renderAC(inp.value, tbody, drop, hid, inp, dataFn, colA, colB); };
    document.addEventListener('click', e => { if (!e.target.closest('.ac-wrap')) drop.classList.remove('open'); });
  }
  function renderAC(q, tbody, drop, hid, inp, dataFn, colA, colB) {
    const items = dataFn(q.toLowerCase()); tbody.innerHTML = '';
    if (!items.length) { tbody.innerHTML = '<tr><td colspan="2" class="ac-td ac-empty">No matches.</td></tr>'; drop.classList.add('open'); return; }
    items.forEach(it => {
      const tr = document.createElement('tr'); tr.className = 'ac-tr';
      tr.innerHTML = '<td class="ac-td">' + esc(it[colA]) + '</td><td class="ac-td muted">' + esc(it[colB]) + '</td>';
      tr.onclick = () => { hid.value = it.id; inp.value = it.label; drop.classList.remove('open'); };
      tbody.appendChild(tr);
    });
    drop.classList.add('open');
  }
  function subjDataFn(q) { return Object.entries(ALL_SUBJECTS).filter(e => !q || (e[1].name || '').toLowerCase().includes(q) || (e[1].course_code || '').toLowerCase().includes(q)).slice(0, 10).map(e => ({ id: e[0], label: e[1].name, code: e[1].course_code || '-' })); }
  function teacherDataFn(q) { return Object.entries(ALL_TEACHERS).filter(e => !q || (e[1].full_name || '').toLowerCase().includes(q) || e[0].toLowerCase().includes(q)).slice(0, 10).map(e => ({ id: e[0], label: e[1].full_name, role: e[1].role })); }

  function validateSchedForm(prefix) {
    const hid = document.getElementById(prefix + 'SubjHidden');
    const thid = document.getElementById(prefix + 'TeacherHidden');
    if (!hid || !thid || !hid.value || !thid.value) { alert('Please select subject and teacher from dropdown.'); return false; }
    return true;
  }

  /* -- PRE-SESSION NOTIFICATION (5 min before) -- */
  const notifiedSessions = new Set();
  function checkPresessions() {
    ALL_SCHEDULES.forEach(s => {
      const mins = minsUntil(s);
      const key = s.schedule_id + '_' + new Date().toDateString();
      if (mins > 0 && mins <= 5 && !notifiedSessions.has(key)) {
        notifiedSessions.add(key);
        showPresessionToast(s, mins);
      }
    });
  }
  function showPresessionToast(s, mins) {
    const c = document.getElementById('presessionContainer');
    const el = document.createElement('div');
    el.className = 'presession-toast';
    el.innerHTML =
      '<button class="pt-close" onclick="this.parentNode.remove()"><i class="bi bi-x"></i></button>' +
      '<div style="font-size:24px;margin-bottom:7px;">ALERT</div>' +
      '<div class="pt-title">Class Starting in ' + mins + ' Minute' + (mins !== 1 ? 's' : '') + '!</div>' +
      '<div class="pt-body">' +
      '<strong>' + esc(s.subject_name) + '</strong><br>' +
      esc(s.teacher_name) + '<br>' +
      (s.section_key || '').replace(/\|/g, ' - ') + '<br>' +
      fmtTime(to24h(s.start_time)) + ' - ' + fmtTime(to24h(s.end_time)) +
      '</div>';
    c.appendChild(el);
    setTimeout(() => {
      if (el.parentNode) { el.classList.add('removing'); setTimeout(() => el.parentNode && el.remove(), 350); }
    }, 30000);
  }

  /* -- RECURRING AUTO-SESSION CHECK -- */
  // This runs every minute to detect if a scheduled class is now "live"
  // and visually marks the block - actual session start/end is handled server-side
  // via the /api/check_recurring_sessions endpoint if implemented.
  function checkRecurringSessions() {
    refreshActiveSessions().finally(() => {
      buildCalendar(ALL_SCHEDULES);
      checkPresessions();
    });
  }

  /* -- INIT -- */
  document.addEventListener('DOMContentLoaded', () => {
    refreshActiveSessions().finally(() => buildCalendar(ALL_SCHEDULES));
    if (IS_SUPER) {
      makeAC('addSubjInput', 'addSubjHidden', 'addSubjBody', 'addSubjDrop', subjDataFn, 'code', 'label');
      makeAC('addTeacherInput', 'addTeacherHidden', 'addTeacherBody', 'addTeacherDrop', teacherDataFn, 'label', 'role');
      makeAC('editSubjInput', 'editSubjHidden', 'editSubjBody', 'editSubjDrop', subjDataFn, 'code', 'label');
      makeAC('editTeacherInput', 'editTeacherHidden', 'editTeacherBody', 'editTeacherDrop', teacherDataFn, 'label', 'role');
    }
    checkPresessions();
    setInterval(checkRecurringSessions, 60000);
  });


