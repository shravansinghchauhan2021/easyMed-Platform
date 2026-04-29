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


});
