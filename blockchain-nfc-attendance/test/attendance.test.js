"""
Test file for smart contract
Run with: truffle test
"""

const Attendance = artifacts.require("Attendance");

contract("Attendance", (accounts) => {
    let attendanceInstance;
    const admin = accounts[0];
    const student = accounts[1];
    const studentId = "STU001";
    const studentName = "Test Student";
    const nfcId = "NFC001";
    const subject = "Mathematics";

    beforeEach(async () => {
        attendanceInstance = await Attendance.new({ from: admin });
    });

    // Test 1: Contract should deploy successfully
    it("should deploy successfully", async () => {
        const instance = await Attendance.new();
        assert(instance.address !== '', "Contract address should not be empty");
    });

    // Test 2: Admin should be set correctly
    it("should set admin correctly", async () => {
        const contractAdmin = await attendanceInstance.admin();
        assert.equal(contractAdmin, admin, "Admin should be contract deployer");
    });

    // Test 3: Register student
    it("should register a student", async () => {
        await attendanceInstance.registerStudent(
            student,
            studentId,
            studentName,
            nfcId,
            { from: admin }
        );

        const registeredStudent = await attendanceInstance.getStudent(student);
        assert.equal(registeredStudent.studentId, studentId, "Student ID should match");
        assert.equal(registeredStudent.name, studentName, "Student name should match");
        assert.equal(registeredStudent.nfcId, nfcId, "NFC ID should match");
    });

    // Test 4: Mark attendance
    it("should mark attendance", async () => {
        // First register student
        await attendanceInstance.registerStudent(
            student,
            studentId,
            studentName,
            nfcId,
            { from: admin }
        );

        // Then mark attendance
        const tx = await attendanceInstance.markAttendance(nfcId, subject);
        assert(tx.receipt.status, "Transaction should succeed");

        // Check if record was added
        const count = await attendanceInstance.getAttendanceRecordsCount();
        assert.equal(count, 1, "Should have one attendance record");
    });

    // Test 5: Get attendance record
    it("should retrieve attendance record", async () => {
        // Register and mark attendance
        await attendanceInstance.registerStudent(
            student,
            studentId,
            studentName,
            nfcId,
            { from: admin }
        );
        await attendanceInstance.markAttendance(nfcId, subject);

        // Retrieve record
        const record = await attendanceInstance.getAttendanceRecord(0);
        assert.equal(record.studentId, studentId, "Student ID should match");
        assert.equal(record.subject, subject, "Subject should match");
        assert.equal(record.isPresent, true, "Should be marked present");
    });

    // Test 6: Get attendance count
    it("should calculate attendance count", async () => {
        // Register and mark attendance
        await attendanceInstance.registerStudent(
            student,
            studentId,
            studentName,
            nfcId,
            { from: admin }
        );
        await attendanceInstance.markAttendance(nfcId, subject);

        // Get count
        const count = await attendanceInstance.getStudentAttendanceCount(studentId);
        assert.equal(count, 1, "Attendance count should be 1");
    });

    // Test 7: Mark absence
    it("should mark absence", async () => {
        const tx = await attendanceInstance.markAbsence(studentId, subject, { from: admin });
        assert(tx.receipt.status, "Transaction should succeed");

        const record = await attendanceInstance.getAttendanceRecord(0);
        assert.equal(record.isPresent, false, "Should be marked absent");
    });

    // Test 8: Deactivate student
    it("should deactivate student", async () => {
        // Register student
        await attendanceInstance.registerStudent(
            student,
            studentId,
            studentName,
            nfcId,
            { from: admin }
        );

        // Deactivate
        await attendanceInstance.deactivateStudent(student, { from: admin });

        // Check status
        const deactivatedStudent = await attendanceInstance.getStudent(student);
        assert.equal(deactivatedStudent.isActive, false, "Student should be inactive");
    });

    // Test 9: Only admin can register
    it("should only allow admin to register students", async () => {
        try {
            await attendanceInstance.registerStudent(
                student,
                studentId,
                studentName,
                nfcId,
                { from: student }
            );
            assert(false, "Should throw error");
        } catch (error) {
            assert(error.message.includes("Only admin can call this function"));
        }
    });

    // Test 10: Invalid NFC ID should fail
    it("should fail with invalid NFC ID", async () => {
        try {
            await attendanceInstance.markAttendance("INVALID_NFC", subject);
            assert(false, "Should throw error");
        } catch (error) {
            assert(error.message.includes("NFC ID not found"));
        }
    });
});
