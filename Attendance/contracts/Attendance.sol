// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

contract Attendance {
    address public admin;

    struct Student {
        string name;
        string nfcId;       // Unique NFC tag UID (as string)
        bool isRegistered;
    }

    struct AttendanceRecord {
        uint256 timestamp;
        bool present;
    }

    mapping(string => Student) public studentsByNfc;   // nfcId => Student
    mapping(address => Student) public studentsByAddr; // student address => Student
    mapping(string => AttendanceRecord[]) public attendance; // nfcId => records

    event StudentRegistered(address indexed studentAddr, string nfcId, string name);
    event AttendanceMarked(string indexed nfcId, uint256 timestamp);

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

    // Mark attendance – called by the student (or by the reader)
    function markAttendance(string memory _nfcId) public {
        require(studentsByNfc[_nfcId].isRegistered, "Student not registered");
        attendance[_nfcId].push(AttendanceRecord(block.timestamp, true));
        emit AttendanceMarked(_nfcId, block.timestamp);
    }

    // Get attendance history for an NFC ID
    function getAttendance(string memory _nfcId)
        public
        view
        returns (uint256[] memory, bool[] memory)
    {
        AttendanceRecord[] memory records = attendance[_nfcId];
        uint256[] memory timestamps = new uint256[](records.length);
        bool[] memory present = new bool[](records.length);
        for (uint256 i = 0; i < records.length; i++) {
            timestamps[i] = records[i].timestamp;
            present[i] = records[i].present;
        }
        return (timestamps, present);
    }
}