const state = {
      blocks: [],
      context: {},
      selectedBlock: null,
      latestBlockSeen: null,
      tour: {
        active: false,
        stepIndex: 0,
        remaining: 60,
        stepCounter: 0,
        stepDuration: 10,
        paused: false,
        timerId: null,
      },
      peers: [
        { name: 'Peer A', lag: 0 },
        { name: 'Peer B', lag: 0 },
        { name: 'Peer C', lag: 0 },
      ],
    };

    const ui = {
      chipNetwork: document.getElementById('chipNetwork'),
      chipLatest: document.getElementById('chipLatest'),
      chipLoaded: document.getElementById('chipLoaded'),
      chipValidity: document.getElementById('chipValidity'),
      contextChips: document.getElementById('contextChips'),
      errorBox: document.getElementById('errorBox'),
      subjectFilter: document.getElementById('subjectFilter'),
      yearFilter: document.getElementById('yearFilter'),
      limitRange: document.getElementById('limitRange'),
      limitText: document.getElementById('limitText'),
      autoRefresh: document.getElementById('autoRefresh'),
      refreshBtn: document.getElementById('refreshBtn'),
      hashInput: document.getElementById('hashInput'),
      nonceInput: document.getElementById('nonceInput'),
      charCount: document.getElementById('charCount'),
      hashOutput: document.getElementById('hashOutput'),
      simBlockNumber: document.getElementById('simBlockNumber'),
      simPrevHash: document.getElementById('simPrevHash'),
      simData: document.getElementById('simData'),
      simDifficulty: document.getElementById('simDifficulty'),
      simNonce: document.getElementById('simNonce'),
      simHash: document.getElementById('simHash'),
      mineBtn: document.getElementById('mineBtn'),
      mineStatus: document.getElementById('mineStatus'),
      blockPicker: document.getElementById('blockPicker'),
      blockDetails: document.getElementById('blockDetails'),
      chainRoot: document.getElementById('chainRoot'),
      peerGrid: document.getElementById('peerGrid'),
      syncDemoBtn: document.getElementById('syncDemoBtn'),
      txBars: document.getElementById('txBars'),
      tamperInput: document.getElementById('tamperInput'),
      tamperOrigHash: document.getElementById('tamperOrigHash'),
      tamperHash: document.getElementById('tamperHash'),
      tamperExpected: document.getElementById('tamperExpected'),
      tamperStatus: document.getElementById('tamperStatus'),
      tamperNextBlock: document.getElementById('tamperNextBlock'),
      tourOverlay: document.getElementById('tourOverlay'),
      tourTitle: document.getElementById('tourTitle'),
      tourText: document.getElementById('tourText'),
      tourWhy: document.getElementById('tourWhy'),
      tourLearn: document.getElementById('tourLearn'),
      tourTryList: document.getElementById('tourTryList'),
      tourProgress: document.getElementById('tourProgress'),
      tourTime: document.getElementById('tourTime'),
      tourBarFill: document.getElementById('tourBarFill'),
      tourNextBtn: document.getElementById('tourNextBtn'),
      tourPrevBtn: document.getElementById('tourPrevBtn'),
      tourPauseBtn: document.getElementById('tourPauseBtn'),
      tourTryBtn: document.getElementById('tourTryBtn'),
      tourSkipBtn: document.getElementById('tourSkipBtn'),
      tourStartBtn: document.getElementById('tourStartBtn'),
    };

    const TOUR_STEPS = [
      {
        key: 'intro',
        tab: 'hash',
        title: 'Welcome: What This Demo Is',
        text: 'You are viewing a public-friendly blockchain explainer powered by live DAVS chain data.',
        why: 'This connects actual attendance operations to blockchain concepts, so users understand both the system and the theory.',
        tryItems: [
          'Look at the top chips: network, latest block, and chain validity.',
          'Use the subject/year filters to narrow the attendance context.'
        ],
        learn: 'How to read the dashboard context before diving into tabs.',
      },
      {
        key: 'hash',
        tab: 'hash',
        title: 'Hash Tab',
        text: 'Type any text and watch SHA-256 hash change completely. One tiny input change causes a very different hash.',
        why: 'Hashes let DAVS verify whether attendance-related data was altered after recording.',
        tryItems: [
          'Change one character in Data and compare the old/new hash.',
          'Increase nonce and observe hash changes again.'
        ],
        learn: 'Why blockchain systems use hashing to protect data integrity.',
      },
      {
        key: 'block',
        tab: 'block',
        title: 'Block Tab',
        text: 'A block stores references to transactions, includes a hash, and points to the previous hash.',
        why: 'This structure is what makes blockchain records auditable over time.',
        tryItems: [
          'Press Mine Demo Block to generate a hash with leading zeros.',
          'Select a real block and compare its hash and previous hash.'
        ],
        learn: 'How block metadata forms the foundation of verifiable history.',
      },
      {
        key: 'tamper',
        tab: 'block',
        title: 'Tampering Check',
        text: 'Tampering mode recalculates a simulated hash and compares it against the next block reference.',
        why: 'If someone edits historical data, linkage should break and be detectable.',
        tryItems: [
          'Type any change in Edited Block Data.',
          'Watch the status switch to broken linkage when hashes no longer match.'
        ],
        learn: 'Why blockchain is resistant to silent record manipulation.',
      },
      {
        key: 'blockchain',
        tab: 'blockchain',
        title: 'Blockchain Tab',
        text: 'Each card is a real block snapshot. Click cards to inspect links and transaction hash references.',
        why: 'This is the actual chain structure behind attendance transaction anchoring in DAVS.',
        tryItems: [
          'Click 2-3 block cards and inspect the details in Block tab.',
          'Watch how previous hash references build a chain.'
        ],
        learn: 'How linked blocks create chronological evidence.',
      },
      {
        key: 'distributed',
        tab: 'distributed',
        title: 'Distributed Tab',
        text: 'Multiple peers hold ledger copies; if one lags, it synchronizes to the valid chain state.',
        why: 'Decentralization reduces single-point trust and improves reliability.',
        tryItems: [
          'Run Peer Sync Demo and observe lag/recovery.',
          'Compare visible block/hash per peer while syncing.'
        ],
        learn: 'How distributed consensus strengthens trust in records.',
      },
      {
        key: 'tokens',
        tab: 'tokens',
        title: 'Tokens Tab',
        text: 'This project focuses on transaction-based proof, not token transfers by students.',
        why: 'The goal is attendance auditability, not payments.',
        tryItems: [
          'Read transaction density bars per block.',
          'Review glossary terms to reinforce core concepts.'
        ],
        learn: 'The difference between token economics and record verification usage.',
      },
      {
        key: 'wrap',
        tab: 'blockchain',
        title: 'Final: Connect It To DAVS Attendance',
        text: 'NFC tap -> session validation -> blockchain transaction -> hash/block reference for audit.',
        why: 'This closes the loop between classroom attendance activity and immutable proof.',
        tryItems: [
          'Choose a subject/year filter and inspect chain updates over time.',
          'Keep auto refresh on and watch for new block pulse alerts.'
        ],
        learn: 'How this visualization maps directly to your project attendance pipeline.',
      },
    ];

    function esc(v) {
      return String(v ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
    }

    function shortHash(h) {
      if (!h) return 'N/A';
      if (h.length < 24) return h;
      return h.slice(0, 12) + '...' + h.slice(-10);
    }

    function setError(msg) {
      ui.errorBox.style.display = msg ? 'block' : 'none';
      ui.errorBox.textContent = msg || '';
    }

    function setTabs(name) {
      document.querySelectorAll('.tab-btn').forEach((b) => b.classList.toggle('active', b.dataset.tab === name));
      document.querySelectorAll('.tab-panel').forEach((t) => t.classList.toggle('active', t.id === `tab-${name}`));
    }

    function clearTourFocus() {
      document.querySelectorAll('.tour-focus').forEach((el) => el.classList.remove('tour-focus'));
    }

    function renderTourStep() {
      const step = TOUR_STEPS[state.tour.stepIndex];
      if (!step) return;
      setTabs(step.tab);
      clearTourFocus();
      const tabBtn = document.querySelector(`.tab-btn[data-tab="${step.tab}"]`);
      const panel = document.getElementById(`tab-${step.tab}`);
      tabBtn?.classList.add('tour-focus');
      panel?.classList.add('tour-focus');
      ui.tourTitle.textContent = step.title;
      ui.tourText.textContent = step.text;
      ui.tourWhy.textContent = step.why || '';
      ui.tourLearn.textContent = step.learn || '';
      ui.tourTryList.innerHTML = (step.tryItems || []).map((item) => `<li>${esc(item)}</li>`).join('');
      ui.tourProgress.textContent = `Step ${state.tour.stepIndex + 1}/${TOUR_STEPS.length}`;
      ui.tourTime.textContent = `${state.tour.remaining}s`;
      const progressPct = Math.max(0, Math.min(100, ((60 - state.tour.remaining) / 60) * 100));
      ui.tourBarFill.style.width = `${progressPct}%`;
      ui.tourPrevBtn.disabled = state.tour.stepIndex === 0;
      ui.tourNextBtn.innerHTML = state.tour.stepIndex === TOUR_STEPS.length - 1
        ? '<i class="bi bi-check2-circle"></i> Finish Tour'
        : '<i class="bi bi-arrow-right-circle"></i> Next';
    }

    function stopTour(markSeen) {
      if (state.tour.timerId) {
        clearInterval(state.tour.timerId);
      }
      state.tour.active = false;
      state.tour.timerId = null;
      ui.tourOverlay.classList.remove('show');
      ui.tourOverlay.setAttribute('aria-hidden', 'true');
      clearTourFocus();
      if (markSeen) {
        localStorage.setItem('davs_public_tour_seen_v1', '1');
      }
    }

    function nextTourStep() {
      if (state.tour.stepIndex >= TOUR_STEPS.length - 1) {
        stopTour(true);
        return;
      }
      state.tour.stepIndex += 1;
      state.tour.stepCounter = 0;
      renderTourStep();
    }

    function prevTourStep() {
      if (state.tour.stepIndex <= 0) return;
      state.tour.stepIndex -= 1;
      state.tour.stepCounter = 0;
      renderTourStep();
    }

    function toggleTourPause() {
      state.tour.paused = !state.tour.paused;
      ui.tourPauseBtn.innerHTML = state.tour.paused
        ? '<i class="bi bi-play-circle"></i> Resume'
        : '<i class="bi bi-pause-circle"></i> Pause';
    }

    function runTourAction() {
      const step = TOUR_STEPS[state.tour.stepIndex];
      if (!step) return;
      if (step.key === 'hash') {
        ui.hashInput.value = `NFC Tap | ${new Date().toISOString()} | Updated`;
        ui.nonceInput.value = String(Number(ui.nonceInput.value || 0) + 1);
        updateHashDemo();
      } else if (step.key === 'block') {
        setTabs('block');
        mineDemoBlock(2); // Use lower difficulty for tour speed
      } else if (step.key === 'tamper') {
        setTabs('block');
        ui.tamperInput.value = `Tampered value ${Date.now()}`;
        runTamperCheck();
      } else if (step.key === 'blockchain') {
        setTabs('blockchain');
        const card = document.querySelector('.chain-card');
        card?.click();
      } else if (step.key === 'distributed') {
        setTabs('distributed');
        ui.syncDemoBtn.click();
      } else if (step.key === 'tokens') {
        setTabs('tokens');
      } else if (step.key === 'wrap') {
        ui.autoRefresh.checked = true;
      }
    }

    function startTour(isAutoStart) {
      state.tour.active = true;
      state.tour.stepIndex = 0;
      state.tour.remaining = 60;
      state.tour.stepCounter = 0;
      state.tour.stepDuration = Math.max(6, Math.floor(60 / TOUR_STEPS.length));
      state.tour.paused = false;
      ui.tourPauseBtn.innerHTML = '<i class="bi bi-pause-circle"></i> Pause';
      ui.tourOverlay.classList.add('show');
      ui.tourOverlay.setAttribute('aria-hidden', 'false');
      renderTourStep();

      if (state.tour.timerId) clearInterval(state.tour.timerId);
      state.tour.timerId = setInterval(() => {
        if (state.tour.paused) return;
        state.tour.remaining -= 1;
        state.tour.stepCounter += 1;
        ui.tourTime.textContent = `${Math.max(0, state.tour.remaining)}s`;
        const progressPct = Math.max(0, Math.min(100, ((60 - state.tour.remaining) / 60) * 100));
        ui.tourBarFill.style.width = `${progressPct}%`;
        if (state.tour.remaining <= 0) {
          stopTour(true);
          return;
        }
        if (state.tour.stepCounter >= state.tour.stepDuration) {
          nextTourStep();
        }
      }, 1000);

      if (isAutoStart) {
        localStorage.setItem('davs_public_tour_seen_v1', '1');
      }
    }

    async function sha256(text) {
      const bytes = new TextEncoder().encode(text);
      const digest = await crypto.subtle.digest('SHA-256', bytes);
      return Array.from(new Uint8Array(digest)).map((b) => b.toString(16).padStart(2, '0')).join('');
    }

    async function updateHashDemo() {
      const text = `${ui.hashInput.value}\nnonce:${ui.nonceInput.value}`;
      ui.charCount.value = String(ui.hashInput.value.length);
      ui.hashOutput.textContent = await sha256(text);
    }

    function renderContextChips(ctx) {
      ui.contextChips.innerHTML = [
        `<span class="chip"><i class="bi bi-book"></i> Subject: ${esc(ctx.subject || 'All Subjects')}</span>`,
        `<span class="chip"><i class="bi bi-calendar-event"></i> Year: ${esc(ctx.year || 'All Years')}</span>`,
        `<span class="chip"><i class="bi bi-journal-check"></i> Attendance Logs: ${Number(ctx.attendance_logs || 0)}</span>`,
        `<span class="chip"><i class="bi bi-link-45deg"></i> Anchored On-Chain: ${Number(ctx.attendance_logs_on_chain || 0)}</span>`,
      ].join('');
    }

    function renderFilters(ctx) {
      const subjects = ctx.subject_options || [];
      const years = ctx.year_options || [];
      const sVal = ui.subjectFilter.value;
      const yVal = ui.yearFilter.value;

      ui.subjectFilter.innerHTML = '<option value="">All Subjects</option>' + subjects.map((s) => `<option value="${esc(s)}">${esc(s)}</option>`).join('');
      ui.yearFilter.innerHTML = '<option value="">All Years</option>' + years.map((y) => `<option value="${esc(y)}">${esc(y)}</option>`).join('');

      if (subjects.includes(sVal)) ui.subjectFilter.value = sVal;
      else ui.subjectFilter.value = '';

      if (years.includes(yVal)) ui.yearFilter.value = yVal;
      else ui.yearFilter.value = '';
    }

    function renderChain() {
      if (!state.blocks.length) {
        ui.chainRoot.innerHTML = '<p class="mini">No blocks found for this filter.</p>';
        return;
      }

      ui.chainRoot.innerHTML = state.blocks.map((b) => {
        const active = Number(state.selectedBlock) === Number(b.number) ? 'active' : '';
        const txPreview = (b.tx_hashes || []).slice(0, 2).map((tx) => `<div class="mono">${esc(tx)}</div>`).join('');
        return `
          <article class="chain-card ${active}" data-block="${b.number}">
            <div class="chain-head">
              <strong>Block #${b.number}</strong>
              <span class="mini">${esc(b.timestamp)}</span>
            </div>
            <div class="chain-body">
              <div class="mini">Hash: ${esc(shortHash(b.hash))}</div>
              <div class="mini">Previous: ${esc(shortHash(b.previous_hash))}</div>
              <div class="mini">Transactions: ${Number(b.tx_count || 0)}</div>
              ${txPreview || '<div class="mini">No matching attendance tx hash in this block.</div>'}
            </div>
          </article>
        `;
      }).join('');

      ui.chainRoot.querySelectorAll('.chain-card').forEach((el) => {
        el.addEventListener('click', () => {
          state.selectedBlock = Number(el.dataset.block);
          renderChain();
          renderBlockDetails();
          setTabs('blockchain');
        });
      });
    }

    function renderBlockPicker() {
      ui.blockPicker.innerHTML = state.blocks.map((b) => `<option value="${b.number}">Block #${b.number} - ${esc(b.timestamp)}</option>`).join('');
      if (!state.blocks.length) {
        ui.blockPicker.innerHTML = '<option value="">No blocks</option>';
        state.selectedBlock = null;
        renderBlockDetails();
        return;
      }
      if (!state.blocks.find((b) => Number(b.number) === Number(state.selectedBlock))) {
        state.selectedBlock = state.blocks[0].number;
      }
      ui.blockPicker.value = String(state.selectedBlock);
      renderBlockDetails();
    }

    function renderBlockDetails() {
      const b = state.blocks.find((x) => Number(x.number) === Number(state.selectedBlock));
      if (!b) {
        ui.blockDetails.innerHTML = '<p class="mini">No block selected.</p>';
        ui.tamperOrigHash.textContent = '--';
        ui.tamperHash.textContent = '--';
        ui.tamperExpected.textContent = '--';
        ui.tamperNextBlock.textContent = '--';
        ui.tamperStatus.textContent = 'No block selected yet.';
        ui.tamperStatus.className = 'status';
        return;
      }
      const txs = (b.tx_hashes || []).length
        ? b.tx_hashes.map((tx) => `<div class="mono">${esc(tx)}</div>`).join('')
        : '<p class="mini">No matching transaction hashes for selected filters.</p>';

      ui.blockDetails.innerHTML = `
        <div class="kv"><div class="k">Block Number</div><div>${b.number}</div></div>
        <div class="kv"><div class="k">Timestamp</div><div>${esc(b.timestamp)}</div></div>
        <div class="kv"><div class="k">Current Hash</div><div class="mono">${esc(b.hash)}</div></div>
        <div class="kv"><div class="k">Previous Hash</div><div class="mono">${esc(b.previous_hash)}</div></div>
        <div class="kv"><div class="k">Transactions</div><div>${txs}</div></div>
      `;

      ui.simPrevHash.value = b.hash;
      ui.simBlockNumber.value = Number(b.number) + 1;
      runTamperCheck();
    }

    async function runTamperCheck() {
      const bIndex = state.blocks.findIndex((x) => Number(x.number) === Number(state.selectedBlock));
      if (bIndex < 0) {
        ui.tamperStatus.textContent = 'Select a block to use tampering mode.';
        ui.tamperStatus.className = 'status';
        return;
      }

      // Since blocks are sorted DESCENDING (latest first), the 'next' chronological block is at bIndex - 1
      const next = state.blocks[bIndex - 1] || null;
      const tamperText = (ui.tamperInput.value || '').trim();

      ui.tamperOrigHash.textContent = current.hash || '--';
      ui.tamperExpected.textContent = next ? next.previous_hash : 'No next block (latest block)';
      ui.tamperNextBlock.textContent = next ? String(next.number) : 'N/A';

      let hashToCompare = current.hash || '';
      if (tamperText) {
        hashToCompare = await sha256(`${current.number}|${current.previous_hash}|${tamperText}`);
      }
      ui.tamperHash.textContent = hashToCompare || '--';

      if (!next) {
        ui.tamperStatus.textContent = tamperText
          ? 'No next block to validate against. Tamper hash changed, but linkage check needs a following block.'
          : 'Latest block selected. No following block for linkage validation.';
        ui.tamperStatus.className = 'status';
        return;
      }

      const linked = next.previous_hash === hashToCompare;
      if (linked) {
        ui.tamperStatus.textContent = tamperText
          ? 'Unexpectedly still linked (rare in simulation).'
          : 'Valid linkage: next block previous hash matches current original hash.';
        ui.tamperStatus.className = 'status';
      } else {
        ui.tamperStatus.textContent = tamperText
          ? 'Broken linkage detected: tampered hash no longer matches the next block previous hash.'
          : 'Chain linkage mismatch detected in current data.';
        ui.tamperStatus.className = 'status bad';
      }
    }

    function renderPeers() {
      const latest = state.blocks[0] || null;
      ui.peerGrid.innerHTML = state.peers.map((p) => {
        const lag = Number(p.lag || 0);
        const idx = Math.min(Math.max(lag, 0), Math.max(state.blocks.length - 1, 0));
        const block = state.blocks[idx] || latest;
        const ok = lag === 0;
        return `
          <div class="peer">
            <h4>${esc(p.name)}</h4>
            <div class="kv"><div class="k">Visible Block</div><div>${block ? block.number : '--'}</div></div>
            <div class="kv"><div class="k">Hash</div><div class="mono">${esc(block ? block.hash : '--')}</div></div>
            <div class="status ${ok ? '' : 'bad'}">${ok ? 'In Sync' : 'Outdated (' + lag + ' block lag)'}</div>
          </div>
        `;
      }).join('');
    }

    function renderBars() {
      if (!state.blocks.length) {
        ui.txBars.innerHTML = '<p class="mini">No block transaction data.</p>';
        return;
      }
      const max = Math.max(1, ...state.blocks.map((b) => Number(b.tx_count || 0)));
      ui.txBars.innerHTML = state.blocks.slice(0, 16).map((b) => {
        const tx = Number(b.tx_count || 0);
        const pct = Math.round((tx / max) * 100);
        return `
          <div class="bar-row">
            <div>Block ${b.number}</div>
            <div class="bar"><span style="width:${pct}%;"></span></div>
            <div>${tx}</div>
          </div>
        `;
      }).join('');
    }

    async function mineDemoBlock(forcedDifficulty) {
      ui.mineBtn.disabled = true;
      ui.mineStatus.textContent = 'Mining in progress...';
      const blockNo = Number(ui.simBlockNumber.value || 1);
      const prev = ui.simPrevHash.value || '';
      const data = ui.simData.value || '';
      const difficulty = forcedDifficulty || Number(ui.simDifficulty.value || 3);
      const target = '0'.repeat(difficulty);

      let nonce = 0;
      let hash = '';
      const start = performance.now();
      const maxTry = 180000;
      const batchSize = 500; // Batching avoids long-running microtasks that freeze UI

      while (nonce < maxTry) {
        for (let i = 0; i < batchSize && nonce < maxTry; i++, nonce++) {
          const payload = `${blockNo}|${prev}|${data}|${nonce}`;
          // Since subtle.digest is async, we still have to await, 
          // but batching helps with UI responsiveness between checks
          hash = await sha256(payload);
          if (hash.startsWith(target)) break;
        }
        if (hash.startsWith(target)) break;
        // Yield to event loop
        await new Promise(r => setTimeout(r, 0));
      }

      ui.simNonce.value = String(nonce);
      ui.simHash.textContent = hash;
      const sec = ((performance.now() - start) / 1000).toFixed(2);
      if (hash.startsWith(target)) {
        ui.mineStatus.textContent = `Success: found hash with ${difficulty} leading zeroes in ${nonce + 1} tries (${sec}s).`;
      } else {
        ui.mineStatus.textContent = `Stopped at ${maxTry} tries (${sec}s). Increase tries or lower difficulty.`;
      }
      ui.mineBtn.disabled = false;
    }

    async function loadData() {
      const params = new URLSearchParams();
      params.set('limit', ui.limitRange.value || '20');
      if (ui.subjectFilter.value) params.set('subject', ui.subjectFilter.value);
      if (ui.yearFilter.value) params.set('year', ui.yearFilter.value);

      try {
        const res = await fetch(`/api/public/blockchain/visualization?${params.toString()}`, { cache: 'no-store' });
        const data = await res.json();
        const latest = Number(data.latest_block ?? -1);

        ui.chipNetwork.innerHTML = `<i class="bi bi-diagram-3"></i> Network: ${esc(data.network || '--')}`;
        ui.chipLatest.innerHTML = `<i class="bi bi-box"></i> Latest Block: ${data.latest_block ?? '--'}`;
        ui.chipLoaded.innerHTML = `<i class="bi bi-collection"></i> Blocks Loaded: ${(data.blocks || []).length}`;

        if (Number.isFinite(latest) && state.latestBlockSeen !== null && latest > state.latestBlockSeen) {
          ui.chipLatest.classList.add('pulse-new');
          setTimeout(() => ui.chipLatest.classList.remove('pulse-new'), 2600);
        }
        if (Number.isFinite(latest) && latest >= 0) {
          state.latestBlockSeen = latest;
        }
        if (data.chain_valid) {
          ui.chipValidity.className = 'chip ok';
          ui.chipValidity.innerHTML = '<i class="bi bi-shield-check"></i> Chain: Valid Linkage';
        } else {
          ui.chipValidity.className = 'chip bad';
          ui.chipValidity.innerHTML = '<i class="bi bi-shield-exclamation"></i> Chain: Check Linkage';
        }

        state.context = data.context || {};
        renderContextChips(state.context);
        renderFilters(state.context);

        if (!data.ok) {
          setError(data.message || 'Unable to load blockchain data.');
          state.blocks = [];
          renderChain();
          renderBlockPicker();
          renderPeers();
          renderBars();
          return;
        }

        setError('');
        state.blocks = data.blocks || [];
        renderChain();
        renderBlockPicker();
        renderPeers();
        renderBars();
        runTamperCheck();
      } catch (e) {
        setError('Error loading blockchain data: ' + e);
      }
    }

    function applyTheme() {
      const saved = localStorage.getItem('davs_theme') || 'light';
      document.documentElement.setAttribute('data-theme', saved);
    }

    document.getElementById('tabButtons').addEventListener('click', (e) => {
      const btn = e.target.closest('.tab-btn');
      if (!btn) return;
      setTabs(btn.dataset.tab);
    });

    document.getElementById('themeBtn').addEventListener('click', () => {
      const cur = document.documentElement.getAttribute('data-theme') || 'light';
      const next = cur === 'dark' ? 'light' : 'dark';
      document.documentElement.setAttribute('data-theme', next);
      localStorage.setItem('davs_theme', next);
    });

    ui.limitRange.addEventListener('input', () => {
      ui.limitText.value = ui.limitRange.value;
    });
    ui.limitRange.addEventListener('change', loadData);
    ui.subjectFilter.addEventListener('change', loadData);
    ui.yearFilter.addEventListener('change', loadData);
    ui.refreshBtn.addEventListener('click', loadData);
    ui.blockPicker.addEventListener('change', () => {
      state.selectedBlock = Number(ui.blockPicker.value || 0);
      renderBlockDetails();
      renderChain();
    });

    ui.hashInput.addEventListener('input', updateHashDemo);
    ui.nonceInput.addEventListener('input', updateHashDemo);
    ui.mineBtn.addEventListener('click', mineDemoBlock);
    ui.tamperInput.addEventListener('input', runTamperCheck);
    ui.tourStartBtn.addEventListener('click', () => startTour(false));
    ui.tourNextBtn.addEventListener('click', () => nextTourStep());
    ui.tourPrevBtn.addEventListener('click', () => prevTourStep());
    ui.tourPauseBtn.addEventListener('click', () => toggleTourPause());
    ui.tourTryBtn.addEventListener('click', () => runTourAction());
    ui.tourSkipBtn.addEventListener('click', () => stopTour(true));

    document.addEventListener('keydown', (e) => {
      if (!state.tour.active) return;
      if (e.key === 'Escape') stopTour(true);
      if (e.key === 'ArrowRight') nextTourStep();
      if (e.key === 'ArrowLeft') prevTourStep();
    });

    ui.syncDemoBtn.addEventListener('click', () => {
      state.peers[1].lag = 2;
      state.peers[2].lag = 1;
      renderPeers();
      setTimeout(() => {
        state.peers[1].lag = 1;
        renderPeers();
      }, 1200);
      setTimeout(() => {
        state.peers[1].lag = 0;
        state.peers[2].lag = 0;
        renderPeers();
      }, 2400);
    });

    applyTheme();
    ui.limitText.value = ui.limitRange.value;
    ui.hashInput.value = 'NFC Tap | 2022-000123 | BSIT 3A | Present | 2026-03-29 20:45';
    updateHashDemo();
    loadData();

    if (!localStorage.getItem('davs_public_tour_seen_v1')) {
      setTimeout(() => startTour(true), 700);
    }

    setInterval(() => {
      if (ui.autoRefresh.checked) loadData();
    }, 5000);

