// Socket events for rematch
socket.on("rematch_status_update", (data) => {
    console.log("Rematch status update:", data);
    const rematchBtn = document.getElementById("rematchBtn");
    const rematchStatus = document.getElementById("rematchStatus");

    if (rematchBtn && rematchStatus) {
        if ((isCreator && data.creator_ready) || (!isCreator && data.joiner_ready)) {
            // This player has already requested rematch
            rematchBtn.disabled = true;
            rematchBtn.innerHTML = ;
            rematchStatus.textContent = "Waiting for opponent to accept rematch...";
        } else if ((isCreator && data.joiner_ready) || (!isCreator && data.creator_ready)) {
            // Opponent has requested rematch
            rematchBtn.classList.add("animate__animated", "animate__pulse", "animate__infinite");
            rematchStatus.textContent = "Opponent wants a rematch! Accept?";
        }
    }
});

socket.on("match_result", (data) => {
    console.log("Match result event received:", data);
    stopMoveTimer();

    // Show result screen with animations
    showScreen("resultScreen");
    updateGameState();

    // Handle rematch button
    const rematchBtn = document.getElementById("rematchBtn");
    const rematchStatus = document.getElementById("rematchStatus");

    if (rematchBtn && rematchStatus) {
        // Only show rematch button if player has enough coins
        if (data.can_rematch) {
            rematchBtn.style.display = "block";
            rematchBtn.disabled = false;
            rematchBtn.classList.remove("animate__pulse", "animate__infinite");
            rematchBtn.innerHTML = ;
            rematchStatus.textContent = "";

            // Handle rematch button click
            rematchBtn.onclick = () => {
                socket.emit("rematch_request", { match_id: currentMatchId });
                rematchBtn.disabled = true;
                rematchBtn.innerHTML = ;
                rematchStatus.textContent = "Waiting for opponent to accept rematch...";
            };
        } else {
            rematchBtn.style.display = "none";
            rematchStatus.textContent = "Not enough coins for rematch";
        }
    }
});

socket.on("match_started", (data) => {
    console.log("Match started event received:", data);
    if (data.match_id === currentMatchId) {
        // Reset game state
        matches[currentMatchId] = {
            status: "playing",
            start_time: data.start_time
        };

        // Show play screen with animation
        showScreen("playScreen");
        startMoveTimer();

        // Reset move buttons
        document.querySelectorAll(".move-btn").forEach(btn => {
            btn.disabled = false;
            btn.style.visibility = "visible";
            btn.classList.remove("animate__fadeOut");
        });

        // Reset status messages
        document.getElementById("playerMoveStatus").textContent = "Waiting for your move...";
        document.getElementById("opponentMoveStatus").textContent = "Waiting for opponent to move...";

        // If this is a rematch, show notification
        if (data.rematch) {
            const notification = document.createElement("div");
            notification.className = "notification animate__animated animate__fadeIn";
            notification.textContent = "Rematch started!";
            document.querySelector(".container").appendChild(notification);
            setTimeout(() => {
                notification.classList.add("animate__fadeOut");
                setTimeout(() => notification.remove(), 1000);
            }, 2000);
        }
    }
});
