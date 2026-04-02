    const CURRENT_TEACHER = "{{ (session.get('username','') or '')|lower }}";
    const ALL_SCHEDULES_RAW = {{ schedules | tojson }};
    const ALL_SCHEDULES = (ALL_SCHEDULES_RAW || []).filter((s) => {
        const owner = String((s || {}).teacher_username || '').trim().toLowerCase();
        return !CURRENT_TEACHER || owner === CURRENT_TEACHER;
    });
    const ALL_SUBJECTS = {{ subjects  | tojson if subjects else '{}' }};
    const DOW_NAMES = {{ dow_list  | tojson }};

    /* ── TIME UTILS ── */
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

    // Track active sessions to hide Live indicator if session has been ended prematurely
    let activeSessions = {};
    async function refreshActiveSessions() {
        try {
            const resp = await fetch('/api/active_sessions_info');
            if (resp.ok) {
                const data = await resp.json();
                activeSessions = data;
            }
        } catch (e) {
            console.warn('Could not fetch active sessions:', e);
        }
    }

    function sameId(a, b) {
        return String(a || '').trim() !== '' && String(a || '').trim() === String(b || '').trim();
    }

    function normalizeSectionKeyJs(v) {
        return String(v || '').trim().toUpperCase().replace(/\s+/g, '');
    }

    function findActiveSessionIdForSchedule(s) {
        const schedId = s.schedule_id;
        const schedSubj = String(s.subject_id || '');
        const schedSection = normalizeSectionKeyJs(s.section_key || '');
        for (const sid in activeSessions) {
            const sess = activeSessions[sid] || {};
            if (!sess.is_active) continue;
            // Primary: schedule-id match (supports number/string mismatches)
            if (sameId(sess.schedule_id, schedId)) return sid;
            // Fallback: subject + section match
            if (
                String(sess.subject_id || '') === schedSubj &&
                normalizeSectionKeyJs(sess.section_key || '') === schedSection
            ) {
                return sid;
            }
        }
        return null;
    }

    function isSessionActive(s) {
        return !!findActiveSessionIdForSchedule(s);
    }

    function isLive(s) {
        const isScheduleLive = occursToday(s) && nowMins() >= timeToMins(s.start_time) && nowMins() < timeToMins(s.end_time);
        // Only show Live if schedule is in the live time AND there's an active session (not ended prematurely)
        return isScheduleLive && isSessionActive(s);
    }
    function isUpcoming(s) { const diff = timeToMins(s.start_time) - nowMins(); return occursToday(s) && diff > 0 && diff <= 5; }
    function minsUntil(s) { return timeToMins(s.start_time) - nowMins(); }
    function classTypeLabel(v) {
        const t = String(v || 'lecture').toLowerCase();
        if (t === 'laboratory') return 'Laboratory';
        if (t === 'school_event') return 'School Event';
        return 'Lecture';
    }
    function joined(arr) {
        return Array.isArray(arr) && arr.length ? arr.join(', ') : '—';
    }

    /* ── HIGHLIGHT TODAY COLUMN ── */
    (function () {
        const th = document.getElementById('th_dow_' + todayDow());
        if (th) th.classList.add('today-col');
    })();

    /* ── CALENDAR ── */
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
        const grid = {};
        for (let d = 0; d < 7; d++) grid[d] = [];
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
                    div.dataset.subject = currentItems.map((s) => s.subject_id || '').join(',');
                    const sk = String(sample.section_key || '').split('|');
                    div.dataset.program = String(sk[0] || '').toLowerCase();
                    div.dataset.year = String(sk[1] || '').toLowerCase();
                    div.dataset.section = String(sk[2] || '').toLowerCase();
                    if (currentItems.some((s) => isLive(s))) div.classList.add('live-now');
                    else if (currentItems.some((s) => isUpcoming(s))) div.classList.add('upcoming-session');
                    div.onclick = () => openSlotModal(bucket, sample);
                    const liveHtml = currentItems.some((s) => isLive(s))
                        ? '<div class="live-badge-block"><span class="live-dot-small"></span> LIVE</div>'
                        : (currentItems.some((s) => isUpcoming(s)) ? '<div style="font-size:9px;color:#f59e0b;margin-top:2px;font-weight:700;IN ' + minsUntil(currentItems[0]) + 'm</div>' : '');
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

    /* ── FILTERS ── */
    let activeFilters = {};
    function applyFilter() {
        const sf = Object.values(activeFilters).filter(f => f.type === 'subject').map(f => f.value);
        const pf = (document.getElementById('tfProgram')?.value || '').trim().toLowerCase();
        const yf = (document.getElementById('tfYear')?.value || '').trim().toLowerCase();
        const secf = (document.getElementById('tfSection')?.value || '').trim().toLowerCase();
        const hasTeacherFilter = !!(pf || yf || secf);
        document.querySelectorAll('.sched-block').forEach(b => {
            const mSubject = sf.length === 0 || sf.includes(b.dataset.subject);
            const mProgram = !pf || b.dataset.program === pf;
            const mYear = !yf || b.dataset.year === yf;
            const mSection = !secf || b.dataset.section === secf;
            const isMatch = mSubject && mProgram && mYear && mSection;
            b.classList.toggle('filtered-out', !isMatch);
            b.classList.toggle('filter-hit', hasTeacherFilter && isMatch);
        });
    }

    function applyTeacherFilters() { applyFilter(); }
    function resetTeacherFilters() {
        const p = document.getElementById('tfProgram');
        const y = document.getElementById('tfYear');
        const s = document.getElementById('tfSection');
        if (p) p.value = '';
        if (y) y.value = '';
        if (s) s.value = '';
        applyFilter();
    }

    function initTeacherFilterOptions() {
        const programs = new Set();
        const years = new Set();
        const sections = new Set();
        (ALL_SCHEDULES || []).forEach((s) => {
            const sk = String(s.section_key || '').split('|');
            if (sk[0]) programs.add(sk[0]);
            if (sk[1]) years.add(sk[1]);
            if (sk[2]) sections.add(sk[2]);
        });
        const fill = (id, vals) => {
            const dl = document.getElementById(id);
            if (!dl) return;
            dl.innerHTML = Array.from(vals).sort().map((v) => '<option value="' + esc(v) + '"></option>').join('');
        };
        fill('programOptions', programs);
        fill('yearOptions', years);
        fill('sectionOptions', sections);
    }
    function addFilter(type, value, label) {
        const key = type + '_' + value;
        if (activeFilters[key]) return;
        activeFilters[key] = { type, value, label };
        renderChips(); applyFilter();
    }
    function removeFilter(key) { delete activeFilters[key]; renderChips(); applyFilter(); }
    function renderChips() {
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

    /* ── SEARCH ── */
    let searchTm = null;
    function onSearchInput() { clearTimeout(searchTm); searchTm = setTimeout(doSearch, 180); }
    function doSearch() {
        const q = (document.getElementById('schedSearchInput').value || '').trim().toLowerCase();
        const drop = document.getElementById('schedSearchDrop'); if (!drop) return;
        if (!q) { drop.classList.remove('open'); return; }
        const subjects = Object.entries(ALL_SUBJECTS).filter(e =>
            (e[1].name || '').toLowerCase().includes(q) || (e[1].course_code || '').toLowerCase().includes(q)
        ).slice(0, 8);
        if (!subjects.length) { drop.innerHTML = '<div style="padding:12px;font-size:12px;color:var(--muted);text-align:center;">No matches.</div>'; drop.classList.add('open'); return; }
        let html = '<div class="search-section-label">Subjects</div>';
        subjects.forEach(e => {
            const lbl = '[' + e[1].course_code + '] ' + e[1].name;
            html += '<div class="search-result-row" onclick="addFilter(\'subject\',\'' + e[0] + '\',\'' + esc(lbl) + '\');closeSearch()">' +
                '<span class="search-result-name">' + esc(lbl) + '</span>' +
                '<span class="search-result-badge">Subject</span></div>';
        });
        drop.innerHTML = html; drop.classList.add('open');
    }
    function closeSearch() { document.getElementById('schedSearchInput').value = ''; document.getElementById('schedSearchDrop').classList.remove('open'); }
    document.addEventListener('click', e => { if (!e.target.closest('.sched-search-wrap')) document.getElementById('schedSearchDrop')?.classList.remove('open'); });

    /* ── MODAL ── */
    let selectedSched = null;
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
            if (sec && !e.section_keys_involved.includes(sec)) e.section_keys_involved.push(sec);
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
        if (summary) summary.textContent = selectedSlot.dayLabel + ' | ' + selectedSlot.timeLabel;
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

    function openSchedModal(s) {
        selectedSched = s;
        const dayIdx = normalizeDow(s.day_of_week);
        document.getElementById('infoSubjectName').textContent = s.subject_name;
        document.getElementById('infoCourseCode').textContent = s.course_code || '';
        if (isSchoolEvent(s)) {
            const teachers = Array.isArray(s.teachers_involved) && s.teachers_involved.length
                ? s.teachers_involved
                : [s.teacher_name || '—'];
            document.getElementById('infoTeacherName').innerHTML = teachers.map((t) => esc(t)).join('<br>');
            const sectionKeys = Array.isArray(s.section_keys_involved) && s.section_keys_involved.length
                ? s.section_keys_involved
                : (s.section_key ? [s.section_key] : []);
            const sections = sectionKeys.map((sec) => {
                const p = String(sec || '').split('|');
                return (p[0] || '-') + '-' + (p[1] || '-') + '-' + (p[2] || '-');
            });
            document.getElementById('infoSectionName').innerHTML = sections.length
                ? sections.map((v) => '<div>' + esc(v) + '</div>').join('')
                : '—';
        } else {
            document.getElementById('infoTeacherName').textContent = s.teacher_name || '—';
            document.getElementById('infoSectionName').textContent = (s.section_key || '').split('|').join(' · ');
        }
        if (isSchoolEvent(s)) {
            document.getElementById('infoDayTime').textContent = (fmtEventDate(s.event_date) || DOW_NAMES[dayIdx]) + ' @ ' + fmtTime(to24h(s.start_time)) + ' – ' + fmtTime(to24h(s.end_time));
        } else {
            document.getElementById('infoDayTime').textContent = DOW_NAMES[dayIdx] + ' @ ' + fmtTime(to24h(s.start_time)) + ' – ' + fmtTime(to24h(s.end_time));
        }
        document.getElementById('infoClassType').textContent = classTypeLabel(s.class_type);
        document.getElementById('infoGrace').textContent = (s.grace_minutes || 15) + ' minutes';
        document.getElementById('infoLiveIndicator').style.display = isLive(s) ? 'block' : 'none';
        const monitorBtn = document.getElementById('monitorLiveBtn');
        const activeSessId = findActiveSessionIdForSchedule(s);
        if (monitorBtn) {
            if (activeSessId) {
                monitorBtn.href = '/teacher/session/' + encodeURIComponent(activeSessId);
                monitorBtn.style.display = 'inline-flex';
            } else {
                monitorBtn.href = '#';
                monitorBtn.style.display = 'none';
            }
        }

        // Next class calculation
        let nextTxt = '—';
        if (isLive(s)) {
            nextTxt = 'Currently in session';
        } else if (isSchoolEvent(s)) {
            const eventDate = parseYmd(s.event_date);
            if (eventDate) {
                const today = new Date();
                today.setHours(0, 0, 0, 0);
                const st = fmtTime(to24h(s.start_time));
                if (eventDate < today) nextTxt = 'Completed event';
                else nextTxt = fmtEventDate(s.event_date) + ' @ ' + st;
            } else {
                nextTxt = DOW_NAMES[normalizeDow(s.day_of_week)] + ' @ ' + fmtTime(to24h(s.start_time));
            }
        } else {
            const d = new Date();
            let diff = (dayIdx - todayDow() + 7) % 7;
            if (diff === 0) diff = 7;
            const nd = new Date(d); nd.setDate(nd.getDate() + diff);
            nextTxt = DOW_NAMES[dayIdx] + ', ' + nd.toLocaleDateString('en-US', { month: 'short', day: 'numeric' }) + ' @ ' + fmtTime(to24h(s.start_time));
        }
        document.getElementById('infoNextClass').textContent = nextTxt;
        document.getElementById('scheduleModal').classList.add('show');
    }
    function closeSchedModal() { document.getElementById('scheduleModal').classList.remove('show'); selectedSched = null; }

    /* ── PRE-SESSION NOTIFICATION (5 minutes) ── */
    const notified = new Set();
    function checkPresessions() {
        ALL_SCHEDULES.forEach(s => {
            if (!occursToday(s)) return;
            const mins = minsUntil(s);
            const key = s.schedule_id + '_' + dateKey(new Date());
            if (mins > 0 && mins <= 5 && !notified.has(key)) {
                notified.add(key);
                showPresessionToast(s, mins);
            }
        });
    }
    function showPresessionToast(s, mins) {
        const c = document.getElementById('presessionContainer');
        const el = document.createElement('div');
        el.className = 'presession-toast';
        el.style.position = 'fixed'; el.style.bottom = '24px'; el.style.right = '24px'; el.style.zIndex = '9999';
        el.innerHTML =
            '<button class="presession-close" onclick="this.parentNode.remove()"><i class="bi bi-x"></i></button>' +
            '<div style="font-size:26px;margin-bottom:7px;">⏰</div>' +
            '<div class="presession-toast-title">Class Starting in ' + mins + ' Minute' + (mins !== 1 ? 's' : '') + '!</div>' +
            '<div class="presession-toast-body">' +
            '<strong>' + esc(s.subject_name) + '</strong><br>' +
            (s.section_key || '').replace(/\|/g, ' · ') + '<br>' +
            fmtTime(to24h(s.start_time)) + ' – ' + fmtTime(to24h(s.end_time)) +
            '</div>';
        c.appendChild(el);
        setTimeout(() => {
            if (el.parentNode) { el.classList.add('removing'); setTimeout(() => el.parentNode && el.remove(), 350); }
        }, 30000);
    }

    /* ── INIT ── */
    document.addEventListener('DOMContentLoaded', () => {
        initTeacherFilterOptions();
        const tick = async () => {
            await refreshActiveSessions();
            buildCalendar(ALL_SCHEDULES);
            checkPresessions();
            if (selectedSched) {
                // Keep modal live/monitor state synced while it is open.
                openSchedModal(selectedSched);
            }
        };
        tick();
        setInterval(tick, 3000);
    });

    document.addEventListener('click', (e) => {
        if (!e.target.closest('.slot-search-wrap')) {
            document.getElementById('slotCurrentSearchDrop')?.classList.remove('open');
            document.getElementById('slotArchiveSearchDrop')?.classList.remove('open');
        }
    });

