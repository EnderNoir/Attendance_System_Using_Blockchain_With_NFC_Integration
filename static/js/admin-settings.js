// Admin settings page script: extracted from template for easier debugging.

function togglePw() {
  const inp = document.getElementById('smtp_password');
  const eye = document.getElementById('pwEye');
  if (inp.type === 'password') {
    inp.type = 'text';
    eye.className = 'bi bi-eye-slash';
  } else {
    inp.type = 'password';
    eye.className = 'bi bi-eye';
  }
}

async function sendTestEmail() {
  const addr = document.getElementById('testEmailAddr').value.trim();
  const btn = document.getElementById('btnTest');
  const res = document.getElementById('testResult');
  const testUrl = document.getElementById('adminSettingsMeta')?.dataset?.testUrl;

  if (!addr || !addr.includes('@')) {
    res.className = 'test-result err';
    res.style.display = 'block';
    res.textContent = '✕ Please enter a valid email address.';
    return;
  }

  if (!testUrl) {
    res.className = 'test-result err';
    res.style.display = 'block';
    res.textContent = '✕ Missing test endpoint configuration.';
    return;
  }

  btn.disabled = true;
  btn.innerHTML = '<i class="bi bi-hourglass-split"></i> Sending…';
  res.style.display = 'none';

  try {
    const fd = new FormData();
    fd.append('test_email', addr);
    const r = await fetch(testUrl, {
      method: 'POST',
      credentials: 'same-origin',
      body: fd,
    });
    const d = await r.json();
    res.className = d.ok ? 'test-result ok' : 'test-result err';
    res.textContent = (d.ok ? '✓ ' : '✕ ') + d.message;
    res.style.display = 'block';
  } catch (e) {
    res.className = 'test-result err';
    res.textContent = '✕ Network error: ' + e.message;
    res.style.display = 'block';
  }

  btn.disabled = false;
  btn.innerHTML = '<i class="bi bi-send"></i> Send Test';
}
