import os
import sys
from pathlib import Path

# Add backend directory to sys.path
backend_dir = Path(__file__).resolve().parent
sys.path.insert(0, str(backend_dir))

from app.services.chroma_service import chroma_service
from app.services.duplicate_service import duplicate_service


def run_tests():
    print("==================================================")
    print("STARTING MODULE 3 UNIT & INTEGRATION TESTS")
    print("==================================================")

    # Clear collection for a fresh test run
    print("\n--- Clearing ChromaDB collection ---")
    chroma_service.clear_collection()
    print("Count after clear:", chroma_service.count_complaints())

    # TEST 1: First complaint (CMP-1001)
    cmp1 = {
        "complaint_id": "CMP-1001",
        "transcript": "There has been no drinking water supply in Anna Nagar for three days.",
        "category": "Water Supply",
        "department": "Water",
        "priority": "HIGH",
        "summary": "No drinking water supply in Anna Nagar for three days",
        "location": "Anna Nagar",
    }
    res1 = duplicate_service.check_and_store_complaint(cmp1)
    print("\n[TEST 1A] First Complaint (CMP-1001):")
    print("Response:", res1)
    assert res1["status"] == "NEW", f"Expected NEW, got {res1['status']}"

    # TEST 1B: Duplicate complaint (CMP-1002)
    cmp2 = {
        "complaint_id": "CMP-1002",
        "transcript": "We haven't received drinking water in Anna Nagar since Monday.",
        "category": "Water Supply",
        "department": "Water",
        "priority": "HIGH",
        "summary": "No drinking water supply in Anna Nagar",
        "location": "Anna Nagar",
    }
    res2 = duplicate_service.check_and_store_complaint(cmp2)
    print("\n[TEST 1B] Duplicate Complaint (CMP-1002):")
    print("Response:", res2)
    assert res2["status"] == "DUPLICATE", f"Expected DUPLICATE, got {res2['status']}"
    assert res2["duplicate_of"] == "CMP-1001", f"Expected duplicate_of CMP-1001, got {res2['duplicate_of']}"

    # TEST 2: Different location (CMP-1003)
    cmp3 = {
        "complaint_id": "CMP-1003",
        "transcript": "We haven't received water in T Nagar for three days.",
        "category": "Water Supply",
        "department": "Water",
        "priority": "HIGH",
        "summary": "No drinking water supply in T Nagar for three days",
        "location": "T Nagar",
    }
    res3 = duplicate_service.check_and_store_complaint(cmp3)
    print("\n[TEST 2] Different Location Complaint (CMP-1003):")
    print("Response:", res3)
    assert res3["status"] == "RELATED", f"Expected RELATED, got {res3['status']}"
    assert res3["status"] != "DUPLICATE", "Different location should NOT be DUPLICATE"

    # TEST 3: Completely different issue (CMP-1004)
    cmp4 = {
        "complaint_id": "CMP-1004",
        "transcript": "The street light near my house has not been working.",
        "category": "Street Lighting",
        "department": "Municipal",
        "priority": "MEDIUM",
        "summary": "Street light not working near house",
        "location": None,
    }
    res4 = duplicate_service.check_and_store_complaint(cmp4)
    print("\n[TEST 3] Completely Different Issue (CMP-1004):")
    print("Response:", res4)
    assert res4["status"] == "NEW", f"Expected NEW, got {res4['status']}"

    # TEST 4: Same issue, different wording (CMP-1005 & CMP-1006)
    cmp5 = {
        "complaint_id": "CMP-1005",
        "transcript": "The garbage has not been collected in Anna Nagar for one week.",
        "category": "Sanitation",
        "department": "Sanitation",
        "priority": "MEDIUM",
        "summary": "Garbage uncollected in Anna Nagar for one week",
        "location": "Anna Nagar",
    }
    res5 = duplicate_service.check_and_store_complaint(cmp5)
    print("\n[TEST 4A] Sanitation Complaint (CMP-1005):")
    print("Response:", res5)

    cmp6 = {
        "complaint_id": "CMP-1006",
        "transcript": "Trash collection has stopped in Anna Nagar for the past seven days.",
        "category": "Sanitation",
        "department": "Sanitation",
        "priority": "MEDIUM",
        "summary": "Trash collection stopped in Anna Nagar for seven days",
        "location": "Anna Nagar",
    }
    res6 = duplicate_service.check_and_store_complaint(cmp6)
    print("\n[TEST 4B] Rephrased Sanitation Complaint (CMP-1006):")
    print("Response:", res6)
    assert res6["status"] == "DUPLICATE", f"Expected DUPLICATE, got {res6['status']}"
    assert res6["duplicate_of"] == "CMP-1005", f"Expected duplicate_of CMP-1005, got {res6['duplicate_of']}"

    # TEST 5: Multilingual (English CMP-1001 vs Tamil CMP-1007)
    cmp7 = {
        "complaint_id": "CMP-1007",
        "transcript": "அண்ணா நகரில் மூன்று நாட்களாக குடிநீர் வழங்கப்படவில்லை.",
        "category": "Water Supply",
        "department": "Water",
        "priority": "HIGH",
        "summary": "No drinking water supply in Anna Nagar for three days",
        "location": "Anna Nagar",
    }
    res7 = duplicate_service.check_and_store_complaint(cmp7)
    print("\n[TEST 5] Multilingual Tamil Complaint (CMP-1007):")
    print("Response:", res7)
    assert res7["status"] == "DUPLICATE", f"Expected DUPLICATE for Tamil transcript matching English CMP-1001, got {res7['status']}"
    assert res7["duplicate_of"] == "CMP-1001", f"Expected duplicate_of CMP-1001, got {res7['duplicate_of']}"

    # PERSISTENCE TEST
    print("\n--- PERSISTENCE TEST ---")
    print("Current complaints stored in ChromaDB:", chroma_service.count_complaints())
    
    # Simulate fresh service instance reload
    from app.services.chroma_service import ChromaService
    fresh_chroma = ChromaService()
    print("Fresh Chroma instance count:", fresh_chroma.count_complaints())
    assert fresh_chroma.count_complaints() > 0, "ChromaDB failed to persist complaints on disk"
    
    # Check duplicate check again against fresh instance
    cmp_test_persist = {
        "complaint_id": "CMP-1008",
        "transcript": "No drinking water in Anna Nagar for 3 days.",
        "category": "Water Supply",
        "department": "Water",
        "priority": "HIGH",
        "summary": "No drinking water in Anna Nagar",
        "location": "Anna Nagar",
    }
    res_persist = duplicate_service.check_and_store_complaint(cmp_test_persist)
    print("Persistence Test Complaint (CMP-1008) Response:", res_persist)
    assert res_persist["status"] == "DUPLICATE", f"Expected DUPLICATE after reload, got {res_persist['status']}"

    print("\n==================================================")
    print("ALL MODULE 3 UNIT & INTEGRATION TESTS PASSED SUCCESSFULLY!")
    print("==================================================")


if __name__ == "__main__":
    run_tests()
