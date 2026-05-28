import unittest
from unittest.mock import patch, MagicMock
import os
import sys
import tempfile

# Ensure backend directory is in path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Mock database connections to avoid database pool runtime errors
with patch('db_connection.init_pool'), patch('db_connection.get_db'):
    from app import app, ALLOWED_EVIDENCE_EXTENSIONS

class TestEvidenceFeatures(unittest.TestCase):
    def setUp(self):
        self.app = app.test_client()
        self.app.testing = True

    def test_allowed_extensions(self):
        """Validate the whitelist of allowed extensions."""
        self.assertEqual(ALLOWED_EVIDENCE_EXTENSIONS, {"pdf", "jpeg", "jpg", "png", "mp4"})

    @patch('queries.get_officer_by_id')
    @patch('queries.get_case_by_id')
    @patch('queries.insert_case_evidence')
    @patch('email_utils.send_evidence_email_async')
    def test_upload_evidence_success(self, mock_send_email, mock_insert, mock_get_case, mock_get_officer):
        """Test successful evidence upload."""
        mock_get_officer.return_value = {"officer_id": 1, "name": "Arjun Nair", "role": "admin"}
        mock_get_case.return_value = {"case_id": 1, "officer_ids": [1]}
        mock_insert.return_value = 100
        
        # We need a file object
        import io
        file_data = (io.BytesIO(b"dummy data"), "test.pdf")
        
        response = self.app.post(
            "/cases/1/evidence",
            headers={"X-Officer-Id": "1", "X-Session-Token": "test-session"},
            data={"file": file_data, "description": "Important evidence doc"},
            content_type="multipart/form-data"
        )
        
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json["success"])
        self.assertEqual(response.json["evidence"]["evidence_id"], 100)
        
        # Verify email async call was triggered
        mock_send_email.assert_called_once_with(1, 1, 100)

    @patch('queries.get_officer_by_id')
    @patch('queries.get_case_by_id')
    def test_upload_evidence_invalid_extension(self, mock_get_case, mock_get_officer):
        """Test evidence upload with blocklisted extension (e.g. exe)."""
        mock_get_officer.return_value = {"officer_id": 1, "name": "Arjun Nair", "role": "admin"}
        mock_get_case.return_value = {"case_id": 1}
        
        import io
        file_data = (io.BytesIO(b"dummy executable"), "malicious.exe")
        
        response = self.app.post(
            "/cases/1/evidence",
            headers={"X-Officer-Id": "1", "X-Session-Token": "test-session"},
            data={"file": file_data},
            content_type="multipart/form-data"
        )
        
        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.json["success"])
        self.assertIn("not allowed", response.json["error"])

    @patch('queries.get_officer_by_id')
    @patch('queries.get_case_by_id')
    def test_upload_evidence_too_large(self, mock_get_case, mock_get_officer):
        """Test evidence upload exceeding 10MB limit."""
        mock_get_officer.return_value = {"officer_id": 1, "name": "Arjun Nair", "role": "admin"}
        mock_get_case.return_value = {"case_id": 1}
        
        import io
        # 11MB file
        large_data = b"0" * (11 * 1024 * 1024)
        file_data = (io.BytesIO(large_data), "too_large.pdf")
        
        response = self.app.post(
            "/cases/1/evidence",
            headers={"X-Officer-Id": "1", "X-Session-Token": "test-session"},
            data={"file": file_data},
            content_type="multipart/form-data"
        )
        
        self.assertEqual(response.status_code, 413)
        self.assertFalse(response.json["success"])
        self.assertIn("File is too large", response.json["error"])

    @patch('queries.get_officer_by_id')
    @patch('queries.get_case_by_id')
    def test_download_unauthorized_officer(self, mock_get_case, mock_get_officer):
        """Test unauthorized officer access to case evidence download."""
        mock_get_officer.return_value = {"officer_id": 2, "name": "Ravi Kumar", "role": "viewer"}
        mock_get_case.return_value = {"case_id": 1, "officer_ids": [1]} # assigned only to officer 1
        
        response = self.app.get(
            "/cases/1/evidence/some_file.pdf/download",
            headers={"X-Officer-Id": "2", "X-Session-Token": "test-session"}
        )
        
        self.assertEqual(response.status_code, 403)
        self.assertFalse(response.json["success"])
        self.assertIn("Access denied", response.json["error"])

    @patch('queries.get_officer_by_id')
    @patch('queries.get_case_by_id')
    def test_download_evidence_accepts_officer_id_query_param(self, mock_get_case, mock_get_officer):
        """Browser download links cannot send X-Officer-Id headers, so query auth must work."""
        mock_get_officer.return_value = {"officer_id": 1, "name": "Arjun Nair", "role": "viewer"}
        mock_get_case.return_value = {"case_id": 1, "officer_ids": [1]}

        with tempfile.TemporaryDirectory() as upload_dir:
            old_upload_dir = app.config['UPLOAD_FOLDER']
            app.config['UPLOAD_FOLDER'] = upload_dir
            case_dir = os.path.join(upload_dir, "case_1")
            os.makedirs(case_dir, exist_ok=True)
            with open(os.path.join(case_dir, "secure_doc.pdf"), "wb") as f:
                f.write(b"secure evidence bytes")

            try:
                response = self.app.get(
                    "/cases/1/evidence/secure_doc.pdf/download?X-Officer-Id=1&X-Session-Token=test-session",
                    buffered=True
                )
            finally:
                app.config['UPLOAD_FOLDER'] = old_upload_dir

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, b"secure evidence bytes")
        self.assertIn("attachment", response.headers.get("Content-Disposition", ""))

    @patch('queries.get_officer_by_id')
    @patch('queries.get_case_by_id')
    def test_open_evidence_accepts_officer_id_query_param(self, mock_get_case, mock_get_officer):
        """Inline evidence previews also use browser requests without custom headers."""
        mock_get_officer.return_value = {"officer_id": 1, "name": "Arjun Nair", "role": "viewer"}
        mock_get_case.return_value = {"case_id": 1, "officer_ids": [1]}

        with tempfile.TemporaryDirectory() as upload_dir:
            old_upload_dir = app.config['UPLOAD_FOLDER']
            app.config['UPLOAD_FOLDER'] = upload_dir
            case_dir = os.path.join(upload_dir, "case_1")
            os.makedirs(case_dir, exist_ok=True)
            with open(os.path.join(case_dir, "image.png"), "wb") as f:
                f.write(b"png bytes")

            try:
                response = self.app.get(
                    "/cases/evidence/file/1/image.png?X-Officer-Id=1&X-Session-Token=test-session",
                    buffered=True
                )
            finally:
                app.config['UPLOAD_FOLDER'] = old_upload_dir

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, b"png bytes")

    @patch('queries.update_case')
    @patch('queries.get_officer_by_id')
    def test_non_admin_cannot_update_case_status(self, mock_get_officer, mock_update_case):
        """Case status updates are admin-only."""
        mock_get_officer.return_value = {"officer_id": 2, "name": "Ravi Kumar", "role": "inspector"}

        response = self.app.patch(
            "/cases/1",
            headers={"X-Officer-Id": "2", "X-Session-Token": "test-session"},
            json={"status": "Solved"}
        )

        self.assertEqual(response.status_code, 403)
        self.assertFalse(response.json["success"])
        self.assertIn("Only admins may update case status", response.json["error"])
        mock_update_case.assert_not_called()

    @patch('queries.update_case')
    @patch('queries.get_officer_by_id')
    def test_admin_can_update_case_status(self, mock_get_officer, mock_update_case):
        """Admins retain case status update access."""
        mock_get_officer.return_value = {"officer_id": 1, "name": "Admin", "role": "admin"}
        mock_update_case.return_value = 1

        response = self.app.patch(
            "/cases/1",
            headers={"X-Officer-Id": "1", "X-Session-Token": "test-session"},
            json={"status": "Solved"}
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json["success"])
        mock_update_case.assert_called_once_with(1, {"status": "Solved"})

if __name__ == "__main__":
    unittest.main()
