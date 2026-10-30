
let currentCard = null;

async function loadStats() {

    const response = await fetch('/api/stats');
    const data = await response.json();

    document.getElementById('total').textContent = data.total;
    document.getElementById('due').textContent = data.due;
    document.getElementById('learned').textContent = data.learned;

    document.getElementById('strength').textContent =
        data.strength + '%';

    document.getElementById('progressFill').style.width =
        data.strength + '%';

    document.getElementById('strengthMessage').textContent =
        'Average memory strength: ' + data.strength + '%';
}


async function loadCards() {

    const response = await fetch('/api/cards');
    const cards = await response.json();

    const list = document.getElementById('cardList');

    list.innerHTML = '';

    if (cards.length === 0) {
        list.textContent = 'No flashcards added yet.';
    }

    cards.forEach(card => {

        const item = document.createElement('div');
        item.className = 'card-item';

        const title = document.createElement('strong');
        title.textContent = card.question;

        const info = document.createElement('p');

        info.textContent =
            'Memory: ' + card.strength +
            '% | Reviews: ' + card.repetitions;

        item.append(title, info);

        list.appendChild(item);
    });
}


async function addCard() {

    const question =
        document.getElementById('question').value.trim();

    const answer =
        document.getElementById('answerInput').value.trim();

    if (!question || !answer) {
        alert('Please enter both question and answer.');
        return;
    }

    const response = await fetch('/api/cards', {

        method: 'POST',

        headers: {
            'Content-Type': 'application/json'
        },

        body: JSON.stringify({
            question: question,
            answer: answer
        })
    });

    const data = await response.json();

    if (!response.ok) {
        alert(data.error || 'Could not add card.');
        return;
    }

    document.getElementById('question').value = '';
    document.getElementById('answerInput').value = '';

    document.getElementById('addMessage').textContent =
        'Flashcard added successfully!';

    await loadCards();
    await loadStats();
    await loadStudy();
}


async function loadStudy() {

    const response = await fetch('/api/study');
    const cards = await response.json();

    currentCard = cards.length ? cards[0] : null;

    document.getElementById('answer').style.display = 'none';
    document.getElementById('ratings').style.display = 'none';
    document.getElementById('showBtn').style.display = 'inline-block';

    if (!currentCard) {

        document.getElementById('studyQuestion').textContent =
            '🎉 No cards due right now!';

        document.getElementById('answer').textContent =
            'Come back when your next revision is due, or add more flashcards.';

        document.getElementById('showBtn').style.display = 'none';

        document.getElementById('studyMessage').textContent =
            'You are up to date!';

        return;
    }

    document.getElementById('studyQuestion').textContent =
        currentCard.question;

    document.getElementById('answer').textContent =
        currentCard.answer;

    document.getElementById('studyMessage').textContent =
        'Your revision session is ready!';
}


function showAnswer() {

    if (!currentCard) return;

    document.getElementById('answer').style.display = 'block';

    document.getElementById('ratings').style.display = 'block';

    document.getElementById('showBtn').style.display = 'none';
}


async function review(rating) {

    if (!currentCard) return;

    const response = await fetch(
        '/api/review/' + currentCard.id,
        {
            method: 'POST',

            headers: {
                'Content-Type': 'application/json'
            },

            body: JSON.stringify({
                rating: rating
            })
        }
    );

    const data = await response.json();

    if (!response.ok) {
        alert(data.error || 'Review failed.');
        return;
    }

    document.getElementById('studyMessage').textContent =
        'Review saved! New memory strength: ' +
        data.strength + '%';

    await loadStats();
    await loadCards();
    await loadStudy();
}


// Start application

async function initializeApp() {

    try {

        await loadStats();
        await loadCards();
        await loadStudy();

    } catch (error) {

        console.error(error);

        alert('Unable to connect to the backend.');

    }
}

initializeApp();
