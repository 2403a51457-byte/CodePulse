import tempfile, unittest
from pathlib import Path
from app import create_app

class CodePulseTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.app = create_app({
            "TESTING": True,
            "DATABASE": str(Path(self.temp.name) / "test.sqlite3"),
            "REPOSITORY_DIR": str(Path(self.temp.name) / "repos"),
            "SECRET_KEY": "test",
            "AUTH_DISABLED": True
        })
        self.client = self.app.test_client()

    def tearDown(self):
        self.temp.cleanup()

    def test_dashboard(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers.get("X-Frame-Options"), "DENY")

    def test_missing_project_is_handled(self):
        response = self.client.post("/projects/999/analyze", follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Project not found", response.data)

    def test_create_and_edit_project(self):
        response = self.client.post("/projects/new", data={
            "name": "Sample", "description": "test", "language": "Python", "repo_url": ""
        }, follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        with self.app.app_context():
            from database.db import get_db
            project_id = get_db().execute("SELECT id FROM projects WHERE name='Sample'").fetchone()["id"]
        response = self.client.post(f"/projects/{project_id}/edit", data={
            "name": "Updated Sample", "description": "", "language": "Python", "repo_url": ""
        }, follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Updated Sample", response.data)

    def test_delete_project(self):
        self.client.post("/projects/new", data={"name":"To Delete"})
        with self.app.app_context():
            from database.db import get_db
            project_id = get_db().execute("SELECT id FROM projects").fetchone()["id"]
        response = self.client.post(f"/projects/{project_id}/delete", follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertNotIn(b"To Delete", response.data)

if __name__ == "__main__":
    unittest.main()
