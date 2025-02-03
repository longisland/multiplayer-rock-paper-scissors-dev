// Game state management
let currentMatchId = null;
let moveTimer = null;
let isCreator = false;
let socket = null;
let matches = {};  // Store match states
let rematchTimer = null;
let lastMatchStake = null;  // Store stake for rematch

// Initialize socket connection with logging
socket = io({
    transports: ['websocket'],
    upgrade: false,
    reconnection: true,
    reconnectionAttempts: 5,
    reconnectionDelay: 1000
});

socket.on('connect', () => {
    console.log('Socket connected:', socket.id);
});

socket.on('connect_error', (error) => {
    console.error('Socket connection error:', error);
});

socket.on('disconnect', () => {
    console.log('Socket disconnected');
});

socket.on('reconnect', (attemptNumber) => {
    console.log('Socket reconnected after', attemptNumber, 'attempts');
    if (currentMatchId) {
        socket.emit('join_match_room', { match_id: currentMatchId });
    }
});

// Balance animation functions
function animateBalanceChange(element, amount) {
    const changeElement = document.createElement('div');
    changeElement.className = 'coin-change';
    changeElement.textContent = amount > 0 ? `+${amount}` : amount;
    changeElement.style.color = amount > 0 ? 'var(--success-color)' : 'var(--danger-color)';
    
    element.parentElement.appendChild(changeElement);
    element.classList.add(amount > 0 ? 'balance-increase' : 'balance-decrease');
    
    setTimeout(() => {
        element.classList.remove('balance-increase', 'balance-decrease');
        changeElement.remove();
    }, 1500);
}

// Update game state with animations
async function updateGameState() {
    try {
        const response = await fetch('/api/state');
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        const data = await response.json();
        
        // Update coin balance and stats with animation
        const coinBalance = document.getElementById('coinBalance');
        if (coinBalance) {
            const oldBalance = parseInt(coinBalance.textContent);
            const newBalance = data.coins;
            if (oldBalance !== newBalance) {
                animateBalanceChange(coinBalance, newBalance - oldBalance);
            }
            coinBalance.textContent = newBalance;
        }

        if (data.stats) {
            const elements = {
                'playerWins': data.stats.wins,
                'playerLosses': data.stats.losses,
                'playerDraws': data.stats.draws,
                'totalCoinsWon': data.stats.total_coins_won
            };

            for (const [id, value] of Object.entries(elements)) {
                const element = document.getElementById(id);
                if (element) {
                    element.textContent = value;
                }
            }
        }
        
        // Update match list
        const matchList = document.getElementById('matchList');
        if (matchList) {
            matchList.innerHTML = '';
            data.open_matches.forEach(match => {
                const matchDiv = document.createElement('div');
                matchDiv.className = 'match-item animate__animated animate__fadeIn';
                matchDiv.innerHTML = `
                    <span>Stake: <span class="coin-icon">🪙</span>${match.stake}</span>
                    <button class="btn" onclick="joinMatch('${match.id}')">Join Match</button>
                `;
                matchList.appendChild(matchDiv);
            });
        }

        // Handle current match state
        if (data.current_match) {
            currentMatchId = data.current_match.id;
            isCreator = data.current_match.is_creator;

            // Show appropriate screen based on match status
            if (data.current_match.status === 'waiting') {
                if (!document.getElementById('waitingScreen').classList.contains('active')) {
                    showScreen('waitingScreen');
                }
            } else if (data.current_match.status === 'playing') {
                if (!document.getElementById('playScreen').classList.contains('active') &&
                    !document.getElementById('resultScreen').classList.contains('active')) {
                    showScreen('playScreen');
                }
            }
        }
    } catch (error) {
        console.error('Error updating game state:', error);
    }
}

// Match creation with immediate balance update
async function createMatch(stake) {
    try {
        const response = await fetch('/api/create_match', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Accept': 'application/json'
            },
            body: JSON.stringify({stake: stake}),
            credentials: 'same-origin'
        });

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const data = await response.json();
        if (data.success) {
            // Immediately update balance with animation
            const coinBalance = document.getElementById('coinBalance');
            if (coinBalance) {
                const oldBalance = parseInt(coinBalance.textContent);
                const newBalance = oldBalance - stake;
                animateBalanceChange(coinBalance, -stake);
                coinBalance.textContent = newBalance;
            }

            currentMatchId = data.match_id;
            isCreator = true;
            socket.emit('join_match_room', { match_id: data.match_id });
            showScreen('waitingScreen');
        }
    } catch (error) {
        console.error('Error creating match:', error);
    }
}

// Match joining with immediate balance update
async function joinMatch(matchId) {
    try {
        const response = await fetch('/api/join_match', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Accept': 'application/json'
            },
            body: JSON.stringify({match_id: matchId}),
            credentials: 'same-origin'
        });

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const data = await response.json();
        if (data.success) {
            // Immediately update balance with animation
            const coinBalance = document.getElementById('coinBalance');
            if (coinBalance) {
                const oldBalance = parseInt(coinBalance.textContent);
                const newBalance = oldBalance - data.stake;
                animateBalanceChange(coinBalance, -data.stake);
                coinBalance.textContent = newBalance;
            }

            currentMatchId = matchId;
            isCreator = false;
            socket.emit('join_match_room', { match_id: matchId });
            showScreen('playScreen');
            startMoveTimer();
        }
    } catch (error) {
        console.error('Error joining match:', error);
    }
}

// Timer functions
function startMoveTimer() {
    let timeLeft = 10;
    const timerElement = document.getElementById('moveTimer');
    const timerRing = document.querySelector('.timer-ring');
    
    if (!timerElement || !timerRing) {
        console.error('Timer elements not found');
        return;
    }
    
    function updateTimer() {
        timerElement.textContent = timeLeft;
        timerRing.style.setProperty('--progress', (timeLeft / 10) * 100 + '%');
        
        if (timeLeft <= 3) {
            timerElement.style.color = 'var(--danger-color)';
            timerElement.classList.add('animate__animated', 'animate__headShake');
        }
        timeLeft--;
        
        if (timeLeft < 0) {
            clearInterval(moveTimer);
            timerElement.textContent = 'Time is up!';
            timerElement.classList.remove('animate__headShake');
            timerElement.classList.add('animate__bounceOut');
            document.querySelectorAll('.move-btn').forEach(btn => {
                btn.disabled = true;
                btn.classList.add('animate__animated', 'animate__fadeOut');
            });
            
            // Notify server about timeout
            if (currentMatchId) {
                socket.emit('move_timeout', { match_id: currentMatchId });
            }
        }
    }
    
    // Clear any existing timer
    stopMoveTimer();
    
    // Reset timer elements
    timerElement.classList.remove('animate__headShake', 'animate__bounceOut');
    timerElement.style.color = 'var(--warning-color)';
    document.querySelectorAll('.move-btn').forEach(btn => {
        btn.disabled = false;
        btn.classList.remove('animate__fadeOut');
    });
    
    updateTimer();
    moveTimer = setInterval(updateTimer, 1000);
}

function stopMoveTimer() {
    if (moveTimer) {
        clearInterval(moveTimer);
        moveTimer = null;
        const timerElement = document.getElementById('moveTimer');
        if (timerElement) {
            timerElement.classList.remove('animate__headShake', 'animate__bounceOut');
        }
    }
}

function stopRematchTimer() {
    if (rematchTimer) {
        clearInterval(rematchTimer);
        rematchTimer = null;
        const rematchBtn = document.getElementById('rematchBtn');
        if (rematchBtn) {
            rematchBtn.classList.remove('animate__headShake');
            rematchBtn.style.color = '';
        }
    }
}

// Socket event handlers
socket.on('match_start', (data) => {
    console.log('Match start event received:', data);
    currentMatchId = data.match_id;
    showScreen('playScreen');
    startMoveTimer();
});

socket.on('match_result', (data) => {
    console.log('Match result event received:', data);
    stopMoveTimer();
    
    const playerMove = document.getElementById('playerMove');
    const opponentMove = document.getElementById('opponentMove');
    
    if (playerMove && opponentMove) {
        const moveIcon = {
            'rock': '✊',
            'paper': '✋',
            'scissors': '✌️'
        };
        
        if (isCreator) {
            playerMove.innerHTML = moveIcon[data.creator_move];
            opponentMove.innerHTML = moveIcon[data.joiner_move];
        } else {
            playerMove.innerHTML = moveIcon[data.joiner_move];
            opponentMove.innerHTML = moveIcon[data.creator_move];
        }
        
        playerMove.classList.add('animate__animated', 'animate__bounceInLeft');
        opponentMove.classList.add('animate__animated', 'animate__bounceInRight');
    }
    
    // Show result with animation
    const resultAnimation = document.getElementById('resultAnimation');
    const resultTextElement = document.getElementById('resultText');
    
    if (resultAnimation && resultTextElement) {
        let resultText = '';
        
        if (data.winner === 'draw') {
            resultText = "It's a draw!";
            resultAnimation.innerHTML = '🤝';
            resultAnimation.classList.add('animate__animated', 'animate__bounce');
        } else if ((isCreator && data.winner === 'player1') || (!isCreator && data.winner === 'player2')) {
            resultText = 'You won!';
            resultAnimation.innerHTML = '🏆';
            resultAnimation.classList.add('animate__animated', 'animate__tada');
        } else {
            resultText = 'You lost!';
            resultAnimation.innerHTML = '💔';
            resultAnimation.classList.add('animate__animated', 'animate__wobble');
        }
        
        resultTextElement.classList.add('animate__animated', 'animate__fadeInUp');
        resultTextElement.textContent = resultText;
    }
    
    // Update match stats
    const matchStats = document.getElementById('matchStats');
    if (matchStats && data.match_stats) {
        matchStats.innerHTML = `
            <div class="stats-item">
                <span class="stats-label">Creator Wins</span>
                <span class="stats-value">${data.match_stats.creator_wins}</span>
            </div>
            <div class="stats-item">
                <span class="stats-label">Joiner Wins</span>
                <span class="stats-value">${data.match_stats.joiner_wins}</span>
            </div>
            <div class="stats-item">
                <span class="stats-label">Draws</span>
                <span class="stats-value">${data.match_stats.draws}</span>
            </div>
        `;
    }
    
    // Show rematch button if available
    const rematchBtn = document.getElementById('rematchBtn');
    if (rematchBtn && data.can_rematch) {
        rematchBtn.style.display = 'block';
        startRematchTimer();
    }
    
    showScreen('resultScreen');
});

// Initialize game state update interval
setInterval(updateGameState, 5000);

// Export functions for global use
window.createMatch = createMatch;
window.joinMatch = joinMatch;
window.showScreen = showScreen;