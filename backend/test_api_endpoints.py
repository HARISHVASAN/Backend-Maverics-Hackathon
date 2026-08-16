import json
import math
import struct
import time
import wave
import urllib.request
import urllib.parse
from pathlib import Path

BASE_URL = "http://127.0.0.1:8001"


def make_sample_wav(filename: str = "sample_test.wav") -> str:
    path = Path(__file__).parent / filename
    with wave.open(str(path), 'wb') as wav_file:
        wav_file.setnchannels(1)  # Mono
        wav_file.setsampwidth(2)  # 16-bit
        wav_file.setframerate(16000)  # 16kHz
        for i in range(16000):
            value = int(10000.0 * math.sin(2.0 * math.pi * 440.0 * i / 16000.0))
            data = struct.pack('<h', value)
            wav_file.writeframesraw(data)
    return str(path)


def test_all_endpoints():
    print("==================================================")
    print("TESTING ALL API ENDPOINTS ON http://127.0.0.1:8001")
    print("==================================================")

    # Wait for server startup
    for _ in range(10):
        try:
            req = urllib.request.urlopen(f"{BASE_URL}/")
            if req.getcode() == 200:
                print("\n[GET /] Server is alive!")
                print("Response:", req.read().decode())
                break
        except Exception:
            time.sleep(1)

    # 1. POST /transcribe
    print("\n[POST /transcribe] Testing STT endpoint...")
    wav_path = make_sample_wav("sample_test.wav")
    boundary = "----WebKitFormBoundary7MA4YWxkTrZu0gW"
    with open(wav_path, "rb") as f:
        file_bytes = f.read()

    body1 = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="file"; filename="sample_test.wav"\r\n'
        f"Content-Type: audio/wav\r\n\r\n"
    ).encode("utf-8") + file_bytes + f"\r\n--{boundary}--\r\n".encode("utf-8")

    req = urllib.request.Request(
        f"{BASE_URL}/transcribe",
        data=body1,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"}
    )
    with urllib.request.urlopen(req) as resp:
        stt_res = json.loads(resp.read().decode())
        print("Response:", json.dumps(stt_res, indent=2))
        assert "transcript" in stt_res
        print("SUCCESS: /transcribe endpoint works!")

    # 2. POST /analyze
    print("\n[POST /analyze] Testing LLM analysis endpoint...")
    analyze_payload = json.dumps({
        "transcript": "There has been no drinking water supply in Anna Nagar for the past three days."
    }).encode("utf-8")

    req = urllib.request.Request(
        f"{BASE_URL}/analyze",
        data=analyze_payload,
        headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req) as resp:
        analyze_res = json.loads(resp.read().decode())
        print("Response:", json.dumps(analyze_res, indent=2))
        assert analyze_res["category"] == "Water Supply"
        print("SUCCESS: /analyze endpoint works!")

    # 3. POST /duplicate-check
    print("\n[POST /duplicate-check] Testing duplicate check endpoint...")
    dup_payload = json.dumps({
        "complaint_id": "CMP-HTTP-9001",
        "transcript": "There has been no drinking water supply in Anna Nagar for three days.",
        "category": "Water Supply",
        "department": "Water",
        "priority": "HIGH",
        "summary": "No drinking water supply in Anna Nagar for three days",
        "location": "Anna Nagar"
    }).encode("utf-8")

    req = urllib.request.Request(
        f"{BASE_URL}/duplicate-check",
        data=dup_payload,
        headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req) as resp:
        dup_res = json.loads(resp.read().decode())
        print("Response:", json.dumps(dup_res, indent=2))
        assert "status" in dup_res
        print("SUCCESS: /duplicate-check endpoint works!")

    # 4. POST /complaints (Module 4)
    print("\n[POST /complaints] Testing Create Complaint & Ticket endpoint...")
    create_payload = json.dumps({
        "transcript": "There has been no drinking water supply in Anna Nagar for three days.",
        "language": "en",
        "category": "Water Supply",
        "department": "Water",
        "priority": "HIGH",
        "summary": "No drinking water supply for three days",
        "location": "Anna Nagar",
        "duplicate_status": "NEW",
        "duplicate_of": None
    }).encode("utf-8")

    req = urllib.request.Request(
        f"{BASE_URL}/complaints",
        data=create_payload,
        headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req) as resp:
        create_res = json.loads(resp.read().decode())
        print("Response:", json.dumps(create_res, indent=2))
        created_cmp_id = create_res["complaint_id"]
        assert created_cmp_id.startswith("CMP-")
        assert create_res["ticket"]["ticket_id"].startswith("TKT-")
        assert create_res["status"] == "PENDING"
        print(f"SUCCESS: Created complaint {created_cmp_id} and ticket {create_res['ticket']['ticket_id']}")

    # 5. GET /complaints/{complaint_id}
    print(f"\n[GET /complaints/{created_cmp_id}] Testing Get Complaint endpoint...")
    req = urllib.request.urlopen(f"{BASE_URL}/complaints/{created_cmp_id}")
    get_res = json.loads(req.read().decode())
    print("Response:", json.dumps(get_res, indent=2))
    assert get_res["complaint_id"] == created_cmp_id
    assert get_res["report_count"] >= 1
    print("SUCCESS: /complaints/{{id}} endpoint works!")

    # 6. GET /complaints
    print("\n[GET /complaints] Testing List Complaints endpoint...")
    req = urllib.request.urlopen(f"{BASE_URL}/complaints?department=Water")
    list_res = json.loads(req.read().decode())
    print(f"Response (Found {len(list_res)} water complaints)")
    assert len(list_res) > 0
    print("SUCCESS: /complaints endpoint works!")

    # 7. PATCH /complaints/{complaint_id}/status
    print(f"\n[PATCH /complaints/{created_cmp_id}/status] Testing Status Update endpoint...")
    patch_payload = json.dumps({"status": "ASSIGNED"}).encode("utf-8")
    req = urllib.request.Request(
        f"{BASE_URL}/complaints/{created_cmp_id}/status",
        data=patch_payload,
        headers={"Content-Type": "application/json"},
        method="PATCH"
    )
    with urllib.request.urlopen(req) as resp:
        patch_res = json.loads(resp.read().decode())
        print("Response:", json.dumps(patch_res, indent=2))
        assert patch_res["status"] == "ASSIGNED"
        assert patch_res["ticket"]["status"] == "ASSIGNED"
        print("SUCCESS: /complaints/{{id}}/status endpoint works!")

    # 8. GET /departments/Water/complaints
    print("\n[GET /departments/Water/complaints] Testing Department Queue endpoint...")
    req = urllib.request.urlopen(f"{BASE_URL}/departments/Water/complaints")
    dept_res = json.loads(req.read().decode())
    print(f"Response (Found {len(dept_res)} complaints in Water queue)")
    assert len(dept_res) > 0
    print("SUCCESS: /departments/{{dept}}/complaints endpoint works!")

    # 9. POST /process-and-create-ticket
    print("\n[POST /process-and-create-ticket] Testing Combined Audio Pipeline...")
    body2 = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="file"; filename="sample_test.wav"\r\n'
        f"Content-Type: audio/wav\r\n\r\n"
    ).encode("utf-8") + file_bytes + f"\r\n--{boundary}--\r\n".encode("utf-8")

    req = urllib.request.Request(
        f"{BASE_URL}/process-and-create-ticket",
        data=body2,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"}
    )
    with urllib.request.urlopen(req) as resp:
        pipeline_res = json.loads(resp.read().decode())
        print("Response:", json.dumps(pipeline_res, indent=2))
        assert "complaint" in pipeline_res
        assert "ticket" in pipeline_res
        assert "duplicate" in pipeline_res
        print("SUCCESS: /process-and-create-ticket endpoint works!")

    print("\n==================================================")
    print("ALL MODULE 1, 2, 3, 4 API REGRESSION TESTS PASSED!")
    print("==================================================")


if __name__ == "__main__":
    test_all_endpoints()
