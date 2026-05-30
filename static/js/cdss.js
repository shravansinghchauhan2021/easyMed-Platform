// static/js/cdss.js

document.addEventListener("DOMContentLoaded", function() {
    let currentStep = "step-complaint";
    const stepHistory = [];
    
    const progressMap = {
        "step-complaint": 15,
        "step-unimplemented": 100,
        "step-redflags": 35,
        "step-admission": 100,
        "step-duration": 55,
        "step-day14": 75,
        "step-day14-positive": 100,
        "step-day57": 75,
        "step-day7plus": 75,
        "step-suspicion": 90,
        "step-treatment": 100
    };

    const prevBtn = document.getElementById("prev-btn");
    const nextBtn = document.getElementById("next-btn");
    const progressFill = document.getElementById("progress-fill");

    function updateProgress(stepId) {
        const pct = progressMap[stepId] || 0;
        progressFill.style.width = pct + "%";
    }

    function showStep(stepId) {
        // Hide all steps
        document.querySelectorAll(".wizard-step").forEach(step => {
            step.classList.remove("active");
        });

        // Show target step
        const target = document.getElementById(stepId);
        if (target) {
            target.classList.add("active");
        }

        currentStep = stepId;
        updateProgress(stepId);

        // Update button states
        prevBtn.disabled = (stepHistory.length === 0);
        
        // If it's a terminal step, hide next button or show a finish message
        const isTerminal = ["step-unimplemented", "step-admission", "step-day14-positive", "step-treatment"].includes(stepId);
        if (isTerminal) {
            nextBtn.style.display = "none";
        } else {
            nextBtn.style.display = "block";
            nextBtn.innerText = "Next";
        }
    }

    window.goNext = function() {
        let nextStep = "";

        if (currentStep === "step-complaint") {
            const selected = document.querySelector('input[name="complaint"]:checked');
            if (!selected) {
                alert("Please select an option to continue.");
                return;
            }
            if (selected.value === "fever") {
                nextStep = "step-redflags";
            } else {
                nextStep = "step-unimplemented";
            }
        } 
        
        else if (currentStep === "step-redflags") {
            const checkedFlags = document.querySelectorAll('input[name="redflags"]:checked');
            if (checkedFlags.length > 0) {
                nextStep = "step-admission";
            } else {
                nextStep = "step-duration";
            }
        } 
        
        else if (currentStep === "step-duration") {
            const selected = document.querySelector('input[name="duration"]:checked');
            if (!selected) {
                alert("Please select the fever duration.");
                return;
            }
            if (selected.value === "day14") {
                nextStep = "step-day14";
            } else if (selected.value === "day57") {
                nextStep = "step-day57";
            } else if (selected.value === "day7plus") {
                nextStep = "step-day7plus";
            }
        } 
        
        else if (currentStep === "step-day14") {
            const selected = document.querySelector('input[name="day14-result"]:checked');
            if (!selected) {
                alert("Please select the test result.");
                return;
            }
            if (selected.value === "positive") {
                nextStep = "step-day14-positive";
            } else {
                nextStep = "step-suspicion";
            }
        } 
        
        else if (currentStep === "step-day57" || currentStep === "step-day7plus") {
            nextStep = "step-suspicion";
        } 
        
        else if (currentStep === "step-suspicion") {
            // Read suspected diseases
            const checkedDiseases = document.querySelectorAll('input[name="suspicion"]:checked');
            
            // Hide all treatment result cards first
            document.querySelectorAll(".disease-info-card").forEach(card => {
                card.style.display = "none";
            });

            // Show selected treatment cards
            if (checkedDiseases.length > 0) {
                checkedDiseases.forEach(cb => {
                    const card = document.getElementById("treatment-" + cb.value);
                    if (card) card.style.display = "block";
                });
            } else {
                // If nothing is selected, show a default message in treatment
                const noSuspCard = document.getElementById("treatment-none");
                if (noSuspCard) noSuspCard.style.display = "block";
            }
            
            nextStep = "step-treatment";
        }

        if (nextStep) {
            stepHistory.push(currentStep);
            showStep(nextStep);
        }
    };

    window.goPrev = function() {
        if (stepHistory.length > 0) {
            const prevStep = stepHistory.pop();
            showStep(prevStep);
        }
    };

    // Initialize first step
    showStep("step-complaint");
});
