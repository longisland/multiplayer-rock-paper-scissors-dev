            socket.on('rematch_started', (data) => {
                console.log('Rematch started:', data);

                // Stop rematch timer
                stopRematchTimer();

                // Clear rematch UI
                const rematchBtn = document.getElementById('rematchBtn');
                const rematchStatus = document.getElementById('rematchStatus');
                if (rematchBtn) {
                    rematchBtn.style.display = 'none';
                    rematchBtn.disabled = false;
                    rematchBtn.classList.remove('animate__headShake', 'animate__pulse', 'animate__infinite');
                    rematchBtn.style.color = '';
                }
                if (rematchStatus) {
                    rematchStatus.textContent = '';
                    rematchStatus.classList.remove('animate__fadeOut');
                }

                // Update balance immediately
                const coinBalance = document.getElementById('coinBalance');
                if (coinBalance && data.coins !== undefined) {
                    coinBalance.textContent = data.coins;
                    coinBalance.classList.add('animate__animated', 'animate__flash');
                    setTimeout(() => {
                        coinBalance.classList.remove('animate__animated', 'animate__flash');
                    }, 1000);
                }

                // Update match state
                currentMatchId = data.match_id;
                isCreator = data.is_creator;