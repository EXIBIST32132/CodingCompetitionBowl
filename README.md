# CodingCompetitionBowl

LAN-friendly coding competition platform with a host dashboard, real-time scoreboard, and in-browser editor. Problems live in JSON files, and submissions are graded automatically for Python, Java, and C++.

## Features
- Live scoreboard and submission feed powered by Flask-SocketIO.
- Host dashboard to start/pause/stop the contest timer, reset scores, and inspect submitted code.
- Participant view with Monaco editor, problem browser, and local code persistence between reloads.
- Auto-grader that runs solutions against predefined tests; adds boilerplate imports/includes where needed.
- Problems defined as JSON in `problems/`, with method signatures to enable structured grading.

## Prerequisites
- Python 3.10+.
- `g++` and the Java toolchain (`javac`, `java`) available on PATH for C++/Java submissions.

## Setup
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Recommended for real use
export HOST_PASSWORD="choose-a-secret"
export SECRET_KEY="another-secret"   # Flask session key
# Optional: export PORT=5005

python app.py
```
Open http://localhost:5005/ for participants and http://localhost:5005/host for the host console.

## Using the app
- Participant flow: enter a name and language, pick a problem, write code, and submit. Submissions are only accepted while the host timer is running (the editor becomes read-only otherwise). Latest results are shown inline.
- Host flow: log in with `HOST_PASSWORD`, control the timer, view the live leaderboard, inspect recent submissions, and reset scores/submissions when needed.
- Data: SQLite database at `database.db` is created automatically; use the host reset button to clear scores and submissions.

## Problems
Problems live in `problems/*.json` with fields like:
```json
{
  "id": 1,
  "title": "Removed Names",
  "description": "...",
  "method_signatures": {
    "java": "public static int removedNames(List<String> draft, List<String> fin)",
    "python": "def removed_names(draft: list[str], fin: list[str]) -> int",
    "cpp": "int removedNames(const std::vector<std::string>& draft, const std::vector<std::string>& fin)"
  },
  "input_format": "...",
  "output_format": "...",
  "constraints": "...",
  "sample_tests": [{ "input": "...", "output": "...", "explanation": "..." }],
  "tests": [{ "input": "...", "output": "...", "hidden": false }]
}
```
`method_signatures` drive the pre-filled editor templates and structured grading harnesses; keep function names in sync across languages when adding new problems.

## Project layout
- `app.py` — Flask app, APIs, Socket.IO events, timer, and session handling.
- `utils/` — grading logic and SQLite helpers.
- `judge/` — language runners for Python/Java/C++, with basic resource limits.
- `problems/` — contest problem set in JSON format.
- `templates/` — participant and host pages.
- `static/` — client-side JS and styling.

## Notes
- Change the default `HOST_PASSWORD` before running a real event.
- The code runner executes user code locally; avoid exposing this app to untrusted networks without stronger sandboxing.
