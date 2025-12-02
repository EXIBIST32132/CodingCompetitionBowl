import os
import secrets
from datetime import datetime, timedelta
from threading import Lock
import time
from pathlib import Path

from flask import Flask, jsonify, render_template, request, session
from flask_socketio import SocketIO, join_room

from utils.grader import grade_submission, list_problems, load_problem
from utils.storage import (
    create_or_get_user,
    get_db_connection,
    get_leaderboard,
    get_recent_submissions,
    init_db,
    record_submission,
    update_user_score,
    get_latest_user_submission,
    reset_scores_and_submissions,
)

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "database.db"

SECRET_KEY = os.environ.get("SECRET_KEY", "dev_secret_key_change_me")
HOST_PASSWORD = os.environ.get("HOST_PASSWORD", "hostpass")

app = Flask(__name__, static_folder="static", template_folder="templates")
app.config["SECRET_KEY"] = SECRET_KEY
app.config["SESSION_COOKIE_NAME"] = "cc_host_session"

socketio = SocketIO(app, cors_allowed_origins="*")
init_db(DB_PATH)

timer_lock = Lock()
timer_state = {
    "status": "stopped",
    "remaining": 0,
    "duration": 0,
    "version": 0,
    "ends_at": None,
}
timer_task = None
host_tokens = set()


def _datetime_now() -> str:
    return datetime.utcnow().isoformat()


def _monotonic_now() -> float:
    return time.monotonic()


def _sync_remaining_locked(now: float = None):
    """Update remaining time based on target end and stop the timer when it hits zero."""
    now = now or _monotonic_now()
    if timer_state["status"] == "running" and timer_state.get("ends_at"):
        remaining = max(0, int(round(timer_state["ends_at"] - now)))
        timer_state["remaining"] = remaining
        if remaining <= 0:
            timer_state["status"] = "stopped"
            timer_state["ends_at"] = None


def _public_timer_state(state: dict = None) -> dict:
    """Hide internal-only fields like ends_at from responses/events."""
    base = dict(state or timer_state)
    base.pop("ends_at", None)
    return base


@app.route("/")
def index():
    return render_template("index.html")


def _is_host(token: str = None, password: str = None) -> bool:
    # Allow callers to pass a (token, password) tuple (e.g., from _extract_token())
    if isinstance(token, (tuple, list)):
        tuple_token = token[0] if len(token) > 0 else None
        tuple_password = token[1] if len(token) > 1 else None
        token = tuple_token
        if password is None:
            password = tuple_password
    if session.get("host_authenticated"):
        return True
    if token and token in host_tokens:
        return True
    if password and HOST_PASSWORD and password == HOST_PASSWORD:
        return True
    return False


def _extract_token():
    token = (
        request.headers.get("X-Host-Token")
        or request.args.get("token")
        or (request.get_json(silent=True) or {}).get("token")
    )
    pwd = (
        request.headers.get("X-Host-Password")
        or request.args.get("password")
        or (request.get_json(silent=True) or {}).get("password")
    )
    return token, pwd


@app.route("/host")
def host():
    return render_template(
        "host.html",
        host_password_set=bool(HOST_PASSWORD),
    )


@app.route("/api/register", methods=["POST"])
def register():
    payload = request.get_json(force=True)
    name = (payload.get("name") or "").strip()
    language = (payload.get("language") or "").strip()
    if not name:
        return jsonify({"error": "Name is required"}), 400

    user = create_or_get_user(DB_PATH, name=name, language=language)
    session["user_id"] = user["id"]
    return jsonify({"user": user})


@app.route("/api/problems")
def problems():
    return jsonify({"problems": list_problems()})


@app.route("/api/problem/<int:problem_id>")
def problem_detail(problem_id: int):
    try:
        problem = load_problem(problem_id)
    except FileNotFoundError:
        return jsonify({"error": "Problem not found"}), 404
    return jsonify({"problem": problem})


@app.route("/api/submit", methods=["POST"])
def submit():
    payload = request.get_json(force=True)
    try:
        user_id = int(payload.get("user_id"))
        problem_id = int(payload.get("problem_id"))
    except (TypeError, ValueError):
        return jsonify({"error": "Invalid user or problem id"}), 400
    language = payload.get("language")
    code = payload.get("code") or ""

    if not all([user_id, problem_id, language, code.strip()]):
        return jsonify({"error": "Missing submission data"}), 400

    timer_snapshot = get_timer_snapshot()
    if timer_snapshot.get("status") != "running":
        return jsonify({"error": "Submissions are paused by host"}), 403

    try:
        problem = load_problem(int(problem_id))
    except FileNotFoundError:
        return jsonify({"error": "Problem not found"}), 404

    grade_result = grade_submission(language, code, problem)
    if grade_result.get("error"):
        return jsonify({"error": grade_result["error"]}), 400
    passed_tests = grade_result["passed"]
    total_tests = grade_result["total"]
    timestamp = _datetime_now()

    submission_id = record_submission(
        DB_PATH,
        user_id=user_id,
        problem_id=problem_id,
        language=language,
        code=code,
        passed_tests=passed_tests,
        total_tests=total_tests,
        timestamp=timestamp,
    )

    update_user_score(DB_PATH, user_id)

    socketio.emit(
        "submission_scored",
        {
            "user_id": user_id,
            "problem_id": problem_id,
            "passed_tests": passed_tests,
            "total_tests": total_tests,
            "timestamp": timestamp,
            "submission_id": submission_id,
        },
        room=f"user_{user_id}",
    )

    socketio.emit(
        "scoreboard_update", {"leaderboard": get_leaderboard(DB_PATH)}, room="hosts"
    )

    socketio.emit(
        "submission_logged",
        {"submission": get_submission_payload(DB_PATH, submission_id)},
        room="hosts",
    )

    return jsonify(
        {
            "result": grade_result,
            "submission_id": submission_id,
            "passed_tests": passed_tests,
            "total_tests": total_tests,
        }
    )


def get_timer_snapshot():
    with timer_lock:
        _sync_remaining_locked()
        return _public_timer_state()


def broadcast_timer():
    socketio.emit("timer_update", {"timer": get_timer_snapshot()})


def start_timer(duration_seconds: int):
    global timer_task
    with timer_lock:
        _sync_remaining_locked()
        target_duration = duration_seconds
        if target_duration is None or target_duration <= 0:
            target_duration = timer_state.get("remaining") or timer_state.get("duration")
        if not target_duration or target_duration <= 0:
            return False
        target_duration = int(target_duration)

        timer_state["status"] = "running"
        timer_state["duration"] = target_duration
        timer_state["remaining"] = target_duration
        timer_state["ends_at"] = _monotonic_now() + target_duration
        timer_state["version"] += 1
        current_version = timer_state["version"]
        should_start_task = not timer_task or not timer_task.is_alive()
    broadcast_timer()
    if should_start_task:
        timer_task = socketio.start_background_task(timer_loop, current_version)
    return True


def pause_timer():
    with timer_lock:
        _sync_remaining_locked()
        timer_state["status"] = "paused"
        timer_state["ends_at"] = None
    broadcast_timer()


def stop_timer():
    with timer_lock:
        timer_state["status"] = "stopped"
        timer_state["remaining"] = 0
        timer_state["ends_at"] = None
    broadcast_timer()


def timer_loop(version: int):
    while True:
        socketio.sleep(1)
        with timer_lock:
            if version != timer_state["version"]:
                break
            _sync_remaining_locked()
            current = _public_timer_state()
            status = timer_state["status"]
        socketio.emit("timer_update", {"timer": current})
        if status != "running":
            break


def get_submission_payload(db_path: Path, submission_id: int):
    conn = get_db_connection(db_path)
    cur = conn.execute(
        """
        SELECT submissions.*, users.name
        FROM submissions
        JOIN users ON users.id = submissions.user_id
        WHERE submissions.id = ?
        """,
        (submission_id,),
    )
    row = cur.fetchone()
    conn.close()
    if not row:
        return None
    return dict(row)


@app.route("/api/user/<int:user_id>/last_submission")
def last_submission(user_id: int):
    problem_id = request.args.get("problem_id", type=int)
    submission = get_latest_user_submission(DB_PATH, user_id, problem_id)
    if not submission:
        return jsonify({"submission": None})
    return jsonify({"submission": submission})


@app.route("/api/host/login", methods=["POST"])
def host_login():
    payload = request.get_json(force=True)
    password = payload.get("password")
    if not HOST_PASSWORD:
        return jsonify({"error": "Host password not configured"}), 500
    if password != HOST_PASSWORD:
        return jsonify({"error": "Invalid password"}), 403
    session["host_authenticated"] = True
    token = secrets.token_hex(16)
    host_tokens.add(token)
    return jsonify({"ok": True, "token": token})


@app.route("/api/host/leaderboard")
def host_leaderboard():
    if not _is_host(*_extract_token()):
        return jsonify({"error": "Unauthorized"}), 403
    return jsonify({"leaderboard": get_leaderboard(DB_PATH)})


@app.route("/api/host/submissions")
def host_submissions():
    if not _is_host(*_extract_token()):
        return jsonify({"error": "Unauthorized"}), 403
    return jsonify({"submissions": get_recent_submissions(DB_PATH, limit=50)})


@app.route("/api/host/submission/<int:submission_id>")
def host_submission_detail(submission_id: int):
    if not _is_host(*_extract_token()):
        return jsonify({"error": "Unauthorized"}), 403
    payload = get_submission_payload(DB_PATH, submission_id)
    if not payload:
        return jsonify({"error": "Not found"}), 404
    return jsonify({"submission": payload})


@app.route("/api/host/reset", methods=["POST"])
def host_reset():
    if not _is_host(*_extract_token()):
        return jsonify({"error": "Unauthorized"}), 403
    reset_scores_and_submissions(DB_PATH)
    socketio.emit(
        "scoreboard_update", {"leaderboard": get_leaderboard(DB_PATH)}, room="hosts"
    )
    return jsonify({"ok": True})


@app.route("/api/timer")
def timer_status():
    return jsonify({"timer": get_timer_snapshot()})


@app.route("/api/host/timer", methods=["POST"])
def host_timer_control():
    if not _is_host(*_extract_token()):
        return jsonify({"error": "Unauthorized"}), 403
    payload = request.get_json(force=True)
    action = (payload.get("action") or "").lower()
    duration = payload.get("duration_seconds") or payload.get("duration")
    try:
        duration = int(duration) if duration is not None else None
    except (TypeError, ValueError):
        duration = None

    if action == "start":
        if not start_timer(duration):
            return jsonify({"error": "Duration required"}), 400
    elif action == "pause":
        pause_timer()
    elif action in ("stop", "reset"):
        stop_timer()
    else:
        return jsonify({"error": "Unknown action"}), 400

    return jsonify({"timer": get_timer_snapshot()})


@socketio.on("register_user")
def register_user_socket(data):
    user_id = data.get("user_id")
    if user_id:
        join_room(f"user_{user_id}")
    socketio.emit("timer_update", {"timer": get_timer_snapshot()}, room=request.sid)


@socketio.on("register_host")
def register_host_socket(data=None):
    token = None
    if data and isinstance(data, dict):
        token = data.get("token")
    if request.args:
        token = request.args.get("token") or token
    if _is_host(token):
        join_room("hosts")
        socketio.emit(
            "scoreboard_update",
            {"leaderboard": get_leaderboard(DB_PATH)},
            room="hosts",
        )
        socketio.emit("timer_update", {"timer": get_timer_snapshot()}, room="hosts")


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5005))
    socketio.run(app, host="0.0.0.0", port=port, allow_unsafe_werkzeug=True)
