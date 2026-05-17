import sys
sys.path.append(r'c:\Users\James NIcolo\Downloads\Attendance_System_Using_Blockchain_With_NFC_Integration')
from app import app

with app.test_client() as client:
    with client.session_transaction() as sess:
        sess['username'] = 'admin'
        sess['role'] = 'super_admin'
    res = client.get('/api/attendance/stats?period=all')
    print("STATUS:", res.status_code)
    try:
        print("JSON:", res.get_json())
    except:
        print("DATA:", res.data.decode('utf-8'))
