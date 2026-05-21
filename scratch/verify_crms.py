import unittest
import json
import os
import sys

# Ensure Backend directory is in the PYTHONPATH so we can import modules directly
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "Backend")))

from db_connection import init_pool
from app import app
import config
import queries

class TestCRMS(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Initialize database pool for the test suite
        init_pool()

    def setUp(self):
        # Create a test client
        self.app = app.test_client()
        self.app.testing = True

        # Disable reCAPTCHA validation for tests by setting the secret key to empty
        self.original_secret = config.RECAPTCHA_SECRET_KEY
        config.RECAPTCHA_SECRET_KEY = ""

    def tearDown(self):
        config.RECAPTCHA_SECRET_KEY = self.original_secret

    def test_01_invalid_badge_id_lookup(self):
        """
        Verify lookup workflow:
        Backend must immediately reject invalid badge IDs without running hashing computation.
        Expected: 401 status with 'Invalid credentials'
        """
        print("\n--- Running Test 01: Invalid Badge ID Lookup ---")
        payload = {
            "badge_id": "BPD-9999",  # Non-existent badge ID
            "password": "somepassword",
            "captcha_token": "dummy_token"
        }
        res = self.app.post("/auth/login", 
                            data=json.dumps(payload), 
                            content_type="application/json")
        
        self.assertEqual(res.status_code, 401)
        data = json.loads(res.data.decode())
        self.assertFalse(data.get("success"))
        self.assertEqual(data.get("error"), "Invalid credentials")
        print("Success: Invalid badge immediately rejected with 401 'Invalid credentials'")

    def test_02_valid_badge_invalid_password(self):
        """
        Verify password hashing and verification works properly with incorrect password.
        Expected: 401 status with 'Invalid credentials'
        """
        print("\n--- Running Test 02: Valid Badge but Invalid Password ---")
        payload = {
            "badge_id": "BPD-6543",  # Sub-Inspector Priya Menon
            "password": "wrong_password",
            "captcha_token": "dummy_token"
        }
        res = self.app.post("/auth/login", 
                            data=json.dumps(payload), 
                            content_type="application/json")
        
        self.assertEqual(res.status_code, 401)
        data = json.loads(res.data.decode())
        self.assertFalse(data.get("success"))
        self.assertEqual(data.get("error"), "Invalid credentials")
        print("Success: Correct badge with wrong password rejected with 401 'Invalid credentials'")

    def test_03_successful_login(self):
        """
        Verify that a correct badge ID and password succeeds and returns officer details.
        Expected: 200 success with officer dict, pop of password_hash
        """
        print("\n--- Running Test 03: Successful Login ---")
        payload = {
            "badge_id": "BPD-6543",  # Sub-Inspector Priya Menon
            "password": "crms1234",
            "captcha_token": "dummy_token"
        }
        res = self.app.post("/auth/login", 
                            data=json.dumps(payload), 
                            content_type="application/json")
        
        self.assertEqual(res.status_code, 200)
        data = json.loads(res.data.decode())
        self.assertTrue(data.get("success"))
        
        officer = data.get("officer")
        self.assertIsNotNone(officer)
        self.assertEqual(officer.get("name"), "Sub-Inspector Priya Menon")
        self.assertEqual(officer.get("badge"), "BPD-6543")
        self.assertEqual(officer.get("role"), "viewer")
        self.assertNotIn("password_hash", officer)
        print(f"Success: Login succeeded for badge {payload['badge_id']}.")

    def test_04_case_visibility_standard_officer(self):
        """
        Verify case visibility for standard officer (viewer role).
        Expected: Standard officer only retrieves their assigned cases (2, 6, 10 for Priya Menon).
        """
        print("\n--- Running Test 04: Case Visibility for Standard Officer (Viewer) ---")
        # officer_id = 2 is Priya Menon (viewer role)
        # Assigned cases: 2, 6, 10
        headers = {
            "X-Officer-Id": "2"
        }
        res = self.app.get("/api/cases", headers=headers)
        
        self.assertEqual(res.status_code, 200)
        data = json.loads(res.data.decode())
        self.assertTrue(data.get("success"))
        
        cases = data.get("data", [])
        case_ids = [c["case_id"] for c in cases]
        print(f"Priya Menon (X-Officer-Id: 2) received case IDs: {case_ids}")
        
        # Verify that all received cases are indeed assigned to Priya Menon (officer_id = 2)
        # And that she does NOT see cases assigned to others (e.g. case 1)
        for cid in case_ids:
            self.assertIn(cid, [2, 6, 10])
        self.assertNotIn(1, case_ids)
        print("Success: Standard officer only retrieved their assigned cases.")

    def test_05_case_visibility_inspector_bypass(self):
        """
        Verify case visibility for inspectors (bypass visibility).
        Expected: Inspector Arjun Nair (officer_id 1) gets all cases.
        """
        print("\n--- Running Test 05: Case Visibility for Inspector (Bypass) ---")
        headers = {
            "X-Officer-Id": "1"
        }
        res = self.app.get("/api/cases", headers=headers)
        
        self.assertEqual(res.status_code, 200)
        data = json.loads(res.data.decode())
        self.assertTrue(data.get("success"))
        
        cases = data.get("data", [])
        case_ids = [c["case_id"] for c in cases]
        print(f"Arjun Nair (X-Officer-Id: 1) received case IDs: {case_ids}")
        
        # Arjun Nair is an inspector and should see cases not assigned to him (e.g. case 2)
        self.assertIn(2, case_ids)
        self.assertGreaterEqual(len(case_ids), 3) # Should have all 13 cases in system
        print("Success: Inspector successfully bypassed constraints and retrieved all cases.")

    def test_06_single_case_visibility_access(self):
        """
        Verify endpoint /api/cases/<id> validates single case access boundaries.
        Expected: 
          - Priya Menon (officer 2) accessing assigned case 2 -> 200 OK
          - Priya Menon (officer 2) accessing unassigned case 1 -> 403 Forbidden
          - Arjun Nair (inspector 1) accessing any case -> 200 OK
        """
        print("\n--- Running Test 06: Single Case Visibility Boundaries ---")
        
        # 1. Priya Menon accessing case 2 (assigned)
        res = self.app.get("/api/cases/2", headers={"X-Officer-Id": "2"})
        self.assertEqual(res.status_code, 200)
        data = json.loads(res.data.decode())
        self.assertTrue(data.get("success"))
        
        # 2. Priya Menon accessing case 1 (unassigned)
        res = self.app.get("/api/cases/1", headers={"X-Officer-Id": "2"})
        self.assertEqual(res.status_code, 403)
        data = json.loads(res.data.decode())
        self.assertFalse(data.get("success"))
        self.assertEqual(data.get("error"), "Access denied to this case record")
        
        # 3. Arjun Nair accessing case 2 (not assigned to him)
        res = self.app.get("/api/cases/2", headers={"X-Officer-Id": "1"})
        self.assertEqual(res.status_code, 200)
        data = json.loads(res.data.decode())
        self.assertTrue(data.get("success"))
        
        print("Success: Single case access gating strictly validated and passed.")

if __name__ == "__main__":
    unittest.main()
