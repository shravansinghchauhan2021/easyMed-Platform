/**
 * Professional Loading Screen Logic
 * Handles the display and automatic hide of the loading overlay.
 */
document.addEventListener('DOMContentLoaded', function() {
    const loader = document.getElementById('loader-overlay');
    if (!loader) return;

    // Minimum display time for the professional animation (2.5 seconds)
    const minDisplayTime = 2500;
    
    // Calculate how long to wait
    // We start counting from the moment DOM is loaded
    setTimeout(() => {
        // Add fade-out class to trigger CSS transition
        loader.classList.add('fade-out');
        
        // Remove from DOM after transition completes (0.8s in loader.css)
        setTimeout(() => {
            loader.style.display = 'none';
        }, 800);
    }, minDisplayTime);
});
