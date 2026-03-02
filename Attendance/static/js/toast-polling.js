/* ============================================
   Toast Notifications & Polling
   ============================================ */

// Timestamp of the last notification we have seen
let lastSeenTimestamp = Date.now() / 1000; // seconds

/**
 * Fetch new attendance events every 3 seconds
 */
function pollAttendance() {
  fetch(`/api/attendance/recent?since=${lastSeenTimestamp}`)
    .then((response) => response.json())
    .then((events) => {
      events.forEach((event) => {
        // Update timestamp to avoid duplicates
        if (event.timestamp > lastSeenTimestamp) {
          lastSeenTimestamp = event.timestamp;
        }
        showToast(event);
      });
    })
    .catch((err) => console.error("Polling error:", err));
}

/**
 * Display a modern Bootstrap toast notification
 */
function showToast(event) {
  const toastEl = document.createElement("div");
  toastEl.className = "toast align-items-center border-0";
  toastEl.setAttribute("role", "alert");
  toastEl.setAttribute("aria-live", "assertive");
  toastEl.setAttribute("aria-atomic", "true");
  toastEl.style.background =
    "linear-gradient(135deg, #11998e 0%, #38ef7d 100%)";

  // Format the time
  const time = new Date(event.timestamp * 1000).toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });

  toastEl.innerHTML = `
    <div class="d-flex w-100 text-white">
      <div class="toast-body">
        <div class="fw-bold mb-1">
          <i class="bi bi-check-circle me-2"></i> Attendance Marked
        </div>
        <small>${event.name}</small><br/>
        <code class="text-white-50">${event.nfc_id}</code> at ${time}
      </div>
      <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button>
    </div>
  `;

  document.getElementById("toastContainer").appendChild(toastEl);
  const toast = new bootstrap.Toast(toastEl, {
    autohide: true,
    delay: 5000,
  });
  toast.show();

  // Remove from DOM after hidden
  toastEl.addEventListener("hidden.bs.toast", () => toastEl.remove());
}

/**
 * Start polling when page loads
 */
window.addEventListener("load", () => {
  pollAttendance(); // immediate check
  setInterval(pollAttendance, 3000); // every 3 seconds
});
