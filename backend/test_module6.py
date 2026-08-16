import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Add backend directory to sys.path
backend_dir = Path(__file__).resolve().parent
sys.path.insert(0, str(backend_dir))

from app.database.database import Base, SessionLocal, engine
from app.services.analytics_service import analytics_service
from app.services.complaint_service import complaint_service


def run_tests():
    print("==================================================")
    print("STARTING MODULE 6 UNIT & INTEGRATION TESTS")
    print("==================================================")

    # Initialize/reset database tables for test run
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    now = datetime.now(timezone.utc)

    try:
        # --------------------------------------------------------------
        # TEST 8 FIRST: EMPTY DATABASE (run before any data is inserted)
        # --------------------------------------------------------------
        print("\n--- [TEST 8] EMPTY DATABASE ---")
        empty_summary = analytics_service.get_summary(db)
        print("Empty Summary:", empty_summary)
        assert empty_summary["total_complaints"] == 0
        assert empty_summary["pending"] == 0
        assert empty_summary["duplicates"] == 0
        assert empty_summary["sla_at_risk"] == 0
        assert empty_summary["sla_breached"] == 0

        assert analytics_service.get_department_breakdown(db) == []
        assert analytics_service.get_category_breakdown(db) == []
        assert analytics_service.get_location_breakdown(db) == []
        assert analytics_service.get_top_issues(db) == []

        empty_priorities = analytics_service.get_priority_breakdown(db)
        assert all(p["count"] == 0 for p in empty_priorities)
        assert [p["priority"] for p in empty_priorities] == ["CRITICAL", "HIGH", "MEDIUM", "LOW"]

        empty_status = analytics_service.get_status_breakdown(db)
        assert all(v == 0 for v in empty_status.values())

        empty_dup = analytics_service.get_duplicate_stats(db)
        assert empty_dup["total_complaints"] == 0
        assert empty_dup["duplicate_percentage"] == 0.0  # no division-by-zero crash

        empty_sla = analytics_service.get_sla_stats(db)
        assert empty_sla["active"] == 0
        assert empty_sla["sla_compliance_percentage"] == 0.0  # no division-by-zero crash

        print("[OK] TEST 8 PASSED: Analytics endpoints handle an empty database safely.")

        # --------------------------------------------------------------
        # Seed a known dataset for the remaining tests
        # --------------------------------------------------------------
        def make(
            department,
            category,
            priority,
            status_after_create,
            location,
            duplicate_status="NEW",
            duplicate_of=None,
        ):
            cmp_obj, _ = complaint_service.create_complaint(
                db=db,
                transcript=f"{category} issue in {location}",
                summary=f"{category} issue in {location}",
                category=category,
                department=department,
                priority=priority,
                location=location,
                duplicate_status=duplicate_status,
                duplicate_of=duplicate_of,
                custom_created_at=now,
            )
            if status_after_create != "PENDING":
                for step in _transition_path(status_after_create):
                    complaint_service.update_status(
                        db=db, complaint_id=cmp_obj.complaint_id, new_status=step, override_now=now
                    )
            return cmp_obj

        def _transition_path(target):
            path = {
                "ASSIGNED": ["ASSIGNED"],
                "IN_PROGRESS": ["ASSIGNED", "IN_PROGRESS"],
                "RESOLVED": ["ASSIGNED", "IN_PROGRESS", "RESOLVED"],
                "CLOSED": ["ASSIGNED", "IN_PROGRESS", "RESOLVED", "CLOSED"],
            }
            return path[target]

        # 3 Water, 2 Electricity, 1 Roads (TEST 2)
        # Categories vary for TEST 3; priorities vary for TEST 4
        c1 = make("Water", "Water Supply", "HIGH", "PENDING", "Anna Nagar")
        c2 = make("Water", "Water Supply", "MEDIUM", "ASSIGNED", "Anna Nagar")
        c3 = make("Water", "Water Supply", "MEDIUM", "IN_PROGRESS", "T Nagar")
        c4 = make("Electricity", "Power Outage", "CRITICAL", "RESOLVED", "T Nagar")
        c5 = make("Electricity", "Power Outage", "LOW", "CLOSED", "T Nagar")
        c6 = make("Roads", "Road Damage", "LOW", "PENDING", "Velachery")

        # Extra complaints to satisfy duplicate-status distribution (TEST 5): 5 NEW, 2 RELATED, 3 DUPLICATE.
        # c1..c6 above are all NEW (6 so far); add more to reach exactly 5 NEW total is impossible now that
        # we already have 6 NEW, so build a dedicated, isolated dataset for the duplicate-percentage test instead.

        # Location counts (TEST 6): Anna Nagar=4, T Nagar=3, Velachery=1
        make("Sanitation", "Garbage", "MEDIUM", "PENDING", "Anna Nagar")
        make("Sanitation", "Garbage", "MEDIUM", "PENDING", "Anna Nagar")
        make("Roads", "Pothole", "MEDIUM", "PENDING", "T Nagar")

        db.commit()

        # --------------------------------------------------------------
        # TEST 1: SUMMARY
        # --------------------------------------------------------------
        print("\n--- [TEST 1] SUMMARY ---")
        summary = analytics_service.get_summary(db)
        print("Summary:", summary)
        assert summary["total_complaints"] == 9
        assert summary["pending"] == 5  # c1, c6, + 2 sanitation Anna Nagar, + roads pothole
        assert summary["assigned"] == 1  # c2
        assert summary["in_progress"] == 1  # c3
        assert summary["resolved"] == 1  # c4
        assert summary["closed"] == 1  # c5
        assert summary["critical"] == 1  # c4
        assert summary["high"] == 1  # c1
        assert summary["medium"] == 5  # c2, c3, 2 sanitation, 1 roads pothole
        assert summary["low"] == 2  # c5, c6
        assert summary["duplicates"] == 0  # none marked DUPLICATE yet
        print("[OK] TEST 1 PASSED: Summary matches known seeded dataset.")

        # --------------------------------------------------------------
        # TEST 2: DEPARTMENTS
        # --------------------------------------------------------------
        print("\n--- [TEST 2] DEPARTMENTS ---")
        departments = analytics_service.get_department_breakdown(db)
        print("Departments:", departments)
        dept_map = {d["department"]: d["count"] for d in departments}
        assert dept_map.get("Water") == 3
        assert dept_map.get("Electricity") == 2
        assert dept_map.get("Roads") == 2  # c6 + "Pothole" roads complaint
        assert dept_map.get("Sanitation") == 2
        # Verify descending order
        counts = [d["count"] for d in departments]
        assert counts == sorted(counts, reverse=True)
        print("[OK] TEST 2 PASSED: Department breakdown correct and sorted descending.")

        # --------------------------------------------------------------
        # TEST 3: CATEGORIES
        # --------------------------------------------------------------
        print("\n--- [TEST 3] CATEGORIES ---")
        categories = analytics_service.get_category_breakdown(db)
        print("Categories:", categories)
        cat_map = {c["category"]: c["count"] for c in categories}
        assert cat_map.get("Water Supply") == 3
        assert cat_map.get("Power Outage") == 2
        assert cat_map.get("Garbage") == 2
        assert cat_map.get("Road Damage") == 1
        assert cat_map.get("Pothole") == 1
        cat_counts = [c["count"] for c in categories]
        assert cat_counts == sorted(cat_counts, reverse=True)
        print("[OK] TEST 3 PASSED: Category aggregation correct and sorted descending.")

        # --------------------------------------------------------------
        # TEST 4: PRIORITIES
        # --------------------------------------------------------------
        print("\n--- [TEST 4] PRIORITIES ---")
        priorities = analytics_service.get_priority_breakdown(db)
        print("Priorities:", priorities)
        assert priorities == [
            {"priority": "CRITICAL", "count": 1},
            {"priority": "HIGH", "count": 1},
            {"priority": "MEDIUM", "count": 5},
            {"priority": "LOW", "count": 2},
        ]
        print("[OK] TEST 4 PASSED: Priority counts match known seeded dataset.")

        # --------------------------------------------------------------
        # TEST 6: LOCATIONS
        # --------------------------------------------------------------
        print("\n--- [TEST 6] LOCATIONS ---")
        locations = analytics_service.get_location_breakdown(db)
        print("Locations:", locations)
        loc_map = {l["location"]: l["count"] for l in locations}
        assert loc_map.get("Anna Nagar") == 4  # c1, c2, + 2 sanitation
        assert loc_map.get("T Nagar") == 4  # c3, c4, c5, + roads pothole
        assert loc_map.get("Velachery") == 1  # c6
        # Verify descending order
        loc_counts = [l["count"] for l in locations]
        assert loc_counts == sorted(loc_counts, reverse=True)
        print("[OK] TEST 6 PASSED: Location breakdown correct and sorted descending.")

        # --------------------------------------------------------------
        # TEST 5: DUPLICATES (isolated dataset: 5 NEW, 2 RELATED, 3 DUPLICATE)
        # --------------------------------------------------------------
        print("\n--- [TEST 5] DUPLICATES ---")
        Base.metadata.drop_all(bind=engine)
        Base.metadata.create_all(bind=engine)
        db.close()
        db = SessionLocal()

        root = None
        for i in range(5):
            cmp_obj, _ = complaint_service.create_complaint(
                db=db,
                transcript=f"New unique issue {i}",
                summary=f"New unique issue {i}",
                duplicate_status="NEW",
                custom_created_at=now,
            )
            if root is None:
                root = cmp_obj.complaint_id
        for i in range(2):
            complaint_service.create_complaint(
                db=db,
                transcript=f"Related issue {i}",
                summary=f"Related issue {i}",
                duplicate_status="RELATED",
                custom_created_at=now,
            )
        for i in range(3):
            complaint_service.create_complaint(
                db=db,
                transcript=f"Duplicate issue {i}",
                summary=f"Duplicate issue {i}",
                duplicate_status="DUPLICATE",
                duplicate_of=root,
                custom_created_at=now,
            )
        db.commit()

        dup_stats = analytics_service.get_duplicate_stats(db)
        print("Duplicate Stats:", dup_stats)
        assert dup_stats["total_complaints"] == 10
        assert dup_stats["new"] == 5
        assert dup_stats["related"] == 2
        assert dup_stats["duplicates"] == 3
        assert dup_stats["duplicate_percentage"] == 30.0  # 3/10 * 100
        print("[OK] TEST 5 PASSED: Duplicate statistics match known distribution.")

        # --------------------------------------------------------------
        # TEST 7: SLA (reuses Module 5's sla_service, no separate SLA math)
        # --------------------------------------------------------------
        print("\n--- [TEST 7] SLA ---")
        Base.metadata.drop_all(bind=engine)
        Base.metadata.create_all(bind=engine)
        db.close()
        db = SessionLocal()

        # analytics_service.get_sla_stats() delegates to sla_service with no time
        # override (it evaluates against real "now", exactly like the live API
        # would), so each scenario is driven purely via created_at -- not via a
        # simulated override_now that a later un-overridden call would undo.

        # ACTIVE: fresh HIGH complaint, well within SLA window
        active_cmp, _ = complaint_service.create_complaint(
            db=db, transcript="Active issue", summary="Active issue",
            priority="HIGH", custom_created_at=now,
        )

        # AT_RISK: HIGH complaint created 7h ago -> ~1h of the 8h SLA remains (<1.6h threshold)
        at_risk_cmp, _ = complaint_service.create_complaint(
            db=db, transcript="At risk issue", summary="At risk issue",
            priority="HIGH", custom_created_at=now - timedelta(hours=7),
        )

        # BREACHED: HIGH complaint created 10h ago -> deadline (8h) already passed, still unresolved
        breached_cmp, _ = complaint_service.create_complaint(
            db=db, transcript="Breached issue", summary="Breached issue",
            priority="HIGH", custom_created_at=now - timedelta(hours=10),
        )

        # COMPLETED: HIGH complaint resolved 3h after creation, before the 8h deadline
        completed_cmp, _ = complaint_service.create_complaint(
            db=db, transcript="Completed issue", summary="Completed issue",
            priority="HIGH", custom_created_at=now,
        )
        resolve_time = now + timedelta(hours=3)
        complaint_service.update_status(db, completed_cmp.complaint_id, "ASSIGNED", override_now=resolve_time)
        complaint_service.update_status(db, completed_cmp.complaint_id, "IN_PROGRESS", override_now=resolve_time)
        complaint_service.update_status(db, completed_cmp.complaint_id, "RESOLVED", override_now=resolve_time)
        db.commit()

        sla_analytics = analytics_service.get_sla_stats(db)
        print("SLA Analytics:", sla_analytics)
        assert sla_analytics["active"] == 1
        assert sla_analytics["at_risk"] == 1
        assert sla_analytics["breached"] == 1
        assert sla_analytics["completed"] == 1
        assert sla_analytics["sla_compliance_percentage"] == 50.0  # 1 completed / (1 completed + 1 breached)
        print("[OK] TEST 7 PASSED: SLA analytics correctly reuse Module 5 logic.")

        print("\n==================================================")
        print("ALL MODULE 6 UNIT & INTEGRATION TESTS PASSED SUCCESSFULLY!")
        print("==================================================")

    finally:
        db.close()


if __name__ == "__main__":
    run_tests()
