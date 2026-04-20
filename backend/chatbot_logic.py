import os
import requests
import json
import sqlite3
import psycopg2
from psycopg2 import extras
from datetime import datetime

# --- Step 1: Database Link Setup ---
DATABASE = 'database.db'
DATABASE_URL = os.environ.get('DATABASE_URL')

# Mock OpenAI and Search API keys - these should be set in environment variables
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "your_openai_key_here")
SERPAPI_KEY = os.getenv("SERPAPI_KEY", "your_serpapi_key_here")

def get_db_connection():
    if DATABASE_URL:
        if DATABASE_URL.startswith('postgres://'):
            url = DATABASE_URL.replace('postgres://', 'postgresql://', 1)
            return psycopg2.connect(url)
        return psycopg2.connect(DATABASE_URL)
    else:
        conn = sqlite3.connect(DATABASE)
        conn.row_factory = sqlite3.Row
        return conn

def db_execute(conn, query, args=()):
    is_postgres = hasattr(conn, 'cursor_factory') or DATABASE_URL is not None
    if is_postgres:
        query = query.replace('?', '%s')
        cursor = conn.cursor(cursor_factory=extras.RealDictCursor)
        cursor.execute(query, args)
        return cursor
    else:
        return conn.execute(query, args)

def fetch_patient_data(patient_name):
    """Fetch patient details by name matching."""
    conn = get_db_connection()
    patient = db_execute(conn, "SELECT * FROM patients WHERE patient_name LIKE ?", (f'%{patient_name}%',)).fetchone()
    conn.close()
    if patient:
        return dict(patient)
    return None

def fetch_conversation_history(patient_id):
    """Fetch all messages for a specific patient case."""
    conn = get_db_connection()
    messages = db_execute(conn, """
        SELECT m.*, u.username, u.profession 
        FROM messages m 
        JOIN users u ON m.sender_id = u.id 
        WHERE m.patient_id = ? 
        ORDER BY m.timestamp ASC
    """, (patient_id,)).fetchall()
    conn.close()
    return [dict(m) for m in messages]

def fetch_cases_by_criteria(criteria_type, value):
    """Fetch a list of cases based on status or priority."""
    conn = get_db_connection()
    if criteria_type == "status":
        cases = db_execute(conn, "SELECT * FROM patients WHERE status = ?", (value,)).fetchall()
    elif criteria_type == "priority":
        cases = db_execute(conn, "SELECT * FROM patients WHERE priority = ?", (value,)).fetchall()
    elif criteria_type == "specialty":
        cases = db_execute(conn, "SELECT * FROM patients WHERE specialist_type = ?", (value,)).fetchall()
    else:
        cases = []
    conn.close()
    return [dict(c) for c in cases]

def perform_web_search(query):
    """Perform a web search using SerpAPI."""
    if not SERPAPI_KEY or SERPAPI_KEY == "your_serpapi_key_here":
        return "Web search is currently unavailable. Please configure SerpAPI key."
    
    params = {
        "engine": "google",
        "q": query,
        "api_key": SERPAPI_KEY
    }
    try:
        response = requests.get("https://serpapi.com/search", params=params)
        results = response.json()
        if "organic_results" in results:
            summary = "\n".join([f"- {res['title']}: {res.get('snippet', '')}" for res in results["organic_results"][:3]])
            return f"According to web search results:\n{summary}"
    except Exception as e:
        return f"Error performing web search: {str(e)}"
    
    return "No relevant web search results found."

def load_config():
    """Load API keys from config.json or environment variables."""
    config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'config.json')
    keys = {"OPENAI_API_KEY": OPENAI_API_KEY, "SERPAPI_KEY": SERPAPI_KEY}
    
    if os.path.exists(config_path):
        try:
            with open(config_path, 'r') as f:
                file_keys = json.load(f)
                for k in keys:
                    if file_keys.get(k) and "Paste_Your" not in file_keys[k]:
                        keys[k] = file_keys[k]
        except:
            pass
    return keys

def is_ai_configured():
    keys = load_config()
    key = keys["OPENAI_API_KEY"]
    if not key or "your_openai_key" in key or "Paste_Your" in key:
        return False
    return True

def mock_clinical_ai(prompt):
    """Provides simulated medical intelligence for demo purposes."""
    prompt_lower = prompt.lower()
    if "heart" in prompt_lower or "cardio" in prompt_lower:
        return "**easyMed - Cardiology Pulse**\nThe heart pumps blood throughout the body. Critical indicators include blood pressure (target 120/80) and heart rate (60-100 bpm). Common issues: arrhythmias, hypertension. *[Demo Mode]*"
    if "brain" in prompt_lower or "neuro" in prompt_lower:
        return "**easyMed - Neurology Insights**\nThe nervous system controls all body functions. Neurologists monitor speech, motor function, and consciousness. Common issues: strokes, seizures, migraines. *[Demo Mode]*"
    if "skin" in prompt_lower or "derma" in prompt_lower:
        return "**easyMed - Dermatology Desk**\nThe skin is the body's largest organ. Dermatologists look for rashes, lesions, and pigmentation changes. Common issues: eczema, melanoma, dermatitis. *[Demo Mode]*"
    if "kidney" in prompt_lower or "nephro" in prompt_lower:
        return "**easyMed - Nephrology Notes**\nKidneys filter waste. Indicators include creatinine levels and urine output. Common issues: CKD, kidney stones. *[Demo Mode]*"
    if "lung" in prompt_lower or "pulmo" in prompt_lower:
        return "**easyMed - Pulmonology Report**\nLungs handle gas exchange. SpO2 should ideally be 95%+. Common issues: asthma, COPD, pneumonia. *[Demo Mode]*"
    if "tumor" in prompt_lower or "cancer" in prompt_lower:
        return "**easyMed - Oncology Overview**\nOncology focuses on cancer treatment. Common approaches include biopsy, imaging, and chemotherapy. *[Demo Mode]*"
    
    return None

USER_CHAT_HISTORY = {}

def query_openai(prompt, system_context, user_id=None):
    keys = load_config()
    if not is_ai_configured():
        mock_resp = mock_clinical_ai(prompt)
        if mock_resp: return mock_resp
        return (
            "### easyMed - Configuration Required\n"
            "To enable my full multi-specialty intelligence, please add your OpenAI API key to `config.json`."
        )

    api_key = keys['OPENAI_API_KEY']
    
    if api_key.startswith('AIza'):
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}"
        headers = { "Content-Type": "application/json" }
        full_text = f"System Context: {system_context}\n\nUser Question: {prompt}"
        
        contents = []
        if user_id:
            # Load up to last 10 messages from session memory
            history = USER_CHAT_HISTORY.get(user_id, [])
            contents.extend(history)
            
        contents.append({"role": "user", "parts": [{"text": full_text}]})
        
        data = {
            "contents": contents,
            "generationConfig": {"temperature": 0.7}
        }
        try:
            response = requests.post(url, headers=headers, json=data, timeout=30)
            res_json = response.json()
            if 'candidates' in res_json and len(res_json['candidates']) > 0:
                answer = res_json['candidates'][0]['content']['parts'][0]['text']
                if user_id:
                    # Save prompt and answer to memory
                    history = USER_CHAT_HISTORY.get(user_id, [])
                    history.append({"role": "user", "parts": [{"text": prompt}]})
                    history.append({"role": "model", "parts": [{"text": answer}]})
                    if len(history) > 10:
                        history = history[-10:] # keep last 5 turns
                    USER_CHAT_HISTORY[user_id] = history
                return answer
            elif 'error' in res_json:
                return f"Gemini Error: {res_json['error'].get('message', 'Unknown API error')}"
            return "Error: Unexpected Gemini response format."
        except requests.exceptions.Timeout:
            return "Error: AI service timed out. Check your connection."
        except Exception as e:
            return f"Error communicating with AI service: {str(e)}"
    
    # Fallback to OpenAI API for sk-... keys
    else:
        url = "https://api.openai.com/v1/chat/completions"
        model = "gpt-3.5-turbo"

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}"
        }
        data = {
            "model": model,
            "messages": [{"role": "system", "content": system_context}, {"role": "user", "content": prompt}],
            "temperature": 0.7
        }
        try:
            response = requests.post(url, headers=headers, json=data, timeout=30)
            res_json = response.json()
            if 'choices' in res_json:
                return res_json['choices'][0]['message']['content']
            elif 'error' in res_json:
                return f"AI Error ({model}): {res_json['error'].get('message', 'Unknown API error')}"
            return "Error: Unexpected AI response format."
        except requests.exceptions.Timeout:
            return "Error: AI service timed out. Check your connection."
        except Exception as e:
            return f"Error communicating with AI service: {str(e)}"

def handle_general_medical_query(user_query):
    query_lower = user_query.lower()
    emergency_keywords = ["chest pain", "breathing difficulty", "unconscious", "stroke", "seizure"]
    if any(ek in query_lower for ek in emergency_keywords):
        return "🚨 **EMERGENCY NOTICE**: Please seek immediate medical attention or visit the nearest hospital."

    responses = {
        "stomach pain": "**Stomach Pain Guidance**:\n- Common causes: gas, indigestion.\n- Suggestion: Hydration and rest. Consult a doctor if severe.",
        "headache": "**Headache Guidance**:\n- Causes: Stress, dehydration, tension.\n- Warning: Seek help if sudden and severe ('worst ever').",
        "fever": "**Fever Guidance**:\n- Common sign of infection.\n- Action: Monitor temperature and stay hydrated. Consult MD if over 103°F.",
    }

    for key, response in responses.items():
        if key in query_lower:
            return response + "\n\n---\n*Disclaimer: Seek professional medical advice.*"
    return None

def suggest_specialist_chatbot(symptoms):
    symptoms = symptoms.lower()
    mapping = {
        'Cardiologist': (['chest pain', 'heart', 'bp', 'blood pressure'], "Based on your symptoms related to chest pain or blood pressure, a **Cardiologist** is recommended for a thorough heart evaluation."),
        'Neurologist': (['headache', 'seizure', 'numbness', 'brain', 'stroke'], "Based on neurological symptoms like headaches or seizures, a **Neurologist** is recommended."),
        'Dermatologist': (['skin', 'rash', 'itching', 'mole'], "For skin-related issues or rashes, a **Dermatologist** is the appropriate specialist."),
        'Pulmonologist': (['breathing', 'breath', 'lung', 'cough', 'oxygen'], "Given the breathing difficulties or lung-related symptoms, we suggest consulting a **Pulmonologist**."),
        'Nephrologist': (['kidney', 'urine', 'renal'], "For symptoms related to kidney function or urinary issues, a **Nephrologist** is recommended."),
        'Oncologist': (['tumor', 'cancer', 'lump'], "For evaluations related to tumors or oncology, an **Oncologist** is recommended.")
    }
    
    for specialist, (keywords, reason) in mapping.items():
        if any(kw in symptoms for kw in keywords):
            return reason
    return None

USER_SESSIONS = {}

def process_chatbot_query(user_query, current_user_id, patient_id=None):
    system_context = """
    You are an intelligent Medical Assistant for easyMed - a Multi-Specialty Telemedicine Platform.
    You have access to specialists across Neurology, Cardiology, Dermatology, Oncology, Nephrology, and Pulmonology.
    Provide professional medical assistance based on patient data (Age, Vitals, Problem Description).
    Always include a disclaimer.
    """

    conn = get_db_connection()
    patients_list = db_execute(conn, "SELECT id, patient_name FROM patients").fetchall()
    conn.close()

    mentioned_patient = None
    # 1. Try to match by explicit name
    sorted_names = sorted([p['patient_name'] for p in patients_list], key=len, reverse=True)
    for p_name in sorted_names:
        if p_name.lower() in user_query.lower():
            mentioned_patient = p_name
            USER_SESSIONS[current_user_id] = p_name
            break

    # 2. Try to match by passed patient_id if pronouns are used
    if not mentioned_patient:
        context_words = ["it", "his", "her", "him", "case", "patient", "consultation", "summary", "conclusion"]
        if any(cw in user_query.lower() for cw in context_words):
            if patient_id:
                # Resolve name from ID
                for p in patients_list:
                    if str(p['id']) == str(patient_id):
                        mentioned_patient = p['patient_name']
                        USER_SESSIONS[current_user_id] = mentioned_patient
                        break
            
            # 3. Fallback to session context if still not found
            if not mentioned_patient and current_user_id in USER_SESSIONS:
                mentioned_patient = USER_SESSIONS[current_user_id]

    if mentioned_patient:
        patient_data = fetch_patient_data(mentioned_patient)
        if patient_data:
            if any(word in user_query.lower() for word in ["summarize", "conversation", "report", "conclusion", "final"]):
                messages = fetch_conversation_history(patient_data['id'])
                if not messages: 
                    # If no messages but completed, still show final info
                    if patient_data.get('status') == 'Completed':
                        return f"The case for **{mentioned_patient}** is completed.\n\n**Specialist Conclusion:**\n- Diagnosis: {patient_data.get('final_diagnosis')}\n- Recommendations: {patient_data.get('final_recommendations')}"
                    return f"I found **{mentioned_patient}**, but no conversation history exists."
                
                if is_ai_configured():
                    context = f"Patient: {mentioned_patient}\nStatus: {patient_data['status']}\nFinal Diagnosis: {patient_data.get('final_diagnosis')}\nFinal Recommendations: {patient_data.get('final_recommendations')}\n\nTranscript: {json.dumps(messages)}"
                    return query_openai(f"Based on this patient data and transcript, answer: {user_query}", context, user_id=current_user_id)
                return f"History for **{mentioned_patient}** found with {len(messages)} messages."

            risk_info = f"- **AI Risk Level**: {patient_data.get('risk_level', 'Low')}\n- **AI Prediction**: {patient_data.get('predicted_condition', 'General Consultation')}"
            vitals = f"BP: {patient_data['blood_pressure'] or 'N/A'}, SpO2: {patient_data['oxygen_level'] or 'N/A'}"
            ai_scan_info = f"- **MRI Scan Analysis**: {patient_data.get('ai_prediction', 'Not analyzed yet')}"
            
            final_conclusion = ""
            if patient_data.get('status') == 'Completed':
                final_conclusion = f"\n- **Specialist's Final Diagnosis**: {patient_data.get('final_diagnosis') or 'N/A'}\n- **Specialist's Recommendations**: {patient_data.get('final_recommendations') or 'N/A'}"
            
            detail_fallback = f"**Patient Profile: {mentioned_patient}**\n- Specialty: {patient_data['specialist_type']}\n- Vitals: {vitals}\n{risk_info}\n{ai_scan_info}{final_conclusion}\n- Problem: {patient_data['problem_description']}"
            
            if any(word in user_query.lower() for word in ["mri", "scan", "imaging", "ct", "heatmap", "x-ray", "xray"]):
                ai_pred = patient_data.get('ai_prediction')
                report = patient_data.get('scan_analysis_report')
                
                if ai_pred and report:
                    if is_ai_configured():
                        return query_openai(f"Explain this MRI scan result for {mentioned_patient}: {report}. Keep it under 60 words, be concise and professional.", system_context, user_id=current_user_id)
                    return f"**Scan Analysis for {mentioned_patient}**\nPrediction: {ai_pred}\n\nReport Summary:\n{report}"
                else:
                    return f"No AI scan analysis has been run for **{mentioned_patient}** yet. Please open their Medical Imaging Viewer and click 'Analyze Scan'."
            if "risk" in user_query.lower():
                return f"The risk level for **{mentioned_patient}** is **{patient_data['risk_level']}**. This assessment is based on recorded symptoms and vital parameters."
                
            if "predict" in user_query.lower() or "condition" in user_query.lower():
                return f"easyMed suggests a possible condition for **{mentioned_patient}**: **{patient_data['predicted_condition']}**. (Note: This is an analytical suggestion, not a diagnosis)."

            if "what" in user_query.lower() or "explain" in user_query.lower() or "who" in user_query.lower() or "symptom" in user_query.lower():
                if is_ai_configured():
                    return query_openai(user_query, detail_fallback, user_id=current_user_id)
                return detail_fallback
                
            return f"I see you mentioned **{mentioned_patient}**. How can I help with this patient? (e.g., 'What is their risk?', 'Summarize their chat')"
            
    if "pending" in user_query.lower():
        cases = fetch_cases_by_criteria("status", "Pending")
        if not cases: return "No pending cases."
        return "Pending Cases:\n" + "\n".join([f"- **{c['patient_name']}** ({c['specialist_type']})" for c in cases])

    general_med_resp = handle_general_medical_query(user_query)
    if general_med_resp: return general_med_resp

    # Specialist Suggestion Check
    specialist_suggestion = suggest_specialist_chatbot(user_query)
    if specialist_suggestion:
        return f"{specialist_suggestion}\n\nWould you like me to help you draft a case for this specialist?"

    if is_ai_configured():
        return query_openai(user_query, system_context, user_id=current_user_id)

    return "I can help with patient data in easyMed. Try 'Show details for [Name]' or 'Check pending cases'."
