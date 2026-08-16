import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Add backend directory to sys.path
backend_dir = Path(__file__).resolve().parent
sys.path.insert(0, str(backend_dir))

from app.database.database import Base, SessionLocal, engine
from app.services.complaint_service import complaint_service
from app.services.sla_service import sla_service


def ensure_utc(dt: datetime) -> datetime:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def run_tests():
    print("==================================================")
    print("STARTING MODULE 5 UNIT & INTEGRATION TESTS")
    print("==================================================")

    # Initialize/reset database tables for test run
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()

    try:
        now = datetime.now(timezone.utc)

        # TEST 1: PRIORITY SLA DEADLINES
        print("\n--- [TEST 1] PRIORITY SLA DEADLINES ---")
        priorities_and_expected_hours = [
            ("CRITICAL", 2),
            ("HIGH", 8),
            ("MEDIUM", 24),
            ("LOW", 72),
        ]

        for prio, expected_hours in priorities_and_expected_hours:
            cmp_obj, _ = complaint_service.create_complaint(
                db=db,
                transcript=f"{prio} issue test transcript",
                summary=f"{prio} issue summary",
                priority=prio,
                custom_created_at=now,
            )
            sla_info = sla_service.get_complaint_sla(db, cmp_obj.complaint_id, override_now=now)
            print(f"{prio} Complaint SLA Info:", sla_info)

            assert sla_info["sla_duration_hours"] == expected_hours, f"Expected {expected_hours}h for {prio}, got {sla_info['sla_duration_hours']}h"
            expected_deadline = now + timedelta(hours=expected_hours)
            actual_deadline = ensure_utc(sla_info["sla_deadline"])
            diff_seconds = abs((actual_deadline - expected_deadline).total_seconds())
            assert diff_seconds < 2.0, f"Deadline mismatch for {prio}: {actual_deadline} vs {expected_deadline}"

        print("[OK] TEST 1 PASSED: SLA duration and deadline calculations match all priority levels.")

        # TEST 2: AT-RISK STATUS
        print("\n--- [TEST 2] AT-RISK STATUS TEST ---")
        # High complaint = 8 hours SLA. 20% threshold = 1.6 hours remaining.
        # At created_at + 7 hours, 1 hour remains (<= 1.6 hours), so status should be AT_RISK.
        cmp_at_risk, _ = complaint_service.create_complaint(
            db=db,
            transcript="Water shortage in Anna Nagar",
            summary="Water shortage",
            priority="HIGH",
            custom_created_at=now,
        )

        simulated_now_at_risk = now + timedelta(hours=7)  # 1 hour remaining
        sla_at_risk = sla_service.get_complaint_sla(db, cmp_at_risk.complaint_id, override_now=simulated_now_at_risk)
        print("At-Risk SLA Response:", sla_at_risk)

        assert sla_at_risk["sla_status"] == "AT_RISK", f"Expected AT_RISK, got {sla_at_risk['sla_status']}"
        assert sla_at_risk["remaining_hours"] <= 1.6, f"Expected remaining_hours <= 1.6, got {sla_at_risk['remaining_hours']}"
        print("[OK] TEST 2 PASSED: At-risk threshold correctly identifies approaching deadlines.")

        # TEST 3: BREACH & ESCALATION LEVELS
        print("\n--- [TEST 3] BREACH & ESCALATION LEVELS TEST ---")
        cmp_breach, _ = complaint_service.create_complaint(
            db=db,
            transcript="Major power outage in T Nagar",
            summary="Major power outage",
            priority="HIGH",  # 8 hour SLA
            custom_created_at=now,
        )

        # Step A: Simulate 10 hours after creation (overdue by 2 hours -> Level 1 Breach)
        simulated_now_level1 = now + timedelta(hours=10)
        sla_level1 = sla_service.get_complaint_sla(db, cmp_breach.complaint_id, override_now=simulated_now_level1)
        print("Level 1 Breach SLA Response:", sla_level1)

        assert sla_level1["sla_status"] == "BREACHED", f"Expected BREACHED, got {sla_level1['sla_status']}"
        assert sla_level1["escalation_level"] == 1, f"Expected escalation level 1, got {sla_level1['escalation_level']}"
        assert sla_level1["was_breached"] is True, "Expected was_breached to be True"
        assert sla_level1["escalated_at"] is not None, "Expected escalated_at to be set"

        # Step B: Simulate 20 hours after creation (overdue by 12 hours, > 8h full SLA duration -> Level 2 Breach)
        simulated_now_level2 = now + timedelta(hours=20)
        sla_level2 = sla_service.get_complaint_sla(db, cmp_breach.complaint_id, override_now=simulated_now_level2)
        print("Level 2 Breach SLA Response:", sla_level2)

        assert sla_level2["sla_status"] == "BREACHED", f"Expected BREACHED, got {sla_level2['sla_status']}"
        assert sla_level2["escalation_level"] == 2, f"Expected escalation level 2, got {sla_level2['escalation_level']}"
        print("[OK] TEST 3 PASSED: SLA breach and escalation levels 1 & 2 evaluated correctly.")

        # TEST 4: COMPLETED BEFORE DEADLINE
        print("\n--- [TEST 4] COMPLETED BEFORE DEADLINE TEST ---")
        cmp_completed, _ = complaint_service.create_complaint(
            db=db,
            transcript="Potholes on Mount Road",
            summary="Potholes on Mount Road",
            priority="HIGH",  # 8 hour SLA
            custom_created_at=now,
        )

        # Resolve complaint at created_at + 3 hours (before deadline)
        simulated_now_resolved = now + timedelta(hours=3)
        res_completed = complaint_service.update_status(
            db=db,
            complaint_id=cmp_completed.complaint_id,
            new_status="ASSIGNED",
            override_now=simulated_now_resolved,
        )
        res_completed = complaint_service.update_status(
            db=db,
            complaint_id=cmp_completed.complaint_id,
            new_status="IN_PROGRESS",
            override_now=simulated_now_resolved,
        )
        res_completed = complaint_service.update_status(
            db=db,
            complaint_id=cmp_completed.complaint_id,
            new_status="RESOLVED",
            override_now=simulated_now_resolved,
        )

        print("Completed Before Deadline SLA Response:", res_completed)
        assert res_completed["sla_status"] == "COMPLETED", f"Expected COMPLETED, got {res_completed['sla_status']}"
        assert res_completed["was_breached"] is False, "Expected was_breached to be False"
        assert res_completed["escalation_level"] == 0, "Expected escalation level 0"
        print("[OK] TEST 4 PASSED: Resolving before deadline sets SLA status to COMPLETED.")

        # TEST 5: BREACHED THEN RESOLVED (HISTORICAL BREACH INTEGRITY)
        print("\n--- [TEST 5] BREACHED THEN RESOLVED TEST ---")
        cmp_breached_then_resolved, _ = complaint_service.create_complaint(
            db=db,
            transcript="Garbage overflowing in Adyar",
            summary="Garbage overflowing",
            priority="HIGH",  # 8 hour SLA
            custom_created_at=now,
        )

        # Let deadline pass -> 10 hours after creation
        simulated_now_breached = now + timedelta(hours=10)
        _ = sla_service.get_complaint_sla(db, cmp_breached_then_resolved.complaint_id, override_now=simulated_now_breached)

        # Now update status to RESOLVED
        _ = complaint_service.update_status(
            db=db,
            complaint_id=cmp_breached_then_resolved.complaint_id,
            new_status="ASSIGNED",
            override_now=simulated_now_breached,
        )
        _ = complaint_service.update_status(
            db=db,
            complaint_id=cmp_breached_then_resolved.complaint_id,
            new_status="IN_PROGRESS",
            override_now=simulated_now_breached,
        )
        res_breached_resolved = complaint_service.update_status(
            db=db,
            complaint_id=cmp_breached_then_resolved.complaint_id,
            new_status="RESOLVED",
            override_now=simulated_now_breached,
        )

        print("Breached Then Resolved SLA Response:", res_breached_resolved)
        assert res_breached_resolved["sla_status"] == "BREACHED", f"Expected BREACHED historically preserved, got {res_breached_resolved['sla_status']}"
        assert res_breached_resolved["was_breached"] is True, "Expected was_breached to remain True"
        print("[OK] TEST 5 PASSED: Resolving after breach preserves historical breach status.")

        # TEST 6: SLA SUMMARY, BREACHED & AT-RISK LIST ENDPOINTS
        print("\n--- [TEST 6] SUMMARY & LIST SERVICE ENDPOINTS ---")
        summary = sla_service.get_sla_summary(db, override_now=simulated_now_breached)
        print("SLA Summary:", summary)
        assert summary["breached"] >= 2, f"Expected at least 2 breached, got {summary['breached']}"

        breached_list = sla_service.get_breached_complaints(db, override_now=simulated_now_breached)
        print(f"Breached Complaints List (Count {len(breached_list)}):")
        for b in breached_list:
            print(" ", b)
        assert len(breached_list) >= 2, f"Expected at least 2 in breached list, got {len(breached_list)}"

        at_risk_list = sla_service.get_at_risk_complaints(db, override_now=now + timedelta(hours=7))
        print(f"At-Risk Complaints List (Count {len(at_risk_list)}):")
        for a in at_risk_list:
            print(" ", a)

        print("[OK] TEST 6 PASSED: SLA summary, breached list, and at-risk list endpoints working.")

        # TEST 7: SQLITE PERSISTENCE TEST
        print("\n--- [TEST 7] SQLITE SLA PERSISTENCE TEST ---")
        db.close()

        db_fresh = SessionLocal()
        persisted_cmp = complaint_service.get_complaint_by_id(db_fresh, cmp_breached_then_resolved.complaint_id)
        print("Persisted Complaint SLA State:", persisted_cmp)

        assert persisted_cmp["was_breached"] is True, "was_breached failed to persist"
        assert persisted_cmp["sla_status"] == "BREACHED", "sla_status failed to persist"
        assert persisted_cmp["sla_duration_hours"] == 8, "sla_duration_hours failed to persist"
        db_fresh.close()
        print("[OK] TEST 7 PASSED: SLA fields persist correctly across database reconnects.")

        print("\n==================================================")
        print("ALL MODULE 5 UNIT & INTEGRATION TESTS PASSED SUCCESSFULLY!")
        print("==================================================")

    finally:
        db.close()


if __name__ == "__main__":
    run_tests()
