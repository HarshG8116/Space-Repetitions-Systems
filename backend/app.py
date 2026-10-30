
import os
import re
from datetime import datetime, timedelta, date
from functools import wraps

from flask import Flask, request, jsonify
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from flask_jwt_extended import (
    JWTManager,
    create_access_token,
    get_jwt_identity,
    jwt_required
)
from werkzeug.security import generate_password_hash, check_password_hash


# =========================================
# 1. APPLICATION CONFIGURATION
# =========================================

app = Flask(__name__)

database_url = os.environ.get("DATABASE_URL", "")

# Render may supply postgres://.
# SQLAlchemy uses the psycopg driver here.
if database_url.startswith("postgres://"):
    database_url = database_url.replace(
        "postgres://",
        "postgresql+psycopg://",
        1
    )
elif database_url.startswith("postgresql://"):
    database_url = database_url.replace(
        "postgresql://",
        "postgresql+psycopg://",
        1
    )

app.config["SQLALCHEMY_DATABASE_URI"] = database_url or (
    "sqlite:///recallx.db"
)

app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

app.config["JWT_SECRET_KEY"] = os.environ.get(
    "JWT_SECRET_KEY", "development-only-change-this-secret"
)

app.config["JWT_ACCESS_TOKEN_EXPIRES"] = timedelta(days=1)

db = SQLAlchemy(app)
jwt = JWTManager(app)

allowed_origins = os.environ.get("FRONTEND_ORIGIN", "*").split(",")

CORS(
    app,
    resources={r"/api/*": {"origins": allowed_origins}}
)


# =========================================
# 2. DATABASE MODELS
# =========================================

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    name = db.Column(db.String(100), nullable=False)

    email = db.Column(
        db.String(150),
        unique=True,
        nullable=False
    )

    password = db.Column(db.String(255), nullable=False)

    exam_date = db.Column(db.Date, nullable=True)

    cards = db.relationship(
        "Flashcard",
        backref="owner",
        cascade="all, delete-orphan"
    )


class Flashcard(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    user_id = db.Column(
        db.Integer,
        db.ForeignKey("user.id"),
        nullable=False
    )

    subject = db.Column(db.String(100), nullable=False)

    front = db.Column(db.Text, nullable=False)

    back = db.Column(db.Text, nullable=False)

    hint = db.Column(db.Text, default="")

    alternative = db.Column(db.Text, default="")

    ease_factor = db.Column(db.Float, default=2.5)

    interval_days = db.Column(db.Integer, default=0)

    repetitions = db.Column(db.Integer, default=0)

    due_at = db.Column(
        db.DateTime,
        default=datetime.utcnow
    )

    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow
    )


class ReviewLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    user_id = db.Column(
        db.Integer,
        db.ForeignKey("user.id"),
        nullable=False
    )

    card_id = db.Column(
        db.Integer,
        db.ForeignKey("flashcard.id"),
        nullable=False
    )

    rating = db.Column(db.Integer, nullable=False)

    reviewed_at = db.Column(
        db.DateTime,
        default=datetime.utcnow
    )


# =========================================
# 3. DATABASE INITIALIZATION
# =========================================

with app.app_context():
    db.create_all()


# =========================================
# 4. USER AUTHENTICATION
# =========================================

def current_user():
    user_id = int(get_jwt_identity())

    return db.session.get(User, user_id)


@app.route("/api/register", methods=["POST"])
def register():

    data = request.get_json() or {}

    name = data.get("name", "").strip()
    email = data.get("email", "").strip().lower()
    password = data.get("password", "")

    if not name or len(name) > 100:
        return jsonify(error="Enter a valid name."), 400

    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
        return jsonify(error="Enter a valid email."), 400

    if len(password) < 8:
        return jsonify(
            error="Password must contain at least 8 characters."
        ), 400

    if User.query.filter_by(email=email).first():
        return jsonify(error="Email already registered."), 409

    user = User(
        name=name,
        email=email,
        password=generate_password_hash(password)
    )

    db.session.add(user)
    db.session.commit()

    access_token = create_access_token(
        identity=str(user.id)
    )

    return jsonify(
        token=access_token,
        user={
            "id": user.id,
            "name": user.name,
            "email": user.email
        }
    ), 201


@app.route("/api/login", methods=["POST"])
def login():

    data = request.get_json() or {}

    email = data.get("email", "").strip().lower()
    password = data.get("password", "")

    user = User.query.filter_by(email=email).first()

    if not user or not check_password_hash(
        user.password, password
    ):
        return jsonify(error="Invalid email or password."), 401

    access_token = create_access_token(
        identity=str(user.id)
    )

    return jsonify(
        token=access_token,
        user={
            "id": user.id,
            "name": user.name,
            "email": user.email
        }
    )


@app.route("/api/me", methods=["GET"])
@jwt_required()
def me():

    user = current_user()

    if not user:
        return jsonify(error="User not found."), 404

    return jsonify(
        user={
            "id": user.id,
            "name": user.name,
            "email": user.email
        }
    )


# =========================================
# 5. FORGETTING RISK CALCULATOR
# =========================================

def calculate_risk(card):

    now = datetime.utcnow()

    days_overdue = max(
        0,
        (now - card.due_at).total_seconds() / 86400
    )

    # A card not yet due has lower immediate risk.
    if card.due_at > now:
        return max(
            0,
            min(100, int(15 + card.repetitions * 2))
        )

    risk = 40 + days_overdue * 7

    risk += max(0, 2.5 - card.ease_factor) * 15

    if card.repetitions == 0:
        risk += 20

    return min(100, int(risk))


# =========================================
# 6. CREATE FLASHCARD
# =========================================

@app.route("/api/cards", methods=["POST"])
@jwt_required()
def create_card():

    user = current_user()
    data = request.get_json() or {}

    subject = data.get("subject", "").strip()
    front = data.get("front", "").strip()
    back = data.get("back", "").strip()

    if not subject or not front or not back:
        return jsonify(
            error="Subject, question and answer are required."
        ), 400

    if any(len(data.get(field, "")) > 10000
           for field in ("front", "back", "hint", "alternative")):
        return jsonify(error="Flashcard text is too long."), 400

    card = Flashcard(
        user_id=user.id,
        subject=subject[:100],
        front=front,
        back=back,
        hint=data.get("hint", "").strip(),
        alternative=data.get("alternative", "").strip(),
        due_at=datetime.utcnow()
    )

    db.session.add(card)
    db.session.commit()

    return jsonify(
        message="Flashcard created successfully.",
        id=card.id
    ), 201


# =========================================
# 7. DISPLAY FLASHCARDS
# =========================================

def card_to_dict(card):

    return {
        "id": card.id,
        "subject": card.subject,
        "front": card.front,
        "back": card.back,
        "hint": card.hint,
        "alternative": card.alternative,
        "interval_days": card.interval_days,
        "repetitions": card.repetitions,
        "ease_factor": round(card.ease_factor, 2),
        "due_at": card.due_at.isoformat() + "Z",
        "risk": calculate_risk(card)
    }


@app.route("/api/cards", methods=["GET"])
@jwt_required()
def get_cards():

    user = current_user()

    cards = Flashcard.query.filter_by(
        user_id=user.id
    ).order_by(Flashcard.created_at.desc()).all()

    return jsonify(
        cards=[card_to_dict(card) for card in cards]
    )


# =========================================
# 8. DELETE FLASHCARD
# =========================================

@app.route("/api/cards/<int:card_id>", methods=["DELETE"])
@jwt_required()
def delete_card(card_id):

    user = current_user()

    card = Flashcard.query.filter_by(
        id=card_id,
        user_id=user.id
    ).first()

    if not card:
        return jsonify(error="Flashcard not found."), 404

    ReviewLog.query.filter_by(card_id=card.id).delete()

    db.session.delete(card)
    db.session.commit()

    return jsonify(message="Flashcard deleted.")


# =========================================
# 9. GET CARDS DUE FOR REVISION
# =========================================

@app.route("/api/review/due", methods=["GET"])
@jwt_required()
def get_due_cards():

    user = current_user()

    cards = Flashcard.query.filter(
        Flashcard.user_id == user.id,
        Flashcard.due_at <= datetime.utcnow()
    ).order_by(Flashcard.due_at.asc()).all()

    # Highest forgetting risk comes first.
    cards.sort(
        key=lambda card: calculate_risk(card),
        reverse=True
    )

    return jsonify(
        cards=[card_to_dict(card) for card in cards]
    )


# =========================================
# 10. SPACED REPETITION ALGORITHM
# =========================================

def update_schedule(card, rating):

    # Ratings:
    # 0 = Again
    # 1 = Hard
    # 2 = Good
    # 3 = Easy

    quality = {
        0: 0,
        1: 3,
        2: 4,
        3: 5
    }[rating]

    if rating == 0:

        card.repetitions = 0
        card.interval_days = 1

    elif rating == 1:

        card.interval_days = max(
            1,
            round(card.interval_days * 1.2)
        )

        card.repetitions += 1

    elif rating == 2:

        if card.repetitions == 0:
            card.interval_days = 1

        elif card.repetitions == 1:
            card.interval_days = 3

        else:
            card.interval_days = max(
                1,
                round(
                    card.interval_days * card.ease_factor
                )
            )

        card.repetitions += 1

    elif rating == 3:

        if card.repetitions == 0:
            card.interval_days = 4

        else:
            card.interval_days = max(
                1,
                round(
                    card.interval_days *
                    card.ease_factor * 1.3
                )
            )

        card.repetitions += 1

    # SM-2 style ease factor adjustment.
    card.ease_factor = max(
        1.3,
        card.ease_factor + (
            0.1 - (5 - quality) *
            (0.08 + (5 - quality) * 0.02)
        )
    )

    card.due_at = (
        datetime.utcnow() +
        timedelta(days=card.interval_days)
    )


# =========================================
# 11. SAVE REVIEW AND UPDATE SCHEDULE
# =========================================

@app.route("/api/review", methods=["POST"])
@jwt_required()
def review_card():

    user = current_user()
    data = request.get_json() or {}

    card_id = data.get("card_id")
    rating = data.get("rating")

    if (
        not isinstance(card_id, int)
        or isinstance(card_id, bool)
        or not isinstance(rating, int)
        or isinstance(rating, bool)
        or rating not in [0, 1, 2, 3]
    ):
        return jsonify(error="Invalid review data."), 400

    card = Flashcard.query.filter_by(
        id=card_id,
        user_id=user.id
    ).first()

    if not card:
        return jsonify(error="Flashcard not found."), 404

    log = ReviewLog(
        user_id=user.id,
        card_id=card.id,
        rating=rating
    )

    db.session.add(log)

    update_schedule(card, rating)

    db.session.commit()

    return jsonify(
        message="Review saved.",
        next_review=card.due_at.isoformat() + "Z",
        interval_days=card.interval_days,
        ease_factor=round(card.ease_factor, 2)
    )


# =========================================
# 12. STUDY STREAK CALCULATOR
# =========================================

def calculate_streak(user_id):

    rows = db.session.query(
        db.func.date(ReviewLog.reviewed_at)
    ).filter(
        ReviewLog.user_id == user_id
    ).distinct().all()

    study_dates = {
        row[0] for row in rows
    }

    today = date.today()

    # A streak remains active if the user studied
    # today or yesterday.
    if today not in study_dates:
        if today - timedelta(days=1) in study_dates:
            today -= timedelta(days=1)
        else:
            return 0

    streak = 0

    while today in study_dates:
        streak += 1
        today -= timedelta(days=1)

    return streak


# =========================================
# 13. SMART STUDY ADVISOR
# =========================================

def generate_advice(due_count, risk_cards, exam_date):

    recommendations = []

    if due_count > 0:
        recommendations.append(
            f"You have {due_count} cards due. "
            "Complete these revisions first."
        )
    else:
        recommendations.append(
            "Excellent! No cards are due. "
            "Create new flashcards to continue learning."
        )

    if risk_cards:
        recommendations.append(
            "Prioritize high-risk topics: " +
            ", ".join(
                card.subject for card in risk_cards[:3]
            )
        )

    if exam_date:

        days_left = (exam_date - date.today()).days

        if 0 <= days_left <= 7:
            recommendations.append(
                f"Your exam is in {days_left} days. "
                "Focus on weak topics and avoid skipping revisions."
            )

    recommendations.append(
        "Use active recall: try answering before revealing."
    )

    return recommendations


# =========================================
# 14. DASHBOARD ANALYTICS
# =========================================

@app.route("/api/dashboard", methods=["GET"])
@jwt_required()
def dashboard():

    user = current_user()

    cards = Flashcard.query.filter_by(
        user_id=user.id
    ).all()

    now = datetime.utcnow()
    today = date.today()

    due_cards = [
        card for card in cards
        if card.due_at <= now
    ]

    reviewed_today = ReviewLog.query.filter(
        ReviewLog.user_id == user.id,
        ReviewLog.reviewed_at >= datetime.combine(
            today, datetime.min.time()
        )
    ).count()

    mastered = [
        card for card in cards
        if card.repetitions >= 3
    ]

    # This is a mastery proxy, not a measured
    # percentage of real-world memory retention.
    retention = round(
        len(mastered) / len(cards) * 100
    ) if cards else 0

    risk_cards = sorted(
        cards,
        key=lambda card: calculate_risk(card),
        reverse=True
    )[:5]

    risk_cards = [
        card for card in risk_cards
        if calculate_risk(card) >= 50
    ]

    advice = (
        f"Complete {len(due_cards)} scheduled revisions today."
        if due_cards
        else "You are up to date. Add a new topic to your collection."
    )

    recommendations = generate_advice(
        len(due_cards),
        risk_cards,
        user.exam_date
    )

    return jsonify(
        total_cards=len(cards),
        due_cards=len(due_cards),
        reviewed_today=reviewed_today,
        mastered_cards=len(mastered),
        retention=retention,
        streak=calculate_streak(user.id),
        exam_date=(
            user.exam_date.isoformat()
            if user.exam_date else None
        ),
        advice=advice,
        recommendations=recommendations,
        risk_cards=[
            {
                "front": card.front,
                "subject": card.subject,
                "risk": calculate_risk(card)
            }
            for card in risk_cards
        ]
    )


# =========================================
# 15. SAVE EXAM DATE
# =========================================

@app.route("/api/exam", methods=["POST"])
@jwt_required()
def save_exam():

    user = current_user()
    data = request.get_json() or {}

    try:
        exam_date = date.fromisoformat(
            data.get("exam_date", "")
        )

        if exam_date < date.today():
            return jsonify(
                error="Exam date cannot be in the past."
            ), 400

        user.exam_date = exam_date

        db.session.commit()

        return jsonify(message="Exam date saved.")

    except (ValueError, TypeError):
        return jsonify(error="Invalid exam date."), 400


# =========================================
# 16. HEALTH CHECK
# =========================================

@app.route("/", methods=["GET"])
def home():

    return jsonify(
        message="RecallX API is running successfully.",
        status="online"
    )


@app.route("/health", methods=["GET"])
def health():

    return jsonify(status="healthy")


# =========================================
# 17. RUN APPLICATION
# =========================================

if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 5000)),
        debug=False
    )
