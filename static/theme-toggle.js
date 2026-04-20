/**
 * static/theme-toggle.js
 * Handles Dark/Light mode switching and persistence.
 */

document.addEventListener('DOMContentLoaded', () => {
    const themeToggle = document.getElementById('themeToggle');
    const htmlElement = document.documentElement;
    const bodyElement = document.body;

    // Load saved theme
    const savedTheme = localStorage.getItem('easymed-theme') || 'light';
    applyTheme(savedTheme);

    if (themeToggle) {
        themeToggle.addEventListener('click', () => {
            const currentTheme = htmlElement.classList.contains('dark-mode') ? 'dark' : 'light';
            const newTheme = currentTheme === 'light' ? 'dark' : 'light';
            
            applyTheme(newTheme);
            localStorage.setItem('easymed-theme', newTheme);
            
            // Optional: Trigger a custom event for other components (like charts) to update
            const event = new CustomEvent('themeChanged', { detail: { theme: newTheme } });
            window.dispatchEvent(event);
        });
    }

    function applyTheme(theme) {
        const icon = themeToggle ? themeToggle.querySelector('i') : null;
        
        if (theme === 'dark') {
            htmlElement.classList.add('dark-mode');
            bodyElement.classList.add('dark-mode');
            if (icon) {
                icon.classList.remove('fa-moon');
                icon.classList.add('fa-sun');
            }
        } else {
            htmlElement.classList.remove('dark-mode');
            bodyElement.classList.remove('dark-mode');
            if (icon) {
                icon.classList.remove('fa-sun');
                icon.classList.add('fa-moon');
            }
        }
    }
});
