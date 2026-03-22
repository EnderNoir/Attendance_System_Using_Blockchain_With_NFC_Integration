/* ============================================
   Dashboard Student Table Filtering
   ============================================ */

/**
 * Filter table based on search input
 */
function filterTable() {
  let input = document.getElementById("searchInput").value.toLowerCase();
  let rows = document.querySelectorAll("#studentTable tbody tr");
  let visibleCount = 0;

  rows.forEach((row) => {
    if (row.cells.length === 5) {
      let name = row.cells[0].innerText.toLowerCase();
      let nfcId = row.cells[1].innerText.toLowerCase();
      if (name.includes(input) || nfcId.includes(input)) {
        row.style.display = "";
        visibleCount++;
      } else {
        row.style.display = "none";
      }
    }
  });
}

/**
 * Clear search and show all rows
 */
function clearSearch() {
  document.getElementById("searchInput").value = "";
  filterTable();
}

/**
 * Initialize event listeners when document is ready
 */
document.addEventListener("DOMContentLoaded", function () {
  const searchInput = document.getElementById("searchInput");
  if (searchInput) {
    // Trigger filter as you type
    searchInput.addEventListener("keyup", filterTable);
  }
});
