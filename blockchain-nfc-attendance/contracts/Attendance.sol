// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

contract Attendance {
    
    struct Student {
        string studentId;
        string name;
        string nfcId;
        bool isActive;
    }
    
    struct AttendanceRecord {
        string studentId;
        uint256 timestamp;
        string subject;
        bool isPresent;
    }
    
    address public admin;
    mapping(address => Student) public students;
    mapping(string => address) public nfcToAddress;
    AttendanceRecord[] public attendanceRecords;
    
    event StudentRegistered(string indexed studentId, string name, string nfcId);
    event AttendanceMarked(string indexed studentId, uint256 timestamp, string subject, bool isPresent);
    event StudentDeactivated(string indexed studentId);
    
    modifier onlyAdmin() {
        require(msg.sender == admin, "Only admin can call this function");
        _;
    }
    
    constructor() {
        admin = msg.sender;
    }
    
    // Register a new student
    function registerStudent(
        address studentAddress,
        string memory studentId,
        string memory name,
        string memory nfcId
    ) public onlyAdmin {
        require(studentAddress != address(0), "Invalid address");
        require(bytes(studentId).length > 0, "Student ID required");
        require(bytes(nfcId).length > 0, "NFC ID required");
        
        students[studentAddress] = Student(studentId, name, nfcId, true);
        nfcToAddress[nfcId] = studentAddress;
        
        emit StudentRegistered(studentId, name, nfcId);
    }
    
    // Mark attendance for a student using NFC
    function markAttendance(
        string memory nfcId,
        string memory subject
    ) public {
        address studentAddress = nfcToAddress[nfcId];
        require(studentAddress != address(0), "NFC ID not found");
        
        Student memory student = students[studentAddress];
        require(student.isActive, "Student is not active");
        require(bytes(student.nfcId).length > 0, "Student not registered");
        
        attendanceRecords.push(AttendanceRecord(
            student.studentId,
            block.timestamp,
            subject,
            true
        ));
        
        emit AttendanceMarked(student.studentId, block.timestamp, subject, true);
    }
    
    // Mark absence
    function markAbsence(
        string memory studentId,
        string memory subject
    ) public onlyAdmin {
        attendanceRecords.push(AttendanceRecord(
            studentId,
            block.timestamp,
            subject,
            false
        ));
        
        emit AttendanceMarked(studentId, block.timestamp, subject, false);
    }
    
    // Get student info
    function getStudent(address studentAddress) public view returns (Student memory) {
        return students[studentAddress];
    }
    
    // Get total attendance records
    function getAttendanceRecordsCount() public view returns (uint256) {
        return attendanceRecords.length;
    }
    
    // Get attendance records by index
    function getAttendanceRecord(uint256 index) public view 
        returns (string memory studentId, uint256 timestamp, string memory subject, bool isPresent) 
    {
        require(index < attendanceRecords.length, "Index out of bounds");
        AttendanceRecord memory record = attendanceRecords[index];
        return (record.studentId, record.timestamp, record.subject, record.isPresent);
    }
    
    // Deactivate a student
    function deactivateStudent(address studentAddress) public onlyAdmin {
        require(students[studentAddress].isActive, "Student already inactive");
        students[studentAddress].isActive = false;
        
        emit StudentDeactivated(students[studentAddress].studentId);
    }
    
    // Get attendance count for a student
    function getStudentAttendanceCount(string memory studentId) public view returns (uint256) {
        uint256 count = 0;
        for (uint256 i = 0; i < attendanceRecords.length; i++) {
            if (keccak256(abi.encodePacked(attendanceRecords[i].studentId)) == 
                keccak256(abi.encodePacked(studentId)) && 
                attendanceRecords[i].isPresent) {
                count++;
            }
        }
        return count;
    }
}
