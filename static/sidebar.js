// static/sidebar.js
document.addEventListener('DOMContentLoaded', function() {
    const sidebar = document.querySelector('.sidebar');
    const sidebarOverlay = document.getElementById('sidebarOverlay');
    
    // Support multiple toggle buttons (ID and Class)
    const toggles = document.querySelectorAll('#sidebarToggle, .menu-toggle');

    if (sidebar && sidebarOverlay) {
        toggles.forEach(toggle => {
            toggle.addEventListener('click', function(e) {
                e.preventDefault();
                sidebar.classList.toggle('active');
                sidebarOverlay.classList.toggle('active');
            });
        });

        // CRITICAL FIX: Ensure clicking overlay ALWAYS closes sidebar
        sidebarOverlay.addEventListener('click', function() {
            console.log("Overlay clicked, closing sidebar...");
            sidebar.classList.remove('active');
            sidebarOverlay.classList.remove('active');
        });

        // Close sidebar when clicking a link on mobile
        document.querySelectorAll('.nav-link').forEach(link => {
            link.addEventListener('click', () => {
                if (window.innerWidth < 992) {
                    sidebar.classList.remove('active');
                    sidebarOverlay.classList.remove('active');
                }
            });
        });
    }
});
