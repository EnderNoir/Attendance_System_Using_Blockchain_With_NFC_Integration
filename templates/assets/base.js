/* ══ SESSION INTEGRITY — prevents cross-tab session mixing ══ */
    (function () {
      // Store current session identity in sessionStorage (tab-local)
      // Each tab tracks its own logged-in user identity
      const username = '{{ session.get("username","") }}';
      const role = '{{ session.get("role","") }}';
      if (username) {
        const stored = window.sessionStorage.getItem('davs_session_user');
        const storedRole = window.sessionStorage.getItem('davs_session_role');
        // If the tab previously had a DIFFERENT user (session was swapped in same tab),
        // reload the page to ensure we show the correct user's data.
        if (stored && stored !== username) {
          window.sessionStorage.setItem('davs_session_user', username);
          window.sessionStorage.setItem('davs_session_role', role);
          // Reload without cache to get fresh server-rendered content for this user
          window.location.reload(true);
          return;
        }
        window.sessionStorage.setItem('davs_session_user', username);
        window.sessionStorage.setItem('davs_session_role', role);
      }
    })();
    function toggleTheme() { var h = document.documentElement, c = h.getAttribute('data-theme') || 'light', n = c === 'dark' ? 'light' : 'dark'; h.setAttribute('data-theme', n); try { localStorage.setItem('davs_theme', n); } catch (e) { } updateThemeIcon(n); }
    function updateThemeIcon(t) { var isDark = (t || document.documentElement.getAttribute('data-theme') || 'light') === 'dark'; var i = document.getElementById('themeIcon'), l = document.getElementById('themeLabel'); if (i) i.className = isDark ? 'bi bi-sun-fill' : 'bi bi-moon-fill'; if (l) l.textContent = isDark ? 'Light' : 'Dark'; }
    (function () { try { var s = localStorage.getItem('davs_theme') || 'light'; document.documentElement.setAttribute('data-theme', s); updateThemeIcon(s); } catch (e) { } })();

    /* ══ CLOCK ══ */
    function updateClock() { var el = document.getElementById('clock'); if (el) el.textContent = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' }); }
    updateClock(); setInterval(updateClock, 1000);

    /* ══ SIDEBAR ══ */
    function openSidebar() { document.getElementById('sidebar').classList.add('open'); document.getElementById('sidebarOverlay').classList.add('open'); document.body.style.overflow = 'hidden'; }
    function closeSidebar() { document.getElementById('sidebar').classList.remove('open'); document.getElementById('sidebarOverlay').classList.remove('open'); document.body.style.overflow = ''; }
    document.addEventListener('keydown', function (e) { if (e.key === 'Escape') closeSidebar(); });

    /* ══ TOAST ══ */
    var lastSeenTimestamp = Date.now() / 1000;
    function showCustomToast(e) { var s = document.getElementById('toastStack'), t = document.createElement('div'); t.className = 'custom-toast'; var tm = new Date(e.timestamp * 1000).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' }); t.innerHTML = '<div class="toast-dot"></div><div><div class="toast-title">Attendance Marked</div><div class="toast-body-text">' + e.name + ' &middot; <code>' + e.nfc_id + '</code></div><div class="toast-body-text">' + tm + '</div></div>'; s.appendChild(t); setTimeout(function () { t.style.opacity = '0'; t.style.transform = 'translateX(20px)'; t.style.transition = 'all .3s'; setTimeout(function () { t.remove(); }, 300); }, 5000); }
    var _davsPollActive = !window.location.pathname.match(/\/session\//);
    function pollAttendance() {
      if (!_davsPollActive) return;
      fetch('/api/attendance/recent?since=' + lastSeenTimestamp, { credentials: 'same-origin' }).then(function (r) { return r.json(); }).then(function (evs) { evs.forEach(function (e) { if (e.timestamp > lastSeenTimestamp) lastSeenTimestamp = e.timestamp; showCustomToast(e); }); }).catch(function () { });
    }
    window.addEventListener('load', function () { if (_davsPollActive) { pollAttendance(); setInterval(pollAttendance, 3000); } });

    /* ══ SIDEBAR PHOTO ══ */
    (function () { fetch('/get_my_photo', { credentials: 'same-origin' }).then(function (r) { return r.json(); }).then(function (d) { if (d.url) setSidebarPhoto(d.url); }).catch(function () { }); })();
    function setSidebarPhoto(url) { var w = document.getElementById('sidebarAvatarWrap'); if (!w) return; w.innerHTML = ''; w.style.cssText = 'width:32px;height:32px;border-radius:50%;overflow:hidden;flex-shrink:0;'; var img = document.createElement('img'); img.src = url + '?t=' + Date.now(); img.style = 'width:100%;height:100%;object-fit:cover;'; w.appendChild(img); }

    /* ══ AVATAR UTIL ══ */
    function setAvatarImg(wrapId, src) { var w = document.getElementById(wrapId); if (!w) return; w.innerHTML = ''; w.style.overflow = 'hidden'; var img = document.createElement('img'); img.src = src; img.style = 'width:100%;height:100%;object-fit:cover;border-radius:50%;'; w.appendChild(img); }

    /* ══ SECTION ACCORDION ══ */
    function buildSectionAccordion(sections) {
      if (!sections || !sections.length) return '<span style="font-size:13px;color:var(--muted);font-weight:500;">No sections assigned.</span>';
      var groups = {};
      sections.forEach(function (key) { var parts = key.split('|'); var prog = parts[0] || 'Unknown'; var yr = parts[1] || '—'; var sec = parts[2] || '—'; if (!groups[prog]) groups[prog] = {}; if (!groups[prog][yr]) groups[prog][yr] = []; groups[prog][yr].push(sec); });
      var html = '';
      Object.keys(groups).sort().forEach(function (prog) {
        var yo = groups[prog]; var tot = Object.values(yo).reduce(function (a, b) { return a + b.length; }, 0);
        html += '<div class="sec-accordion"><div class="sec-acc-program" onclick="toggleSecAccProgram(this)">';
        html += '<span class="sec-acc-program-name"><i class="bi bi-mortarboard"></i>' + prog + '</span>';
        html += '<span style="display:flex;align-items:center;gap:8px;"><span class="sec-acc-program-count">' + tot + ' section' + (tot !== 1 ? 's' : '') + '</span><i class="bi bi-chevron-down sec-acc-chevron"></i></span></div>';
        html += '<div class="sec-acc-years">';
        Object.keys(yo).sort().forEach(function (yr) {
          var secs = yo[yr];
          html += '<div class="sec-acc-year" onclick="toggleSecAccYear(this)">';
          html += '<span class="sec-acc-year-label"><i class="bi bi-layers"></i>' + yr + '</span>';
          html += '<span style="display:flex;align-items:center;gap:8px;"><span style="font-size:12px;color:var(--muted);font-weight:600;">' + secs.join(', ') + '</span><i class="bi bi-chevron-down sec-acc-year-chevron"></i></span></div>';
          html += '<div class="sec-acc-sections">';
          secs.forEach(function (s) { html += '<span class="sec-chip">' + s + '</span>'; });
          html += '</div>';
        });
        html += '</div></div>';
      });
      return html;
    }
    function toggleSecAccProgram(el) { var d = el.nextElementSibling; var o = d.classList.contains('open'); el.classList.toggle('open', !o); d.classList.toggle('open', !o); }
    function toggleSecAccYear(el) { var d = el.nextElementSibling; var o = d.classList.contains('open'); el.classList.toggle('open', !o); d.classList.toggle('open', !o); }
    function buildSectionsTable(s) { return buildSectionAccordion(s); }

    /* ══ ADMIN PROFILE MODAL ══ */
    var pmStagedFile = null;
    function openPM() {
      var m = document.getElementById('profileModal'); if (!m) return;
      document.querySelectorAll('#profileModal .pm-pane').forEach(function (p) { p.classList.remove('active'); });
      var ip = document.getElementById('pm-info'); if (ip) ip.classList.add('active');
      document.querySelectorAll('#profileModal .pm-tab').forEach(function (b, i) { b.classList.toggle('active-tab', i === 0); });
      pmStagedFile = null; m.classList.add('show');
      fetch('/api/my_profile', { credentials: 'same-origin' }).then(function (r) { return r.json(); }).then(function (d) {
        var em = document.getElementById('pmEmail'); if (em && d.email) em.value = d.email;
        var ie = document.getElementById('pm_info_email'); if (ie) ie.textContent = d.email || '—';
        var rp = document.getElementById('pmRolePill'); if (rp) rp.textContent = (d.role || 'admin').toUpperCase();
        if (d.photo) { var url = '/static/uploads/' + d.photo + '?t=' + Date.now(); setAvatarImg('pmInfoAvatarWrap', url); setAvatarImg('pmEditAvatarWrap', url); }
      }).catch(function () { });
    }
    function closePM() { var m = document.getElementById('profileModal'); if (m) m.classList.remove('show'); pmStagedFile = null; }
    function switchPmTab(id, btn) {
      document.querySelectorAll('#profileModal .pm-pane').forEach(function (p) { p.classList.remove('active'); });
      document.querySelectorAll('#profileModal .pm-tab').forEach(function (b) { b.classList.remove('active-tab'); });
      var p = document.getElementById('pm-' + id); if (p) p.classList.add('active'); if (btn) btn.classList.add('active-tab');
    }
    function stageAdminPhoto(input) { if (!input.files || !input.files[0]) return; pmStagedFile = input.files[0]; var reader = new FileReader(); reader.onload = function (e) { setAvatarImg('pmEditAvatarWrap', e.target.result); }; reader.readAsDataURL(pmStagedFile); }
    function clearPmErr(el, errId) { el.style.borderColor = ''; var e = document.getElementById(errId); if (e) e.style.display = 'none'; }
    function checkPmPwMatch() { var pw = document.getElementById('pmPass') ? document.getElementById('pmPass').value : ''; var pw2 = document.getElementById('pmPass2') ? document.getElementById('pmPass2').value : ''; var err = document.getElementById('pmPass2Err'); if (err) err.style.display = (pw && pw2 && pw !== pw2) ? 'block' : 'none'; }
    async function requestProfilePasswordOtp(kind) {
      var isTeacher = kind === 'teacher';
      var prefix = isTeacher ? 'tpm' : 'pm';
      var passEl = document.getElementById(prefix + 'Pass');
      var pass = passEl ? passEl.value : '';
      var msg = document.getElementById(prefix + 'Msg');
      var hint = document.getElementById(prefix + 'OtpHint');
      var btn = document.getElementById(prefix + 'OtpBtn');
      if (!pass || pass.length < 6) {
        if (passEl) passEl.style.borderColor = 'var(--danger)';
        var perr = document.getElementById(prefix + 'PassErr');
        if (perr) perr.style.display = 'block';
        if (hint) { hint.style.color = 'var(--danger)'; hint.textContent = 'Enter your new password first before requesting OTP.'; }
        return;
      }
      if (btn) { btn.disabled = true; btn.textContent = 'Sending...'; }
      try {
        var r = await fetch('/request_password_change_otp', { method: 'POST', credentials: 'same-origin', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({}) });
        var d = await r.json();
        if (d.ok) {
          if (hint) { hint.style.color = 'var(--success)'; hint.textContent = 'OTP sent to ' + (d.sent_to || 'your email') + '.'; }
          if (msg) { msg.style.display = 'block'; msg.style.color = 'var(--success)'; msg.textContent = 'OTP sent. Enter the 6-digit code to continue.'; }
        } else {
          if (hint) { hint.style.color = 'var(--danger)'; hint.textContent = d.error || 'Unable to send OTP.'; }
          if (msg) { msg.style.display = 'block'; msg.style.color = 'var(--danger)'; msg.textContent = d.error || 'Unable to send OTP.'; }
        }
      } catch (e) {
        if (hint) { hint.style.color = 'var(--danger)'; hint.textContent = 'Network error while sending OTP.'; }
      } finally {
        if (btn) { btn.disabled = false; btn.textContent = 'Send OTP'; }
      }
    }
    async function saveProfileModal() {
      var name = document.getElementById('pmName') ? document.getElementById('pmName').value.trim() : '';
      var email = document.getElementById('pmEmail') ? document.getElementById('pmEmail').value.trim() : '';
      var pass = document.getElementById('pmPass') ? document.getElementById('pmPass').value : '';
      var pass2 = document.getElementById('pmPass2') ? document.getElementById('pmPass2').value : '';
      var otp = document.getElementById('pmOtp') ? document.getElementById('pmOtp').value.trim() : '';
      var msg = document.getElementById('pmMsg'); var ok = true;
      if (!name) { var el = document.getElementById('pmName'); if (el) el.style.borderColor = 'var(--danger)'; var er = document.getElementById('pmNameErr'); if (er) er.style.display = 'block'; ok = false; }
      if (email && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) { var el = document.getElementById('pmEmail'); if (el) el.style.borderColor = 'var(--danger)'; var er = document.getElementById('pmEmailErr'); if (er) er.style.display = 'block'; ok = false; }
      if (pass && pass.length < 6) { var el = document.getElementById('pmPass'); if (el) el.style.borderColor = 'var(--danger)'; var er = document.getElementById('pmPassErr'); if (er) er.style.display = 'block'; ok = false; }
      if (pass && pass2 && pass !== pass2) { var er = document.getElementById('pmPass2Err'); if (er) er.style.display = 'block'; ok = false; }
      if (pass && (!otp || otp.length !== 6)) { var el = document.getElementById('pmOtp'); if (el) el.style.borderColor = 'var(--danger)'; var er = document.getElementById('pmOtpErr'); if (er) er.style.display = 'block'; ok = false; }
      if (!ok) return;
      if (pmStagedFile) { var fd = new FormData(); fd.append('photo', pmStagedFile); fd.append('person_id', '{{ session.get("username","") }}'); try { var pr = await fetch('/upload_photo', { method: 'POST', credentials: 'same-origin', body: fd }); var pd = await pr.json(); if (pd.ok) { setSidebarPhoto(pd.url); setAvatarImg('pmInfoAvatarWrap', pd.url + '?t=' + Date.now()); } } catch (e) { console.warn(e); } pmStagedFile = null; }
      try {
        var r = await fetch('/update_profile', { method: 'POST', credentials: 'same-origin', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ full_name: name, email: email, password: pass || undefined, password_otp: pass ? otp : undefined }) });
        var d = await r.json(); if (msg) msg.style.display = 'block';
        if (d.ok) {
          if (msg) { msg.style.color = 'var(--success)'; msg.textContent = '✓ Profile saved!'; }
          var sn = document.getElementById('sidebarName'); if (sn) sn.textContent = d.full_name;
          var dn = document.getElementById('pmDisplayName'); if (dn) dn.textContent = d.full_name;
          var ni = document.getElementById('pm_info_name'); if (ni) ni.textContent = d.full_name;
          var ei = document.getElementById('pm_info_email'); if (ei && email) ei.textContent = email;
          setTimeout(function () { closePM(); if (msg) msg.style.display = 'none'; }, 1400);
        } else { if (msg) { msg.style.color = 'var(--danger)'; msg.textContent = d.error || 'Error saving.'; } }
      } catch (e) { if (msg) { msg.style.color = 'var(--danger)'; msg.textContent = 'Network error.'; } }
    }

    /* ══ TEACHER PROFILE MODAL ══ */
    var tpmStagedFile = null;
    function openTPM() {
      var m = document.getElementById('teacherProfileModal'); if (!m) return;
      document.querySelectorAll('#teacherProfileModal .pm-pane').forEach(function (p) { p.classList.remove('active'); });
      var ip = document.getElementById('tpm-info'); if (ip) ip.classList.add('active');
      document.querySelectorAll('#teacherProfileModal .pm-tab').forEach(function (b, i) { b.classList.toggle('active-tab', i === 0); });
      tpmStagedFile = null; m.classList.add('show');
      fetch('/api/my_profile', { credentials: 'same-origin' }).then(function (r) { return r.json(); }).then(function (d) {
        var em = document.getElementById('tpmEmail'); if (em && d.email) em.value = d.email;
        var ie = document.getElementById('tpm_info_email'); if (ie) ie.textContent = d.email || '—';
        var iu = document.getElementById('tpm_info_username'); if (iu) iu.innerHTML = '<code>' + d.username + '</code>';
        var eu = document.getElementById('tpmUsername'); if (eu) eu.value = d.username || '';
        var sw = document.getElementById('tpm_info_sections_wrap'); if (sw) sw.innerHTML = buildSectionAccordion(d.sections || []);
        if (d.photo) { var url = '/static/uploads/' + d.photo + '?t=' + Date.now(); setAvatarImg('tpmInfoAvatarWrap', url); setAvatarImg('tpmEditAvatarWrap', url); }
      }).catch(function () { });
    }
    function closeTPM() { var m = document.getElementById('teacherProfileModal'); if (m) m.classList.remove('show'); tpmStagedFile = null; }
    function switchTPMTab(id, btn) {
      document.querySelectorAll('#teacherProfileModal .pm-pane').forEach(function (p) { p.classList.remove('active'); });
      document.querySelectorAll('#teacherProfileModal .pm-tab').forEach(function (b) { b.classList.remove('active-tab'); });
      var p = document.getElementById('tpm-' + id); if (p) p.classList.add('active'); if (btn) btn.classList.add('active-tab');
    }
    function stageTeacherPhoto(input) { if (!input.files || !input.files[0]) return; tpmStagedFile = input.files[0]; var reader = new FileReader(); reader.onload = function (e) { setAvatarImg('tpmEditAvatarWrap', e.target.result); }; reader.readAsDataURL(tpmStagedFile); }
    function clearTPMErr(el, errId) { el.style.borderColor = ''; var e = document.getElementById(errId); if (e) e.style.display = 'none'; }
    function checkTPMPwMatch() { var pw = document.getElementById('tpmPass') ? document.getElementById('tpmPass').value : ''; var pw2 = document.getElementById('tpmPass2') ? document.getElementById('tpmPass2').value : ''; var err = document.getElementById('tpmPass2Err'); if (err) err.style.display = (pw && pw2 && pw !== pw2) ? 'block' : 'none'; }
    async function saveTeacherProfile() {
      var name = document.getElementById('tpmName') ? document.getElementById('tpmName').value.trim() : '';
      var uname = document.getElementById('tpmUsername') ? document.getElementById('tpmUsername').value.trim() : '';
      var email = document.getElementById('tpmEmail') ? document.getElementById('tpmEmail').value.trim() : '';
      var pass = document.getElementById('tpmPass') ? document.getElementById('tpmPass').value : '';
      var pass2 = document.getElementById('tpmPass2') ? document.getElementById('tpmPass2').value : '';
      var otp = document.getElementById('tpmOtp') ? document.getElementById('tpmOtp').value.trim() : '';
      var msg = document.getElementById('tpmMsg'); var ok = true;
      if (!name) { var el = document.getElementById('tpmName'); if (el) el.style.borderColor = 'var(--danger)'; var er = document.getElementById('tpmNameErr'); if (er) er.style.display = 'block'; ok = false; }
      if (!uname) { var el = document.getElementById('tpmUsername'); if (el) el.style.borderColor = 'var(--danger)'; var er = document.getElementById('tpmUsernameErr'); if (er) er.style.display = 'block'; ok = false; }
      if (email && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) { var el = document.getElementById('tpmEmail'); if (el) el.style.borderColor = 'var(--danger)'; var er = document.getElementById('tpmEmailErr'); if (er) er.style.display = 'block'; ok = false; }
      if (pass && pass.length < 6) { var el = document.getElementById('tpmPass'); if (el) el.style.borderColor = 'var(--danger)'; var er = document.getElementById('tpmPassErr'); if (er) er.style.display = 'block'; ok = false; }
      if (pass && pass2 && pass !== pass2) { var er = document.getElementById('tpmPass2Err'); if (er) er.style.display = 'block'; ok = false; }
      if (pass && (!otp || otp.length !== 6)) { var el = document.getElementById('tpmOtp'); if (el) el.style.borderColor = 'var(--danger)'; var er = document.getElementById('tpmOtpErr'); if (er) er.style.display = 'block'; ok = false; }
      if (!ok) return;
      if (tpmStagedFile) { var fd = new FormData(); fd.append('photo', tpmStagedFile); fd.append('person_id', '{{ session.get("username","") }}'); try { var pr = await fetch('/upload_photo', { method: 'POST', credentials: 'same-origin', body: fd }); var pd = await pr.json(); if (pd.ok) { setSidebarPhoto(pd.url); setAvatarImg('tpmInfoAvatarWrap', pd.url + '?t=' + Date.now()); } } catch (e) { console.warn(e); } tpmStagedFile = null; }
      try {
        var r = await fetch('/update_profile', { method: 'POST', credentials: 'same-origin', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ full_name: name, new_username: uname, email: email, password: pass || undefined, password_otp: pass ? otp : undefined }) });
        var d = await r.json(); if (msg) msg.style.display = 'block';
        if (d.ok) {
          if (msg) { msg.style.color = 'var(--success)'; msg.textContent = '✓ Profile saved!'; }
          var sn = document.getElementById('sidebarName'); if (sn) sn.textContent = d.full_name;
          var dn = document.getElementById('tpmDisplayName'); if (dn) dn.textContent = d.full_name;
          var ni = document.getElementById('tpm_info_name'); if (ni) ni.textContent = d.full_name;
          var ei = document.getElementById('tpm_info_email'); if (ei && email) ei.textContent = email;
          var ui = document.getElementById('tpm_info_username'); if (ui) ui.innerHTML = '<code>' + uname + '</code>';
          setTimeout(function () { closeTPM(); if (msg) msg.style.display = 'none'; }, 1400);
        } else { if (msg) { msg.style.color = 'var(--danger)'; msg.textContent = d.error || 'Error saving.'; } }
      } catch (e) { if (msg) { msg.style.color = 'var(--danger)'; msg.textContent = 'Network error.'; } }
    }

    /* ══ BLOCKCHAIN STATUS ══ */
    function updateChainBadge() { fetch('/api/blockchain_status', { credentials: 'same-origin' }).then(function (r) { return r.json(); }).then(function (d) { var badge = document.getElementById('chainBadge'), lbl = document.getElementById('chainStatus'); if (!badge || !lbl) return; if (d.online) { badge.classList.remove('offline'); lbl.textContent = 'Blockchain Online'; } else { badge.classList.add('offline'); lbl.textContent = 'Offline — ' + d.student_cache_count + ' cached'; } }).catch(function () { var badge = document.getElementById('chainBadge'), lbl = document.getElementById('chainStatus'); if (badge) badge.classList.add('offline'); if (lbl) lbl.textContent = 'Network error'; }); }
    updateChainBadge(); setInterval(updateChainBadge, 10000);

    // ── Shared export button animation ────────────────────────────────────────
    // Call this on ANY export button: animateExportBtn(btn, '/export/url?params')
    // The button shows "Exporting…" for 2s then resets. Works for all export types.
    function animateExportBtn(btn, url) {
      const original = btn.innerHTML;
      btn.disabled = true;
      btn.innerHTML = '<i class="bi bi-hourglass-split"></i> Exporting…';
      const a = document.createElement('a');
      a.href = url;
      a.style.display = 'none';
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      setTimeout(() => {
        btn.disabled = false;
        btn.innerHTML = original;
      }, 2000);
    }
