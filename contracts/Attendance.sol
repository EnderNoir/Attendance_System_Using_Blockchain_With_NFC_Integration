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

    struct StudentAttendanceDetail {
        string nfcUid;              // NFC UID
        string studentName;
        string studentNumber;
        string studentType;         // REGULAR STUDENT, IRREGULAR, etc.
        uint8 status;               // 0=PRESENT, 1=LATE, 2=ABSENT, 3=EXCUSED
        string attendanceRemarks;   // PRESENT, LATE, ABSENT, EXCUSED
        string excusedReason;       // NONE or reason
        uint256 tappedTime;         // Timestamp of tap
    }

    struct AttendanceRecord {
        uint256 timestamp;
        uint8 status;
        string nfcId;               // NFC UID for record linking
    }

    struct LectureSessionMetadata {
        string courseCode;
        string instructorName;
        string program;
        string yearLevel;
        string section;
        string semester;
    }

    struct SchoolEventMetadata {
        string eventName;
        string instructorNames;     // Comma-separated list of instructors
        string programsAndSections; // Comma-separated list
    }

    struct SessionRecord {
        string sessionId;
        string classType;           // 'lecture', 'laboratory', 'school_event'
        string subjectName;
        string teacherName;
        uint256 startTime;
        uint256 endTime;
        uint256 sessionDate;        // Timestamp of session date
        string timeSlot;            // e.g., "7:00 AM TO 9:00 AM"
        
        // Lecture/Laboratory specific
        string courseCode;
        string program;
        string yearLevel;
        string section;
        string semester;
        
        // School event specific
        string eventName;
        string instructorNames;
        string programsAndSections;
        
        // Attendance data
        StudentAttendanceDetail[] attendanceRecords;
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

    // Events with detailed attendance information
    event StudentRegistered(address indexed studentAddr, string nfcId, string name);
    event AttendanceMarked(string indexed nfcId, uint256 timestamp, uint8 status, string statusLabel);
    
    event SessionRecordedLecture(
        string indexed sessionId,
        string classType,
        string subjectName,
        string courseCode,
        string instructorName,
        string program,
        string yearLevel,
        string section,
        string semester,
        uint256 sessionDate,
        string timeSlot,
        uint256 studentCount,
        string logData
    );
    
    event SessionRecordedSchoolEvent(
        string indexed sessionId,
        string classType,
        string eventName,
        string instructorNames,
        string programsAndSections,
        uint256 sessionDate,
        string timeSlot,
        uint256 studentCount,
        string logData
    );
    
    event StudentAttendanceRecorded(
        string indexed sessionId,
        string indexed nfcUid,
        string studentName,
        string studentNumber,
        string studentType,
        string attendanceRemarks,
        string excusedReason,
        uint256 tappedTime
    );

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
        attendance[_nfcId].push(AttendanceRecord(block.timestamp, _status, _nfcId));
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

    // Record a complete lecture/laboratory session with detailed attendance
    function recordLectureSession(
        string memory _sessionId,
        string memory _classType,           // "LECTURE" or "LABORATORY"
        string memory _subjectName,
        string memory _courseCode,
        string memory _instructorName,
        string memory _program,
        string memory _yearLevel,
        string memory _section,
        string memory _semester,
        uint256 _sessionDate,
        string memory _timeSlot,
        uint256 _startTime,
        uint256 _endTime,
        string[] memory _nfcUids,
        string[] memory _studentNames,
        string[] memory _studentNumbers,
        string[] memory _studentTypes,
        uint8[] memory _statuses,
        string[] memory _attendanceRemarks,
        string[] memory _excusedReasons,
        uint256[] memory _tappedTimes,
        string memory _logData
    ) public onlyAdmin {
        require(_nfcUids.length == _statuses.length, "Mismatched arrays");
        require(_startTime < _endTime, "Invalid time range");
        require(_nfcUids.length == _studentNames.length, "Student names mismatch");
        require(_nfcUids.length == _studentNumbers.length, "Student numbers mismatch");
        require(_nfcUids.length == _tappedTimes.length, "Tapped times mismatch");
        
        uint256 countPresent = 0;
        uint256 countLate = 0;
        uint256 countAbsent = 0;
        uint256 countExcused = 0;
        
        // Create session record
        SessionRecord storage newSession = sessionRecords[_sessionId];
        newSession.sessionId = _sessionId;
        newSession.classType = _classType;
        newSession.subjectName = _subjectName;
        newSession.courseCode = _courseCode;
        newSession.teacherName = _instructorName;
        newSession.program = _program;
        newSession.yearLevel = _yearLevel;
        newSession.section = _section;
        newSession.semester = _semester;
        newSession.sessionDate = _sessionDate;
        newSession.timeSlot = _timeSlot;
        newSession.startTime = _startTime;
        newSession.endTime = _endTime;
        newSession.logData = _logData;
        
        // Record each student's attendance with full details
        for (uint256 i = 0; i < _nfcUids.length; i++) {
            uint8 status = _statuses[i];
            
            StudentAttendanceDetail memory detail = StudentAttendanceDetail({
                nfcUid: _nfcUids[i],
                studentName: _studentNames[i],
                studentNumber: _studentNumbers[i],
                studentType: _studentTypes[i],
                status: status,
                attendanceRemarks: _attendanceRemarks[i],
                excusedReason: _excusedReasons[i],
                tappedTime: _tappedTimes[i]
            });
            
            newSession.attendanceRecords.push(detail);
            
            // Count statuses
            if (status == STATUS_PRESENT) countPresent++;
            else if (status == STATUS_LATE) countLate++;
            else if (status == STATUS_ABSENT) countAbsent++;
            else if (status == STATUS_EXCUSED) countExcused++;
            
            // Emit individual student attendance event
            emit StudentAttendanceRecorded(
                _sessionId,
                _nfcUids[i],
                _studentNames[i],
                _studentNumbers[i],
                _studentTypes[i],
                _attendanceRemarks[i],
                _excusedReasons[i],
                _tappedTimes[i]
            );
            
            // Also record in individual attendance tracking
            attendance[_nfcUids[i]].push(AttendanceRecord(_tappedTimes[i], status, _nfcUids[i]));
        }
        
        newSession.totalPresent = countPresent;
        newSession.totalLate = countLate;
        newSession.totalAbsent = countAbsent;
        newSession.totalExcused = countExcused;
        
        sessionIds.push(_sessionId);
        
        emit SessionRecordedLecture(
            _sessionId,
            _classType,
            _subjectName,
            _courseCode,
            _instructorName,
            _program,
            _yearLevel,
            _section,
            _semester,
            _sessionDate,
            _timeSlot,
            _nfcUids.length,
            _logData
        );
    }

    // Record a complete school event session with detailed attendance
    function recordSchoolEventSession(
        string memory _sessionId,
        string memory _eventName,
        string memory _instructorNames,
        string memory _programsAndSections,
        uint256 _sessionDate,
        string memory _timeSlot,
        uint256 _startTime,
        uint256 _endTime,
        string[] memory _nfcUids,
        string[] memory _studentNames,
        string[] memory _studentNumbers,
        string[] memory _studentTypes,
        string[] memory _programsAndSectionsPerStudent,
        uint8[] memory _statuses,
        string[] memory _attendanceRemarks,
        uint256[] memory _tappedTimes,
        string memory _logData
    ) public onlyAdmin {
        require(_nfcUids.length == _statuses.length, "Mismatched arrays");
        require(_startTime < _endTime, "Invalid time range");
        require(_nfcUids.length == _studentNames.length, "Student names mismatch");
        require(_nfcUids.length == _studentNumbers.length, "Student numbers mismatch");
        require(_nfcUids.length == _tappedTimes.length, "Tapped times mismatch");
        require(_nfcUids.length == _programsAndSectionsPerStudent.length, "Programs/sections mismatch");
        
        uint256 countPresent = 0;
        uint256 countLate = 0;
        uint256 countAbsent = 0;
        uint256 countExcused = 0;
        
        // Create session record
        SessionRecord storage newSession = sessionRecords[_sessionId];
        newSession.sessionId = _sessionId;
        newSession.classType = "SCHOOL EVENT";
        newSession.eventName = _eventName;
        newSession.instructorNames = _instructorNames;
        newSession.programsAndSections = _programsAndSections;
        newSession.sessionDate = _sessionDate;
        newSession.timeSlot = _timeSlot;
        newSession.startTime = _startTime;
        newSession.endTime = _endTime;
        newSession.logData = _logData;
        
        // Record each student's attendance with full details
        for (uint256 i = 0; i < _nfcUids.length; i++) {
            uint8 status = _statuses[i];
            
            StudentAttendanceDetail memory detail = StudentAttendanceDetail({
                nfcUid: _nfcUids[i],
                studentName: _studentNames[i],
                studentNumber: _studentNumbers[i],
                studentType: _studentTypes[i],
                status: status,
                attendanceRemarks: _attendanceRemarks[i],
                excusedReason: _programsAndSectionsPerStudent[i],  // Store program/section in excusedReason for now
                tappedTime: _tappedTimes[i]
            });
            
            newSession.attendanceRecords.push(detail);
            
            // Count statuses
            if (status == STATUS_PRESENT) countPresent++;
            else if (status == STATUS_LATE) countLate++;
            else if (status == STATUS_ABSENT) countAbsent++;
            else if (status == STATUS_EXCUSED) countExcused++;
            
            // Emit individual student attendance event
            emit StudentAttendanceRecorded(
                _sessionId,
                _nfcUids[i],
                _studentNames[i],
                _studentNumbers[i],
                _studentTypes[i],
                _attendanceRemarks[i],
                _programsAndSectionsPerStudent[i],
                _tappedTimes[i]
            );
            
            // Also record in individual attendance tracking
            attendance[_nfcUids[i]].push(AttendanceRecord(_tappedTimes[i], status, _nfcUids[i]));
        }
        
        newSession.totalPresent = countPresent;
        newSession.totalLate = countLate;
        newSession.totalAbsent = countAbsent;
        newSession.totalExcused = countExcused;
        
        sessionIds.push(_sessionId);
        
        emit SessionRecordedSchoolEvent(
            _sessionId,
            "SCHOOL EVENT",
            _eventName,
            _instructorNames,
            _programsAndSections,
            _sessionDate,
            _timeSlot,
            _nfcUids.length,
            _logData
        );
    }

    // Get a recorded session
    function getSession(string memory _sessionId)
        public
        view
        returns (SessionRecord memory)
    {
        return sessionRecords[_sessionId];
    }
    
    // Get session attendance records count
    function getSessionAttendanceCount(string memory _sessionId)
        public
        view
        returns (uint256)
    {
        return sessionRecords[_sessionId].attendanceRecords.length;
    }
    
    // Get a specific attendance record from a session
    function getSessionAttendanceRecord(string memory _sessionId, uint256 _index)
        public
        view
        returns (StudentAttendanceDetail memory)
    {
        require(_index < sessionRecords[_sessionId].attendanceRecords.length, "Index out of bounds");
        return sessionRecords[_sessionId].attendanceRecords[_index];
    }
    
    // Get all attendance records for a session
    function getSessionAllAttendanceRecords(string memory _sessionId)
        public
        view
        returns (StudentAttendanceDetail[] memory)
    {
        return sessionRecords[_sessionId].attendanceRecords;
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