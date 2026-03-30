// Login page script: extracted from template for easier debugging.

function validateLogin() {
  let ok = true;
  const u = document.getElementById('login_user');
  const p = document.getElementById('login_pass');

  if (!u.value.trim()) {
    u.classList.add('invalid');
    document.getElementById('login_user_err').classList.add('show');
    ok = false;
  }

  if (!p.value) {
    p.classList.add('invalid');
    document.getElementById('login_pass_err').classList.add('show');
    ok = false;
  }

  return ok;
}

function clearErr(el, errId) {
  el.classList.remove('invalid');
  document.getElementById(errId)?.classList.remove('show');
}

function toggleTheme() {
  const html = document.documentElement;
  const isDark = html.getAttribute('data-theme') === 'dark';
  const next = isDark ? 'light' : 'dark';
  html.setAttribute('data-theme', next);
  localStorage.setItem('davs_theme', next);
  updateIcon();
}

function updateIcon() {
  const isDark = document.documentElement.getAttribute('data-theme') === 'dark';
  document.getElementById('themeIcon').className = isDark ? 'bi bi-sun-fill' : 'bi bi-moon-fill';
  document.getElementById('themeLabel').textContent = isDark ? 'Light Mode' : 'Dark Mode';
}

(function initTheme() {
  const saved = localStorage.getItem('davs_theme') || 'light';
  document.documentElement.setAttribute('data-theme', saved);
  updateIcon();
})();
