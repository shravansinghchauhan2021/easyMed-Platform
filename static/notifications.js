document.addEventListener('DOMContentLoaded', function() {
    const socket = io();
    const notifBadge = document.getElementById('notifBadge');
    const notifPanelBody = document.querySelector('.notifications-panel .panel-body');
    const userStatusDot = document.getElementById('userStatusDot');

    // --- Audio Notification System ---
    const notifSound = new Audio('https://assets.mixkit.co/active_storage/sfx/2869/2869-preview.mp3'); // Professional medical 'ping'
    notifSound.volume = 0.6;
    
    // Safety: Browsers block sound until user interacts. 
    // We'll unlock audio on the first click in the app.
    let audioUnlocked = false;
    document.addEventListener('click', () => {
        if (!audioUnlocked) {
            notifSound.play().then(() => {
                notifSound.pause();
                notifSound.currentTime = 0;
                audioUnlocked = true;
                console.log(">>> [AUDIO] System Unlocked");
            }).catch(e => console.log("Audio unlock failed:", e));
        }
    }, { once: true });

    window.playNotificationSound = function() {
        if (audioUnlocked) {
            notifSound.currentTime = 0;
            notifSound.play().catch(e => console.error("Sound play failed:", e));
        }
    }

    function playSound() {
        window.playNotificationSound();
    }

    // Handle real-time status changes
    socket.on('status_change', function(data) {
        const userId = data.user_id;
        const status = data.status.toLowerCase();
        
        // Update all status dots with this user ID
        const dots = document.querySelectorAll(`#status-${userId}`);
        dots.forEach(dot => {
            dot.className = `status-dot status-${status}`;
        });
    });

    // Handle new notifications (Patient Case Created, New Requests, etc.)
    socket.on('new_notification', function(notif) {
        playSound(); // <--- RING!
        
        // 1. Update/Show Badge
        if (notifBadge) {
            notifBadge.classList.remove('d-none');
            // Flash effect
            notifBadge.style.transform = 'scale(1.5)';
            setTimeout(() => notifBadge.style.transform = 'scale(1)', 300);
        }

        // 2. Add to Panel
        if (notifPanelBody) {
            const emptyMsg = notifPanelBody.querySelector('.text-center.py-4');
            if (emptyMsg) emptyMsg.remove();

            const notifHtml = `
                <a href="/handle_notification/${notif.id}" class="notif-item unread notif-item-new">
                    <div class="notif-icon">
                        <i class="fa-solid fa-circle-info"></i>
                    </div>
                    <div class="notif-content">
                        <p class="m-0 text-dark small">${notif.message}</p>
                        <span class="text-muted" style="font-size: 0.7rem;">Just now</span>
                    </div>
                </a>
            `;
            notifPanelBody.insertAdjacentHTML('afterbegin', notifHtml);
        }
    });

    // Handle Chat Messages (Ring when someone types to you)
    socket.on('receive_message', function(data) {
        // Only sound if we aren't the sender
        const currentUserId = parseInt(document.body.dataset.userId); // We'll add this to body
        if (data.sender_id !== currentUserId) {
            playSound();
        }
    });
});
