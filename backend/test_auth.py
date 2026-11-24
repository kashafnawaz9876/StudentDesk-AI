import json
import os
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import patch
from sqlalchemy.exc import SQLAlchemyError

os.environ["DATABASE_URL"] = "sqlite://"
os.environ["SECRET_KEY"] = "test-only-secret-that-is-long-enough-123456789"
os.environ["GROQ_API_KEY"] = "test-only-groq-key"
sys.path.insert(0, os.path.dirname(__file__))

from app import AgentLog, Assignment, User, app, db, get_assignment_database_context, run_tool
from migrate_auth import migrate


class AuthOwnershipTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with app.app_context():
            db.create_all()

    @classmethod
    def tearDownClass(cls):
        with app.app_context():
            db.session.remove()
            db.drop_all()
            db.engine.dispose()

    def setUp(self):
        with app.app_context():
            db.session.remove()
            db.drop_all()
            db.create_all()

    def signup(self, client, email):
        return client.post(
            "/api/auth/signup",
            json={"name": email.split("@")[0], "email": email, "password": "a-strong-test-password"},
        )

    def test_signup_login_logout_and_protection(self):
        client = app.test_client()
        self.assertEqual(client.get("/api/dashboard").status_code, 401)
        self.assertFalse(client.get("/api/auth/me").json["authenticated"])

        response = self.signup(client, "student@example.test")
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json["user"]["email"], "student@example.test")
        with app.app_context():
            user = User.query.filter_by(email="student@example.test").one()
            self.assertNotEqual(user.password_hash, "a-strong-test-password")

        self.assertEqual(
            client.post("/api/auth/logout", headers={"Content-Type": "application/json"}).status_code,
            200,
        )
        self.assertEqual(client.get("/api/assignments").status_code, 401)
        self.assertEqual(
            client.post(
                "/api/auth/login",
                json={"email": "student@example.test", "password": "incorrect-password"},
            ).status_code,
            401,
        )
        self.assertEqual(
            client.post(
                "/api/auth/login",
                json={"email": "student@example.test", "password": "a-strong-test-password"},
            ).status_code,
            200,
        )
        self.assertTrue(client.get("/api/auth/me").json["authenticated"])

    def test_duplicate_and_invalid_signup_are_rejected(self):
        client = app.test_client()
        self.assertEqual(self.signup(client, "first@example.test").status_code, 201)
        self.assertEqual(self.signup(client, "first@example.test").status_code, 409)
        self.assertEqual(
            client.post(
                "/api/auth/signup",
                json={"name": "Student", "email": "not-an-email", "password": "short"},
            ).status_code,
            400,
        )

    def test_signup_rolls_back_user_when_seed_schema_is_unavailable(self):
        client = app.test_client()
        with patch("app.seed_data", side_effect=SQLAlchemyError("schema unavailable")):
            with patch("app.app.logger.exception"):
                response = self.signup(client, "rollback@example.test")
        self.assertEqual(response.status_code, 503)
        with app.app_context():
            self.assertIsNone(User.query.filter_by(email="rollback@example.test").first())

    def test_planner_records_and_mutations_are_user_scoped(self):
        first = app.test_client()
        second = app.test_client()
        self.signup(first, "first@example.test")
        self.signup(second, "second@example.test")

        assignment_response = first.post(
            "/api/assignments",
            json={"title": "Private assignment", "due_date": "2026-12-20"},
        )
        event_response = first.post(
            "/api/events",
            json={"title": "Private event", "event_date": "2026-12-21"},
        )
        class_response = first.post(
            "/api/classes",
            json={
                "subject": "Private class",
                "day": "Thursday",
                "start_time": "10:00",
                "end_time": "11:00",
            },
        )
        self.assertEqual(assignment_response.status_code, 201)
        self.assertEqual(event_response.status_code, 201)
        self.assertEqual(class_response.status_code, 201)

        assignment_id = assignment_response.json["id"]
        event_id = event_response.json["id"]
        self.assertNotIn(
            "Private assignment",
            [item["title"] for item in second.get("/api/assignments").json],
        )
        self.assertNotIn(
            "Private event",
            [item["title"] for item in second.get("/api/events").json],
        )
        self.assertNotIn(
            "Private class",
            [item["subject"] for item in second.get("/api/classes").json],
        )
        self.assertEqual(
            second.patch(f"/api/assignments/{assignment_id}", json={"title": "stolen"}).status_code,
            404,
        )
        self.assertEqual(
            second.delete(
                f"/api/assignments/{assignment_id}",
                headers={"Content-Type": "application/json"},
            ).status_code,
            404,
        )

        self.assertEqual(
            first.patch(f"/api/assignments/{assignment_id}", json={"status": "Completed"}).status_code,
            200,
        )
        self.assertEqual(
            first.get("/api/dashboard").json["completed_assignments"], 1,
        )

    def test_ai_chat_history_and_tools_use_authenticated_owner(self):
        first = app.test_client()
        second = app.test_client()
        self.signup(first, "first@example.test")
        self.signup(second, "second@example.test")
        with app.app_context():
            first_user = User.query.filter_by(email="first@example.test").one()
            second_user = User.query.filter_by(email="second@example.test").one()
            run_tool(
                "add_assignment",
                {
                    "title": "Tool-owned assignment",
                    "subject": "Testing",
                    "due_date": "2026-12-22",
                    "user_id": second_user.id,
                },
                first_user.id,
            )
            tool_item = Assignment.query.filter_by(title="Tool-owned assignment").one()
            self.assertEqual(tool_item.user_id, first_user.id)
            first_context = json.loads(
                get_assignment_database_context("show my assignments", first_user.id)
            )
            second_context = json.loads(
                get_assignment_database_context("show my assignments", second_user.id)
            )
            self.assertIn("Tool-owned assignment", [item["title"] for item in first_context["assignments"]])
            self.assertNotIn("Tool-owned assignment", [item["title"] for item in second_context["assignments"]])
            db.session.add(
                AgentLog(
                    user_id=first_user.id,
                    user_message="first private question",
                    agent_response="first private answer",
                    tool_name="groq",
                )
            )
            db.session.commit()

        response = SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(tool_calls=None, content="Mocked Groq reply"))]
        )
        with patch("app.Groq") as groq:
            groq.return_value.chat.completions.create.return_value = response
            chat_response = first.post("/api/agent/chat", json={"message": "Hello"})
        self.assertEqual(chat_response.status_code, 200)
        self.assertEqual(chat_response.json["reply"], "Mocked Groq reply")
        first_history = first.get("/api/agent/history").json
        second_history = second.get("/api/agent/history").json
        self.assertTrue(any(item["message"] == "first private question" for item in first_history))
        self.assertFalse(any(item["message"] == "first private question" for item in second_history))
        self.assertTrue(any(item["message"] == "Hello" for item in first_history))

    def test_migration_adds_nullable_ownership_without_changing_legacy_rows(self):
        with app.app_context():
            db.drop_all()
            with db.engine.begin() as connection:
                connection.exec_driver_sql(
                    "CREATE TABLE assignment (id INTEGER PRIMARY KEY, title VARCHAR(180) NOT NULL, "
                    "subject VARCHAR(100), description TEXT, due_date VARCHAR(30) NOT NULL, "
                    "priority VARCHAR(20), status VARCHAR(20), created_at DATETIME)"
                )
                connection.exec_driver_sql(
                    "CREATE TABLE class_session (id INTEGER PRIMARY KEY, subject VARCHAR(120) NOT NULL, "
                    "teacher VARCHAR(120), room VARCHAR(50), day VARCHAR(20) NOT NULL, "
                    "start_time VARCHAR(10) NOT NULL, end_time VARCHAR(10) NOT NULL)"
                )
                connection.exec_driver_sql(
                    "CREATE TABLE calendar_event (id INTEGER PRIMARY KEY, title VARCHAR(180) NOT NULL, "
                    "event_date VARCHAR(30) NOT NULL, event_time VARCHAR(10), category VARCHAR(40), "
                    "notes TEXT, created_at DATETIME)"
                )
                connection.exec_driver_sql(
                    "CREATE TABLE agent_log (id INTEGER PRIMARY KEY, user_message TEXT NOT NULL, "
                    "agent_response TEXT NOT NULL, tool_name VARCHAR(100), created_at DATETIME)"
                )
                connection.exec_driver_sql(
                    "INSERT INTO assignment (id, title, due_date) VALUES (41, 'Legacy row', '2026-12-30')"
                )

            migrate()
            legacy = db.session.get(Assignment, 41)
            self.assertIsNotNone(legacy)
            self.assertEqual(legacy.title, "Legacy row")
            self.assertIsNone(legacy.user_id)
            self.assertEqual(Assignment.query.filter_by(user_id=None).count(), 1)


if __name__ == "__main__":
    unittest.main()
