import unittest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient
from src.server import app

class TestMigrationAPI(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    @patch('src.comic_migration.migrate_comic_series')
    def test_trigger_migration(self, mock_migrate):
        # Mock background tasks
        with patch('fastapi.BackgroundTasks.add_task') as mock_add_task:
            response = self.client.post("/api/comics/migrate", json={"user_id": 12345})
            
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json(), {"success": True, "message": "Comic series migration started in background."})
            
            # Verify task added
            # Note: Since migrate_comic_series is imported inside the function, 
            # we need to ensure the patch works correctly or check if the task was added with the function.
            # FastAPIs BackgroundTasks stores tasks. TestClient executes them unless disabled.
            # But add_task is mocked.
            mock_add_task.assert_called_once()