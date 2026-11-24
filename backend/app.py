import json
import os
import time
import re
from functools import wraps
from datetime import datetime, date, timezone
from dotenv import load_dotenv
from flask import Flask, g, jsonify, request, session
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from google.genai import types
from groq import Groq
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from werkzeug.security import check_password_hash, generate_password_hash

load_dotenv()
app = Flask(__name__)
secret_key = os.getenv("SECRET_KEY", "")
if len(secret_key) < 32:
    raise RuntimeError("Configure SECRET_KEY with at least 32 random characters before starting Flask.")
app.config["SECRET_KEY"] = secret_key
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SESSION_COOKIE_SECURE"] = os.getenv("SESSION_COOKIE_SECURE", "0").lower() in ("1", "true", "yes")
db_url = os.getenv("DATABASE_URL", "sqlite:///studentdesk.db")
app.config["SQLALCHEMY_DATABASE_URI"] = db_url
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db = SQLAlchemy(app)
CORS(app, resources={r"/api/*": {"origins": os.getenv("FRONTEND_ORIGIN", "http://localhost:5173")}}, supports_credentials=True)

def utc_now_naive():
    return datetime.now(timezone.utc).replace(tzinfo=None)

class User(db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(255), nullable=False, unique=True, index=True)
    password_hash = db.Column(db.String(256), nullable=False)
    created_at = db.Column(db.DateTime, default=utc_now_naive, nullable=False)

class Assignment(db.Model):
    __table_args__ = (db.Index("ix_assignment_user_id", "user_id"),)
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    title = db.Column(db.String(180), nullable=False)
    subject = db.Column(db.String(100), default="General")
    description = db.Column(db.Text, default="")
    due_date = db.Column(db.String(30), nullable=False)
    priority = db.Column(db.String(20), default="Medium")
    status = db.Column(db.String(20), default="Pending")
    created_at = db.Column(db.DateTime, default=utc_now_naive)

class ClassSession(db.Model):
    __table_args__ = (db.Index("ix_class_session_user_id", "user_id"),)
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    subject = db.Column(db.String(120), nullable=False)
    teacher = db.Column(db.String(120), default="")
    room = db.Column(db.String(50), default="")
    day = db.Column(db.String(20), nullable=False)
    start_time = db.Column(db.String(10), nullable=False)
    end_time = db.Column(db.String(10), nullable=False)

class CalendarEvent(db.Model):
    __table_args__ = (db.Index("ix_calendar_event_user_id", "user_id"),)
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    title = db.Column(db.String(180), nullable=False)
    event_date = db.Column(db.String(30), nullable=False)
    event_time = db.Column(db.String(10), default="09:00")
    category = db.Column(db.String(40), default="Event")
    notes = db.Column(db.Text, default="")
    created_at = db.Column(db.DateTime, default=utc_now_naive)

class AgentLog(db.Model):
    __table_args__ = (db.Index("ix_agent_log_user_id", "user_id"),)
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    user_message = db.Column(db.Text, nullable=False)
    agent_response = db.Column(db.Text, nullable=False)
    tool_name = db.Column(db.String(100), default="")
    created_at = db.Column(db.DateTime, default=utc_now_naive)

def current_user_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        user_id = session.get("user_id")
        user = db.session.get(User, user_id) if user_id else None
        if user is None:
            session.clear()
            return jsonify({"error": "Authentication required."}), 401
        g.current_user = user
        return view(*args, **kwargs)
    return wrapped

def user_dict(user):
    return {"id": user.id, "name": user.name, "email": user.email}

def assignment_dict(x):
    return {"id": x.id, "title": x.title, "subject": x.subject, "description": x.description,
            "due_date": x.due_date, "priority": x.priority, "status": x.status}

def class_dict(x):
    return {"id": x.id, "subject": x.subject, "teacher": x.teacher, "room": x.room,
            "day": x.day, "start_time": x.start_time, "end_time": x.end_time}

def event_dict(x):
    return {"id": x.id, "title": x.title, "event_date": x.event_date, "event_time": x.event_time,
            "category": x.category, "notes": x.notes}

def seed_data(user_id):
    if ClassSession.query.filter_by(user_id=user_id).count() == 0:
        samples = [
            ClassSession(user_id=user_id, subject="Database Systems", teacher="Course Instructor", room="Room 204", day="Monday", start_time="09:00", end_time="10:30"),
            ClassSession(user_id=user_id, subject="Computer Networks", teacher="Course Instructor", room="Room 105", day="Tuesday", start_time="11:00", end_time="12:30"),
            ClassSession(user_id=user_id, subject="Artificial Intelligence", teacher="Course Instructor", room="Lab 3", day="Wednesday", start_time="13:00", end_time="14:30"),
        ]
        db.session.add_all(samples)
    if Assignment.query.filter_by(user_id=user_id).count() == 0:
        db.session.add(Assignment(user_id=user_id, title="Cloud Infrastructure Report", subject="System & Network Administration",
                                  description="Document cloud, network, Linux, AI, database and security configuration.",
                                  due_date="2026-12-18", priority="High", status="In Progress"))
@app.before_request
def require_json_for_api_writes():
    if request.path.startswith("/api/") and request.method in {"POST", "PUT", "PATCH", "DELETE"} and not request.is_json:
        return jsonify({"error": "Requests that change data must use application/json."}), 415

@app.post("/api/auth/signup")
def signup():
    data = request.get_json(silent=True) or {}
    name = str(data.get("name") or "").strip()
    email = str(data.get("email") or "").strip().lower()
    password = data.get("password")
    if not name or len(name) > 120 or not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
        return jsonify({"error": "Enter a valid name and email address."}), 400
    if not isinstance(password, str) or len(password) < 8 or len(password) > 128:
        return jsonify({"error": "Password must be between 8 and 128 characters."}), 400

    user = User(name=name, email=email, password_hash=generate_password_hash(password))
    db.session.add(user)
    try:
        db.session.flush()
        seed_data(user.id)
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return jsonify({"error": "An account with that email already exists."}), 409
    except SQLAlchemyError:
        db.session.rollback()
        app.logger.exception("Database error during signup.")
        return jsonify({
            "error": "Signup could not complete because the database is unavailable or needs its authentication migration."
        }), 503

    session.clear()
    session["user_id"] = user.id
    session.permanent = True
    return jsonify({"user": user_dict(user)}), 201

@app.post("/api/auth/login")
def login():
    data = request.get_json(silent=True) or {}
    email = str(data.get("email") or "").strip().lower()
    password = data.get("password")
    user = User.query.filter_by(email=email).first() if email else None
    if user is None or not isinstance(password, str) or not check_password_hash(user.password_hash, password):
        return jsonify({"error": "Email or password is incorrect."}), 401

    session.clear()
    session["user_id"] = user.id
    session.permanent = True
    return jsonify({"user": user_dict(user)})

@app.post("/api/auth/logout")
@current_user_required
def logout():
    session.clear()
    return jsonify({"message": "Logged out."})

@app.get("/api/auth/me")
def auth_me():
    user_id = session.get("user_id")
    user = db.session.get(User, user_id) if user_id else None
    if user is None:
        session.clear()
        return jsonify({"authenticated": False})
    return jsonify({"authenticated": True, "user": user_dict(user)})

@app.get("/api/health")
def health():
    return jsonify({"status": "ok", "service": "StudentDesk AI API"})

@app.get("/api/dashboard")
@current_user_required
def dashboard():
    today = date.today().isoformat()
    assignments = Assignment.query.filter_by(user_id=g.current_user.id).order_by(Assignment.due_date.asc()).all()
    events = CalendarEvent.query.filter_by(user_id=g.current_user.id).order_by(CalendarEvent.event_date.asc(), CalendarEvent.event_time.asc()).all()
    return jsonify({
        "total_assignments": len(assignments),
        "pending_assignments": sum(1 for a in assignments if a.status != "Completed"),
        "completed_assignments": sum(1 for a in assignments if a.status == "Completed"),
        "upcoming_events": sum(1 for e in events if e.event_date >= today),
        "assignments": [assignment_dict(a) for a in assignments[:5]],
        "events": [event_dict(e) for e in events[:5]]
    })

@app.route("/api/assignments", methods=["GET", "POST"])
@current_user_required
def assignments():
    if request.method == "GET":
        items = Assignment.query.filter_by(user_id=g.current_user.id).order_by(Assignment.due_date.asc()).all()
        return jsonify([assignment_dict(a) for a in items])
    data = request.get_json(force=True)
    if not data.get("title") or not data.get("due_date"):
        return jsonify({"error": "Title and due date are required."}), 400
    item = Assignment(user_id=g.current_user.id, title=data["title"], subject=data.get("subject", "General"),
                      description=data.get("description", ""), due_date=data["due_date"],
                      priority=data.get("priority", "Medium"), status=data.get("status", "Pending"))
    db.session.add(item); db.session.commit()
    return jsonify(assignment_dict(item)), 201

@app.patch("/api/assignments/<int:item_id>")
@current_user_required
def update_assignment(item_id):
    item = Assignment.query.filter_by(id=item_id, user_id=g.current_user.id).first()
    if not item: return jsonify({"error": "Assignment not found."}), 404
    data = request.get_json(force=True)
    for field in ["title", "subject", "description", "due_date", "priority", "status"]:
        if field in data: setattr(item, field, data[field])
    db.session.commit()
    return jsonify(assignment_dict(item))

@app.delete("/api/assignments/<int:item_id>")
@current_user_required
def delete_assignment(item_id):
    item = Assignment.query.filter_by(id=item_id, user_id=g.current_user.id).first()
    if not item: return jsonify({"error": "Assignment not found."}), 404
    db.session.delete(item); db.session.commit()
    return jsonify({"message": "Assignment deleted."})

@app.route("/api/classes", methods=["GET", "POST"])
@current_user_required
def classes():
    if request.method == "GET":
        items = ClassSession.query.filter_by(user_id=g.current_user.id).all()
        return jsonify([class_dict(c) for c in items])
    data = request.get_json(force=True)
    required = ["subject", "day", "start_time", "end_time"]
    if any(not data.get(k) for k in required):
        return jsonify({"error": "Subject, day and class times are required."}), 400
    item = ClassSession(user_id=g.current_user.id, subject=data["subject"], teacher=data.get("teacher", ""),
                        room=data.get("room", ""), day=data["day"],
                        start_time=data["start_time"], end_time=data["end_time"])
    db.session.add(item); db.session.commit()
    return jsonify(class_dict(item)), 201

@app.route("/api/events", methods=["GET", "POST"])
@current_user_required
def events():
    if request.method == "GET":
        items = CalendarEvent.query.filter_by(user_id=g.current_user.id).order_by(CalendarEvent.event_date.asc()).all()
        return jsonify([event_dict(e) for e in items])
    data = request.get_json(force=True)
    if not data.get("title") or not data.get("event_date"):
        return jsonify({"error": "Event title and date are required."}), 400
    item = CalendarEvent(user_id=g.current_user.id, title=data["title"], event_date=data["event_date"],
                         event_time=data.get("event_time", "09:00"),
                         category=data.get("category", "Event"), notes=data.get("notes", ""))
    db.session.add(item); db.session.commit()
    return jsonify(event_dict(item)), 201

@app.get("/api/agent/history")
@current_user_required
def agent_history():
    logs = AgentLog.query.filter_by(user_id=g.current_user.id).order_by(AgentLog.created_at.desc()).limit(20).all()
    return jsonify([{"id": x.id, "message": x.user_message, "response": x.agent_response,
                     "tool": x.tool_name, "created_at": x.created_at.isoformat()} for x in logs])

def is_temporary_gemini_error(error):
    error_text = str(error).lower()

    permanent_markers = (
        "api key",
        "api_key",
        "unauthenticated",
        "permission denied",
        "invalid api",
        "401",
        "403",
    )
    if any(marker in error_text for marker in permanent_markers):
        return False

    return any(marker in error_text for marker in (
        "429",
        "resource_exhausted",
        "rate limit",
        "503",
        "unavailable",
    ))

def generate_gemini_response(client, model, contents, config=None):
    retry_delays = (2, 4, 8)

    for attempt in range(len(retry_delays) + 1):
        try:
            return client.models.generate_content(
                model=model,
                contents=contents,
                config=config
            )
        except Exception as error:
            if attempt >= len(retry_delays) or not is_temporary_gemini_error(error):
                raise

            delay = retry_delays[attempt]
            print(
                "Gemini temporary error; retrying in "
                f"{delay} seconds ({attempt + 1}/{len(retry_delays)}): "
                f"{repr(error)}",
                flush=True,
            )
            time.sleep(delay)


@app.post("/api/agent/chat")
@current_user_required
def agent_chat():
    data = request.get_json(force=True)
    message = (data.get("message") or "").strip()
    user_id = g.current_user.id

    if not message:
        return jsonify({"error": "Please enter a message."}), 400

    api_key = os.getenv("GROQ_API_KEY", "").strip()

    if not api_key:
        return jsonify({
            "error": "Groq API key is missing. Add GROQ_API_KEY to backend/.env"
        }), 500

    try:
        client = Groq(api_key=api_key)

        model = os.getenv(
            "GROQ_MODEL",
            "llama-3.3-70b-versatile"
        ).strip()

        database_context = get_assignment_database_context(message, user_id)
        prompt = message

        if database_context is not None:
            prompt = (
                f"{message}\n\n"
                "Authoritative database lookup result. "
                "Use these records exactly and do not invent assignments:\n"
                f"{database_context}"
            )

        messages = [
            {
                "role": "system",
                "content": (
                    "You are the StudentDesk AI assistant. "
                    "Use list_assignments to retrieve actual assignments. "
                    "Use list_classes for timetable questions. "
                    "Use add_assignment to create assignments. "
                    "Use create_event to create calendar events. "
                    "Never invent database records. "
                    "Always report actual database tool results."
                )
            },
            {
                "role": "user",
                "content": prompt
            }
        ]

        tool_name = "groq"

        for _ in range(4):
            response = client.chat.completions.create(
                model=model,
                messages=messages,
                tools=TOOLS,
                tool_choice="auto",
                temperature=0.3
            )

            assistant_message = response.choices[0].message

            if not assistant_message.tool_calls:
                break

            messages.append(
                assistant_message.model_dump(exclude_none=True)
            )

            for tool_call in assistant_message.tool_calls:
                name = tool_call.function.name
                args = json.loads(tool_call.function.arguments or "{}")

                try:
                    tool_result = run_tool(name, args, user_id)
                except Exception as tool_error:
                    db.session.rollback()
                    tool_result = {
                        "error": f"Database tool failed: {str(tool_error)}"
                    }

                tool_name = name

                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": json.dumps(tool_result, default=str)
                })

        reply = (
            response.choices[0].message.content
            or "No response received from Groq."
        )

        log = AgentLog(
            user_id=user_id,
            user_message=message,
            agent_response=reply,
            tool_name=tool_name
        )

        try:
            db.session.add(log)
            db.session.commit()
        except Exception:
            db.session.rollback()
            return jsonify({
                "error": "Database error while saving chat history."
            }), 500

        return jsonify({
            "reply": reply,
            "response": reply,
            "tool": tool_name
        })

    except Exception as e:
        db.session.rollback()
        print("Groq Error:", repr(e), flush=True)

        error_text = str(e).lower()

        if "429" in error_text or "rate limit" in error_text:
            return jsonify({
                "error": "Groq is currently rate-limited. Please try again shortly."
            }), 429

        if "401" in error_text or "403" in error_text or "authentication" in error_text:
            return jsonify({
                "error": "Groq API authentication failed. Check GROQ_API_KEY."
            }), 401

        return jsonify({
            "error": "Groq API request failed. Please check backend terminal."
        }), 502
    
def tool_add_assignment(title, subject, due_date, user_id, priority="Medium", description=""):
    item = Assignment(user_id=user_id, title=title, subject=subject, due_date=due_date, priority=priority,
                      description=description, status="Pending")
    db.session.add(item); db.session.commit()
    return {"success": True, "assignment": assignment_dict(item)}

def tool_list_assignments(user_id, status="all"):
    items = Assignment.query.filter_by(user_id=user_id).order_by(Assignment.due_date.asc()).all()
    if status.lower() != "all":
        items = [a for a in items if a.status.lower() == status.lower()]
    return [assignment_dict(a) for a in items]

def tool_list_classes(user_id, day="all"):
    items = ClassSession.query.filter_by(user_id=user_id).all()
    if day.lower() != "all":
        items = [c for c in items if c.day.lower() == day.lower()]
    return [class_dict(c) for c in items]

def tool_create_event(title, event_date, user_id, event_time="09:00", category="Event", notes=""):
    item = CalendarEvent(user_id=user_id, title=title, event_date=event_date, event_time=event_time,
                         category=category, notes=notes)
    db.session.add(item); db.session.commit()
    return {"success": True, "event": event_dict(item)}

TOOLS = [
    {"type":"function","function":{"name":"add_assignment","description":"Create and save a student assignment in the database.",
     "parameters":{"type":"object","properties":{"title":{"type":"string"},"subject":{"type":"string"},"due_date":{"type":"string","description":"Date in YYYY-MM-DD format"},"priority":{"type":"string","enum":["Low","Medium","High"]},"description":{"type":"string"}},"required":["title","subject","due_date"]}}},
    {"type":"function","function":{"name":"list_assignments","description":"Retrieve assignments from the database.",
     "parameters":{"type":"object","properties":{"status":{"type":"string","description":"all, Pending, In Progress, or Completed"}}}}},
    {"type":"function","function":{"name":"list_classes","description":"Retrieve class timetable entries, optionally for a weekday.",
     "parameters":{"type":"object","properties":{"day":{"type":"string","description":"Weekday or all"}}}}},
    {"type":"function","function":{"name":"create_event","description":"Create a calendar event in the database.",
     "parameters":{"type":"object","properties":{"title":{"type":"string"},"event_date":{"type":"string","description":"Date in YYYY-MM-DD format"},"event_time":{"type":"string","description":"24-hour time HH:MM"},"category":{"type":"string"},"notes":{"type":"string"}},"required":["title","event_date"]}}}
]

def run_tool(name, args, user_id):
    scoped_args = {key: value for key, value in args.items() if key != "user_id"}
    if name == "add_assignment": return tool_add_assignment(user_id=user_id, **scoped_args)
    if name == "list_assignments": return tool_list_assignments(user_id=user_id, **scoped_args)
    if name == "list_classes": return tool_list_classes(user_id=user_id, **scoped_args)
    if name == "create_event": return tool_create_event(user_id=user_id, **scoped_args)
    return {"error": "Unknown tool"}

def build_gemini_tools():
    declarations = []
    for tool in TOOLS:
        declaration = tool["function"]
        declarations.append(types.FunctionDeclaration(
            name=declaration["name"],
            description=declaration["description"],
            parameters_json_schema=declaration["parameters"],
        ))
    return [types.Tool(function_declarations=declarations)]

def get_assignment_database_context(message, user_id):
    normalized = message.lower()
    if not any(word in normalized for word in (
        "assignment",
        "assignments",
        "task",
        "tasks",
        "homework",
        "deadline",
        "due",
    )):
        return None

    status = "all"
    if "pending" in normalized or "not completed" in normalized:
        status = "Pending"
    elif "completed" in normalized or "done" in normalized:
        status = "Completed"
    elif "in progress" in normalized:
        status = "In Progress"

    try:
        assignments = tool_list_assignments(user_id, status)
        return json.dumps({
            "database": "StudentDesk SQLAlchemy Assignment table",
            "filter": status,
            "count": len(assignments),
            "assignments": assignments,
        })
    except Exception:
        db.session.rollback()
        return json.dumps({
            "database_error": "Assignment lookup failed.",
        })



if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=os.getenv("FLASK_DEBUG", "0") == "1")
