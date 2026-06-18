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
        "step-day14-negative": 100,
        "step-day57": 85,
        "step-day7plus": 85,
        "step-treatment": 100
    };

    const prevBtn = document.getElementById("prev-btn");
    const nextBtn = document.getElementById("next-btn");
    const progressFill = document.getElementById("progress-fill");



    // Mutual Exclusivity Logic for Disease Suspicion checkboxes
    document.querySelectorAll(".wizard-step").forEach(step => {
        const noneCheckbox = step.querySelector('.suspicion-none-class');
        const otherCheckboxes = step.querySelectorAll('input[name="suspicion"]:not(.suspicion-none-class)');
        if (noneCheckbox) {
            noneCheckbox.addEventListener("change", function() {
                if (this.checked) {
                    otherCheckboxes.forEach(cb => cb.checked = false);
                }
            });
            otherCheckboxes.forEach(cb => {
                cb.addEventListener("change", function() {
                    if (this.checked) {
                        noneCheckbox.checked = false;
                    }
                });
            });
        }
    });

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
        const isTerminal = ["step-unimplemented", "step-admission", "step-day14-positive", "step-day14-negative", "step-treatment"].includes(stepId);
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
            const selected = document.querySelector('input[name="redflags"]:checked');
            if (!selected) {
                alert("Please select Yes or No to continue.");
                return;
            }
            if (selected.value === "yes") {
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
                nextStep = "step-day14-negative";
            }
        } 
        
        else if (currentStep === "step-day57" || currentStep === "step-day7plus") {
            const activeStep = document.getElementById(currentStep);
            const checkedDiseases = activeStep.querySelectorAll('input[name="suspicion"]:checked');
            if (checkedDiseases.length === 0) {
                alert("Please select at least one option, or select 'None of the above'.");
                return;
            }
            
            // Hide all treatment result cards first
            document.querySelectorAll(".disease-info-card").forEach(card => {
                card.style.display = "none";
            });
            const noSuspCard = document.getElementById("treatment-none");
            if (noSuspCard) {
                noSuspCard.style.display = "none";
            }

            // Show selected treatment cards
            checkedDiseases.forEach(cb => {
                const card = document.getElementById("treatment-" + cb.value);
                if (card) card.style.display = "block";
            });
            
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
