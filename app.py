
from flask import Flask, request, jsonify, render_template_string
import sqlite3
from datetime import datetime, timedelta, timezone

app = Flask(__name__)

DATABASE = "flashcards.db"


# DATABASE CONNECTION
def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


# CREATE DATABASE
def init_db():
    conn = get_db()

    conn.execute("""
        CREATE TABLE IF NOT EXISTS cards (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            question TEXT NOT NULL,
            answer TEXT NOT NULL,
            interval_days REAL DEFAULT 0,
            due_at TEXT NOT NULL,
            reviews INTEGER DEFAULT 0
        )
    """)

    conn.commit()
    conn.close()


# FRONTEND HTML, CSS AND JAVASCRIPT
HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>StudySmart - Flashcards</title>

    <meta name="viewport" content="width=device-width, initial-scale=1">

    <style>
        * {
            box-sizing: border-box;
        }

        body {
            font-family: Arial, sans-serif;
            background: #f1f3f9;
            margin: 0;
            color: #222;
        }

        header {
            background: #5146c8;
            color: white;
            text-align: center;
            padding: 25px;
        }

        main {
            max-width: 850px;
            width: 92%;
            margin: 25px auto;
        }

        .stats {
            display: flex;
            gap: 15px;
            margin-bottom: 20px;
        }

        .stat-box {
            background: white;
            flex: 1;
            padding: 20px;
            text-align: center;
            border-radius: 10px;
        }

        .stat-box h2 {
            color: #5146c8;
        }

        .section {
            background: white;
            padding: 22px;
            margin-bottom: 20px;
            border-radius: 10px;
        }

        input, textarea {
            width: 100%;
            padding: 13px;
            margin: 8px 0;
            border: 1px solid #ccc;
            border-radius: 6px;
            font-size: 15px;
        }

        textarea {
            height: 90px;
        }

        button {
            background: #5146c8;
            color: white;
            border: none;
            padding: 11px 16px;
            border-radius: 6px;
            cursor: pointer;
            margin: 5px 3px;
        }

        button:hover {
            opacity: 0.8;
        }

        .flashcard {
            background: #f5f4ff;
            border-left: 5px solid #5146c8;
            padding: 18px;
            margin-bottom: 15px;
            border-radius: 8px;
        }

        .answer {
            background: white;
            padding: 12px;
            margin-top: 10px;
            border-radius: 6px;
        }

        .again { background: #dc4545; }
        .hard { background: #e69525; }
        .good { background: #269b62; }
        .easy { background: #397bd5; }

        footer {
            text-align: center;
            padding: 20px;
            color: #777;
        }

        @media(max-width: 550px) {
            .stats {
                flex-direction: column;
            }
        }
    </style>
</head>

<body>

<header>
    <h1>📚 StudySmart</h1>
    <p>Smart Flashcard Learning System</p>
</header>

<main>

    <div class="stats">

        <div class="stat-box">
            <h2 id="totalCards">0</h2>
            <p>Total Flashcards</p>
        </div>

        <div class="stat-box">
            <h2 id="dueCards">0</h2>
            <p>Cards Due Today</p>
        </div>

    </div>

    <div class="section">

        <h2>Add New Flashcard</h2>

        <form id="cardForm">

            <input
                id="question"
                placeholder="Enter your question"
                required
            >

            <textarea
                id="answer"
                placeholder="Enter your answer"
                required
            ></textarea>

            <button type="submit">Add Flashcard</button>

        </form>

    </div>

    <div class="section">

        <h2>📖 Study Room</h2>

        <div id="flashcards"></div>

    </div>

</main>

<footer>
    StudySmart | Spaced Repetition System
</footer>


<script>

const form = document.getElementById("cardForm");
const flashcards = document.getElementById("flashcards");


// ADD FLASHCARD
form.addEventListener("submit", async function(e) {

    e.preventDefault();

    const question = document.getElementById("question").value;
    const answer = document.getElementById("answer").value;

    const response = await fetch("/api/cards", {
        method: "POST",
        headers: {
            "Content-Type": "application/json"
        },
        body: JSON.stringify({question, answer})
    });

    if (response.ok) {
        alert("Flashcard added successfully!");
        form.reset();
        loadCards();
    } else {
        alert("Could not add flashcard.");
    }

});


// LOAD FLASHCARDS
async function loadCards() {

    const response = await fetch("/api/cards");
    const cards = await response.json();

    const dueResponse = await fetch("/api/due");
    const dueCards = await dueResponse.json();

    document.getElementById("totalCards").textContent =
        cards.length;

    document.getElementById("dueCards").textContent =
        dueCards.length;

    flashcards.innerHTML = "";

    if (cards.length === 0) {
        flashcards.textContent =
            "No flashcards available. Add your first card!";
        return;
    }

    cards.forEach(card => {

        const box = document.createElement("div");
        box.className = "flashcard";

        const question = document.createElement("h3");
        question.textContent = "Q: " + card.question;

        const answer = document.createElement("div");
        answer.className = "answer";
        answer.hidden = true;
        answer.textContent = "Answer: " + card.answer;

        const reveal = document.createElement("button");
        reveal.textContent = "Show Answer";

        reveal.onclick = function() {
            answer.hidden = !answer.hidden;

            reveal.textContent = answer.hidden
                ? "Show Answer"
                : "Hide Answer";
        };

        box.appendChild(question);
        box.appendChild(reveal);
        box.appendChild(answer);

        if (dueCards.some(item => item.id === card.id)) {

            const status = document.createElement("p");
            status.textContent = "Due for Revision";
            status.style.color = "red";

            box.appendChild(status);

            const ratings = document.createElement("div");

            ["Again", "Hard", "Good", "Easy"].forEach(rating => {

                const btn = document.createElement("button");

                btn.textContent = rating;
                btn.className = rating.toLowerCase();

                btn.onclick = async function() {

                    if (answer.hidden) {
                        alert("Please show the answer first!");
                        return;
                    }

                    const result = await fetch(
                        "/api/review/" + card.id,
                        {
                            method: "POST",
                            headers: {
                                "Content-Type": "application/json"
                            },
                            body: JSON.stringify({rating})
                        }
                    );

                    if (result.ok) {
                        alert("Next revision scheduled!");
                        loadCards();
                    }
                };

                ratings.appendChild(btn);

            });

            box.appendChild(ratings);

        } else {

            const status = document.createElement("p");
            status.textContent = "Not Due Yet";
            status.style.color = "green";

            box.appendChild(status);

        }

        flashcards.appendChild(box);

    });

}

loadCards();

</script>

</body>
</html>
"""


# HOME PAGE
@app.route("/")
def home():
    return render_template_string(HTML)


# ADD FLASHCARD
@app.route("/api/cards", methods=["POST"])
def add_card():

    data = request.get_json()

    question = data.get("question", "").strip()
    answer = data.get("answer", "").strip()

    if not question or not answer:
        return jsonify({"error": "Both fields are required"}), 400

    now = datetime.now(timezone.utc).isoformat(timespec="seconds")

    conn = get_db()

    conn.execute("""
        INSERT INTO cards (question, answer, due_at)
        VALUES (?, ?, ?)
    """, (question, answer, now))

    conn.commit()
    conn.close()

    return jsonify({"message": "Card added successfully"})


# GET ALL FLASHCARDS
@app.route("/api/cards")
def get_cards():

    conn = get_db()

    cards = conn.execute(
        "SELECT * FROM cards ORDER BY id DESC"
    ).fetchall()

    conn.close()

    return jsonify([dict(card) for card in cards])


# GET DUE FLASHCARDS
@app.route("/api/due")
def get_due():

    now = datetime.now(timezone.utc).isoformat(timespec="seconds")

    conn = get_db()

    cards = conn.execute("""
        SELECT * FROM cards
        WHERE due_at <= ?
    """, (now,)).fetchall()

    conn.close()

    return jsonify([dict(card) for card in cards])


# REVIEW FLASHCARD
@app.route("/api/review/<int:card_id>", methods=["POST"])
def review_card(card_id):

    data = request.get_json()
    rating = data.get("rating")

    if rating not in ["Again", "Hard", "Good", "Easy"]:
        return jsonify({"error": "Invalid rating"}), 400

    conn = get_db()

    card = conn.execute(
        "SELECT * FROM cards WHERE id = ?",
        (card_id,)
    ).fetchone()

    if card is None:
        conn.close()
        return jsonify({"error": "Card not found"}), 404

    interval = card["interval_days"]

    if rating == "Again":
        interval = 1 / 1440

    elif rating == "Hard":
        interval = max(1, interval * 1.2)

    elif rating == "Good":
        interval = 1 if interval == 0 else interval * 2

    elif rating == "Easy":
        interval = 4 if interval == 0 else interval * 2.5

    next_review = (
        datetime.now(timezone.utc)
        + timedelta(days=interval)
    ).isoformat(timespec="seconds")

    conn.execute("""
        UPDATE cards
        SET interval_days = ?,
            due_at = ?,
            reviews = reviews + 1
        WHERE id = ?
    """, (interval, next_review, card_id))

    conn.commit()
    conn.close()

    return jsonify({
        "message": "Review saved successfully",
        "next_review_days": round(interval, 4)
    })


# START APPLICATION
init_db()

if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=5000,
        debug=True
    )
