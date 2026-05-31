"""
Security regression tests for the auth guards added in the security pass.
Confirms that:
  - previously-open officer/admin routes now reject unauthenticated requests
  - public routes remain reachable
  - error responses do not leak raw exception text
Mocks the query layer so no DB is required.
"""
import json
import unittest
from unittest.mock import patch

import app as app_module


class SecurityGuardTests(unittest.TestCase):
    def setUp(self):
        self.client = app_module.app.test_client()
        app_module.app.testing = True

    # ── Unauthenticated access is rejected on now-protected routes ──────────
    def test_add_officer_requires_auth(self):
        r = self.client.post("/officers", json={"name": "X", "rank": "Constable"})
        self.assertEqual(r.status_code, 401)

    def test_delete_case_requires_auth(self):
        r = self.client.delete("/cases/1")
        self.assertEqual(r.status_code, 401)

    def test_add_case_requires_auth(self):
        r = self.client.post("/cases", json={"title": "t", "crime_type": "Theft", "location": "x"})
        self.assertEqual(r.status_code, 401)

    def test_assign_officer_requires_auth(self):
        r = self.client.post("/case-officer", json={"case_id": 1, "officer_id": 1})
        self.assertEqual(r.status_code, 401)

    def test_analytics_requires_auth(self):
        r = self.client.get("/analytics")
        self.assertEqual(r.status_code, 401)

    def test_public_complaints_list_requires_auth(self):
        r = self.client.get("/public-complaints")
        self.assertEqual(r.status_code, 401)

    # ── Non-admin officer is forbidden from admin-only routes ───────────────
    @patch("queries.validate_officer_session", return_value=True)
    @patch("queries.get_officer_by_id", return_value={"officer_id": 2, "name": "V", "role": "viewer"})
    def test_delete_case_forbidden_for_non_admin(self, _g, _v):
        r = self.client.delete("/cases/1", headers={"X-Officer-Id": "2", "X-Session-Token": "tok"})
        self.assertEqual(r.status_code, 403)

    @patch("queries.validate_officer_session", return_value=True)
    @patch("queries.get_officer_by_id", return_value={"officer_id": 2, "name": "V", "role": "viewer"})
    def test_promote_complaint_forbidden_for_non_admin(self, _g, _v):
        r = self.client.post("/public-complaints/1/promote", headers={"X-Officer-Id": "2", "X-Session-Token": "tok"})
        self.assertEqual(r.status_code, 403)

    # ── Admin is allowed through ────────────────────────────────────────────
    @patch("queries.delete_case", return_value=1)
    @patch("queries.validate_officer_session", return_value=True)
    @patch("queries.get_officer_by_id", return_value={"officer_id": 1, "name": "A", "role": "admin"})
    def test_delete_case_allowed_for_admin(self, _g, _v, _d):
        r = self.client.delete("/cases/1", headers={"X-Officer-Id": "1", "X-Session-Token": "tok"})
        self.assertEqual(r.status_code, 200)

    # ── Invalid session is rejected ─────────────────────────────────────────
    @patch("queries.validate_officer_session", return_value=False)
    def test_invalid_session_rejected(self, _v):
        r = self.client.get("/analytics", headers={"X-Officer-Id": "1", "X-Session-Token": "bad"})
        self.assertEqual(r.status_code, 401)

    # ── Public routes remain reachable ──────────────────────────────────────
    def test_health_is_public(self):
        r = self.client.get("/health")
        self.assertEqual(r.status_code, 200)

    @patch("queries.get_public_stats", return_value={"active_cases": 1})
    def test_stats_is_public(self, _s):
        r = self.client.get("/stats")
        self.assertEqual(r.status_code, 200)

    # ── Error responses do not leak raw exception text ──────────────────────
    @patch("queries.get_public_stats", side_effect=app_module.mysql.connector.Error("SECRET_TABLE detail"))
    def test_db_error_does_not_leak(self, _s):
        r = self.client.get("/stats")
        self.assertEqual(r.status_code, 500)
        self.assertNotIn("SECRET_TABLE", r.get_data(as_text=True))

    # ── Security headers present ────────────────────────────────────────────
    def test_security_headers_present(self):
        r = self.client.get("/health")
        self.assertEqual(r.headers.get("X-Content-Type-Options"), "nosniff")
        self.assertEqual(r.headers.get("X-Frame-Options"), "DENY")


if __name__ == "__main__":
    unittest.main()
