
// ========================================
// RECALLX - FRONTEND JAVASCRIPT
// ========================================

// Replace this URL after deploying Flask on Render.
const API_URL = "https://YOUR-BACKEND-NAME.onrender.com/api";

let token = localStorage.getItem("recallx_token");
let currentUser = null;
let reviewCards = [];
let currentIndex = 0;
let isFlipped = false;
let authMode = "login";

// ========================================
// API CONNECTION
// ========================================

async function api(path, method = "GET", data = null) {
  const headers = {
    "Content-Type": "application/json"
  };

  if (token) {
    headers.Authorization = `Bearer ${token}`;
  }

  const options = { method, headers };

  if (data) {
    options.body = JSON.stringify(data);
  }

  const response = await fetch(API_URL + path, options);

  const result = await response.json();

  if (!response.ok) {
    throw new Error(result.error || "Something went wrong");
  }

  return result;
}

// ========================================
// AUTHENTICATION
// ========================================

function showAuth(mode) {
  authMode = mode;

  document.getElementById("authName").hidden =
    mode !== "register";

  document.getElementById("authName").required =
    mode === "register";

  document.getElementById("authSubmit").textContent =
    mode === "login" ? "Login" : "Create Account";

  document.getElementById("loginTab").classList.toggle(
    "active", mode === "login"
  );

  document.getElementById("registerTab").classList.toggle(
    "active", mode === "register"
  );

  document.getElementById("authMessage").textContent = "";
}

document.getElementById("authForm").addEventListener(
  "submit", async function(event) {
    event.preventDefault();

    const data = {
      name: document.getElementById("authName").value,
      email: document.getElementById("authEmail").value,
      password: document.getElementById("authPassword").value
    };

    try {
      const result = await api(
        authMode === "login" ? "/login" : "/register",
        "POST",
        data
      );

      token = result.token;
      currentUser = result.user;

      localStorage.setItem("recallx_token", token);

      openApp();
    } catch (error) {
      document.getElementById("authMessage").textContent =
        error.message;
    }
  }
);

async function openApp() {
  try {
    if (!currentUser) {
      const result = await api("/me");
      currentUser = result.user;
    }

    document.getElementById("authScreen").hidden = true;
    document.getElementById("appScreen").hidden = false;

    document.getElementById("profileName").textContent =
      currentUser.name;

    document.getElementById("welcome").textContent =
      "Welcome, " + currentUser.name + "!";

    await loadDashboard();
    await loadCards();
  } catch (error) {
    logout();
    showToast("Please log in again.");
  }
}

function logout() {
  token = null;
  currentUser = null;
  localStorage.removeItem("recallx_token");

  document.getElementById("appScreen").hidden = true;
  document.getElementById("authScreen").hidden = false;
}

// ========================================
// PAGE NAVIGATION
// ========================================

function showPage(pageId) {
  document.querySelectorAll(".page").forEach(page => {
    page.hidden = page.id !== pageId;
  });

  document.querySelectorAll(".sidebar nav a").forEach(link => {
    link.classList.toggle(
      "active",
      link.getAttribute("href") === "#" + pageId
    );
  });

  if (pageId === "review") {
    startReview();
  }

  if (pageId === "flashcards") {
    loadCards();
  }

  if (pageId === "analytics" || pageId === "advisor") {
    loadDashboard();
  }
}

document.querySelectorAll(".sidebar nav a").forEach(link => {
  link.addEventListener("click", event => {
    event.preventDefault();
    showPage(link.getAttribute("href").substring(1));
  });
});

// ========================================
// DASHBOARD
// ========================================

async function loadDashboard() {
  try {
    const data = await api("/dashboard");

    document.getElementById("totalCards").textContent =
      data.total_cards;

    document.getElementById("dueCards").textContent =
      data.due_cards;

    document.getElementById("reviewedToday").textContent =
      data.reviewed_today;

    document.getElementById("masteredCards").textContent =
      data.mastered_cards;

    document.getElementById("streak").textContent =
      data.streak;

    document.getElementById("studyPlan").textContent =
      data.advice;

    document.getElementById("retentionBar").style.width =
      data.retention + "%";

    document.getElementById("retentionText").textContent =
      data.retention + "% retention";

    document.getElementById("analyticsSummary").textContent =
      `You have ${data.total_cards} cards and ${data.due_cards} cards waiting for revision.`;

    document.getElementById("advisorContent").innerHTML =
      data.recommendations.map(item =>
        `<div class="advice-item">${escapeHTML(item)}</div>`
      ).join("");

    document.getElementById("riskList").innerHTML =
      data.risk_cards.length
        ? data.risk_cards.map(card =>
          `<div class="risk-item">
            <strong>${escapeHTML(card.front)}</strong>
            <p>${escapeHTML(card.subject)} · Risk: ${card.risk}%</p>
          </div>`
        ).join("")
        : "<p>No high-risk cards right now. Great work!</p>";

    document.getElementById("examDate").value =
      data.exam_date || "";

    updateCountdown();
  } catch (error) {
    showToast(error.message);
  }
}

// ========================================
// FLASHCARD CREATION
// ========================================

document.getElementById("cardForm").addEventListener(
  "submit", async function(event) {
    event.preventDefault();

    const card = {
      subject: document.getElementById("cardSubject").value,
      front: document.getElementById("cardFront").value,
      back: document.getElementById("cardBack").value,
      hint: document.getElementById("cardHint").value,
      alternative: document.getElementById("cardAlternative").value
    };

    try {
      await api("/cards", "POST", card);

      this.reset();

      document.getElementById("cardMessage").textContent =
        "Flashcard created successfully!";

      await loadCards();
      await loadDashboard();
    } catch (error) {
      document.getElementById("cardMessage").textContent =
        error.message;
    }
  }
);

// ========================================
// DISPLAY FLASHCARDS
// ========================================

async function loadCards() {
  try {
    const data = await api("/cards");

    const container = document.getElementById("cardList");

    if (!data.cards.length) {
      container.innerHTML =
        "<p>You haven't created any flashcards yet.</p>";
      return;
    }

    container.innerHTML = data.cards.map(card => `
      <div class="saved-card">
        <small>${escapeHTML(card.subject)}</small>
        <h3>${escapeHTML(card.front)}</h3>
        <p>${escapeHTML(card.back)}</p>
        <p>Next review: ${new Date(card.due_at).toLocaleDateString()}</p>
        <button class="delete-btn"
          onclick="deleteCard(${card.id})">Delete</button>
      </div>
    `).join("");

  } catch (error) {
    showToast(error.message);
  }
}

async function deleteCard(id) {
  if (!confirm("Are you sure you want to delete this card?")) {
    return;
  }

  try {
    await api(`/cards/${id}`, "DELETE");
    await loadCards();
    await loadDashboard();
    showToast("Flashcard deleted.");
  } catch (error) {
    showToast(error.message);
  }
}

// ========================================
// STUDY ROOM
// ========================================

async function startReview() {
  try {
    const data = await api("/review/due");

    reviewCards = data.cards;
    currentIndex = 0;
    isFlipped = false;

    displayReviewCard();
  } catch (error) {
    showToast(error.message);
  }
}

function displayReviewCard() {
  const card = reviewCards[currentIndex];

  const question = document.getElementById("studyQuestion");
  const label = document.getElementById("cardLabel");
  const controls = document.getElementById("reviewControls");
  const rescue = document.getElementById("rescueArea");
  const reveal = document.getElementById("revealBtn");

  document.getElementById("reviewProgress").textContent =
    reviewCards.length
      ? `${currentIndex + 1} / ${reviewCards.length}`
      : "0 / 0";

  if (!card) {
    question.textContent = "🎉 All caught up!";
    label.textContent = "COMPLETE";
    document.getElementById("reviewSubject").textContent =
      "Study session finished";
    document.getElementById("flipInstruction").textContent =
      "Come back when your next cards are due.";

    controls.hidden = true;
    rescue.hidden = true;
    reveal.hidden = true;
    return;
  }

  document.getElementById("reviewSubject").textContent =
    card.subject;

  question.textContent = card.front;
  label.textContent = "QUESTION";

  document.getElementById("flipInstruction").textContent =
    "Try to remember the answer before revealing it.";

  controls.hidden = true;
  rescue.hidden = false;
  reveal.hidden = false;

  document.getElementById("rescueText").textContent = "";

  reveal.textContent = "Reveal Answer";
  isFlipped = false;
}

function flipCard() {
  const card = reviewCards[currentIndex];

  if (!card) return;

  if (!isFlipped) {
    isFlipped = true;

    document.getElementById("studyQuestion").textContent =
      card.back;

    document.getElementById("cardLabel").textContent =
      "ANSWER";

    document.getElementById("flipInstruction").textContent =
      "Rate how well you remembered.";

    document.getElementById("reviewControls").hidden = false;
    document.getElementById("revealBtn").hidden = true;
  }
}

// ========================================
// MEMORY RESCUE
// ========================================

function showHint() {
  const card = reviewCards[currentIndex];
  if (!card) return;

  document.getElementById("rescueText").textContent =
    card.hint || "No hint available. Try recalling the main keyword.";
}

function showAlternative() {
  const card = reviewCards[currentIndex];
  if (!card) return;

  document.getElementById("rescueText").textContent =
    card.alternative ||
    "Try explaining this concept in your own words.";
}

// ========================================
// SPACED REPETITION RATINGS
// ========================================

async function rateCard(rating) {
  const card = reviewCards[currentIndex];

  if (!card) return;

  try {
    await api("/review", "POST", {
      card_id: card.id,
      rating: rating
    });

    currentIndex++;
    displayReviewCard();

    await loadDashboard();
  } catch (error) {
    showToast(error.message);
  }
}

// ========================================
// EXAM COUNTDOWN
// ========================================

async function saveExam() {
  const date = document.getElementById("examDate").value;

  if (!date) {
    showToast("Please select an exam date.");
    return;
  }

  try {
    await api("/exam", "POST", { exam_date: date });
    updateCountdown();
    showToast("Exam date saved!");
  } catch (error) {
    showToast(error.message);
  }
}

function updateCountdown() {
  const value = document.getElementById("examDate").value;
  const output = document.getElementById("countdown");

  if (!value) {
    output.textContent = "No exam selected";
    return;
  }

  const exam = new Date(value + "T00:00:00");
  const today = new Date();
  today.setHours(0, 0, 0, 0);

  const days = Math.ceil(
    (exam - today) / (1000 * 60 * 60 * 24)
  );

  output.textContent = days > 0
    ? `${days} days remaining`
    : days === 0
      ? "Your exam is today!"
      : "Exam date has passed.";
}

// ========================================
// SECURITY AND UI HELPERS
// ========================================

function escapeHTML(value) {
  return String(value ?? "").replace(/[&<>"']/g, char => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;"
  })[char]);
}

function showToast(message) {
  const toast = document.getElementById("toast");
  toast.textContent = message;
  toast.classList.add("show");

  setTimeout(() => {
    toast.classList.remove("show");
  }, 3000);
}

// ========================================
// APPLICATION STARTUP
// ========================================

if (token) {
  openApp();
} else {
  showAuth("login");
}
