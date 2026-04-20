/* Voice Recognition for Medical Chatbot and AI Assistant Page */
document.addEventListener('DOMContentLoaded', function() {
    setupVoiceInput('voiceChatbotBtn', 'chatbotInput');
    setupVoiceInput('voiceFullBtn', 'ai-input-full');
});

function setupVoiceInput(btnId, inputId) {
    const voiceBtn = document.getElementById(btnId);
    const textInput = document.getElementById(inputId);

    if (!voiceBtn || !textInput) {
        console.warn(`Voice elements not found: btn=${btnId}, input=${inputId}`);
        return;
    }

    console.log(`Initializing voice input for ${btnId}`);

    // Check for browser support
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    
    if (!SpeechRecognition) {
        console.error("Speech recognition not supported");
        voiceBtn.title = "Speech recognition not supported in your browser";
        voiceBtn.style.opacity = "0.5";
        voiceBtn.style.cursor = "not-allowed";
        return;
    }

    const recognition = new SpeechRecognition();
    recognition.continuous = false;
    recognition.lang = 'en-US';
    recognition.interimResults = false;
    recognition.maxAlternatives = 1;

    let isListening = false;

    voiceBtn.addEventListener('click', function() {
        console.log("Voice button clicked, current state:", isListening);
        if (isListening) {
            recognition.stop();
        } else {
            try {
                textInput.placeholder = "Listening... Speak now";
                voiceBtn.classList.add('text-danger');
                voiceBtn.innerHTML = '<i class="fa-solid fa-microphone-lines fa-bounce"></i>';
                recognition.start();
                console.log("Recognition started successfully");
            } catch (e) {
                console.error("Recognition start error:", e);
                alert("Could not start voice recognition: " + e.message);
            }
        }
    });

    recognition.onstart = function() {
        console.log("Recognition session started");
        isListening = true;
    };

    recognition.onresult = function(event) {
        const transcript = event.results[0][0].transcript;
        console.log("Voice result received:", transcript);
        textInput.value = transcript;
        textInput.placeholder = "Type your clinical question here...";
    };

    recognition.onspeechend = function() {
        console.log("Speech ended");
        recognition.stop();
    };

    recognition.onend = function() {
        console.log("Recognition session ended");
        isListening = false;
        voiceBtn.classList.remove('text-danger');
        voiceBtn.innerHTML = '<i class="fa-solid fa-microphone"></i>';
        if (textInput.placeholder === "Listening... Speak now") {
            textInput.placeholder = "Type your clinical question here...";
        }
    };

    recognition.onerror = function(event) {
        console.error("Speech recognition error:", event.error);
        if (event.error === 'not-allowed') {
            alert("Microphone permission denied. Please allow microphone access in your browser settings.");
        } else {
            alert("Speech recognition error: " + event.error);
        }
        isListening = false;
        voiceBtn.classList.remove('text-danger');
        voiceBtn.innerHTML = '<i class="fa-solid fa-microphone"></i>';
        textInput.placeholder = "Error. Please type instead.";
    };
}
