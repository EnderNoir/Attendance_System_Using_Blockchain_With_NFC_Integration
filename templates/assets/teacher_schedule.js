const ALL_SCHEDULES = {{ schedules | tojson }};
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
        const isScheduleLive = s.day_of_week === todayDow() && nowMins() >= timeToMins(s.start_time) && nowMins() < timeToMins(s.end_time);
        // Only show Live if schedule is in the live time AND there's an active session (not ended prematurely)
        return isScheduleLive && isSessionActive(s);
    }
    function isUpcoming(s) { const diff = timeToMins(s.start_time) - nowMins(); return s.day_of_week === todayDow() && diff > 0 && diff <= 5; }
    function minsUntil(s) { return timeToMins(s.start_time) - nowMins(); }

    /* ── HIGHLIGHT TODAY COLUMN ── */
    (function () {
        const th = document.getElementById('th_dow_' + todayDow());
        if (th) th.classList.add('today-col');
    })();

    /* ── CALENDAR ── */
    const TIME_SLOTS = ['07:00', '07:30', '08:00', '08:30', '09:00', '09:30', '10:00', '10:30',
        '11:00', '11:30', '12:00', '12:30', '13:00', '13:30', '14:00', '14:30',
        '15:00', '15:30', '16:00', '16:30', '17:00', '17:30', '18:00'];

    function esc(s) { return String(s || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;'); }

    function buildCalendar(filtered) {
        const body = document.getElementById('calBody'); if (!body) return;
        body.innerHTML = '';
        const grid = {};
        for (let d = 0; d < 7; d++) grid[d] = [];
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
                    div.dataset.subject = s.subject_id || '';
                    if (isLive(s)) div.classList.add('live-now');
                    else if (isUpcoming(s)) div.classList.add('upcoming-session');
                    div.onclick = () => openSchedModal(s);
                    const liveHtml = isLive(s)
                        ? '<div class="live-badge-block"><span class="live-dot-small"></span> LIVE</div>'
                        : (isUpcoming(s) ? '<div style="font-size:9px;color:#f59e0b;margin-top:2px;font-weight:700;">⏱ ' + minsUntil(s) + 'm</div>' : '');
                    div.innerHTML =
                        '<div class="sb-subject">' + esc(s.subject_name) + '</div>' +
                        '<div class="sb-time">' + fmtTime(to24h(s.start_time)) + ' – ' + fmtTime(to24h(s.end_time)) + '</div>' +
                        '<div class="sb-section">' + (s.section_key || '').replace(/\|/g, ' · ') + '</div>' + liveHtml;
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
        document.querySelectorAll('.sched-block').forEach(b => {
            b.classList.toggle('filtered-out', sf.length > 0 && !sf.includes(b.dataset.subject));
        });
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
    function openSchedModal(s) {
        selectedSched = s;
        document.getElementById('infoSubjectName').textContent = s.subject_name;
        document.getElementById('infoCourseCode').textContent = s.course_code || '';
        document.getElementById('infoTeacherName').textContent = s.teacher_name || '—';
        document.getElementById('infoSectionName').textContent = (s.section_key || '').split('|').join(' · ');
        document.getElementById('infoDayTime').textContent = DOW_NAMES[s.day_of_week] + ' @ ' + fmtTime(to24h(s.start_time)) + ' – ' + fmtTime(to24h(s.end_time));
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
        } else {
            const d = new Date();
            let diff = (s.day_of_week - todayDow() + 7) % 7;
            if (diff === 0) diff = 7;
            const nd = new Date(d); nd.setDate(nd.getDate() + diff);
            nextTxt = DOW_NAMES[s.day_of_week] + ', ' + nd.toLocaleDateString('en-US', { month: 'short', day: 'numeric' }) + ' @ ' + fmtTime(to24h(s.start_time));
        }
        document.getElementById('infoNextClass').textContent = nextTxt;
        document.getElementById('scheduleModal').classList.add('show');
    }
    function closeSchedModal() { document.getElementById('scheduleModal').classList.remove('show'); selectedSched = null; }

    /* ── PRE-SESSION NOTIFICATION (5 minutes) ── */
    const notified = new Set();
    function checkPresessions() {
        ALL_SCHEDULES.forEach(s => {
            const mins = minsUntil(s);
            const key = s.schedule_id + '_' + new Date().toDateString();
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

