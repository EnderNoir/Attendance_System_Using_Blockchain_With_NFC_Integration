/* -- DATA -- */
  const SCHEDULE_BOOTSTRAP = window.ADMIN_SCHEDULES_BOOTSTRAP || {};
  const ALL_SCHEDULES = Array.isArray(SCHEDULE_BOOTSTRAP.schedules) ? SCHEDULE_BOOTSTRAP.schedules : [];
  const ALL_SUBJECTS = SCHEDULE_BOOTSTRAP.subjects || {};
  const ALL_TEACHERS = SCHEDULE_BOOTSTRAP.teachers || {};
  const SECTION_KEYS = Array.isArray(SCHEDULE_BOOTSTRAP.sections) ? SCHEDULE_BOOTSTRAP.sections : [];
  const NO_CLASS_DAYS = Array.isArray(SCHEDULE_BOOTSTRAP.noClassDays) ? SCHEDULE_BOOTSTRAP.noClassDays : [];
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
  function normalizeDow(value) {
    const n = Number(value);
    if (!Number.isFinite(n)) return -1;
    if (n >= 0 && n <= 6) return n;
    if (n >= 1 && n <= 7) return n - 1;
    return -1;
  }
  function dateKey(d) {
    const y = d.getFullYear();
    const m = String(d.getMonth() + 1).padStart(2, '0');
    const day = String(d.getDate()).padStart(2, '0');
    return y + '-' + m + '-' + day;
  }
  function parseYmd(ymd) {
    const m = String(ymd || '').match(/^(\d{4})-(\d{2})-(\d{2})$/);
    if (!m) return null;
    return new Date(Number(m[1]), Number(m[2]) - 1, Number(m[3]));
  }
  function parseDateTime(dt) {
    const raw = String(dt || '').trim();
    if (!raw) return null;
    const m = raw.match(/^(\d{4})-(\d{2})-(\d{2})\s+(\d{2}):(\d{2})(?::\d{2})?$/);
    if (!m) return null;
    return new Date(Number(m[1]), Number(m[2]) - 1, Number(m[3]), Number(m[4]), Number(m[5]), 0);
  }
  function isSchoolEvent(s) {
    return String(s.class_type || '').toLowerCase() === 'school_event' && !!s.event_date;
  }
  function isArchivedSchedule(s) {
    if (!isSchoolEvent(s)) return false;
    const endDt = parseDateTime(s.event_end_at);
    return !!endDt && endDt < new Date();
  }
  function getNoClassEntriesForDate(ymd) {
    const date = String(ymd || '').trim();
    if (!date) return [];
    return NO_CLASS_DAYS.filter((n) => {
      const fromDate = String(n.from_date || '').trim();
      const toDate = String(n.to_date || '').trim();
      return fromDate && toDate && fromDate <= date && toDate >= date;
    });
  }
  function occursToday(s) {
    if (!isSchoolEvent(s)) return normalizeDow(s.day_of_week) === todayDow();
    return String(s.event_date || '') === dateKey(new Date());
  }
  function isVisibleThisWeek(s) {
    if (!isSchoolEvent(s)) return true;
    const eventDate = parseYmd(s.event_date);
    if (!eventDate) return false;
    const now = new Date();
    const dow = todayDow();
    const weekStart = new Date(now.getFullYear(), now.getMonth(), now.getDate() - dow);
    weekStart.setHours(0, 0, 0, 0);
    const weekEnd = new Date(weekStart);
    weekEnd.setDate(weekStart.getDate() + 6);
    weekEnd.setHours(23, 59, 59, 999);
    return eventDate >= weekStart && eventDate <= weekEnd;
  }
  function fmtEventDate(ymd) {
    const d = parseYmd(ymd);
    return d ? d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' }) : '';
  }
  function classTypeLabel(value) {
    const normalized = String(value || 'lecture').toLowerCase();
    if (normalized === 'laboratory') return 'Laboratory';
    if (normalized === 'school_event') return 'School Event';
    return 'Lecture';
  }
  function classTypeCss(value) {
    const normalized = String(value || 'lecture').toLowerCase();
    if (normalized === 'laboratory') return 'sb-type-lab';
    if (normalized === 'school_event') return 'sb-type-event';
    return 'sb-type-lec';
  }
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
    const targetScheduleId = String(s.schedule_id || '').trim();

    // Exact schedule_id match prevents side-by-side lecture/lab blocks from
    // incorrectly sharing the same live session link.
    if (targetScheduleId) {
      for (const sid in activeSessions) {
        const live = activeSessions[sid] || {};
        if (!live.is_active) continue;
        if ((live.schedule_id || '') === targetScheduleId) {
          return live;
        }
      }
      return null;
    }

    for (const sid in activeSessions) {
      const live = activeSessions[sid] || {};
      if (!live.is_active) continue;
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
      occursToday(s) &&
      nowMins() >= timeToMins(s.start_time) &&
      nowMins() < timeToMins(s.end_time);
    return inScheduleWindow && isSessionActive(s);
  }
  function isUpcoming(s) { const diff = timeToMins(s.start_time) - nowMins(); return occursToday(s) && diff > 0 && diff <= 10; }
  function minsUntil(s) { return timeToMins(s.start_time) - nowMins(); }

  /* -- DAY HEADERS -- */
  function initializeDayHeaders() {
    const now = new Date();
    const dow = todayDow();
    const weekStart = new Date(now.getFullYear(), now.getMonth(), now.getDate() - dow);
    weekStart.setHours(0, 0, 0, 0);
    for (let d = 0; d < 7; d++) {
      const th = document.getElementById('th_dow_' + d);
      if (!th) continue;
      if (d === todayDow()) th.classList.add('today-col');
      th.classList.add('day-clickable');
      const dayDate = new Date(weekStart);
      dayDate.setDate(weekStart.getDate() + d);
      const ymd = dateKey(dayDate);
      const noClassEntries = getNoClassEntriesForDate(ymd);
      th.onclick = () => openDayNoClassModal(DOW_NAMES[d], ymd, noClassEntries);
      th.title = noClassEntries.length
        ? 'Click to view no-class details'
        : 'Click to view day details';
      const markerId = 'holiday_pill_' + d;
      let marker = document.getElementById(markerId);
      if (noClassEntries.length) {
        if (!marker) {
          marker = document.createElement('div');
          marker.id = markerId;
          marker.className = 'day-holiday-pill';
          th.appendChild(marker);
        }
        marker.innerHTML = '<i class="bi bi-calendar2-x"></i> ' + noClassEntries.length + ' no-class';
      } else if (marker) {
        marker.remove();
      }
    }
  }

  /* -- BUILD CALENDAR -- */
  const DEFAULT_GRID_START_MINS = 7 * 60;
  const DEFAULT_GRID_END_MINS = 18 * 60;

  function minsTo24h(mins) {
    const clamped = Math.max(0, Math.min(24 * 60 - 1, Number(mins) || 0));
    const h = Math.floor(clamped / 60);
    const m = clamped % 60;
    return String(h).padStart(2, '0') + ':' + String(m).padStart(2, '0');
  }

  function buildTimeSlots(schedules) {
    let minStart = Infinity;
    let maxEnd = -Infinity;
    (schedules || []).forEach((s) => {
      const start = timeToMins(s.start_time);
      const end = timeToMins(s.end_time);
      if (!Number.isFinite(start) || !Number.isFinite(end)) return;
      if (end <= start) return;
      minStart = Math.min(minStart, start);
      maxEnd = Math.max(maxEnd, end);
    });

    if (!Number.isFinite(minStart) || !Number.isFinite(maxEnd)) {
      minStart = DEFAULT_GRID_START_MINS;
      maxEnd = DEFAULT_GRID_END_MINS;
    }

    const gridStart = Math.min(DEFAULT_GRID_START_MINS, Math.floor(minStart / 30) * 30);
    const gridEnd = Math.max(DEFAULT_GRID_END_MINS, Math.ceil(maxEnd / 30) * 30);
    const slots = [];
    for (let mins = gridStart; mins <= gridEnd; mins += 30) {
      slots.push(minsTo24h(mins));
    }
    return slots;
  }

  function esc(s) { return String(s || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;'); }

  function buildCalendar(filtered) {
    const body = document.getElementById('calBody'); if (!body) return;
    body.innerHTML = '';
    const sourceSchedules = filtered || ALL_SCHEDULES;
    const timeSlots = buildTimeSlots(sourceSchedules);
    const grid = {}; for (let d = 0; d < 7; d++) grid[d] = [];
    sourceSchedules.forEach(s => {
      if (!isVisibleThisWeek(s)) return;
      const dayIndex = normalizeDow(s.day_of_week);
      if (dayIndex < 0 || dayIndex > 6) return;
      grid[dayIndex].push(s);
    });
    timeSlots.forEach((slot, idx) => {
      const tr = document.createElement('tr');
      const tc = document.createElement('td');
      tc.className = 'time-cell'; tc.textContent = fmtTime(slot);
      tr.appendChild(tc);
      for (let d = 0; d < 7; d++) {
        const td = document.createElement('td');
        const slotSchedules = grid[d].filter(s => {
          const st = to24h(s.start_time);
          return st >= slot && st < (timeSlots[idx + 1] || '23:59');
        });
        const grouped = {};
        slotSchedules.forEach((s) => {
          const key = [
            String(normalizeDow(s.day_of_week)),
            to24h(s.start_time),
            to24h(s.end_time),
          ].join('|');
          if (!grouped[key]) grouped[key] = [];
          grouped[key].push(s);
        });

        Object.values(grouped).forEach((bucket) => {
          const sample = bucket[0] || {};
          const currentItems = bucket.filter((s) => !isArchivedSchedule(s));
          const archivedItems = bucket.filter((s) => isArchivedSchedule(s));
          const counts = {
            lecture: currentItems.filter((s) => String(s.class_type || '').toLowerCase() === 'lecture').length,
            laboratory: currentItems.filter((s) => String(s.class_type || '').toLowerCase() === 'laboratory').length,
            school_event: currentItems.filter((s) => String(s.class_type || '').toLowerCase() === 'school_event').length,
          };
          const div = document.createElement('div');
          div.className = 'sched-block grouped';
          div.dataset.teacher = currentItems.map((s) => s.teacher_username || '').join(',');
          div.dataset.subject = currentItems.map((s) => s.subject_id || '').join(',');
          if (currentItems.some((s) => isLive(s))) div.classList.add('live-now');
          else if (currentItems.some((s) => isUpcoming(s))) div.classList.add('upcoming-block');
          div.onclick = () => openSlotModal(bucket, sample);
          const liveHtml = currentItems.some((s) => isLive(s))
            ? '<div class="live-badge-block"><span class="live-dot-s"></span> LIVE</div>'
            : (currentItems.some((s) => isUpcoming(s)) ? '<div style="font-size:9px;color:#f59e0b;margin-top:2px;font-weight:700;">IN ' + minsUntil(currentItems[0]) + 'm</div>' : '');
          const typeChips = [
            counts.lecture ? '<span class="sb-type-count lec">Lecture: ' + counts.lecture + '</span>' : '',
            counts.laboratory ? '<span class="sb-type-count lab">Laboratory: ' + counts.laboratory + '</span>' : '',
            counts.school_event ? '<span class="sb-type-count event">Event: ' + counts.school_event + '</span>' : '',
            archivedItems.length ? '<span class="sb-type-count archive">Archived: ' + archivedItems.length + '</span>' : '',
          ].filter(Boolean).join('');
          const singlePreviewHtml = bucket.length === 1
            ? '<div class="sb-time" style="margin-top:4px;">' + esc(sample.subject_name || '-') + '</div>' +
              '<div class="sb-section">' + esc(sample.teacher_name || '-') + '</div>'
            : '';
          const eventDateHtml = isSchoolEvent(sample)
            ? '<div class="sb-date">' + esc(fmtEventDate(sample.event_date)) + '</div>'
            : '';
          div.innerHTML =
            '<div class="sb-group-head">' +
            '<div class="sb-subject">' + esc(fmtTime(to24h(sample.start_time)) + ' - ' + fmtTime(to24h(sample.end_time))) + '</div>' +
            '<span class="sb-count-pill">' + bucket.length + ' item' + (bucket.length > 1 ? 's' : '') + '</span>' +
            '</div>' +
            '<div class="sb-group-types">' + typeChips + '</div>' +
            singlePreviewHtml +
            eventDateHtml +
            liveHtml;
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
      const teachers = String(b.dataset.teacher || '').split(',').filter(Boolean);
      const subjects = String(b.dataset.subject || '').split(',').filter(Boolean);
      const mT = !tf.length || teachers.some((t) => tf.includes(t));
      const mS = !sf.length || subjects.some((s) => sf.includes(s));
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
    const dayIdx = normalizeDow(s.day_of_week);
    // Info tab
    document.getElementById('infoSubjectName').textContent = s.subject_name;
    document.getElementById('infoCourseCode').textContent = s.course_code || '';
    if (isSchoolEvent(s)) {
      const teachers = Array.isArray(s.teachers_involved) && s.teachers_involved.length
        ? s.teachers_involved
        : [s.teacher_name || '-'];
      document.getElementById('infoTeacherName').innerHTML = teachers.map((t) => esc(t)).join('<br>');

      const sectionKeys = Array.isArray(s.section_keys_involved) && s.section_keys_involved.length
        ? s.section_keys_involved
        : (s.section_key ? [s.section_key] : []);
      const scopeLines = sectionKeys
        .filter(Boolean)
        .map((sec) => {
          const p = String(sec).split('|');
          return (p[0] || '-') + '-' + (p[1] || '-') + '-' + (p[2] || '-');
        });
      document.getElementById('infoSectionName').innerHTML = scopeLines.length
        ? scopeLines.map((x) => esc(x)).join('<br>')
        : '-';
    } else {
      document.getElementById('infoTeacherName').textContent = s.teacher_name || '-';
      document.getElementById('infoSectionName').textContent = (s.section_key || '').split('|').join(' - ');
    }
    if (isSchoolEvent(s)) {
      document.getElementById('infoDayTime').textContent = (fmtEventDate(s.event_date) || DOW_NAMES[dayIdx]) + ' @ ' + fmtTime(to24h(s.start_time)) + ' - ' + fmtTime(to24h(s.end_time));
    } else {
      document.getElementById('infoDayTime').textContent = DOW_NAMES[dayIdx] + ' @ ' + fmtTime(to24h(s.start_time)) + ' - ' + fmtTime(to24h(s.end_time));
    }
    document.getElementById('infoClassType').textContent = classTypeLabel(s.class_type);
    document.getElementById('infoGrace').textContent = (s.grace_minutes || 15) + ' minutes';
    const infoPatternLbl = document.getElementById('infoPatternLbl');
    const infoPatternVal = document.getElementById('infoPatternVal');
    if (infoPatternLbl && infoPatternVal) {
      if (isSchoolEvent(s)) {
        infoPatternLbl.textContent = 'Event Trigger';
        infoPatternVal.innerHTML = '<span style="background:rgba(16,185,129,.12);color:#10b981;border:1px solid rgba(16,185,129,.3);border-radius:6px;padding:2px 8px;font-size:11px;font-weight:700;"><i class="bi bi-calendar-check"></i> One-Time Event</span>';
      } else {
        infoPatternLbl.textContent = 'Schedule Pattern';
        infoPatternVal.innerHTML = '<span style="background:rgba(45,106,39,.1);color:var(--success);border:1px solid rgba(45,106,39,.25);border-radius:6px;padding:2px 8px;font-size:11px;font-weight:700;"><i class="bi bi-arrow-repeat"></i> Weekly Recurring</span>';
      }
    }
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
    else if (isSchoolEvent(s)) {
      const eventDate = parseYmd(s.event_date);
      if (eventDate) {
        const today = new Date();
        today.setHours(0, 0, 0, 0);
        const st = fmtTime(to24h(s.start_time));
        if (eventDate < today) nextTxt = 'Completed event';
        else nextTxt = fmtEventDate(s.event_date) + ' @ ' + st;
      } else {
        nextTxt = DOW_NAMES[dayIdx] + ' @ ' + fmtTime(to24h(s.start_time));
      }
    }
    else {
      const d = new Date(); let diff = (dayIdx - todayDow() + 7) % 7;
      if (diff === 0) diff = 7;
      const nd = new Date(d); nd.setDate(nd.getDate() + diff);
      nextTxt = DOW_NAMES[dayIdx] + ', ' + nd.toLocaleDateString('en-US', { month: 'short', day: 'numeric' }) + ' @ ' + fmtTime(to24h(s.start_time));
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
      document.getElementById('editDay').value = dayIdx;
      document.getElementById('editClassType').value = String(s.class_type || 'lecture').toLowerCase();
      document.getElementById('editStartTime').value = to24h(s.start_time);
      document.getElementById('editEndTime').value = to24h(s.end_time);
      document.getElementById('editGrace').value = s.grace_minutes || 15;
    }
    switchSchedTab('info');
    document.getElementById('scheduleModal').classList.add('show');
  }
  function closeSchedModal() { document.getElementById('scheduleModal').classList.remove('show'); selectedSched = null; }

  let selectedSlot = { current: [], archive: [], dayLabel: '', timeLabel: '' };

  function eventGroupKey(s) {
    const schedId = String((s || {}).schedule_id || '');
    if (schedId.startsWith('event:')) {
      const parts = schedId.split(':', 4);
      if (parts.length >= 2 && parts[1]) return 'event:' + parts[1];
    }
    const subj = String((s || {}).subject_id || '');
    if (subj.startsWith('event:')) return subj;
    return '';
  }

  function collapseEventItems(items) {
    const out = [];
    const events = {};
    (items || []).forEach((s) => {
      if (!isSchoolEvent(s)) {
        out.push(s);
        return;
      }
      const key = eventGroupKey(s) || ('event:' + String(s.subject_name || '') + ':' + String(s.event_date || '') + ':' + to24h(s.start_time) + ':' + to24h(s.end_time));
      if (!events[key]) {
        events[key] = {
          ...s,
          teachers_involved: [],
          sections_involved: [],
          section_keys_involved: [],
          programs_involved: [],
          years_involved: [],
          _event_item_count: 0,
        };
      }
      const e = events[key];
      e._event_item_count += 1;
      const t = String(s.teacher_name || '').trim();
      if (t && !e.teachers_involved.includes(t)) e.teachers_involved.push(t);
      const sec = String(s.section_key || '').trim();
      if (sec && !e.sections_involved.includes(sec)) e.sections_involved.push(sec);
      if (sec && !e.section_keys_involved.includes(sec)) e.section_keys_involved.push(sec);
      if (Array.isArray(s.sections_involved)) {
        s.sections_involved.forEach((sk) => {
          const n = String(sk || '').trim();
          if (n && !e.sections_involved.includes(n)) e.sections_involved.push(n);
        });
      }
      if (Array.isArray(s.section_keys_involved)) {
        s.section_keys_involved.forEach((sk) => {
          const n = String(sk || '').trim();
          if (n && !e.section_keys_involved.includes(n)) e.section_keys_involved.push(n);
        });
      }
      e.sections_involved.forEach((sk) => {
        const p = String(sk).split('|');
        const prog = p[0] || '';
        const yr = p[1] || '';
        if (prog && !e.programs_involved.includes(prog)) e.programs_involved.push(prog);
        if (yr && !e.years_involved.includes(yr)) e.years_involved.push(yr);
      });
    });
    return out.concat(Object.values(events));
  }
  function openSlotModal(items, sample) {
    selectedSlot = {
      current: (items || []).filter((s) => !isArchivedSchedule(s)),
      archive: (items || []).filter((s) => isArchivedSchedule(s)),
      dayLabel: DOW_NAMES[normalizeDow(sample.day_of_week)] || '',
      timeLabel: fmtTime(to24h(sample.start_time)) + ' - ' + fmtTime(to24h(sample.end_time)),
    };
    const summary = document.getElementById('slotSummary');
    if (summary) {
      summary.textContent = selectedSlot.dayLabel + ' | ' + selectedSlot.timeLabel;
    }
    const currentSearch = document.getElementById('slotCurrentSearch');
    const archiveSearch = document.getElementById('slotArchiveSearch');
    if (currentSearch) currentSearch.value = '';
    if (archiveSearch) archiveSearch.value = '';
    renderSlotPane('current');
    renderSlotPane('archive');
    switchSlotTab('current');
    document.getElementById('slotModal')?.classList.add('show');
  }

  function closeSlotModal() {
    document.getElementById('slotCurrentSearchDrop')?.classList.remove('open');
    document.getElementById('slotArchiveSearchDrop')?.classList.remove('open');
    document.getElementById('slotModal')?.classList.remove('show');
  }

  function switchSlotTab(tabName) {
    const currentBtn = document.getElementById('slot-tab-current');
    const archiveBtn = document.getElementById('slot-tab-archive');
    const currentPane = document.getElementById('slotPaneCurrent');
    const archivePane = document.getElementById('slotPaneArchive');
    if (tabName === 'archive') {
      archiveBtn?.classList.add('active-tab');
      currentBtn?.classList.remove('active-tab');
      archivePane?.classList.add('active');
      currentPane?.classList.remove('active');
      return;
    }
    currentBtn?.classList.add('active-tab');
    archiveBtn?.classList.remove('active-tab');
    currentPane?.classList.add('active');
    archivePane?.classList.remove('active');
  }

  function renderSlotPane(tabName) {
    const pane = document.getElementById(tabName === 'archive' ? 'slotPaneArchive' : 'slotPaneCurrent');
    if (!pane) return;
    const list = document.getElementById(tabName === 'archive' ? 'slotArchiveList' : 'slotCurrentList');
    if (!list) return;
    const input = document.getElementById(tabName === 'archive' ? 'slotArchiveSearch' : 'slotCurrentSearch');
    const query = String((input && input.value) || '').trim().toLowerCase();
    const baseItems = tabName === 'archive' ? selectedSlot.archive : selectedSlot.current;
    const items = collapseEventItems(baseItems)
      .filter((s) => {
        if (!query) return true;
        return String(s.subject_name || '').toLowerCase().includes(query)
          || String(s.teacher_name || '').toLowerCase().includes(query)
          || String((s.teachers_involved || []).join(' ') || '').toLowerCase().includes(query)
          || String(s.course_code || '').toLowerCase().includes(query);
      });

    list.innerHTML = '';
    if (!items.length) {
      list.innerHTML = '<div class="slot-empty">No ' + (tabName === 'archive' ? 'archived' : 'current') + ' schedules in this slot.</div>';
      return;
    }
    items.forEach((s) => {
      const row = document.createElement('div');
      row.className = 'slot-item';
      row.innerHTML =
        '<div class="slot-item-title">' + esc(s.subject_name || '-') + '</div>' +
        '<div class="slot-item-meta">' +
        '<span><i class="bi bi-person"></i> ' + esc(isSchoolEvent(s) ? ((s.teachers_involved || []).join(', ') || s.teacher_name || '-') : (s.teacher_name || '-')) + '</span>' +
        '<span><i class="bi bi-diagram-3"></i> ' + esc(isSchoolEvent(s) ? ((s.sections_involved || []).map((sk) => String(sk || '').split('|').join('-')).join(', ') || (s.section_key || '').split('|').join(' - ')) : (s.section_key || '').split('|').join(' - ')) + '</span>' +
        '<span><i class="bi bi-tag"></i> ' + esc(classTypeLabel(s.class_type)) + '</span>' +
        '</div>';
      row.addEventListener('click', () => {
        closeSlotModal();
        openSchedModal(s);
      });
      list.appendChild(row);
    });
  }

  function onSlotSearchInput(tabName) {
    const items = collapseEventItems(tabName === 'archive' ? selectedSlot.archive : selectedSlot.current);
    const input = document.getElementById(tabName === 'archive' ? 'slotArchiveSearch' : 'slotCurrentSearch');
    const drop = document.getElementById(tabName === 'archive' ? 'slotArchiveSearchDrop' : 'slotCurrentSearchDrop');
    const body = document.getElementById(tabName === 'archive' ? 'slotArchiveSearchBody' : 'slotCurrentSearchBody');
    if (!input || !drop || !body) return;
    const query = String(input.value || '').trim().toLowerCase();

    body.innerHTML = '';
    const matched = items.filter((s) => {
      if (!query) return true;
      return String(s.subject_name || '').toLowerCase().includes(query)
        || String(s.teacher_name || '').toLowerCase().includes(query)
        || String(s.course_code || '').toLowerCase().includes(query);
    }).slice(0, 12);

    if (!matched.length) {
      body.innerHTML = '<tr><td class="ac-td ac-empty" colspan="2">No matches.</td></tr>';
      drop.classList.add('open');
      renderSlotPane(tabName);
      return;
    }

    matched.forEach((s) => {
      const tr = document.createElement('tr');
      tr.className = 'ac-tr';
      tr.innerHTML = '<td class="ac-td">' + esc(s.subject_name || '-') + '</td>' +
        '<td class="ac-td muted">' + esc(s.teacher_name || '-') + '</td>';
      tr.addEventListener('click', () => {
        input.value = s.subject_name || '';
        drop.classList.remove('open');
        renderSlotPane(tabName);
      });
      body.appendChild(tr);
    });

    drop.classList.add('open');
    renderSlotPane(tabName);
  }

  function switchSchedTab(tabId) {
    document.querySelectorAll('.sched-pane').forEach(p => p.classList.remove('active'));
    document.querySelectorAll('.pm-tab').forEach(t => t.classList.remove('active-tab'));
    const p = document.getElementById('pane-' + tabId);
    const b = document.getElementById('tab-' + tabId + '-btn');
    if (p) p.classList.add('active');
    if (b) b.classList.add('active-tab');
  }

  async function deleteCurrentSched() {
    if (!selectedSched) return;
    const ok = await showAppConfirm('Permanently delete this schedule?', 'Delete Schedule', 'Delete', 'Cancel');
    if (!ok) return;
    const f = document.getElementById('deleteForm');
    f.action = '/admin/schedules/' + selectedSched.schedule_id + '/delete';
    f.submit();
  }

  /* -- ADD MODAL -- */
  function openAddModal() {
    const form = document.getElementById('addForm');
    if (form) form.reset();
    const lectureToggle = document.getElementById('addLectureEnabled');
    if (lectureToggle) lectureToggle.checked = true;
    const labToggle = document.getElementById('addLabEnabled');
    if (labToggle) labToggle.checked = false;
    toggleClassTypeFields();
    document.getElementById('addModal').classList.add('show');
  }
  function closeAddModal() { document.getElementById('addModal').classList.remove('show'); }

  function openNoClassModal() {
    const form = document.getElementById('noClassForm');
    if (form) form.reset();
    noClassTeachers = [];
    renderNoClassTeachers();
    renderNoClassExistingRanges();
    toggleNoClassTeacherScope();
    document.getElementById('noClassModal')?.classList.add('show');
  }
  function closeNoClassModal() {
    document.getElementById('noClassModal')?.classList.remove('show');
  }

  function openDayNoClassModal(dayName, ymd, items) {
    const title = document.getElementById('dayNoClassTitle');
    const body = document.getElementById('dayNoClassBody');
    if (title) {
      title.innerHTML = '<i class="bi bi-calendar2-x"></i> ' + esc(dayName) + ' | ' + esc(fmtEventDate(ymd));
    }
    if (body) {
      if (!items || !items.length) {
        body.innerHTML = '<div class="slot-empty">No no-class or holiday range set for this day.</div>';
      } else {
        body.innerHTML = items.map((n) => (
          '<div class="day-no-class-card">' +
          '<div class="day-no-class-title">' + esc(n.title || 'No-Class') + '</div>' +
          '<div class="day-no-class-range"><i class="bi bi-calendar3"></i> ' + esc(fmtEventDate(n.from_date)) + ' to ' + esc(fmtEventDate(n.to_date)) + '</div>' +
          '<div class="day-no-class-desc">' + esc(n.description || 'No additional description.') + '</div>' +
          (IS_SUPER
            ? '<div style="margin-top:10px;display:flex;justify-content:flex-end;">' +
              '<button type="button" class="btn-outline" style="border-color:#dc2626;color:#dc2626;" onclick="deleteNoClassRange(' + Number(n.id || 0) + ')">' +
              '<i class="bi bi-trash"></i> Remove Range</button></div>'
            : '') +
          '</div>'
        )).join('');
      }
    }
    document.getElementById('dayNoClassModal')?.classList.add('show');
  }

  async function deleteNoClassRange(noClassId) {
    const id = Number(noClassId || 0);
    if (!id) return;
    const ok = await showAppConfirm(
      'Remove this no-class range? You can create another one later if needed.',
      'Delete No-Class Range',
      'Delete',
      'Cancel'
    );
    if (!ok) return;
    const f = document.getElementById('deleteForm');
    if (!f) return;
    f.action = '/admin/no-class-days/' + id + '/delete';
    f.submit();
  }

  function closeDayNoClassModal() {
    document.getElementById('dayNoClassModal')?.classList.remove('show');
  }

  let eventTeachers = [];
  let eventSections = [];
  let noClassTeachers = [];
  function openEventModal() {
    const form = document.getElementById('eventForm');
    if (form) form.reset();
    eventTeachers = [];
    eventSections = [];
    renderEventTeachers();
    renderEventSections();
    document.getElementById('eventModal')?.classList.add('show');
  }
  function closeEventModal() {
    document.getElementById('eventModal')?.classList.remove('show');
  }

  function addNoClassTeacher() {
    const input = document.getElementById('noClassTeacherInput');
    if (!input) return;
    const raw = String(input.value || '').trim();
    if (!raw) return;
    const match = Object.entries(ALL_TEACHERS).find(([u, t]) => {
      const name = String((t || {}).full_name || '').trim().toLowerCase();
      return u.toLowerCase() === raw.toLowerCase() || name === raw.toLowerCase();
    });
    if (!match) {
      showAppAlert('Please select a valid teacher from the list.', 'Invalid Teacher');
      return;
    }
    const [username, teacher] = match;
    if (!noClassTeachers.some((t) => t.username === username)) {
      noClassTeachers.push({ username, full_name: teacher.full_name || username });
      renderNoClassTeachers();
    }
    input.value = '';
  }

  function removeNoClassTeacher(username) {
    noClassTeachers = noClassTeachers.filter((t) => t.username !== username);
    renderNoClassTeachers();
  }

  function renderNoClassTeachers() {
    const wrap = document.getElementById('noClassTeachersList');
    const hidden = document.getElementById('noClassTeachersHidden');
    if (!wrap || !hidden) return;
    hidden.value = noClassTeachers.map((t) => t.username).join(',');
    wrap.innerHTML = noClassTeachers.map((t) => (
      '<span class="filter-chip">' + esc(t.full_name) +
      '<button type="button" onclick="removeNoClassTeacher(\'' + esc(t.username) + '\')"><i class="bi bi-x"></i></button></span>'
    )).join('');
  }

  function renderNoClassExistingRanges() {
    const wrap = document.getElementById('noClassExistingList');
    if (!wrap) return;
    if (!NO_CLASS_DAYS.length) {
      wrap.innerHTML = '<div class="slot-empty">No no-class ranges found.</div>';
      return;
    }
    const rows = [...NO_CLASS_DAYS].sort((a, b) => String(a.from_date || '').localeCompare(String(b.from_date || '')));
    wrap.innerHTML = rows.map((n) => (
      '<div class="day-no-class-card" style="margin-bottom:8px;">' +
      '<div class="day-no-class-title">' + esc(n.title || 'No-Class') + '</div>' +
      '<div class="day-no-class-range"><i class="bi bi-calendar3"></i> ' + esc(fmtEventDate(n.from_date)) + ' to ' + esc(fmtEventDate(n.to_date)) + '</div>' +
      '<div class="day-no-class-desc">' + esc(n.description || 'No additional description.') + '</div>' +
      (IS_SUPER
        ? '<div style="margin-top:8px;display:flex;justify-content:flex-end;">' +
          '<button type="button" class="btn-outline" style="border-color:#dc2626;color:#dc2626;" onclick="deleteNoClassRange(' + Number(n.id || 0) + ')"><i class="bi bi-trash"></i> Remove</button>' +
          '</div>'
        : '') +
      '</div>'
    )).join('');
  }

  function toggleNoClassTeacherScope() {
    const applyAll = !!document.getElementById('noClassApplyAllTeachers')?.checked;
    const picker = document.getElementById('noClassTeacherPicker');
    if (picker) picker.style.display = applyAll ? 'none' : 'flex';
    if (applyAll) {
      noClassTeachers = [];
      renderNoClassTeachers();
    }
  }

  function addEventTeacher() {
    const input = document.getElementById('eventTeacherInput');
    if (!input) return;
    const raw = String(input.value || '').trim();
    if (!raw) return;
    const match = Object.entries(ALL_TEACHERS).find(([u, t]) => {
      const name = String((t || {}).full_name || '').trim().toLowerCase();
      return u.toLowerCase() === raw.toLowerCase() || name === raw.toLowerCase();
    });
    if (!match) {
      showAppAlert('Please select a valid teacher from the list.', 'Invalid Teacher');
      return;
    }
    const [username, teacher] = match;
    if (!eventTeachers.some((t) => t.username === username)) {
      eventTeachers.push({ username, full_name: teacher.full_name || username });
      renderEventTeachers();
    }
    input.value = '';
  }
  function removeEventTeacher(username) {
    eventTeachers = eventTeachers.filter((t) => t.username !== username);
    renderEventTeachers();
  }
  function renderEventTeachers() {
    const wrap = document.getElementById('eventTeachersList');
    const hidden = document.getElementById('eventTeachersHidden');
    if (!wrap || !hidden) return;
    hidden.value = eventTeachers.map((t) => t.username).join(',');
    wrap.innerHTML = eventTeachers.map((t) => (
      '<span class="filter-chip">' + esc(t.full_name) +
      '<button type="button" onclick="removeEventTeacher(\'' + esc(t.username) + '\')"><i class="bi bi-x"></i></button></span>'
    )).join('');
  }
  function addEventSection() {
    const programInput = document.getElementById('eventProgramInput');
    const yearInput = document.getElementById('eventYearInput');
    const sectionInput = document.getElementById('eventSectionInput');
    if (!programInput || !yearInput || !sectionInput) return;
    const program = String(programInput.value || '').trim();
    const year = String(yearInput.value || '').trim();
    const section = String(sectionInput.value || '').trim();
    if (!program || !year || !section) {
      showAppAlert('Please select program, year level, and section.', 'Incomplete Section');
      return;
    }
    const combined = program + '|' + year + '|' + section;
    const norm = combined.replace(/\s+/g, '').toUpperCase();
    const sec = SECTION_KEYS.find((s) => String(s || '').replace(/\s+/g, '').toUpperCase() === norm);
    if (!sec) {
      showAppAlert('Please select a valid Program/Year/Section from existing sections.', 'Invalid Section');
      return;
    }
    if (!eventSections.includes(sec)) {
      eventSections.push(sec);
      renderEventSections();
    }
    programInput.value = '';
    yearInput.value = '';
    sectionInput.value = '';
  }
  function removeEventSection(sec) {
    eventSections = eventSections.filter((s) => s !== sec);
    renderEventSections();
  }
  function renderEventSections() {
    const wrap = document.getElementById('eventSectionsTableWrap');
    const hidden = document.getElementById('eventSectionsHidden');
    if (!wrap || !hidden) return;
    hidden.value = eventSections.join(',');
    if (!eventSections.length) {
      wrap.innerHTML = '';
      return;
    }
    wrap.innerHTML = '<table class="ac-table"><thead><tr><th class="ac-th">Program</th><th class="ac-th">Year</th><th class="ac-th">Section</th><th class="ac-th">Action</th></tr></thead><tbody>' +
      eventSections.map((sec) => {
        const p = String(sec).split('|');
        return '<tr><td class="ac-td">' + esc(p[0] || '') + '</td><td class="ac-td">' + esc(p[1] || '') + '</td><td class="ac-td">' + esc(p[2] || '') + '</td>' +
          '<td class="ac-td"><button type="button" class="btn-outline" onclick="removeEventSection(\'' + esc(sec) + '\')">Remove</button></td></tr>';
      }).join('') + '</tbody></table>';
  }
  function applyPreset(prefix, st, et) {
    document.getElementById(prefix + 'StartTime').value = st;
    document.getElementById(prefix + 'EndTime').value = et;
  }

  function toggleClassTypeFields() {
    const lectureEnabled = !!document.getElementById('addLectureEnabled')?.checked;
    const labEnabled = !!document.getElementById('addLabEnabled')?.checked;
    const lectureStart = document.getElementById('addLectureStartTime');
    const lectureEnd = document.getElementById('addLectureEndTime');
    const labStart = document.getElementById('addLabStartTime');
    const labEnd = document.getElementById('addLabEndTime');
    const lectureRow = document.getElementById('addLectureRow');
    const lecturePresets = document.getElementById('addLecturePresets');
    const labBlock = document.getElementById('addLabBlock');

    if (lectureRow) lectureRow.style.display = lectureEnabled ? 'grid' : 'none';
    if (lecturePresets) lecturePresets.style.display = lectureEnabled ? 'flex' : 'none';
    if (labBlock) labBlock.style.display = labEnabled ? 'block' : 'none';

    if (lectureStart) lectureStart.required = lectureEnabled;
    if (lectureEnd) lectureEnd.required = lectureEnabled;
    if (labStart) labStart.required = labEnabled;
    if (labEnd) labEnd.required = labEnabled;
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
    if (!hid || !thid || !hid.value || !thid.value) { showAppAlert('Please select subject and teacher from dropdown.', 'Missing Required Fields'); return false; }

    if (prefix === 'add') {
      const lectureEnabled = !!document.getElementById('addLectureEnabled')?.checked;
      const labEnabled = !!document.getElementById('addLabEnabled')?.checked;
      let lectureRange = null;
      let labRange = null;
      if (!lectureEnabled && !labEnabled) {
        showAppAlert('Please select at least one class type (Lecture or Laboratory).', 'Missing Class Type');
        return false;
      }

      if (lectureEnabled) {
        const st = document.getElementById('addLectureStartTime')?.value || '';
        const et = document.getElementById('addLectureEndTime')?.value || '';
        const stMins = timeToMins(st);
        const etMins = timeToMins(et);
        if (!st || !et || stMins >= etMins) {
          showAppAlert('Lecture end time must be later than lecture start time.', 'Invalid Lecture Time');
          return false;
        }
        lectureRange = { start: stMins, end: etMins };
      }

      if (labEnabled) {
        const st = document.getElementById('addLabStartTime')?.value || '';
        const et = document.getElementById('addLabEndTime')?.value || '';
        const stMins = timeToMins(st);
        const etMins = timeToMins(et);
        if (!st || !et || stMins >= etMins) {
          showAppAlert('Laboratory end time must be later than laboratory start time.', 'Invalid Laboratory Time');
          return false;
        }
        labRange = { start: stMins, end: etMins };
      }

      // Overlap check allows back-to-back schedules (e.g., lecture ends 09:00 and lab starts 09:00).
      if (lectureRange && labRange) {
        const overlaps = lectureRange.end > labRange.start && labRange.end > lectureRange.start;
        if (overlaps) {
          showAppAlert('Lecture and Laboratory times overlap. Back-to-back schedules are allowed, but overlapping times are not.', 'Time Overlap');
          return false;
        }
      }
    }

    if (prefix === 'edit') {
      const st = document.getElementById('editStartTime')?.value || '';
      const et = document.getElementById('editEndTime')?.value || '';
      if (!st || !et || timeToMins(st) >= timeToMins(et)) {
        showAppAlert('End time must be later than start time.', 'Invalid Time Range');
        return false;
      }
    }

    return true;
  }

  /* -- PRE-SESSION NOTIFICATION (5 min before) -- */
  const notifiedSessions = new Set();
  function checkPresessions() {
    ALL_SCHEDULES.forEach(s => {
      if (!occursToday(s)) return;
      const mins = minsUntil(s);
      const key = s.schedule_id + '_' + dateKey(new Date());
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
    initializeDayHeaders();
    refreshActiveSessions().finally(() => buildCalendar(ALL_SCHEDULES));
    if (IS_SUPER) {
      toggleClassTypeFields();
      makeAC('addSubjInput', 'addSubjHidden', 'addSubjBody', 'addSubjDrop', subjDataFn, 'code', 'label');
      makeAC('addTeacherInput', 'addTeacherHidden', 'addTeacherBody', 'addTeacherDrop', teacherDataFn, 'label', 'role');
      makeAC('editSubjInput', 'editSubjHidden', 'editSubjBody', 'editSubjDrop', subjDataFn, 'code', 'label');
      makeAC('editTeacherInput', 'editTeacherHidden', 'editTeacherBody', 'editTeacherDrop', teacherDataFn, 'label', 'role');
    }
    checkPresessions();
    setInterval(checkRecurringSessions, 60000);
  });

  document.addEventListener('click', (e) => {
    if (!e.target.closest('.slot-search-wrap')) {
      document.getElementById('slotCurrentSearchDrop')?.classList.remove('open');
      document.getElementById('slotArchiveSearchDrop')?.classList.remove('open');
    }
  });


