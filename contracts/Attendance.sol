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

    struct SessionRecord {
        string sessionId;
        string subjectName;
        string teacherName;
        uint256 startTime;
        uint256 endTime;
        string[] studentNfcIds;
        uint8[] studentStatuses;
        uint256 totalPresent;
        uint256 totalLate;
        uint256 totalAbsent;
        uint256 totalExcused;
        string logData;
    }

    mapping(string => Student) public studentsByNfc;   // nfcId => Student
    mapping(address => Student) public studentsByAddr; // student address => Student
    mapping(string => AttendanceRecord[]) public attendance; // nfcId => records
    mapping(string => SessionRecord) public sessionRecords; // sessionId => SessionRecord
    string[] public sessionIds; // Keep track of all recorded sessions

    event StudentRegistered(address indexed studentAddr, string nfcId, string name);
    event AttendanceMarked(string indexed nfcId, uint256 timestamp, uint8 status, string statusLabel);
    event SessionRecorded(string indexed sessionId, string subjectName, string teacherName, uint256 startTime, uint256 endTime, uint256 studentCount, string logData);

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
        // require(studentsByNfc[_nfcId].isRegistered, "Student not registered"); // Removed as requested
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

    // Record an entire session's attendance data (called by admin at session end)
    function recordSession(
        string memory _sessionId,
        string memory _subjectName,
        string memory _teacherName,
        uint256 _startTime,
        uint256 _endTime,
        string[] memory _studentNfcIds,
        uint8[] memory _studentStatuses,
        string memory _logData
    ) public onlyAdmin {
        require(_studentNfcIds.length == _studentStatuses.length, "Mismatched arrays");
        require(_startTime < _endTime, "Invalid time range");
        
        uint256 countPresent = 0;
        uint256 countLate = 0;
        uint256 countAbsent = 0;
        uint256 countExcused = 0;
        
        // Count by status
        for (uint256 i = 0; i < _studentStatuses.length; i++) {
            uint8 status = _studentStatuses[i];
            if (status == STATUS_PRESENT) countPresent++;
            else if (status == STATUS_LATE) countLate++;
            else if (status == STATUS_ABSENT) countAbsent++;
            else if (status == STATUS_EXCUSED) countExcused++;
        }
        
        // Store the complete session record immutably on blockchain
        SessionRecord storage newSession = sessionRecords[_sessionId];
        newSession.sessionId = _sessionId;
        newSession.subjectName = _subjectName;
        newSession.teacherName = _teacherName;
        newSession.startTime = _startTime;
        newSession.endTime = _endTime;
        newSession.studentNfcIds = _studentNfcIds;
        newSession.studentStatuses = _studentStatuses;
        newSession.totalPresent = countPresent;
        newSession.totalLate = countLate;
        newSession.totalAbsent = countAbsent;
        newSession.totalExcused = countExcused;
        newSession.logData = _logData;
        
        sessionIds.push(_sessionId);
        
        emit SessionRecorded(_sessionId, _subjectName, _teacherName, _startTime, _endTime, _studentNfcIds.length, _logData);
    }

    // Get a recorded session
    function getSession(string memory _sessionId)
        public
        view
        returns (SessionRecord memory)
    {
        return sessionRecords[_sessionId];
    }

    // Get all recorded session IDs
    function getAllSessionIds()
        public
        view
        returns (string[] memory)
    {
        return sessionIds;
    }

    // Get session count
    function getSessionCount()
        public
        view
        returns (uint256)
    {
        return sessionIds.length;
    }
}