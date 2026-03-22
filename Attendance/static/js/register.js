/* ============================================
   NFC Registration Functions
   ============================================ */

/**
 * Initiate NFC scanning
 */
function scanNFC() {
  const scanBtn = document.querySelector('button[onclick="scanNFC()"]');
  const nfcInput = document.getElementById("nfc_id");
  const statusDiv = document.getElementById("scanStatus");

  // Disable button and show loading state
  scanBtn.disabled = true;
  const originalHTML = scanBtn.innerHTML;
  scanBtn.innerHTML = '<i class="bi bi-hourglass-split"></i> Scanning...';

  // Show status message
  statusDiv.style.display = "block";
  statusDiv.className = "alert alert-info d-flex align-items-center";
  statusDiv.innerHTML = `
    <div class="spinner-border spinner-border-sm me-2" role="status">
      <span class="visually-hidden">Loading...</span>
    </div>
    <div>
      <strong>Ready to scan</strong>
      <br/>
      <small>Tap your NFC card on the reader...</small>
    </div>
  `;

  fetch("/request_registration_scan", { method: "POST" })
    .then((response) => response.json())
    .then((data) => {
      if (data.status === "ready") {
        pollForUID();
      } else {
        throw new Error("Server not ready");
      }
    })
    .catch((error) => {
      console.error("Error:", error);
      statusDiv.className = "alert alert-danger d-flex align-items-center";
      statusDiv.innerHTML = `
        <i class="bi bi-exclamation-circle me-2" style="font-size: 1.2rem;"></i>
        <div>
          <strong>Could not connect to NFC listener</strong>
          <br/>
          <small>Make sure the NFC listener service is running</small>
        </div>
      `;
      resetButton();
    });
}

/**
 * Poll for scanned NFC UID
 */
function pollForUID() {
  let attempts = 0;
  const maxAttempts = 30;
  const statusDiv = document.getElementById("scanStatus");

  const poll = setInterval(() => {
    fetch("/get_scanned_uid")
      .then((response) => response.json())
      .then((data) => {
        if (data.uid) {
          clearInterval(poll);

          // Set the NFC ID and show success
          document.getElementById("nfc_id").value = data.uid;

          statusDiv.className = "alert alert-success d-flex align-items-center";
          statusDiv.innerHTML = `
            <i class="bi bi-check-circle me-2" style="font-size: 1.2rem;"></i>
            <div>
              <strong>NFC card scanned successfully!</strong>
              <br/>
              <small>UID: <code>${data.uid}</code></small>
            </div>
          `;

          resetButton();

          // Auto-hide success message after 3 seconds
          setTimeout(() => {
            statusDiv.style.display = "none";
          }, 3000);
        } else {
          attempts++;
          if (attempts >= maxAttempts) {
            clearInterval(poll);
            statusDiv.className =
              "alert alert-warning d-flex align-items-center";
            statusDiv.innerHTML = `
              <i class="bi bi-clock-history me-2" style="font-size: 1.2rem;"></i>
              <div>
                <strong>Scan timeout</strong>
                <br/>
                <small>Please try again</small>
              </div>
            `;
            resetButton();
          }
        }
      })
      .catch((err) => console.error("Polling error:", err));
  }, 500);
}

/**
 * Reset the scan button to initial state
 */
function resetButton() {
  const scanBtn = document.querySelector('button[onclick="scanNFC()"]');
  scanBtn.disabled = false;
  scanBtn.innerHTML = '<i class="bi bi-phone"></i> Scan';
}
