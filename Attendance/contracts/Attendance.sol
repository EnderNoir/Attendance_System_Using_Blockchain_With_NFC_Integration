// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

contract Attendance {
    address public admin;
    uint8 public constant STATUS_PRESENT = 0;
    uint8 public constant STATUS_LATE = 1;
    uint8 public constant STATUS_ABSENT = 2;
    uint8 public constant STATUS_EXCUSED = 3;

    struct Student {
        string name;
        string nfcId;       // Unique NFC tag UID (as string)
        bool isRegistered;
    }

    struct AttendanceRecord {
        uint256 timestamp;
        uint8 status;
    }

    mapping(string => Student) public studentsByNfc;   // nfcId => Student
    mapping(address => Student) public studentsByAddr; // student address => Student
    mapping(string => AttendanceRecord[]) public attendance; // nfcId => records

    event StudentRegistered(address indexed studentAddr, string nfcId, string name);
    event AttendanceMarked(string indexed nfcId, uint256 timestamp, uint8 status, string statusLabel);

    modifier onlyAdmin() {
        require(msg.sender == admin, "Only admin can perform this action");
        _;
    }

    constructor() {
        admin = msg.sender;
    }

    // Register a new student (admin only)
    function registerStudent(
        address _studentAddress,
        string memory _nfcId,
        string memory _name
    ) public onlyAdmin {
        require(!studentsByNfc[_nfcId].isRegistered, "NFC ID already registered");
        require(studentsByAddr[_studentAddress].isRegistered == false, "Address already used");

        Student memory newStudent = Student({
            name: _name,
            nfcId: _nfcId,
            isRegistered: true
        });

        studentsByNfc[_nfcId] = newStudent;
        studentsByAddr[_studentAddress] = newStudent;
        emit StudentRegistered(_studentAddress, _nfcId, _name);
    }

    function _statusLabel(uint8 _status) internal pure returns (string memory) {
        if (_status == STATUS_PRESENT) return "present";
        if (_status == STATUS_LATE) return "late";
        if (_status == STATUS_ABSENT) return "absent";
        if (_status == STATUS_EXCUSED) return "excused";
        return "unknown";
    }

    // Backward-compatible helper (defaults to present).
    function markAttendance(string memory _nfcId) public {
        markAttendanceWithStatus(_nfcId, STATUS_PRESENT);
    }

    // Mark attendance with explicit status for immutable auditing.
    function markAttendanceWithStatus(string memory _nfcId, uint8 _status) public {
        require(studentsByNfc[_nfcId].isRegistered, "Student not registered");
        require(_status <= STATUS_EXCUSED, "Invalid status");
        attendance[_nfcId].push(AttendanceRecord(block.timestamp, _status));
        emit AttendanceMarked(_nfcId, block.timestamp, _status, _statusLabel(_status));
    }

    // Get attendance history for an NFC ID
    function getAttendance(string memory _nfcId)
        public
        view
        returns (uint256[] memory, uint8[] memory)
    {
        AttendanceRecord[] memory records = attendance[_nfcId];
        uint256[] memory timestamps = new uint256[](records.length);
        uint8[] memory statuses = new uint8[](records.length);
        for (uint256 i = 0; i < records.length; i++) {
            timestamps[i] = records[i].timestamp;
            statuses[i] = records[i].status;
        }
        return (timestamps, statuses);
    }
}