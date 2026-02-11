const API_URL = "http://localhost:5000";

// Load data on page load
document.addEventListener("DOMContentLoaded", function () {
  checkSystemHealth();
  refreshRecords();
  setInterval(refreshRecords, 60000); // Refresh every minute

  // NFC input focus
  document.getElementById("nfcInput").focus();
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

async function markAttendance() {
  const nfcId = document.getElementById("nfcInput").value.trim();
  const subject = document.getElementById("markSubject").value.trim();

  if (!nfcId) {
    alert("Please tap an NFC tag");
    return;
  }

  if (!subject) {
    alert("Please enter a subject");
    return;
  }

  try {
    const response = await fetch(`${API_URL}/api/mark-attendance`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        nfc_id: nfcId,
        subject: subject,
      }),
    });

    const data = await response.json();

    if (data.success) {
      alert(
        `✓ Attendance marked successfully!\nTx: ${data.transaction_hash.substring(0, 10)}...`,
      );
      document.getElementById("nfcInput").value = "";
      document.getElementById("markSubject").value = "";
      document.getElementById("nfcInput").focus();
      refreshRecords();
    } else {
      alert(`✗ Error: ${data.message}`);
    }
  } catch (error) {
    alert(`✗ Error: ${error.message}`);
    console.error("Error:", error);
  }
}

async function refreshRecords() {
  try {
    const response = await fetch(`${API_URL}/api/all-records`);
    const data = await response.json();

    if (data.success) {
      const records = data.records;
      const tbody = document.getElementById("recordsBody");

      // Calculate statistics
      document.getElementById("totalRecords").textContent = records.length;

      const today = new Date().toDateString();
      const todayCount = records.filter((r) => {
        const recordDate = new Date(
          r.datetime * 1000 || r.datetime,
        ).toDateString();
        return recordDate === today && r.is_present;
      }).length;
      document.getElementById("todayAttendance").textContent = todayCount;

      const uniqueStudents = new Set(records.map((r) => r.student_id)).size;
      document.getElementById("activeStudents").textContent = uniqueStudents;

      // Display records
      tbody.innerHTML = "";

      if (records.length === 0) {
        tbody.innerHTML =
          '<tr><td colspan="4" class="text-center">No records found</td></tr>';
      } else {
        records.reverse().forEach((record) => {
          const row = document.createElement("tr");
          const statusClass = record.is_present ? "present" : "absent";
          const statusText = record.is_present ? "Present" : "Absent";

          row.innerHTML = `
                        <td>${record.student_id}</td>
                        <td>${record.subject}</td>
                        <td>${record.datetime}</td>
                        <td class="${statusClass}">${statusText}</td>
                    `;
          tbody.appendChild(row);
        });
      }
    } else {
      console.error("Error fetching records:", data.message);
    }
  } catch (error) {
    console.error("Error:", error);
    document.getElementById("recordsBody").innerHTML =
      '<tr><td colspan="4" class="text-center error">Error loading records</td></tr>';
  }
}

async function searchStudent() {
  const studentId = document.getElementById("searchStudentId").value.trim();
  const resultDiv = document.getElementById("searchResult");

  if (!studentId) {
    resultDiv.innerHTML = "";
    return;
  }

  try {
    const response = await fetch(
      `${API_URL}/api/attendance-count/${studentId}`,
    );
    const data = await response.json();

    if (data.success) {
      resultDiv.innerHTML = `
                <div class="success">
                    <strong>Student ID:</strong> ${studentId}<br>
                    <strong>Total Attendance:</strong> ${data.attendance_count}
                </div>
            `;
    } else {
      resultDiv.innerHTML = `<div class="error">✗ ${data.message}</div>`;
    }
  } catch (error) {
    resultDiv.innerHTML = `<div class="error">✗ Error: ${error.message}</div>`;
    console.error("Error:", error);
  }
}

function exportRecords() {
  const table = document.getElementById("recordsTable");
  const csv = [];
  const rows = table.querySelectorAll("tr");

  rows.forEach((row) => {
    const cols = row.querySelectorAll("td, th");
    const csvRow = [];
    cols.forEach((col) => {
      csvRow.push(col.innerText);
    });
    csv.push(csvRow.join(","));
  });

  const csvContent = "data:text/csv;charset=utf-8," + csv.join("\n");
  const link = document.createElement("a");
  link.setAttribute("href", encodeURI(csvContent));
  link.setAttribute(
    "download",
    `attendance_${new Date().toISOString().split("T")[0]}.csv`,
  );
  link.click();
}

// Keep NFC input focused
document.addEventListener(
  "focus",
  function () {
    if (document.activeElement !== document.getElementById("nfcInput")) {
      document.getElementById("nfcInput").focus();
    }
  },
  true,
);
