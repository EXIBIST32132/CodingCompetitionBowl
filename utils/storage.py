import sqlite3
from pathlib import Path
from typing import Optional


def get_db_connection(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path: Path):
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = get_db_connection(db_path)
    cur = conn.cursor()
    cur.executescript(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            language_preference TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS submissions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            problem_id INTEGER NOT NULL,
            language TEXT NOT NULL,
            code TEXT NOT NULL,
            passed_tests INTEGER DEFAULT 0,
            total_tests INTEGER DEFAULT 0,
            timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS scores (
            user_id INTEGER PRIMARY KEY,
            total_score INTEGER DEFAULT 0,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );

        CREATE INDEX IF NOT EXISTS idx_submissions_user_problem
            ON submissions(user_id, problem_id);
        """
    )
    conn.commit()
    conn.close()


def create_or_get_user(db_path: Path, name: str, language: str = ""):
    conn = get_db_connection(db_path)
    cur = conn.execute("SELECT * FROM users WHERE name = ?", (name,))
    row = cur.fetchone()
    if row:
        if language:
            conn.execute(
                "UPDATE users SET language_preference = ? WHERE id = ?",
                (language, row["id"]),
            )
            conn.commit()
        result = conn.execute("SELECT * FROM users WHERE id = ?", (row["id"],)).fetchone()
        conn.close()
        return dict(result)

    cur = conn.execute(
        "INSERT INTO users (name, language_preference) VALUES (?, ?)",
        (name, language),
    )
    user_id = cur.lastrowid
    conn.commit()
    user_row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    conn.close()
    return dict(user_row)


def record_submission(
    db_path: Path,
    user_id: int,
    problem_id: int,
    language: str,
    code: str,
    passed_tests: int,
    total_tests: int,
    timestamp: str,
) -> int:
    conn = get_db_connection(db_path)
    cur = conn.execute(
        """
        INSERT INTO submissions (user_id, problem_id, language, code, passed_tests, total_tests, timestamp)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (user_id, problem_id, language, code, passed_tests, total_tests, timestamp),
    )
    conn.commit()
    submission_id = cur.lastrowid
    conn.close()
    return submission_id


def update_user_score(db_path: Path, user_id: int):
    conn = get_db_connection(db_path)
    cur = conn.execute(
        """
        SELECT problem_id, MAX(passed_tests) AS best
        FROM submissions
        WHERE user_id = ?
        GROUP BY problem_id
        """,
        (user_id,),
    )
    total_score = sum(row["best"] or 0 for row in cur.fetchall())
    conn.execute(
        """
        INSERT INTO scores (user_id, total_score)
        VALUES (?, ?)
        ON CONFLICT(user_id) DO UPDATE SET total_score=excluded.total_score
        """,
        (user_id, total_score),
    )
    conn.commit()
    conn.close()


def get_leaderboard(db_path: Path):
    conn = get_db_connection(db_path)
    cur = conn.execute(
        """
        SELECT users.id, users.name, scores.total_score
        FROM users
        LEFT JOIN scores ON users.id = scores.user_id
        ORDER BY COALESCE(scores.total_score, 0) DESC, users.created_at ASC
        """
    )
    data = [
        {
            "user_id": row["id"],
            "name": row["name"],
            "total_score": row["total_score"] or 0,
        }
        for row in cur.fetchall()
    ]
    conn.close()
    return data


def get_recent_submissions(db_path: Path, limit: int = 50):
    conn = get_db_connection(db_path)
    cur = conn.execute(
        """
        SELECT submissions.*, users.name
        FROM submissions
        JOIN users ON users.id = submissions.user_id
        ORDER BY datetime(submissions.timestamp) DESC
        LIMIT ?
        """,
        (limit,),
    )
    submissions = [dict(row) for row in cur.fetchall()]
    conn.close()
    return submissions


def get_latest_user_submission(
    db_path: Path, user_id: int, problem_id: Optional[int] = None
):
    query = """
        SELECT *
        FROM submissions
        WHERE user_id = ?
    """
    params = [user_id]
    if problem_id is not None:
        query += " AND problem_id = ?"
        params.append(problem_id)
    query += " ORDER BY datetime(timestamp) DESC LIMIT 1"

    conn = get_db_connection(db_path)
    cur = conn.execute(query, tuple(params))
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None


def reset_scores_and_submissions(db_path: Path):
    conn = get_db_connection(db_path)
    conn.execute("DELETE FROM submissions")
    conn.execute("DELETE FROM scores")
    conn.commit()
    conn.close()
