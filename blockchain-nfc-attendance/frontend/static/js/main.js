const API_URL = "http://localhost:5000";

// Check system health on load
document.addEventListener("DOMContentLoaded", function () {
  checkSystemHealth();
  setInterval(checkSystemHealth, 30000); // Check every 30 seconds
});

async function checkSystemHealth() {
  try {
    const response = await fetch(`${API_URL}/api/health`);
    const data = await response.json();

    const statusElement = document.getElementById("status");
    if (data.web3_connected) {
      statusElement.textContent = "✓ Connected";
      statusElement.classList.remove("disconnected");
    } else {
      statusElement.textContent = "✗ Disconnected";
      statusElement.classList.add("disconnected");
    }
  } catch (error) {
    console.error("Health check failed:", error);
    const statusElement = document.getElementById("status");
    statusElement.textContent = "✗ Disconnected";
    statusElement.classList.add("disconnected");
  }
}

function goToDashboard() {
  window.location.href = "/dashboard";
}

function showRegisterModal() {
  document.getElementById("registerModal").style.display = "block";
}

function closeRegisterModal() {
  document.getElementById("registerModal").style.display = "none";
}

async function registerStudent(event) {
  event.preventDefault();

  const studentAddress = document.getElementById("studentAddress").value;
  const studentId = document.getElementById("studentId").value;
  const studentName = document.getElementById("studentName").value;
  const nfcId = document.getElementById("nfcId").value;

  const statusDiv = document.getElementById("registerStatus");
  statusDiv.innerHTML = '<div class="warning">Registering...</div>';

  try {
    const response = await fetch(`${API_URL}/api/register-student`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        student_address: studentAddress,
        student_id: studentId,
        name: studentName,
        nfc_id: nfcId,
      }),
    });

    const data = await response.json();

    if (data.success) {
      statusDiv.innerHTML = `<div class="success">✓ ${data.message}<br>Tx: ${data.transaction_hash}</div>`;
      document.getElementById("registerForm").reset();
      setTimeout(() => {
        closeRegisterModal();
      }, 2000);
    } else {
      statusDiv.innerHTML = `<div class="error">✗ Error: ${data.message}</div>`;
    }
  } catch (error) {
    statusDiv.innerHTML = `<div class="error">✗ Error: ${error.message}</div>`;
    console.error("Error:", error);
  }
}

// Close modal when clicking outside of it
window.onclick = function (event) {
  const modal = document.getElementById("registerModal");
  if (event.target === modal) {
    modal.style.display = "none";
  }
};
