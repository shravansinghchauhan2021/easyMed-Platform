/**
 * URD Symptom Workflow Logic
 */

let currentStep = 1;

function showStep(stepId) {
    document.getElementById('wizardError').classList.add('d-none'); // Clear error on step change
    document.querySelectorAll('.wizard-step').forEach(step => {
        step.classList.remove('active');
    });
    document.getElementById(stepId).classList.add('active');
    updateProgress();
}

function toggleNone(groupName) {
    const noneCheckbox = document.querySelector(`input[name="${groupName}None"]`);
    const otherCheckboxes = document.querySelectorAll(`input[name="${groupName}"]`);
    
    if (noneCheckbox.checked) {
        otherCheckboxes.forEach(cb => cb.checked = false);
    }
}

// Added mutual exclusivity when other boxes are checked
document.addEventListener('change', (e) => {
    if (e.target.type === 'checkbox' && !e.target.name.endsWith('None')) {
        const groupName = e.target.name;
        const noneCheckbox = document.querySelector(`input[name="${groupName}None"]`);
        if (noneCheckbox && e.target.checked) {
            noneCheckbox.checked = false;
        }
    }
});

function showError() {
    document.getElementById('wizardError').classList.remove('d-none');
}

function updateProgress() {
    const dots = document.querySelectorAll('.progress-dot');
    dots.forEach((dot, index) => {
        if (index < currentStep) {
            dot.classList.add('active');
        } else {
            dot.classList.remove('active');
        }
    });
}

function selectInitialSymptom(type) {
    if (type === 'Urinary') {
        currentStep = 2;
        showStep('step2');
    } else {
        showResult('Please consult a doctor for further evaluation.', 'consult');
    }
}

function handleStep2(isYes) {
    if (isYes) {
        showStep('step2Right');
    } else {
        showStep('step2Left');
    }
}

function evaluateStep2Left() {
    const selected = document.querySelectorAll('input[name="symptomLeft"]:checked');
    const noneSelected = document.querySelector('input[name="symptomLeftNone"]').checked;
    
    if (!noneSelected && selected.length === 0) {
        showError();
        return;
    }

    if (selected.length > 0) {
        showResult('Most likely vaginitis/prostatitis. Please consult a doctor.', 'consult');
    } else {
        showResult('Consider alternative diagnosis.', 'consult');
    }
}

function evaluateStep2Right() {
    const selected = document.querySelectorAll('input[name="symptomRight"]:checked');
    const noneSelected = document.querySelector('input[name="symptomRightNone"]').checked;

    if (!noneSelected && selected.length === 0) {
        showError();
        return;
    }

    if (selected.length > 0) {
        showResult('Most likely vaginitis/prostatitis. Please consult a doctor.', 'consult');
    } else {
        currentStep = 3;
        showStep('step3');
    }
}

function evaluateRedFlags() {
    const selected = document.querySelectorAll('input[name="redflag"]:checked');
    const noneSelected = document.querySelector('input[name="redflagNone"]').checked;

    if (!noneSelected && selected.length === 0) {
        showError();
        return;
    }

    if (selected.length > 0) {
        showResult('Refer to hospital immediately.', 'emergency');
    } else {
        currentStep = 4;
        showStep('step4');
    }
}

function evaluateFinal(hasFever) {
    if (hasFever) {
        showResult(`
            <div class="text-start">
                <h4 class="fw-bold">Complicated UTI</h4>
                <p><strong>Management:</strong></p>
                <ul>
                    <li>Urine culture</li>
                    <li>Hospital admission</li>
                    <li>Antibiotics as per AST report</li>
                </ul>
            </div>
        `, 'complicated');
    } else {
        showResult(`
            <div class="text-start">
                <h4 class="fw-bold">Uncomplicated UTI</h4>
                <p><strong>Management:</strong></p>
                <ul>
                    <li>Urine RE/ME</li>
                    <li>Dipstick</li>
                    <li>Urine culture</li>
                </ul>
                <p><strong>Treatment (Adult):</strong></p>
                <ul>
                    <li>Nitrofurantoin 100 mg BD &times; 5 days</li>
                    <li>OR</li>
                    <li>Cotrimoxazole 960 mg BD &times; 5 days</li>
                </ul>
            </div>
        `, 'uncomplicated');
    }
}

function showResult(message, type) {
    const resultContent = document.getElementById('resultContent');
    let className = 'result-box';
    
    if (type === 'emergency') className += ' result-emergency';
    else if (type === 'complicated') className += ' result-complicated';
    else if (type === 'uncomplicated') className += ' result-uncomplicated';
    else className += ' result-consult';

    resultContent.innerHTML = `<div class="${className}">${message}</div>`;
    showStep('resultStep');
    
    // Set final step for progress
    currentStep = 4;
    updateProgress();
}
