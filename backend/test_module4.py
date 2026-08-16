import sys
from pathlib import Path

# Add backend directory to sys.path
backend_dir = Path(__file__).resolve().parent
sys.path.insert(0, str(backend_dir))

from app.database.database import Base, SessionLocal, engine
from app.services.complaint_service import complaint_service
from app.services.department_routing import department_routing_service


def run_tests():
    print("==================================================")
    print("STARTING MODULE 4 UNIT & INTEGRATION TESTS")
    print("==================================================")

    # Initialize/reset database tables for test run
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()

    try:
        # TEST 1: NEW COMPLAINT
        print("\n--- [TEST 1] NEW COMPLAINT CREATION ---")
        cmp1, tkt1 = complaint_service.create_complaint(
            db=db,
            transcript="There has been no drinking water supply in Anna Nagar for three days.",
            summary="No drinking water supply in Anna Nagar for three days",
            category="Water Supply",
            department="Water",
            priority="HIGH",
            location="Anna Nagar",
            duplicate_status="NEW",
            duplicate_of=None,
        )

        res1 = complaint_service.get_complaint_by_id(db, cmp1.complaint_id)
        print("CMP-1 Output:", res1)

        assert res1["complaint_id"] == "CMP-1001", f"Expected CMP-1001, got {res1['complaint_id']}"
        assert res1["ticket"]["ticket_id"] == "TKT-1001", f"Expected TKT-1001, got {res1['ticket']['ticket_id']}"
        assert res1["department"] == "Water", f"Expected Water, got {res1['department']}"
        assert res1["priority"] == "HIGH", f"Expected HIGH, got {res1['priority']}"
        assert res1["status"] == "PENDING", f"Expected PENDING, got {res1['status']}"
        assert res1["report_count"] == 1, f"Expected report_count 1, got {res1['report_count']}"
        print("[OK] TEST 1 PASSED: New complaint and ticket generated correctly.")

        # TEST 2: DUPLICATE COMPLAINT
        print("\n--- [TEST 2] DUPLICATE COMPLAINT CREATION ---")
        cmp2, tkt2 = complaint_service.create_complaint(
            db=db,
            transcript="We haven't received drinking water in Anna Nagar since Monday.",
            summary="No drinking water supply in Anna Nagar",
            category="Water Supply",
            department="Water",
            priority="HIGH",
            location="Anna Nagar",
            duplicate_status="DUPLICATE",
            duplicate_of="CMP-1001",
            similarity_score=0.936,
        )

        res2 = complaint_service.get_complaint_by_id(db, cmp2.complaint_id)
        print("CMP-2 Output:", res2)

        assert res2["complaint_id"] == "CMP-1002", f"Expected CMP-1002, got {res2['complaint_id']}"
        assert res2["duplicate_status"] == "DUPLICATE", f"Expected DUPLICATE, got {res2['duplicate_status']}"
        assert res2["duplicate_of"] == "CMP-1001", f"Expected duplicate_of CMP-1001, got {res2['duplicate_of']}"
        assert res2["ticket"]["parent_ticket"] == "TKT-1001", f"Expected parent_ticket TKT-1001, got {res2['ticket']['parent_ticket']}"

        # Re-fetch CMP-1001 to verify report count updated to 2
        res1_updated = complaint_service.get_complaint_by_id(db, "CMP-1001")
        print("CMP-1 Updated Report Count:", res1_updated["report_count"])
        assert res1_updated["report_count"] == 2, f"Expected report_count 2, got {res1_updated['report_count']}"
        print("[OK] TEST 2 PASSED: Duplicate relationship linked and report count updated.")

        # TEST 3: STATUS WORKFLOW & HISTORY
        print("\n--- [TEST 3] STATUS TRANSITION WORKFLOW & HISTORY ---")
        # Step A: PENDING -> ASSIGNED
        s1 = complaint_service.update_status(db, "CMP-1001", "ASSIGNED")
        assert s1["status"] == "ASSIGNED"
        assert s1["ticket"]["status"] == "ASSIGNED"

        # Step B: ASSIGNED -> IN_PROGRESS
        s2 = complaint_service.update_status(db, "CMP-1001", "IN_PROGRESS")
        assert s2["status"] == "IN_PROGRESS"
        assert s2["ticket"]["status"] == "IN_PROGRESS"

        # Step C: IN_PROGRESS -> RESOLVED
        s3 = complaint_service.update_status(db, "CMP-1001", "RESOLVED")
        assert s3["status"] == "RESOLVED"
        assert s3["ticket"]["status"] == "RESOLVED"

        # Step D: Invalid Transition Test (RESOLVED -> ASSIGNED invalid transition check)
        try:
            complaint_service.update_status(db, "CMP-1001", "ASSIGNED")
            assert False, "Should have raised ValueError for invalid transition"
        except ValueError as ve:
            print("Successfully caught invalid status transition:", str(ve))

        # Check status history records
        history = complaint_service.get_status_history(db, "CMP-1001")
        print("Status History for CMP-1001:")
        for h in history:
            print(f"  {h['old_status']} -> {h['new_status']} at {h['changed_at']}")
        assert len(history) == 4, f"Expected 4 history records, got {len(history)}"
        print("[OK] TEST 3 PASSED: Status transitions and history logging work correctly.")

        # TEST 4: DEPARTMENT ROUTING & FILTERING
        print("\n--- [TEST 4] DEPARTMENT ROUTING & FILTERING ---")
        # Add Electricity and Roads complaints
        complaint_service.create_complaint(
            db=db,
            transcript="Power outage in T Nagar for 5 hours.",
            summary="Power outage in T Nagar",
            category="Power Outage",
            department="Electricity",
            priority="HIGH",
            location="T Nagar",
        )

        complaint_service.create_complaint(
            db=db,
            transcript="Potholes on Mount Road causing traffic congestion.",
            summary="Potholes on Mount Road",
            category="Road Repair",
            department="Roads",
            priority="MEDIUM",
            location="Mount Road",
        )

        water_queue = complaint_service.list_complaints(db=db, department="Water")
        print("Water Department Queue Count:", len(water_queue))
        for c in water_queue:
            assert c["department"] == "Water", f"Expected Water, got {c['department']}"

        elec_queue = complaint_service.list_complaints(db=db, department="Electricity")
        print("Electricity Department Queue Count:", len(elec_queue))
        for c in elec_queue:
            assert c["department"] == "Electricity", f"Expected Electricity, got {c['department']}"

        assert len(water_queue) == 2, f"Expected 2 Water complaints, got {len(water_queue)}"
        assert len(elec_queue) == 1, f"Expected 1 Electricity complaint, got {len(elec_queue)}"
        print("[OK] TEST 4 PASSED: Department filtering and routing work as expected.")

        # TEST 5: PERSISTENCE TEST
        print("\n--- [TEST 5] SQLITE PERSISTENCE TEST ---")
        db.close()

        # Open fresh Session DB instance
        db_fresh = SessionLocal()
        persisted_list = complaint_service.list_complaints(db=db_fresh)
        print("Total complaints in database after reconnect:", len(persisted_list))
        assert len(persisted_list) == 4, f"Expected 4 complaints in DB, got {len(persisted_list)}"

        cmp1_persisted = complaint_service.get_complaint_by_id(db_fresh, "CMP-1001")
        assert cmp1_persisted["status"] == "RESOLVED", "Status failed to persist on disk"
        assert cmp1_persisted["report_count"] == 2, "Report count failed to persist"
        db_fresh.close()
        print("[OK] TEST 5 PASSED: SQLite database persists correctly across connections.")

        print("\n==================================================")
        print("ALL MODULE 4 UNIT & INTEGRATION TESTS PASSED SUCCESSFULLY!")
        print("==================================================")

    finally:
        db.close()


if __name__ == "__main__":
    run_tests()
