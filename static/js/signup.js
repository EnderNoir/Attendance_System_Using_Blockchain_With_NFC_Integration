// Signup page script: extracted from template for easier debugging.

function toggleTeacher() {
  document.getElementById('teacherSection').classList.toggle('visible', document.getElementById('role_teacher').checked);
}

function updateCount() {
  const total = document.querySelectorAll('.sec-cb:checked').length;
  document.getElementById('selectedCount').textContent = total === 0 ? '0 sections selected' : total + ' section' + (total > 1 ? 's' : '') + ' selected';
}

function selectAll(course) {
  const cbs = document.querySelectorAll('.' + course + '-cb');
  const allChecked = [...cbs].every((cb) => cb.checked);
  cbs.forEach((cb) => cb.checked = !allChecked);
  updateCount();
}

function previewSignupPhoto(input) {
  if (!input.files || !input.files[0]) return;
  const reader = new FileReader();
  reader.onload = (e) => {
    const img = document.getElementById('signupPhotoImg');
    const init = document.getElementById('signupPhotoInit');
    img.src = e.target.result;
    img.style.display = 'block';
    init.style.display = 'none';
    document.getElementById('signupPhotoWrap').style.borderStyle = 'solid';
    document.getElementById('signupPhotoWrap').style.borderColor = 'var(--accent)';
  };
  reader.readAsDataURL(input.files[0]);
}

// Suggest username from full name until user edits the username field manually.
function suggestUsername(fullName) {
  const userInput = document.getElementById('inp_username');
  const suggest = document.getElementById('usernameSuggest');
  if (!fullName.trim()) {
    suggest.textContent = '';
    return;
  }

  const parts = fullName.trim().split(/\s+/);
  const last = parts[parts.length - 1] || '';
  const first = parts[0] || '';
  const suggested = (first.charAt(0) + last).toLowerCase().replace(/[^a-z0-9]/g, '');

  if (!userInput.dataset.userModified) {
    userInput.value = suggested;
    suggest.textContent = suggested ? '→ Suggested: ' + suggested : '';
  } else {
    suggest.textContent = '';
  }
}

document.addEventListener('DOMContentLoaded', () => {
  const userInput = document.getElementById('inp_username');
  if (userInput) {
    userInput.addEventListener('input', function onUsernameInput() {
      this.dataset.userModified = 'true';
      document.getElementById('usernameSuggest').textContent = '';
    });
  }
});

function toggleTheme() {
  const html = document.documentElement;
  const isDark = html.getAttribute('data-theme') === 'dark';
  html.setAttribute('data-theme', isDark ? 'light' : 'dark');
  localStorage.setItem('davs_theme', isDark ? 'light' : 'dark');
  updateThemeIcon();
}

function updateThemeIcon() {
  const isDark = document.documentElement.getAttribute('data-theme') === 'dark';
  document.getElementById('themeIcon').className = isDark ? 'bi bi-sun-fill' : 'bi bi-moon-fill';
  document.getElementById('themeLabel').textContent = isDark ? 'Light Mode' : 'Dark Mode';
}

(function initTheme() {
  const saved = localStorage.getItem('davs_theme') || 'light';
  document.documentElement.setAttribute('data-theme', saved);
  updateThemeIcon();
})();
