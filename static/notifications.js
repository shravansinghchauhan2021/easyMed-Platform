document.addEventListener('DOMContentLoaded', function() {
    const socket = io();
    const notifBadge = document.getElementById('notifBadge');
    const notifPanelBody = document.querySelector('.notifications-panel .panel-body');
    const userStatusDot = document.getElementById('userStatusDot');

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

    // Handle new notifications
    socket.on('new_notification', function(notif) {
        // 1. Update/Show Badge
        if (notifBadge) {
            notifBadge.classList.remove('d-none');
            // Flash effect
            notifBadge.style.transform = 'scale(1.5)';
            setTimeout(() => notifBadge.style.transform = 'scale(1)', 300);
        } else {
            // If badge doesn't exist, we might need to create it or just show it
            // (Assuming existing structure has it hidden if count is 0)
        }

        // 2. Add to Panel
        if (notifPanelBody) {
            // Remove "No recent notifications" if present
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

        // 3. Play subtle sound or show toast? (Optional)
    });
});
