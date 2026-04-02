// Attendance report page script: extracted from template for easier debugging.

const totalR = document.querySelectorAll('#reportList .student-card').length;

function filterReports() {
  const q = document.getElementById('rf_search').value.toLowerCase();
  const course = document.getElementById('rf_course').value;
  const year = document.getElementById('rf_year').value;
  const standing = document.getElementById('rf_standing').value;
  const cards = document.querySelectorAll('#reportList .student-card');
  let shown = 0;

  cards.forEach((c) => {
    const m = (!q || c.dataset.name.includes(q) || c.dataset.nfc.includes(q))
      && (!course || c.dataset.course === course)
      && (!year || c.dataset.year === year)
      && (!standing || c.dataset.standing === standing);
    c.classList.toggle('hidden-card', !m);
    if (m) shown += 1;
  });

  const count = document.getElementById('rf_count');
  const empty = document.getElementById('rf_empty');
  if (count) count.textContent = `${shown} of ${totalR}`;
  if (empty) empty.style.display = shown === 0 ? 'block' : 'none';
}

function resetReports() {
  ['rf_search', 'rf_course', 'rf_year', 'rf_standing'].forEach((id) => {
    const el = document.getElementById(id);
    if (el) el.value = '';
  });
  filterReports();
}
