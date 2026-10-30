
from flask import Flask, jsonify, request, send_from_directory
import sqlite3
import os
from datetime import datetime, timedelta, timezone

app = Flask(__name__)

DB_NAME = os.environ.get("DB_PATH", "recallx.db")


def get_db():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn


def initialize_db():
    conn = get_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS cards (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            question TEXT NOT NULL,
            answer TEXT NOT NULL,
            repetitions INTEGER DEFAULT 0,
            strength INTEGER DEFAULT 30,
            next_review TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()


initialize_db()


# Serve frontend files from the root directory
@app.route("/")
def home():
    return send_from_directory(".", "index.html")


@app.route("/style.css")
def css():
    return send_from_directory(".", "style.css")


@app.route("/script.js")
def javascript():
    return send_from_directory(".", "script.js")


@app.route("/api/cards", methods=["GET"])
def get_cards():
    conn = get_db()
    cards = conn.execute(
        "SELECT * FROM cards ORDER BY id DESC"
    ).fetchall()
    conn.close()
    return jsonify([dict(card) for card in cards])


@app.route("/api/cards", methods=["POST"])
def add_card():
    data = request.get_json(silent=True) or {}

    question = data.get("question", "").strip()
    answer = data.get("answer", "").strip()

    if not question or not answer:
        return jsonify({"error": "Both fields are required"}), 400

    now = datetime.now(timezone.utc).isoformat()

    conn = get_db()
    conn.execute("""
        INSERT INTO cards
        (question, answer, next_review, created_at)
        VALUES (?, ?, ?, ?)
    """, (question, answer, now, now))
    conn.commit()
    conn.close()

    return jsonify({"message": "Card added successfully"}), 201


@app.route("/api/study")
def study():
    now = datetime.now(timezone.utc).isoformat()

    conn = get_db()
    cards = conn.execute("""
        SELECT * FROM cards
        WHERE next_review <= ?
        ORDER BY next_review ASC
    """, (now,)).fetchall()
    conn.close()

    return jsonify([dict(card) for card in cards])


@app.route("/api/review/<int:card_id>", methods=["POST"])
def review(card_id):
    data = request.get_json(silent=True) or {}
    rating = data.get("rating")

    if rating not in ["easy", "medium", "hard"]:
        return jsonify({"error": "Invalid rating"}), 400

    conn = get_db()
    card = conn.execute(
        "SELECT * FROM cards WHERE id = ?", (card_id,)
    ).fetchone()

    if not card:
        conn.close()
        return jsonify({"error": "Card not found"}), 404

    repetitions = card["repetitions"]
    strength = card["strength"]

    if rating == "easy":
        repetitions += 1
        strength = min(100, strength + 20)
        delay = timedelta(days=3 if repetitions == 1 else 7 * repetitions)

    elif rating == "medium":
        repetitions += 1
        strength = min(100, strength + 10)
        delay = timedelta(days=1)

    else:
        repetitions = 0
        strength = max(10, strength - 15)
        delay = timedelta(minutes=10)

    next_review = (
        datetime.now(timezone.utc) + delay
    ).isoformat()

    conn.execute("""
        UPDATE cards
        SET repetitions = ?, strength = ?, next_review = ?
        WHERE id = ?
    """, (repetitions, strength, next_review, card_id))

    conn.commit()
    conn.close()

    return jsonify({
        "message": "Review saved",
        "strength": strength,
        "next_review": next_review
    })


@app.route("/api/stats")
def stats():
    now = datetime.now(timezone.utc).isoformat()

    conn = get_db()

    total = conn.execute(
        "SELECT COUNT(*) FROM cards"
    ).fetchone()[0]

    due = conn.execute("""
        SELECT COUNT(*) FROM cards WHERE next_review <= ?
    """, (now,)).fetchone()[0]

    learned = conn.execute("""
        SELECT COUNT(*) FROM cards WHERE repetitions >= 2
    """).fetchone()[0]

    average = conn.execute(
        "SELECT AVG(strength) FROM cards"
    ).fetchone()[0]

    conn.close()

    return jsonify({
        "total": total,
        "due": due,
        "learned": learned,
        "strength": round(average or 0)
    })


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 5000)),
        debug=False
    )
