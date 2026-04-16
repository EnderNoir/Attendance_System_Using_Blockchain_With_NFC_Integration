# Thesis Alignment Gap Analysis

This report compares the thesis goals for **“Decentralized Attendance Verification System Using Blockchain Technology”** against the current repository implementation.

## 1) RFID/NFC integration for attendance

### What is implemented
- NFC tap capture exists through `nfc.py` / `nfc_listener.py` and forwards `nfc_id` to Flask (`/mark_pico`).
- A keyboard simulator fallback can submit synthetic NFC IDs when no reader is detected (`nfc.py`).

### Gaps / mismatches
- The implementation is NFC UID based only; no robust RFID/NFC cryptographic authentication flow is present (UID can be replayed/spoofed).
- The simulator path allows attendance events without physical card presence, which weakens strict hardware-backed attendance claims.
- The listener auto-installs runtime dependencies (`pip install`) instead of having a controlled deployment setup, which is operationally brittle for production hardware integration.

## 2) Blockchain and smart contract implementation

### What is implemented
- Solidity contract (`contracts/Attendance.sol`) stores attendance by NFC ID and status.
- Flask writes attendance to chain when online (`mark_attendance_on_chain`, `/mark_pico`).

### Gaps / mismatches
- Contract-level attendance write is not restricted to admin/authorized role (`markAttendanceWithStatus` is `public` without `onlyAdmin`), conflicting with stronger security/control expectations.
- On-chain record schema is minimal (`nfcId`, `timestamp`, `status`) and does not include session/class/teacher context used by the app workflow; most academic attendance context stays off-chain in SQLite.
- The app intentionally falls back to SQLite-only logging when chain is offline, so immutability/tamper-proof guarantees are not end-to-end enforced.
- Hardhat compile in this environment depends on external compiler download and failed (`HH502`), indicating blockchain toolchain reproducibility gaps for validation.

## 3) Flask middleware role and design

### What is implemented
- Flask receives NFC tap events and coordinates DB + blockchain writes in `/mark_pico`.

### Gaps / mismatches
- The middleware is not separated as a thin integration layer; `app.py` is a large monolith (~6k lines, ~91 routes) that mixes UI routes, business logic, DB operations, blockchain calls, and session state.
- This tightly coupled design makes methodology claims around modular middleware architecture harder to support.

## 4) Attendance recording and verification workflow/data flow

### What is implemented
- Tap -> `/mark_pico` -> optional on-chain write -> SQLite attendance log -> dashboard/API update.
- Transaction hash/block number are stored when available.

### Gaps / mismatches
- Verification is partial: if blockchain write fails, attendance is still accepted in SQLite, so “verification by blockchain” is conditional.
- There is no strict reconciliation job enforcing that every attendance log has a confirmed on-chain transaction.
- README claims API endpoints (`/api/attendance/checkin`, `/api/attendance/records`, `/api/blockchain/transaction/:tx_hash`) that are not implemented in `app.py`, creating documentation/implementation drift for data flow.

## 5) Methodology adherence (iterative prototyping and user feedback phases)

### Observed mismatch
- No repository artifacts were found for iterative prototype cycles, technical/user survey instruments, or formal feedback-driven iteration evidence (e.g., survey forms/results, phase reports, acceptance criteria logs).
- Codebase contents focus on application functionality, but not the thesis-described methodology traceability.

## 6) System evaluation/testing as described

### Observed mismatch
- Automated test coverage is effectively absent (`test/` contains only `.gitkeep`).
- No reproducible evaluation suite for performance/usability/security metrics described by thesis-style validation is present.
- Baseline checks show limited validation tooling available in-repo (no configured Python test runner scripts; blockchain compile requires external network access).

## 7) Additional thesis/repository claim gaps

### Not fully realized or unsupported by code evidence
- README security claim “cryptographic hashing of attendance data” is not implemented as an attendance-record integrity mechanism (hashing in code is used for passwords and deterministic key derivation, not per-attendance proof objects).
- README claim “smart contract auditing” has no audit report or audit artifacts in repository.
- The “decentralized” claim is only partially realized because core source of truth for rich attendance context remains centralized in SQLite/application state.

---

## Summary

The repository demonstrates a **hybrid attendance system** (NFC + Flask + optional blockchain logging), but it does **not fully implement** the stronger thesis-level claims of strict decentralized verification, complete on-chain attendance context, formal iterative methodology traceability, and comprehensive evaluation evidence.
