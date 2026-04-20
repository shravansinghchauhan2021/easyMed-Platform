document.addEventListener('DOMContentLoaded', function() {
    const fab = document.getElementById('chatbotFab');
    const window_el = document.getElementById('chatbotWindow');
    const closeBtn = document.getElementById('closeChatbot');
    const input = document.getElementById('chatbotInput');
    const sendBtn = document.getElementById('chatbotSend');
    const messages = document.getElementById('chatbotMessages');
    const typing = document.getElementById('chatbotTyping');

    // Toggle and Draggable logic
    let isDragging = false;
    let dragStartX, dragStartY;
    let initialX, initialY;
    const dragThreshold = 5;

    function onDragStart(e) {
        const event = e.type === 'touchstart' ? e.touches[0] : e;
        dragStartX = event.clientX;
        dragStartY = event.clientY;
        
        const rect = fab.getBoundingClientRect();
        initialX = rect.left;
        initialY = rect.top;
        
        fab.style.transition = 'none';
        
        document.addEventListener('mousemove', onDragging);
        document.addEventListener('mouseup', onDragEnd);
        document.addEventListener('touchmove', onDragging, { passive: false });
        document.addEventListener('touchend', onDragEnd);
        
        // Reset dragging state for each start
        setTimeout(() => isDragging = false, 0);
    }

    function onDragging(e) {
        const event = e.type === 'touchmove' ? e.touches[0] : e;
        const dx = event.clientX - dragStartX;
        const dy = event.clientY - dragStartY;
        
        if (!isDragging && (Math.abs(dx) > dragThreshold || Math.abs(dy) > dragThreshold)) {
            isDragging = true;
        }
        
        if (isDragging) {
            if (e.cancelable) e.preventDefault();
            fab.style.left = `${initialX + dx}px`;
            fab.style.top = `${initialY + dy}px`;
            fab.style.bottom = 'auto';
            fab.style.right = 'auto';
        }
    }

    function onDragEnd() {
        fab.style.transition = '';
        document.removeEventListener('mousemove', onDragging);
        document.removeEventListener('mouseup', onDragEnd);
        document.removeEventListener('touchmove', onDragging);
        document.removeEventListener('touchend', onDragEnd);
        
        // Use a small timeout to clear isDragging so click handler can see it
        setTimeout(() => {
            // isDragging will be cleared on next interaction start
        }, 50);
    }

    fab.addEventListener('mousedown', onDragStart);
    fab.addEventListener('touchstart', onDragStart, { passive: true });

    fab.addEventListener('click', (e) => {
        if (isDragging) {
            isDragging = false; // Reset for next time
            return;
        }
        window_el.classList.toggle('show');
        if (window_el.classList.contains('show')) {
            input.focus();
        }
    });

    closeBtn.addEventListener('click', () => {
        window_el.classList.remove('show');
    });

    // Send logic
    function addMessage(text, role) {
        const msg = document.createElement('div');
        msg.className = role === 'user' ? 'user-msg shadow-sm' : 'bot-msg shadow-sm';
        
        let processedText = "";
        if (typeof marked !== 'undefined' && typeof marked.parse === 'function') {
            processedText = marked.parse(text);
        } else {
            // Simple Markdown-ish highlighting fallback
            processedText = text.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
            processedText = processedText.replace(/\[(.*?)\]\((.*?)\)/g, '<a href="$2" target="_blank" class="text-primary fw-bold">$1</a>');
            processedText = processedText.replace(/\n/g, '<br>');
        }
        
        msg.innerHTML = processedText;
        messages.appendChild(msg);
        messages.scrollTop = messages.scrollHeight;
    }

    async function handleSend() {
        const query = input.value.trim();
        if (!query) return;

        addMessage(query, 'user');
        input.value = '';
        
        // Show typing
        typing.style.display = 'block';
        messages.scrollTop = messages.scrollHeight;

        try {
            const patientIdInput = document.getElementById('chatbotPatientId');
            const patient_id = patientIdInput ? patientIdInput.value : '';

            const response = await fetch('/chatbot/query', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ 
                    query: query,
                    patient_id: patient_id
                })
            });
            const data = await response.json();
            
            typing.style.display = 'none';
            if (data.success) {
                addMessage(data.response, 'bot');
            } else {
                addMessage("I'm sorry, I'm having trouble processing that right now. " + (data.error || ""), 'bot');
            }
        } catch (error) {
            typing.style.display = 'none';
            addMessage("Connection error. Please try again later.", 'bot');
        }
    }

    sendBtn.addEventListener('click', handleSend);
    input.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') handleSend();
    });

    // Global toggle from sidebar
    window.openAIChatbot = function() {
        window_el.classList.add('show');
        input.focus();
    };
});
