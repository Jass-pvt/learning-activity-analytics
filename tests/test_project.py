
from tracker.run import build_events, signature, stable_source


def test_unchanged_leetcode_submission_is_not_new():
    submission = {
        "id": "123",
        "title": "Two Sum",
        "title_slug": "two-sum",
        "timestamp": 1791559786,
        "status": "Accepted",
    }
    previous = {
        "sources": {
            "leetcode": {
                "status": "ok",
                "data": {"recent_accepted_submissions": [submission]},
            }
        }
    }
    current = {
        "sources": {
            "leetcode": {
                "status": "ok",
                "data": {"recent_accepted_submissions": [submission]},
            }
        }
    }

    assert build_events(previous, current, "2026-10-19") == []


def test_new_leetcode_submission_is_detected():
    previous = {
        "sources": {
            "leetcode": {
                "status": "ok",
                "data": {"recent_accepted_submissions": []},
            }
        }
    }
    current = {
        "sources": {
            "leetcode": {
                "status": "ok",
                "data": {
                    "recent_accepted_submissions": [
                        {
                            "id": "123",
                            "title": "Two Sum",
                            "title_slug": "two-sum",
                            "timestamp": 1791559786,
                            "status": "Accepted",
                        }
                    ]
                },
            }
        }
    }

    events = build_events(previous, current, "2026-10-19")

    assert len(events) == 1
    assert events[0]["type"] == "new_accepted_submission_observed"
    assert events[0]["details"]["id"] == "123"


def test_new_google_skills_badge_is_detected():
    previous = {
        "sources": {
            "google_skills": {
                "status": "ok",
                "data": {"earned_badges": ["Cloud Basics"]},
            }
        }
    }
    current = {
        "sources": {
            "google_skills": {
                "status": "ok",
                "data": {
                    "earned_badges": ["Cloud Basics", "Kubernetes Basics"]
                },
            }
        }
    }

    events = build_events(previous, current, "2026-10-19")

    assert len(events) == 1
    assert events[0]["type"] == "new_badge_observed"
    assert events[0]["details"]["badge"] == "Kubernetes Basics"


def test_gfg_solved_count_increase_is_detected():
    previous = {
        "sources": {
            "geeksforgeeks": {
                "status": "ok",
                "data": {"total_problems_solved": 10},
            }
        }
    }
    current = {
        "sources": {
            "geeksforgeeks": {
                "status": "ok",
                "data": {"total_problems_solved": 12},
            }
        }
    }

    events = build_events(previous, current, "2026-10-19")

    assert len(events) == 1
    assert events[0]["type"] == "solved_count_increased"
    assert events[0]["details"]["increase"] == 2


def test_failed_source_does_not_create_activity():
    previous = {
        "sources": {
            "leetcode": {
                "status": "ok",
                "data": {"recent_accepted_submissions": []},
            }
        }
    }
    current = {
        "sources": {
            "leetcode": {
                "status": "error",
                "error": "Temporary network failure",
            }
        }
    }

    assert build_events(previous, current, "2026-10-19") == []


def test_signature_is_independent_of_dictionary_key_order():
    assert signature({"a": 1, "b": 2}) == signature({"b": 2, "a": 1})


def test_stable_source_excludes_collection_timestamp():
    snapshot = {
        "collected_at_utc": "2026-10-19T10:00:00+00:00",
        "sources": {"leetcode": {"status": "ok", "data": {}}},
    }

    assert stable_source(snapshot) == snapshot["sources"]
