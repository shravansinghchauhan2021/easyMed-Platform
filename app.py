import eventlet
eventlet.monkey_patch()

# Standard imports
import os
import json
import sqlite3
import time
import requests
import threading
from datetime import datetime
from werkzeug.utils import secure_filename
import traceback
import psycopg2
from psycopg2 import extras
try:
    from psycogreen.eventlet import patch_psycopg
    patch_psycopg()
    print(">>> [SUCCESS] Psycogreen Activated (PostgreSQL is now Green)", flush=True)
except ImportError:
    print(">>> [INFO] Psycogreen not found, using standard mode.", flush=True)

# --- Step 1: Database Link Setup ---
DATABASE = 'database.db'
DATABASE_URL = os.environ.get('DATABASE_URL')

# Fix logic: Clean the URL and check for common typos
if DATABASE_URL:
    DATABASE_URL = DATABASE_URL.strip()
    # Check if the user accidentally pasted the name "DATABASE_URL" as the VALUE
    if DATABASE_URL == "DATABASE_URL" or not DATABASE_URL.startswith("post"):
        print("\n" + "!"*60)
        print("⚠️  [WARNING] DATABASE_URL is invalid or a typo. Using local backup.")
        print("!"*60 + "\n", flush=True)
        DATABASE_URL = None
    elif DATABASE_URL.startswith('postgres://'):
        DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql://', 1)

# Load configuration safely
try:
    with open('config.json') as f:
        config = json.load(f)
except:
    config = {}

# --- Step 1.5: API Priority Configuration ---
# Prioritize Environment Variables for Production Security
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY', config.get('GEMINI_API_KEY', ''))
# Backward compatibility for old variable names if used
if not GEMINI_API_KEY:
    GEMINI_API_KEY = os.getenv('OPENAI_API_KEY', config.get('OPENAI_API_KEY', config.get('GOOGLE_API_KEY', '')))

# --- Step 2: Database Helpers ---
def get_db_connection():
    if DATABASE_URL:
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

def db_get_last_rowid(conn, cursor):
    """Handles getting the last inserted ID across databases"""
    is_postgres = hasattr(conn, 'cursor_factory') or DATABASE_URL is not None
    if is_postgres:
        cursor.execute("SELECT LASTVAL()")
        return cursor.fetchone()['lastval']
    else:
        return cursor.lastrowid

def db_get_count(conn, query, args=()):
    """Safely get a COUNT(*) value across SQLite and Postgres"""
    is_postgres = hasattr(conn, 'cursor_factory') or DATABASE_URL is not None
    if is_postgres:
        query = query.replace('?', '%s')
        if "COUNT(*)" in query and "as count" not in query.lower():
            query = query.replace("COUNT(*)", "COUNT(*) as count")
        cursor = conn.cursor(cursor_factory=extras.RealDictCursor)
        cursor.execute(query, args)
        res = cursor.fetchone()
        return res['count'] if res else 0
    else:
        return conn.execute(query, args).fetchone()[0]

def init_db():
    conn = get_db_connection()
    is_postgres = DATABASE_URL is not None
    
    if is_postgres:
        print("\n" + "="*50)
        print("[SYSTEM] Database Status: CONNECTED TO PERMANENT POSTGRESQL")
        print("[SYSTEM] Production Schema Active.", flush=True)
    else:
        print("\n" + "!"*50)
        print("[SYSTEM] Database Status: USING TEMPORARY LOCAL SQLITE")
        print("!"*50 + "\n", flush=True)

    pk_style = "SERIAL PRIMARY KEY" if is_postgres else "INTEGER PRIMARY KEY AUTOINCREMENT"
    
    db_execute(conn, f'''
        CREATE TABLE IF NOT EXISTS users (
            id {pk_style},
            username TEXT UNIQUE,
            password TEXT,
            profession TEXT,
            mobile_number TEXT UNIQUE,
            status TEXT DEFAULT 'Offline'
        )
    ''')
    conn.commit()

    db_execute(conn, f'''
        CREATE TABLE IF NOT EXISTS patients (
            id {pk_style},
            patient_name TEXT,
            patient_mobile TEXT,
            patient_user_id INTEGER,
            age INTEGER,
            gender TEXT,
            specialist_type TEXT,
            blood_pressure TEXT,
            heart_rate INTEGER,
            oxygen_level INTEGER,
            problem_description TEXT,
            priority TEXT DEFAULT 'Normal',
            status TEXT DEFAULT 'Pending'
        )
    ''')
    conn.commit()
    
    # --- Production Schema Hardening (Ensure all columns exist) ---
    if is_postgres:
        # Users Table Maintenance
        users_cols = [
            ('mobile_number', 'TEXT'),
            ('status', "TEXT DEFAULT 'Offline'")
        ]
        for col_name, col_type in users_cols:
            try:
                db_execute(conn, f'ALTER TABLE users ADD COLUMN {col_name} {col_type}')
                conn.commit()
                print(f"[SCHEMA] Added {col_name} to users table.")
            except: 
                conn.rollback() # Column likely exists

        # Patients Table Maintenance
        patients_cols = [
            ('patient_user_id', 'INTEGER'),
            ('priority_level', "TEXT DEFAULT 'Normal'"),
            ('status', "TEXT DEFAULT 'Pending'"),
            ('headache_severity', 'TEXT'),
            ('consciousness_level', 'TEXT'),
            ('specialist_id', 'INTEGER'),
            ('report_file_path', 'TEXT'),
            ('report_file', 'TEXT'),
            ('final_diagnosis', 'TEXT'),
            ('final_recommendations', 'TEXT'),
            ('specialist_type', 'TEXT'),
            ('heart_rate', 'INTEGER'),
            ('blood_pressure', 'TEXT'),
            ('oxygen_level', 'INTEGER'),
            ('patient_name', 'TEXT'),
            ('rural_doctor_id', 'INTEGER')
        ]
        for col_name, col_type in patients_cols:
            try:
                db_execute(conn, f'ALTER TABLE patients ADD COLUMN {col_name} {col_type}')
                conn.commit()
                print(f"[SCHEMA] Added {col_name} to patients table.")
            except: 
                conn.rollback() # Column likely exists
    else:
        # SQLite Maintenance (Backward compat)
        try:
            db_execute(conn, 'ALTER TABLE users ADD COLUMN mobile_number TEXT')
            conn.commit()
        except: pass
    
    # 3. Create Additional Tables
    for table_sql in [
        f'CREATE TABLE IF NOT EXISTS messages (id {pk_style}, patient_id INTEGER, sender_id INTEGER, message TEXT, file_path TEXT, timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP)',
        f'CREATE TABLE IF NOT EXISTS notifications (id {pk_style}, user_id INTEGER, patient_id INTEGER, message TEXT, link TEXT, read_status BOOLEAN DEFAULT FALSE, timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP)'
    ]:
        db_execute(conn, table_sql)
        conn.commit()
    
    cols_to_add = [
        ('patients', 'patient_user_id', 'INTEGER'), ('patients', 'risk_level', "TEXT DEFAULT 'Low'"),
        ('patients', 'predicted_condition', "TEXT DEFAULT 'General Consultation'"),
        ('patients', 'ai_prediction', 'TEXT'), ('patients', 'scan_analysis_report', 'TEXT'),
        ('patients', 'consciousness_level', 'TEXT'), ('patients', 'speech_condition', 'TEXT'),
        ('patients', 'motor_function', 'TEXT'), ('patients', 'headache_severity', 'TEXT'),
        ('patients', 'seizure_history', 'TEXT'), ('patients', 'tumor_details', 'TEXT'),
        ('patients', 'cancer_history', 'TEXT'), ('patients', 'kidney_function', 'TEXT'),
        ('patients', 'urine_reports', 'TEXT'), ('patients', 'skin_condition', 'TEXT'),
        ('patients', 'rash_description', 'TEXT'), ('patients', 'breathing_condition', 'TEXT'),
        ('patients', 'priority_level', 'TEXT'), ('patients', 'final_diagnosis', 'TEXT'),
        ('patients', 'final_recommendations', 'TEXT'), ('patients', 'assigned_doctor_id', 'INTEGER'),
        ('patients', 'report_file_path', 'TEXT'),
        ('patients', 'specialist_type', 'TEXT'),
        ('patients', 'heart_rate', 'INTEGER'),
        ('patients', 'blood_pressure', 'TEXT'),
        ('patients', 'oxygen_level', 'INTEGER'),
        ('patients', 'patient_name', 'TEXT'),
        ('patients', 'rural_doctor_id', 'INTEGER'),
        ('patients', 'created_at', 'TIMESTAMP DEFAULT CURRENT_TIMESTAMP')
    ]
    
    for table, col, dtype in cols_to_add:
        try:
            db_execute(conn, f'ALTER TABLE {table} ADD COLUMN {col} {dtype}')
            conn.commit()
        except: pass

    conn.close()


_db_initialized = False

def safe_init_db():
    global _db_initialized
    if not _db_initialized:
        try:
            print(">>> [LAZY INIT] Verifying database schema...", flush=True)
            init_db()
            _db_initialized = True
        except Exception as e:
            print(f">>> [ERROR] Lazy Init Failed: {e}", flush=True)

# --- Step 3: Global Logic & Flask App Setup ---

import random
import requests
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify, send_from_directory
from flask_socketio import SocketIO, emit, join_room, leave_room
from flask_cors import CORS
from werkzeug.middleware.proxy_fix import ProxyFix
from werkzeug.security import generate_password_hash, check_password_hash
from backend.chatbot_logic import process_chatbot_query

# PDF and Report Generation
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle

app = Flask(__name__)
safe_init_db()  # ACTIVATE SELF-HEALING DATABASE ON STARTUP
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev_key_123')
app.before_request(safe_init_db)
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)
app.secret_key = 'super_secret_medical_key_for_dev'
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*")

# --- Self-Ping / Keep-Alive System ---
def keep_alive(url):
    """Pings the app every 10 minutes to prevent Render sleep mode"""
    # Wait longer for app to fully boot on Render's slow free tier
    time.sleep(60)
    
    print(f">>> [HEARTBEAT] Starting background pinger for {url}", flush=True)
    while True:
        try:
            # Safer 10-minute interval (Render sleeps at 15m)
            time.sleep(10 * 60)
            # Use /ping endpoint to avoid heavy load
            ping_url = f"{url.rstrip('/')}/ping"
            requests.get(ping_url, timeout=15)
            print(f">>> [HEARTBEAT] Pulse sent at {datetime.now()}", flush=True)
        except Exception as e:
            print(f">>> [HEARTBEAT] Pulse failed: {e}", flush=True)

# --- Initialize Neural Heartbeat (Keep-Alive) ---
def start_heartbeat():
    if os.environ.get('RENDER'):
        # Try to find the URL automatically
        url = os.environ.get('RENDER_EXTERNAL_URL')
        if not url and os.environ.get('RENDER_EXTERNAL_HOSTNAME'):
            url = f"https://{os.environ.get('RENDER_EXTERNAL_HOSTNAME')}"
            
        if url:
            ka_thread = threading.Thread(target=keep_alive, args=(url,), daemon=True)
            ka_thread.start()
        else:
            print(">>> [HEARTBEAT] Warning: RENDER_EXTERNAL_URL not set. Heartbeat skipped.", flush=True)

start_heartbeat()

@app.context_processor
def inject_global_notifications():
    if 'user_id' in session:
        try:
            conn = get_db_connection()
            notifications = db_execute(conn, 'SELECT * FROM notifications WHERE user_id = ? ORDER BY id DESC LIMIT 10', (session['user_id'],)).fetchall()
            unread_count = sum(1 for n in notifications if not n['read_status'])
            conn.close()
            return dict(notifications=notifications, unread_count=unread_count)
        except:
            pass
    return dict(notifications=[], unread_count=0)


UPLOAD_FOLDER = 'uploads'
IMAGING_FOLDER = os.path.join(UPLOAD_FOLDER, 'imaging')
ALLOWED_EXTENSIONS = {'txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif', 'doc', 'docx', 'xls', 'xlsx', 'ppt', 'pptx', 'zip', 'rar', 'csv', 'mp4', 'mov', 'avi', 'dcm', 'edf'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['IMAGING_FOLDER'] = IMAGING_FOLDER

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(IMAGING_FOLDER, exist_ok=True)

FAST2SMS_API_KEY = 'CqjKpBhzOQWFb2H4mkYRouv08LxMfDtl16ZaGUTISA9ngXNrwy5TRbSlhIeWMPaAq3nfOpZygLX8Jzvi'
SPECIALIST_ROLES = ['Neurologist', 'Cardiologist', 'Dermatologist', 'Oncologist', 'Nephrologist', 'Pulmonologist']

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def send_sms(mobile_number, otp_message):
    url = "https://www.fast2sms.com/dev/bulkV2"
    payload = {
        "route": "q",
        "message": otp_message,
        "language": "english",
        "flash": 0,
        "numbers": mobile_number
    }
    headers = {
        "authorization": FAST2SMS_API_KEY,
        "Content-Type": "application/x-www-form-urlencoded"
    }
    try:
        response = requests.post(url, data=payload, headers=headers, timeout=5)
        res_json = response.json()
        print(f"\nFAST2SMS RAW RESPONSE: {res_json}\n", flush=True)
        return res_json
    except Exception as e:
        print(f"Error sending SMS: {e}")
        return None

def suggest_specialist_ai(symptoms):
    symptoms = symptoms.lower()
    mapping = {
        'Cardiologist': ['chest pain', 'heart', 'bp', 'blood pressure', 'palpitations', 'cardiac'],
        'Neurologist': ['headache', 'seizure', 'numbness', 'brain', 'stroke', 'dizzy', 'consciousness'],
        'Dermatologist': ['skin', 'rash', 'itching', 'mole', 'acne', 'dermatitis'],
        'Pulmonologist': ['breathing', 'breath', 'lung', 'cough', 'shortness of breath', 'asthma', 'oxygen'],
        'Nephrologist': ['kidney', 'urine', 'renal', 'dialysis', 'flank pain'],
        'Oncologist': ['tumor', 'cancer', 'chemo', 'lump', 'biopsy', 'malignant']
    }
    
    for specialist, keywords in mapping.items():
        if any(kw in symptoms for kw in keywords):
            return specialist
    return "Neurologist" # Default

def detect_emergency_ai(symptoms, consciousness='Alert', oxygen_level=None, heart_rate=None):
    symptoms = symptoms.lower()
    # Severe symptom detection
    critical_keywords = ['unconscious', 'seizure', 'chest pain', 'breathing issue', 'heavy bleeding', 'stroke']
    if any(kw in symptoms for kw in critical_keywords):
        return 'Emergency'
        
    if consciousness == 'Unconscious':
        return 'Emergency'
        
    try:
        if oxygen_level and int(oxygen_level) < 90:
            return 'Emergency'
        if heart_rate and (int(heart_rate) > 120 or int(heart_rate) < 50):
            return 'Emergency'
    except:
        pass
        
    return 'Normal'
    
def calculate_risk_score(symptoms, bp, oxygen, heart_rate, consciousness):
    symptoms = symptoms.lower()
    score = 0
    
    # Symptom severity
    critical_keywords = ['unconscious', 'seizure', 'chest pain', 'breathing issue', 'heavy bleeding', 'stroke', 'severe']
    moderate_keywords = ['fever', 'pain', 'vomiting', 'dizzy', 'cough']
    
    if any(kw in symptoms for kw in critical_keywords):
        score += 3
    elif any(kw in symptoms for kw in moderate_keywords):
        score += 1
        
    # Vitals check
    try:
        if oxygen and int(oxygen) < 92: score += 3
        elif oxygen and int(oxygen) < 95: score += 1
        
        if heart_rate and (int(heart_rate) > 120 or int(heart_rate) < 50): score += 3
        elif heart_rate and (int(heart_rate) > 100 or int(heart_rate) < 60): score += 1
        
        if bp:
            parts = bp.split('/')
            if len(parts) == 2:
                sys, dia = int(parts[0]), int(parts[1])
                if sys > 160 or dia > 100 or sys < 90: score += 3
                elif sys > 140 or dia > 90: score += 1
    except:
        pass
        
    if consciousness != 'Alert':
        score += 2
        
    if score >= 5: return 'High'
    if score >= 2: return 'Medium'
    return 'Low'

def predict_disease(symptoms, specialty):
    symptoms = symptoms.lower()
    
    if specialty == 'Cardiologist':
        if 'chest pain' in symptoms or 'palpitations' in symptoms:
            return "Possible Cardiac Event / Hypertension"
    elif specialty == 'Neurologist':
        if 'headache' in symptoms and ('speech' in symptoms or 'numbness' in symptoms):
            return "Possible Stroke / TIA"
        if 'seizure' in symptoms:
            return "Possible Epilepsy"
    elif specialty == 'Pulmonologist':
        if 'breathing' in symptoms or 'cough' in symptoms:
            return "Possible Respiratory Infection / Asthma"
    elif specialty == 'Dermatologist':
        if 'rash' in symptoms or 'itching' in symptoms:
            return "Possible Dermatitis / Allergic Reaction"
            
    return "General Clinical Observation"

def find_best_specialist(specialist_type):
    conn = get_db_connection()
    # Try to find an Online specialist
    spec = db_execute(conn, 'SELECT id, username FROM users WHERE profession = ? AND status = ? LIMIT 1', (specialist_type, 'Online')).fetchone()
    if spec:
        conn.close()
        return spec['id'], spec['username'], True
    
    spec = db_execute(conn, 'SELECT id, username FROM users WHERE profession = ? LIMIT 1', (specialist_type,)).fetchone()
    conn.close()
    if spec:
        return spec['id'], spec['username'], False
    return None, None, False

def create_notification(user_id, message, link="#", patient_id=None, conn=None):
    close_conn = False
    if conn is None:
        conn = get_db_connection()
        close_conn = True
    
    is_postgres = DATABASE_URL is not None
    insert_sql = 'INSERT INTO notifications (user_id, patient_id, message, link) VALUES (?, ?, ?, ?) '
    params = (user_id, patient_id, message, link)
    
    if is_postgres:
        cur = db_execute(conn, insert_sql + ' RETURNING id', params)
        notif_id = cur.fetchone()['id']
    else:
        cur = db_execute(conn, insert_sql, params)
        notif_id = cur.lastrowid
    
    # Emit real-time update
    try:
        socketio.emit('new_notification', {
            'id': notif_id,
            'message': message,
            'link': link,
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }, room=f"user_{user_id}")
    except:
        pass # Handle cases where we are outside of request context
    
    if close_conn:
        conn.commit()
        conn.close()

@app.route('/privacy')
def privacy():
    return render_template('privacy.html')

@app.route('/')
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        profession = request.form['profession']
        password = request.form['password']

        conn = get_db_connection()
        user = db_execute(conn, 'SELECT * FROM users WHERE username = ? AND profession = ?', (username, profession)).fetchone()
        conn.close()

        if user and check_password_hash(user['password'], password):
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['profession'] = user['profession']
            
            # Set user status to Online
            conn = get_db_connection()
            db_execute(conn, "UPDATE users SET status = 'Online' WHERE id = ?", (user['id'],))
            conn.commit()
            conn.close()
            
            # flash('Login successful!', 'success')
            if user['profession'] == 'Rural Doctor':
                return redirect(url_for('rural_dashboard'))
            elif user['profession'] in SPECIALIST_ROLES:
                return redirect(url_for('specialist_dashboard'))
            elif user['profession'] == 'Patient':
                return redirect(url_for('patient_dashboard'))
            else:
                return redirect(url_for('dashboard')) # fallback
        else:
            flash('Invalid credentials. Please try again.', 'error')

    return render_template('login.html')

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return f"Welcome {session['username']}! <br><a href='/logout'>Logout</a>"

@app.route('/logout')
def logout():
    if 'user_id' in session:
        # Set user status to Offline
        conn = get_db_connection()
        db_execute(conn, "UPDATE users SET status = 'Offline' WHERE id = ?", (session['user_id'],))
        conn.commit()
        conn.close()
        
    session.clear()
    flash('You have been logged out.', 'info')
    return redirect(url_for('login'))

@app.route('/profile')
def profile_view():
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    conn = get_db_connection()
    user = db_execute(conn, 'SELECT * FROM users WHERE id = ?', (session['user_id'],)).fetchone()
    conn.close()
    
    if not user:
        session.clear()
        return redirect(url_for('login'))
        
    return render_template('profile.html', user=user)

@app.route('/api/delete_account', methods=['POST'])
def delete_account():
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401
        
    user_id = session['user_id']
    profession = session.get('profession')
    
    try:
        conn = get_db_connection()
        
        # 1. Delete notifications
        db_execute(conn, "DELETE FROM notifications WHERE user_id = ?", (user_id,))
        
        # 2. Delete messages sent by user
        db_execute(conn, "DELETE FROM messages WHERE sender_id = ?", (user_id,))
        
        # 3. If Patient, delete patient record
        if profession == 'Patient':
            db_execute(conn, "DELETE FROM patients WHERE patient_user_id = ?", (user_id,))
            
        # 4. If Doctor, handle assigned patients (optional: could delete or unassign)
        # For simplicity and to comply with "delete everything", we'll remove their metadata in dashboard items if any
        
        # 5. Finally delete the user
        db_execute(conn, "DELETE FROM users WHERE id = ?", (user_id,))
        
        conn.commit()
        conn.close()
        
        session.clear()
        flash('Your account and all associated data have been permanently deleted.', 'info')
        return jsonify({'success': True, 'redirect': url_for('login')})
        
    except Exception as e:
        print(f"ERROR DELETING ACCOUNT: {e}", flush=True)
        return jsonify({'success': False, 'message': 'Internal Server Error'}), 500

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        profession = request.form['profession']
        mobile_number = request.form['mobile']
        password = request.form['password']
        entered_otp = request.form.get('otp')

        if not entered_otp:
            flash('OTP is required.', 'error')
            return render_template('register.html', username=username, profession=profession, mobile=mobile_number)

        # Verify OTP
        session_otp = session.get('registration_otp')
        session_mobile = session.get('registration_mobile')

        if session_otp and str(session_otp) == str(entered_otp) and session_mobile == mobile_number:
            # OTP is correct
            hashed_password = generate_password_hash(password)
            
            try:
                conn = get_db_connection()
                db_execute(conn, "INSERT INTO users (username, profession, mobile_number, password) VALUES (?, ?, ?, ?)",
                             (username, profession, mobile_number, hashed_password))
                
                # LINKAGE: Link existing patients with this mobile number to this new account
                if profession == 'Patient':
                    user = db_execute(conn, "SELECT id FROM users WHERE username = ?", (username,)).fetchone()
                    if user:
                        db_execute(conn, "UPDATE patients SET patient_user_id = ? WHERE patient_mobile = ?", (user['id'], mobile_number))
                
                conn.commit()
                conn.close()
                
                # Clear session variables
                session.pop('registration_otp', None)
                session.pop('registration_mobile', None)
                
                flash('Registration successful! Please login.', 'success')
                return redirect(url_for('login'))
            except Exception as e:
                # Log the actual error for the developer
                print(f"ERROR DURING REGISTRATION DB OP: {e}", flush=True)
                flash('Username or mobile number already registered.', 'error')
        else:
            flash('Invalid or expired OTP.', 'error')
            return render_template('register.html', username=username, profession=profession, mobile=mobile_number)

    return render_template('register.html')

@app.route('/api/send_registration_otp', methods=['POST'])
def send_registration_otp():
    print(">>> Received request for /api/send_registration_otp", flush=True)
    data = request.get_json()
    if not data:
        print(">>> Error: No JSON data received in OTP request", flush=True)
        return jsonify({'success': False, 'message': 'Invalid request data'})
    
    mobile = data.get('mobile')
    
    if not mobile:
        return jsonify({'success': False, 'message': 'Mobile number is required'})

    # Check if mobile already exists
    try:
        conn = get_db_connection()
        user = db_execute(conn, 'SELECT id FROM users WHERE mobile_number = ?', (mobile,)).fetchone()
        conn.close()
        if user:
            return jsonify({'success': False, 'message': 'Mobile number already registered'})
    except Exception as e:
        print(f"DATABASE ERROR in send_registration_otp: {e}", flush=True)
        # Fallback: Proceed even if DB check fails, or inform user

    # Generate OTP
    otp = random.randint(100000, 999999)
    session['registration_otp'] = otp
    session['registration_mobile'] = mobile

    # Always print OTP to the terminal for debugging, regardless of SMS success
    print(f"\n{'*'*40}")
    print(f"DEBUG OTP for {mobile} (Registration): {otp}")
    print(f"{'*'*40}\n", flush=True)

    # Send actual SMS
    message = f"Your Telemedicine Registration OTP is: {otp}"
    response = send_sms(mobile, message)
    
    if response and response.get('return'):
        return jsonify({'success': True, 'message': 'OTP sent successfully'})
    else:
        # Fallback to console print if API fails (good for development until key is added)
        print(f"\n{'='*40}")
        print(f"SIMULATED SMS to {mobile} (Fast2SMS API failed or key missing)")
        print(f"Your Telemedicine Registration OTP is: {otp}")
        print(f"{'='*40}\n")
        return jsonify({'success': True, 'message': 'OTP sent (Check terminal if SMS failed)'})

@app.route('/forgot_password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        mobile_number = request.form['mobile']
        entered_otp = request.form.get('otp')

        if not entered_otp:
            flash('OTP is required.', 'error')
            return render_template('forgot_password.html', mobile=mobile_number)

        # Verify OTP
        session_otp = session.get('forgot_otp')
        session_mobile = session.get('forgot_mobile')

        if session_otp and str(session_otp) == str(entered_otp) and session_mobile == mobile_number:
            # OTP correct, allow resetting password
            session['reset_mobile'] = mobile_number
            session.pop('forgot_otp', None)
            session.pop('forgot_mobile', None)
            
            flash('OTP verified. Please enter your new password.', 'success')
            return redirect(url_for('reset_password'))
        else:
            flash('Invalid or expired OTP.', 'error')
            return render_template('forgot_password.html', mobile=mobile_number)

    return render_template('forgot_password.html')

@app.route('/api/send_forgot_otp', methods=['POST'])
def send_forgot_otp():
    data = request.get_json()
    mobile = data.get('mobile')
    
    if not mobile:
        return jsonify({'success': False, 'message': 'Mobile number is required'})

    # Check if mobile exists
    conn = get_db_connection()
    user = db_execute(conn, 'SELECT id FROM users WHERE mobile_number = ?', (mobile,)).fetchone()
    conn.close()

    if not user:
        return jsonify({'success': False, 'message': 'Mobile number not found'})

    # Generate OTP
    otp = random.randint(100000, 999999)
    session['forgot_otp'] = otp
    session['forgot_mobile'] = mobile

    # Always print OTP to the terminal for debugging, regardless of SMS success
    print(f"\n{'*'*40}")
    print(f"DEBUG OTP for {mobile} (Password Reset): {otp}")
    print(f"{'*'*40}\n", flush=True)

    # Send actual SMS
    message = f"Your Telemedicine Password Reset OTP is: {otp}"
    response = send_sms(mobile, message)

    if response and response.get('return'):
        return jsonify({'success': True, 'message': 'OTP sent successfully'})
    else:
        # Fallback to console print if API fails (good for development until key is added)
        print(f"\n{'='*40}")
        print(f"SIMULATED SMS to {mobile} (Fast2SMS API failed or key missing)")
        print(f"Your Telemedicine Password Reset OTP is: {otp}")
        print(f"{'='*40}\n")
        return jsonify({'success': True, 'message': 'OTP sent (Check terminal if SMS failed)'})

@app.route('/reset_password', methods=['GET', 'POST'])
def reset_password():
    if 'reset_mobile' not in session:
        flash('Unauthorized access. Please verify your mobile number first.', 'error')
        return redirect(url_for('forgot_password'))

    if request.method == 'POST':
        new_password = request.form['password']
        confirm_password = request.form['confirm_password']

        if new_password != confirm_password:
            flash('Passwords do not match.', 'error')
            return render_template('reset_password.html')

        hashed_password = generate_password_hash(new_password)
        mobile_number = session['reset_mobile']

        conn = get_db_connection()
        db_execute(conn, 'UPDATE users SET password = ? WHERE mobile_number = ?', (hashed_password, mobile_number))
        conn.commit()
        conn.close()

        session.pop('reset_mobile', None)
        flash('Password reset successful. You can now login.', 'success')
        return redirect(url_for('login'))

    return render_template('reset_password.html')

@app.route('/rural_dashboard')
def rural_dashboard():
    if 'user_id' not in session or session.get('profession') != 'Rural Doctor':
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    total_patients = db_get_count(conn, 'SELECT COUNT(*) FROM patients WHERE rural_doctor_id = ?', (session['user_id'],))
    reviewed_patients = db_get_count(conn, "SELECT COUNT(*) FROM patients WHERE rural_doctor_id = ? AND status IN ('Accepted', 'Reviewed', 'Rejected', 'Completed')", (session['user_id'],))
    pending_patients = db_get_count(conn, 'SELECT COUNT(*) FROM patients WHERE rural_doctor_id = ? AND status = ?', (session['user_id'], 'Pending'))
    
    # Get all patients for this rural doctor (Emergency first)
    patients = db_execute(conn, "SELECT p.*, s.username as specialist_name \
                             FROM patients p \
                             LEFT JOIN users s ON p.specialist_id = s.id \
                             WHERE p.rural_doctor_id = ? \
                             ORDER BY CASE WHEN p.priority = 'Emergency' THEN 0 ELSE 1 END, p.id DESC", (session['user_id'],)).fetchall()
                             
    # Get unread notifications
    notifications = db_execute(conn, 'SELECT * FROM notifications WHERE user_id = ? ORDER BY id DESC LIMIT 10', (session['user_id'],)).fetchall()
    unread_count = sum(1 for n in notifications if not n['read_status'])
    
    conn.close()
    
    return render_template('rural_dashboard.html', 
                           total=total_patients, 
                           reviewed=reviewed_patients, 
                           pending=pending_patients,
                           notifications=notifications,
                           unread_count=unread_count)

@app.route('/patient_dashboard')
def patient_dashboard():
    if 'user_id' not in session or session.get('profession') != 'Patient':
        return redirect(url_for('login'))
        
    conn = get_db_connection()
    # Fetch all cases linked to this patient 
    patients = db_execute(conn, '''
        SELECT p.*, r.username as rural_doctor_name, s.username as specialist_name 
        FROM patients p 
        LEFT JOIN users r ON p.rural_doctor_id = r.id
        LEFT JOIN users s ON p.specialist_id = s.id
        WHERE p.patient_user_id = ? 
        ORDER BY p.id DESC
    ''', (session['user_id'],)).fetchall()
    
    notifications = db_execute(conn, 'SELECT * FROM notifications WHERE user_id = ? ORDER BY id DESC LIMIT 10', (session['user_id'],)).fetchall()
    unread_count = sum(1 for n in notifications if not n['read_status'])
    conn.close()
    
    return render_template('patient_dashboard.html', patients=patients, notifications=notifications, unread_count=unread_count)

@app.route('/patient_case/<int:patient_id>')
def patient_case_view(patient_id):
    if 'user_id' not in session or session.get('profession') != 'Patient':
        return redirect(url_for('login'))
        
    conn = get_db_connection()
    # Verify ownership
    patient = db_execute(conn, 'SELECT * FROM patients WHERE id = ? AND patient_user_id = ?', (patient_id, session['user_id'])).fetchone()
    
    if not patient:
        conn.close()
        flash('Case not found or unauthorized access.', 'error')
        return redirect(url_for('patient_dashboard'))
        
    messages = db_execute(conn, 'SELECT m.*, u.username, u.profession FROM messages m JOIN users u ON m.sender_id = u.id WHERE m.patient_id = ? ORDER BY m.timestamp ASC', (patient_id,)).fetchall()
    
    rural_doctor = db_execute(conn, 'SELECT id, username, status, profession FROM users WHERE id = ?', (patient['rural_doctor_id'],)).fetchone()
    specialist = None
    if patient['specialist_id']:
        specialist = db_execute(conn, 'SELECT id, username, status, profession FROM users WHERE id = ?', (patient['specialist_id'],)).fetchone()
    
    notifications = db_execute(conn, 'SELECT * FROM notifications WHERE user_id = ? ORDER BY id DESC LIMIT 10', (session['user_id'],)).fetchall()
    unread_count = sum(1 for n in notifications if not n['read_status'])
    conn.close()
    
    return render_template('patient_case_view.html', patient=patient, messages=messages, rural_doctor=rural_doctor, specialist=specialist, notifications=notifications, unread_count=unread_count)

@app.route('/my_patients')
def my_patients():
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    priority_filter = request.args.get('priority', '')
    status_filter = request.args.get('status', '')
    
    conn = get_db_connection()
    if session['profession'] == 'Rural Doctor':
        # Rural Doctors see all patients they submitted
        patients = db_execute(conn, '''
            SELECT p.*, s.username as specialist_name, s.status as specialist_status
            FROM patients p 
            LEFT JOIN users s ON p.specialist_id = s.id 
            WHERE p.rural_doctor_id = ? 
            ORDER BY CASE WHEN p.priority = 'Emergency' THEN 0 ELSE 1 END, p.id DESC
        ''', (session['user_id'],)).fetchall()
    else: 
        # Specialists see only their specialty AND assigned to them (or unassigned/pending)
        query = '''
            SELECT p.*, r.username as rural_doctor_name, r.status as doctor_status
            FROM patients p 
            JOIN users r ON p.rural_doctor_id = r.id 
            WHERE p.specialist_type = ? AND (CAST(p.specialist_id AS INTEGER) = CAST(? AS INTEGER) OR p.status = 'Pending')
        '''
        params = [session['profession'], session['user_id']]
        
        if priority_filter:
            query += ' AND p.priority = ?'
            params.append(priority_filter)
        if status_filter:
            query += ' AND p.status = ?'
            params.append(status_filter)
            
        query += " ORDER BY CASE WHEN p.priority = 'Emergency' THEN 0 ELSE 1 END, p.id DESC"
        patients = db_execute(conn, query, params).fetchall()
    
    notifications = db_execute(conn, 'SELECT * FROM notifications WHERE user_id = ? ORDER BY id DESC LIMIT 10', (session['user_id'],)).fetchall()
    unread_count = sum(1 for n in notifications if not n['read_status'])
    conn.close()
    
    return render_template('my_patients.html', patients=patients, notifications=notifications, unread_count=unread_count)

@app.route('/pending_requests')
def pending_requests():
    if 'user_id' not in session or session.get('profession') not in SPECIALIST_ROLES:
        return redirect(url_for('login'))
        
    priority_filter = request.args.get('priority', '')
    conn = get_db_connection()
    
    query = '''
        SELECT p.*, r.username as rural_doctor_name, r.status as doctor_status 
        FROM patients p 
        JOIN users r ON p.rural_doctor_id = r.id 
        WHERE p.status = ? AND p.specialist_type = ? AND (p.specialist_id = ? OR p.specialist_id IS NULL)
    '''
    params = ['Pending', session['profession'], session['user_id']]
    
    if priority_filter:
        query += ' AND p.priority = ?'
        params.append(priority_filter)
        
    query += " ORDER BY CASE WHEN p.priority = 'Emergency' THEN 0 ELSE 1 END, p.id DESC"
    
    patients = db_execute(conn, query, params).fetchall()
    
    notifications = db_execute(conn, 'SELECT * FROM notifications WHERE user_id = ? ORDER BY id DESC LIMIT 10', (session['user_id'],)).fetchall()
    unread_count = sum(1 for n in notifications if not n['read_status'])
    conn.close()
    
    return render_template('pending_requests.html', pending=patients, notifications=notifications, unread_count=unread_count)

@app.route('/active_chats')
def active_chats():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    # Fetch patients that have at least one message
    patients = db_execute(conn, '''
        SELECT DISTINCT p.*, s.username as specialist_name, r.username as rural_doctor_name,
                        s.status as specialist_status, r.status as doctor_status
        FROM patients p
        JOIN messages m ON p.id = m.patient_id
        LEFT JOIN users s ON p.specialist_id = s.id
        LEFT JOIN users r ON p.rural_doctor_id = r.id
        WHERE (p.rural_doctor_id = ? OR p.specialist_id = ?)
        ORDER BY p.id DESC
    ''', (session['user_id'], session['user_id'])).fetchall()
    
    notifications = db_execute(conn, 'SELECT * FROM notifications WHERE user_id = ? ORDER BY id DESC LIMIT 10', (session['user_id'],)).fetchall()
    unread_count = sum(1 for n in notifications if not n['read_status'])
    conn.close()
    
    return render_template('active_chats.html', patients=patients, notifications=notifications, unread_count=unread_count)

@app.route('/reports_view')
def reports_view():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    # Patients with reports
    patients = db_execute(conn, '''
        SELECT p.*, s.username as specialist_name, r.username as rural_doctor_name,
               s.status as specialist_status, r.status as doctor_status
        FROM patients p 
        LEFT JOIN users s ON p.specialist_id = s.id
        LEFT JOIN users r ON p.rural_doctor_id = r.id
        WHERE (p.rural_doctor_id = ? OR p.specialist_id = ?) AND p.report_file != ''
    ''', (session['user_id'], session['user_id'])).fetchall()
    
    notifications = db_execute(conn, 'SELECT * FROM notifications WHERE user_id = ? ORDER BY id DESC LIMIT 10', (session['user_id'],)).fetchall()
    unread_count = sum(1 for n in notifications if not n['read_status'])
    conn.close()
    
    return render_template('reports_view.html', patients=patients, notifications=notifications, unread_count=unread_count)

@app.route('/ai_assistant')
def ai_assistant():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    notifications = db_execute(conn, 'SELECT * FROM notifications WHERE user_id = ? ORDER BY id DESC LIMIT 10', (session['user_id'],)).fetchall()
    unread_count = sum(1 for n in notifications if not n['read_status'])
    conn.close()
    
    return render_template('ai_assistant_page.html', notifications=notifications, unread_count=unread_count)

@app.route('/api/suggest_specialist', methods=['POST'])
def suggest_specialist_endpoint():
    data = request.get_json()
    symptoms = data.get('symptoms', '')
    if not symptoms:
        return jsonify({'success': False, 'message': 'No symptoms provided'})
    
    specialist = suggest_specialist_ai(symptoms)
    return jsonify({
        'success': True, 
        'specialist': specialist,
        'reason': f"Based on symptoms like '{symptoms[:30]}...', we recommend a {specialist}."
    })

@app.route('/add_patient', methods=['POST'])
def add_patient():
    if 'user_id' not in session or session.get('profession') != 'Rural Doctor':
        return redirect(url_for('login'))

    conn = get_db_connection()
    try:
        patient_name = request.form['patient_name']
        patient_mobile = request.form.get('patient_mobile', '')
        age_raw = request.form.get('age', '')
        age = int(age_raw) if age_raw.strip().isdigit() else None
        
        gender = request.form.get('gender', 'Other')
        specialist_type = request.form.get('specialist_type', 'Neurologist')
        blood_pressure = request.form.get('blood_pressure', '')
        
        heart_rate_raw = request.form.get('heart_rate', '')
        heart_rate = int(heart_rate_raw) if heart_rate_raw.strip().isdigit() else None
        
        oxygen_raw = request.form.get('oxygen_level', '')
        oxygen_level = int(oxygen_raw) if oxygen_raw.strip().isdigit() else None
        problem_description = request.form.get('problem_description', '')
        priority = request.form.get('priority', 'Normal')
        is_online = False
        
        # AI Assistance: Auto-Priority and Suggestion
        ai_priority = detect_emergency_ai(problem_description, 
                                         request.form.get('consciousness_level', 'Alert'),
                                         oxygen_level, heart_rate)
        
        if ai_priority == 'Emergency':
            priority = 'Emergency'
            flash('AI System detected a potential emergency and set priority to high.', 'warning')

        # Smart Allocation (Manual override logic)
        manual_id = request.form.get('assigned_specialist_id')
        if manual_id and manual_id.isdigit():
            specialist_id = int(manual_id)
            # Fetch name for flash message
            spec_user = db_execute(conn, 'SELECT username FROM users WHERE id = ?', (specialist_id,)).fetchone()
            assigned_doctor_name = spec_user['username'] if spec_user else "Specialist"
        else:
            # Fallback to auto-allocation if not specified
            specialist_id, assigned_doctor_name, is_online = find_best_specialist(specialist_type)
        
        # Specialty parameters
        consciousness_level = request.form.get('consciousness_level', 'Alert')
        speech_condition = request.form.get('speech_condition', 'Normal')
        motor_function = request.form.get('motor_function', 'Normal')
        
        seizure_history = request.form.get('seizure_history', 'No')
        tumor_details = request.form.get('tumor_details', '')
        cancer_history = request.form.get('cancer_history', '')
        kidney_function = request.form.get('kidney_function', '')
        urine_reports = request.form.get('urine_reports', '')
        skin_condition = request.form.get('skin_condition', '')
        rash_description = request.form.get('rash_description', '')
        breathing_condition = request.form.get('breathing_condition', '')

        # Ensure headache_severity is safe for both TEXT and logic (default to '0')
        headache_severity = request.form.get('headache_severity', '0')
        if not str(headache_severity).strip():
            headache_severity = '0'

        report_file = ''
        if 'report_file' in request.files:
            file = request.files['report_file']
            if file and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                filename = f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{filename}"
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                report_file = filename

        # Robust Mobile Normalization: Link accounts even if formatting differs (spaces, +, dashes)
        clean_mobile = "".join(filter(str.isdigit, patient_mobile))
        patient_user = None
        if len(clean_mobile) >= 10:
            last_10 = clean_mobile[-10:]
            # Search for any user whose number ends in these same 10 digits
            patient_user = db_execute(conn, "SELECT id FROM users WHERE mobile_number LIKE ? AND profession = 'Patient'", (f'%{last_10}',)).fetchone()
        
        # Fallback to exact match if normalization failed or was ambiguous
        if not patient_user:
            patient_user = db_execute(conn, "SELECT id FROM users WHERE mobile_number = ? AND profession = 'Patient'", (patient_mobile,)).fetchone()
            
        patient_user_id = patient_user['id'] if patient_user else None

        # For Postgres, we can use INSERT ... RETURNING id
        is_postgres = DATABASE_URL is not None
        insert_sql = '''
            INSERT INTO patients (
                patient_name, patient_mobile, patient_user_id, age, gender, blood_pressure, heart_rate, oxygen_level, 
                problem_description, report_file, rural_doctor_id, priority, 
                specialist_type, specialist_id, consciousness_level, speech_condition, 
                motor_function, headache_severity, seizure_history, tumor_details, 
                cancer_history, kidney_function, urine_reports, skin_condition, 
                rash_description, breathing_condition, priority_level, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        '''
        params = (
            patient_name, patient_mobile, patient_user_id, age, gender, blood_pressure, heart_rate, oxygen_level, 
            problem_description, report_file, session['user_id'], priority, 
            specialist_type, specialist_id, consciousness_level, speech_condition, 
            motor_function, headache_severity, seizure_history, tumor_details, 
            cancer_history, kidney_function, urine_reports, skin_condition, 
            rash_description, breathing_condition, priority, 'Pending'
        )
        
        if is_postgres:
            cur = db_execute(conn, insert_sql + ' RETURNING id', params)
            patient_id = cur.fetchone()['id']
        else:
            cur = db_execute(conn, insert_sql, params)
            patient_id = cur.lastrowid
        
        # Handle initial medical images if provided
        if 'medical_images' in request.files:
            files = request.files.getlist('medical_images')
            for file in files:
                if file and allowed_file(file.filename):
                    filename = secure_filename(file.filename)
                    filename = f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{filename}"
                    file.save(os.path.join(app.config['IMAGING_FOLDER'], filename))
                    
                    ext = filename.rsplit('.', 1)[1].lower() if '.' in filename else 'other'
                    modality = request.form.get('dicom_modality', 'CT Scan') if ext == 'dcm' else 'EEG' if ext in ['edf', 'csv'] else 'Other'
                    
                    db_execute(conn,
                        'INSERT INTO medical_images (patient_id, file_path, modality, sequence_type) VALUES (?, ?, ?, ?)',
                        (patient_id, filename, modality, 'Standard')
                    )
        
        # Calculate Risk and Prediction
        risk_level = calculate_risk_score(problem_description, blood_pressure, oxygen_level, heart_rate, consciousness_level)
        predicted_condition = predict_disease(problem_description, specialist_type)
        
        # Update patient with AI results
        db_execute(conn, 'UPDATE patients SET risk_level = ?, predicted_condition = ? WHERE id = ?', 
                    (risk_level, predicted_condition, patient_id))
        
        # Personalized Notification
        msg = f"New {specialist_type} Case: {patient_name}"
        if priority == 'Emergency':
            msg = f"🚨 {specialist_type.upper()} EMERGENCY: {patient_name}"
        
        if specialist_id:
            status_msg = "Online" if is_online else "Waiting"
            notif_msg = f"{msg} (Assigned to you: {status_msg})"
            create_notification(specialist_id, notif_msg, url_for('specialist_dashboard'), patient_id=patient_id, conn=conn)
        else:
            # Fallback: Notify all specialists
            specialists = db_execute(conn, 'SELECT id FROM users WHERE profession = ?', (specialist_type,)).fetchall()
            for spec in specialists:
                create_notification(spec['id'], msg, url_for('specialist_dashboard'), patient_id=patient_id, conn=conn)
            
        conn.commit()
        conn.close()
        
        success_msg = f"Patient case added successfully! Assigned to Dr. {assigned_doctor_name}" if assigned_doctor_name else "Patient case added successfully!"
        flash(success_msg, 'success')
        return redirect(url_for('rural_dashboard'))
    except Exception as e:
        error_msg = f"CRITICAL SUBMISSION ERROR: {str(e)}"
        print(error_msg)
        traceback.print_exc()
        if conn:
            try: conn.rollback()
            except: pass
            try: conn.close()
            except: pass
        flash(error_msg, 'error')
        return redirect(url_for('rural_dashboard'))

@app.route('/upload_imaging/<int:patient_id>', methods=['POST'])
def upload_imaging(patient_id):
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401
        
    if 'imaging_file' not in request.files:
        return jsonify({'success': False, 'message': 'No file part'}), 400
        
    file = request.files['imaging_file']
    modality = request.form.get('modality', 'CT Scan')
    sequence_type = request.form.get('sequence_type', 'Standard')
    
    if file.filename == '':
        return jsonify({'success': False, 'message': 'No selected file'}), 400
        
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        filename = f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{filename}"
        file.save(os.path.join(app.config['IMAGING_FOLDER'], filename))
        
        conn = get_db_connection()
        db_execute(conn,
            'INSERT INTO medical_images (patient_id, file_path, modality, sequence_type) VALUES (?, ?, ?, ?)',
            (patient_id, filename, modality, sequence_type)
        )
        conn.commit()
        conn.close()
        
        return jsonify({'success': True, 'message': 'Imaging file uploaded successfully', 'file_path': filename})
        
    return jsonify({'success': False, 'message': 'Invalid file type'}), 400

@app.route('/delete_patient/<int:patient_id>', methods=['POST'])
def delete_patient(patient_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    conn = get_db_connection()
    db_execute(conn, 'DELETE FROM patients WHERE id = ?', (patient_id,))
    db_execute(conn, 'DELETE FROM messages WHERE patient_id = ?', (patient_id,))
    db_execute(conn, 'DELETE FROM notifications WHERE patient_id = ?', (patient_id,))
    db_execute(conn, 'DELETE FROM medical_images WHERE patient_id = ?', (patient_id,))
    conn.commit()
    conn.close()
    
    flash('Patient case deleted successfully.', 'success')
    if session.get('profession') == 'Rural Doctor':
        return redirect(url_for('rural_dashboard'))
    return redirect(url_for('specialist_dashboard'))

@app.route('/imaging_file/<filename>')
def imaging_file(filename):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    file_path = os.path.join(app.config['IMAGING_FOLDER'], filename)
    if not os.path.exists(file_path):
        print(f">>> [DICOM ALERT] File missing from disk: {filename}. It may have been deleted by a server redeploy.", flush=True)
        return "File not found on server. It may have been deleted by a redeploy.", 404
        
    return send_from_directory(app.config['IMAGING_FOLDER'], filename)

@app.route('/api/patient_images/<int:patient_id>')
def api_patient_images(patient_id):
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401
        
    conn = get_db_connection()
    images = db_execute(conn, 'SELECT * FROM medical_images WHERE patient_id = ? ORDER BY uploaded_at DESC', (patient_id,)).fetchall()
    conn.close()
    
    images_list = [{'id': img['id'], 'file_path': img['file_path'], 'modality': img['modality'], 'sequence_type': img['sequence_type'], 'uploaded_at': img['uploaded_at']} for img in images]
    return jsonify({'success': True, 'images': images_list})

@app.route('/imaging_viewer/<int:patient_id>')
def imaging_viewer(patient_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    conn = get_db_connection()
    patient = db_execute(conn, 'SELECT * FROM patients WHERE id = ?', (patient_id,)).fetchone()
    if not patient:
        conn.close()
        return "Patient not found", 404

    # Get existing images
    images = db_execute(conn, 'SELECT * FROM medical_images WHERE patient_id = ? ORDER BY uploaded_at DESC', (patient_id,)).fetchall()
    conn.close()

    # Allow for individual file viewing (e.g. from chat)
    view_file = request.args.get('file_path')
    images_list = [dict(img) for img in images]
    
    if view_file:
        exists = any(img['file_path'] == view_file for img in images_list)
        if not exists:
            ext = view_file.rsplit('.', 1)[1].lower() if '.' in view_file else ''
            modality = 'CT Scan' if ext == 'dcm' else 'EEG' if ext in ['edf', 'csv'] else 'Other'
            images_list.insert(0, {
                'file_path': view_file,
                'modality': modality,
                'sequence_type': 'Consultation Image',
                'uploaded_at': 'Just now'
            })

    return render_template('imaging_viewer.html', patient=patient, images=images_list)



@app.route('/analytics')
def analytics_dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    conn = get_db_connection()
    
    # 1. Total Cases by Specialty
    specialty_data = db_execute(conn, 'SELECT specialist_type, COUNT(*) as count FROM patients GROUP BY specialist_type').fetchall()
    specialty_labels = [r['specialist_type'] for r in specialty_data]
    specialty_counts = [r['count'] for r in specialty_data]
    
    # 2. Risk Level Distribution
    risk_data = db_execute(conn, 'SELECT risk_level, COUNT(*) as count FROM patients GROUP BY risk_level').fetchall()
    # Ensure standard order: Low, Medium, High
    risk_order = ['Low', 'Medium', 'High']
    risk_dict = {r['risk_level']: r['count'] for r in risk_data}
    risk_labels = [lvl for lvl in risk_order if lvl in risk_dict]
    risk_counts = [risk_dict[lvl] for lvl in risk_labels]
    
    # 3. Monthly Trends
    if DATABASE_URL:
        # PostgreSQL syntax for month
        trend_data = db_execute(conn, "SELECT to_char(created_at, 'YYYY-MM') as month, COUNT(*) as count FROM patients GROUP BY month ORDER BY month ASC LIMIT 12").fetchall()
    else:
        # SQLite syntax for month
        trend_data = db_execute(conn, "SELECT strftime('%Y-%m', created_at) as month, COUNT(*) as count FROM patients GROUP BY month ORDER BY month ASC LIMIT 12").fetchall()
    
    trend_labels = [r['month'] for r in trend_data]
    trend_counts = [r['count'] for r in trend_data]
    
    # 4. General Stats
    stats = {
        'total': db_get_count(conn, 'SELECT COUNT(*) FROM patients'),
        'high_risk': db_get_count(conn, "SELECT COUNT(*) FROM patients WHERE risk_level = 'High'"),
        'reviewed': db_get_count(conn, "SELECT COUNT(*) FROM patients WHERE status = 'Reviewed'"),
        'pending': db_get_count(conn, "SELECT COUNT(*) FROM patients WHERE status = 'Pending'")
    }
    
    # Notifications for header
    notifications = db_execute(conn, 'SELECT * FROM notifications WHERE user_id = ? ORDER BY id DESC LIMIT 10', (session['user_id'],)).fetchall()
    unread_count = sum(1 for n in notifications if not n['read_status'])
    
    conn.close()
    
    return render_template('analytics.html', 
                           specialty_labels=specialty_labels, specialty_counts=specialty_counts,
                           risk_labels=risk_labels, risk_counts=risk_counts,
                           trend_labels=trend_labels, trend_counts=trend_counts,
                           stats=stats,
                           unread_count=unread_count,
                           notifications=notifications)

@app.route('/case_history')
def case_history():
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    status_filter = request.args.get('status', '')
    priority_filter = request.args.get('priority', '')
    search_query = request.args.get('search', '')
    sort_by = request.args.get('sort', 'latest')
    
    conn = get_db_connection()
    
    query = 'SELECT * FROM patients WHERE (CAST(rural_doctor_id AS INTEGER) = CAST(? AS INTEGER) OR CAST(specialist_id AS INTEGER) = CAST(? AS INTEGER))'
    params = [session['user_id'], session['user_id']]
    
    if status_filter:
        if status_filter == 'Reviewed':
            query += ' AND status IN (?, ?)'
            params.extend(['Reviewed', 'Completed'])
        else:
            query += ' AND status = ?'
            params.append(status_filter)
        
    if priority_filter:
        query += ' AND priority = ?'
        params.append(priority_filter)
        
    if search_query:
        query += ' AND patient_name LIKE ?'
        params.append(f'%{search_query}%')
        
    if sort_by == 'emergency':
        query += " ORDER BY CASE WHEN priority = 'Emergency' THEN 0 ELSE 1 END, id DESC"
    else:
        query += ' ORDER BY id DESC'
        
    patients = db_execute(conn, query, params).fetchall()
    
    # Get unread notifications for the header
    notifications = db_execute(conn, 'SELECT * FROM notifications WHERE user_id = ? ORDER BY id DESC LIMIT 10', (session['user_id'],)).fetchall()
    unread_count = sum(1 for n in notifications if not n['read_status'])
    
    conn.close()
    
    return render_template('case_history.html', patients=patients, unread_count=unread_count, notifications=notifications)

# --- Chatbot / Query Handling ---
@app.route('/ping')
def ping():
    return "PONG", 200

@app.route('/chatbot/query', methods=['POST'])
def chatbot_query():
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Unauthorized'})
        
    data = request.get_json()
    user_query = data.get('query')
    patient_id = data.get('patient_id')
    
    if not user_query:
        return jsonify({'success': False, 'error': 'Empty query'})
        
    try:
        response = process_chatbot_query(user_query, session['user_id'], patient_id=patient_id)
        return jsonify({'success': True, 'response': response})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/specialist_dashboard')
def specialist_dashboard():
    if 'user_id' not in session or session.get('profession') not in SPECIALIST_ROLES:
        return redirect(url_for('login'))
        
    conn = None
    try:
        conn = get_db_connection()
        pending_patients = db_execute(conn, "SELECT p.*, r.username as rural_doctor_name, r.status as doctor_status \
                                        FROM patients p \
                                        JOIN users r ON p.rural_doctor_id = r.id \
                                        WHERE p.status = ? AND p.specialist_type = ? AND (p.specialist_id = ? OR p.specialist_id IS NULL) \
                                        ORDER BY CASE WHEN p.priority = 'Emergency' THEN 0 ELSE 1 END, p.id DESC", ('Pending', session['profession'], session['user_id'])).fetchall()
        
        accepted_patients = db_execute(conn, "SELECT p.*, r.username as rural_doctor_name \
                                          FROM patients p \
                                          JOIN users r ON p.rural_doctor_id = r.id \
                                          WHERE p.specialist_id = ? AND p.status IN (?, ?, ?) \
                                          ORDER BY CASE WHEN p.priority = 'Emergency' THEN 0 ELSE 1 END, p.id DESC", 
                                          (session['user_id'], 'Accepted', 'Reviewed', 'Completed')).fetchall()
                                          
        total_system_patients = db_get_count(conn, 'SELECT COUNT(*) FROM patients WHERE specialist_type = ? AND (specialist_id = ? OR specialist_id IS NULL)', (session['profession'], session['user_id']))
        total_pending_patients = db_get_count(conn, 'SELECT COUNT(*) FROM patients WHERE status = ? AND specialist_type = ? AND (specialist_id = ? OR specialist_id IS NULL)', ('Pending', session['profession'], session['user_id']))
        
        specialty_stats = {
            'emergency_cases': db_get_count(conn, "SELECT COUNT(*) FROM patients WHERE priority = 'Emergency' AND specialist_type = ?", (session['profession'],)),
            'reviewed_cases': db_get_count(conn, "SELECT COUNT(*) FROM patients WHERE status = 'Reviewed' AND specialist_id = ?", (session['user_id'],)),
            'stroke_suspicion': 0,
            'heart_critical': 0
        }
        
        if session['profession'] == 'Neurologist':
            specialty_stats['stroke_suspicion'] = db_get_count(conn, "SELECT COUNT(*) FROM patients WHERE specialist_type = 'Neurologist' AND (consciousness_level = 'Unconscious' OR speech_condition != 'Normal')")
        elif session['profession'] == 'Cardiologist':
            # Use CAST and COALESCE to be ultra-safe on Postgres
            specialty_stats['heart_critical'] = db_get_count(conn, "SELECT COUNT(*) FROM patients WHERE specialist_type = 'Cardiologist' AND (CAST(COALESCE(CAST(heart_rate AS TEXT), '0') AS INTEGER) > 100 OR CAST(COALESCE(CAST(heart_rate AS TEXT), '0') AS INTEGER) < 60 AND heart_rate IS NOT NULL)")
    
        notifications = db_execute(conn, 'SELECT * FROM notifications WHERE user_id = ? ORDER BY id DESC LIMIT 10', (session['user_id'],)).fetchall()
        unread_count = sum(1 for n in notifications if not n['read_status'])
        conn.close()
        
        return render_template('specialist_dashboard.html', 
                               pending=pending_patients, 
                               accepted=accepted_patients,
                               total=total_system_patients,
                               pending_count=total_pending_patients,
                               specialty_stats=specialty_stats,
                               notifications=notifications,
                               unread_count=unread_count)
    except Exception as e:
        if conn:
            try: conn.close()
            except: pass
        print(f">>> [DASHBOARD ERROR] {session['profession']}: {str(e)}")
        traceback.print_exc()
        flash(f"Dashboard Diagnostic: {str(e)}. Please retry.", "error")
        return redirect(url_for('login'))

@app.route('/update_case_status/<int:patient_id>', methods=['POST'])
def update_case_status(patient_id):
    if 'user_id' not in session or session.get('profession') not in SPECIALIST_ROLES:
        return redirect(url_for('login'))
        
    action = request.form.get('action')
    status = 'Rejected'
    if action == 'accept':
        status = 'Accepted'
        
    conn = get_db_connection()
    db_execute(conn, 'UPDATE patients SET status = ?, specialist_id = ? WHERE id = ?', (status, session['user_id'], patient_id))
    
    # Notify rural doctor
    patient = db_execute(conn, 'SELECT patient_name, rural_doctor_id FROM patients WHERE id = ?', (patient_id,)).fetchone()
    if patient:
        create_notification(patient['rural_doctor_id'], f"Case {status}: {patient['patient_name']}", url_for('rural_dashboard'), patient_id=patient_id, conn=conn)
        
    conn.commit()
    conn.close()
    
    flash(f'Case {status.lower()} successfully.', 'success')
    return redirect(url_for('specialist_dashboard'))

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.route('/chat/<int:patient_id>')
def chat(patient_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    conn = get_db_connection()
    patient = db_execute(conn, 'SELECT * FROM patients WHERE id = ?', (patient_id,)).fetchone()
    
    if not patient:
        conn.close()
        flash('Patient not found.', 'error')
        return redirect(url_for('dashboard'))
        
    if session.get('profession') == 'Rural Doctor' and patient['rural_doctor_id'] != session['user_id']:
        conn.close()
        flash('Unauthorized access.', 'error')
        return redirect(url_for('rural_dashboard'))
    elif session.get('profession') in SPECIALIST_ROLES and patient['specialist_id'] != session['user_id']:
        conn.close()
        flash('Unauthorized access.', 'error')
        return redirect(url_for('specialist_dashboard'))
        
    messages = db_execute(conn, 'SELECT m.*, u.username, u.profession FROM messages m JOIN users u ON m.sender_id = u.id WHERE m.patient_id = ? ORDER BY m.timestamp ASC', (patient_id,)).fetchall()
    
    # Get doctor details for UI and status sync
    rural_doctor = db_execute(conn, 'SELECT id, username, status, profession FROM users WHERE id = ?', (patient['rural_doctor_id'],)).fetchone()
    specialist = None
    if patient['specialist_id']:
        specialist = db_execute(conn, 'SELECT id, username, status, profession FROM users WHERE id = ?', (patient['specialist_id'],)).fetchone()
    
    conn.close()
    
    return render_template('patient_chat.html', patient=patient, messages=messages, rural_doctor=rural_doctor, specialist=specialist, SPECIALIST_ROLES=SPECIALIST_ROLES)

    return redirect(url_for('chat', patient_id=patient_id))

@app.route('/upload_chat_attachment/<int:patient_id>', methods=['POST'])
def upload_chat_attachment(patient_id):
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401
        
    if 'file' not in request.files:
        return jsonify({'success': False, 'message': 'No file part'}), 400
        
    file = request.files['file']
    if file.filename == '':
        return jsonify({'success': False, 'message': 'No selected file'}), 400
        
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        filename = f"chat_{patient_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}_{filename}"
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        return jsonify({'success': True, 'filename': filename})
    
    return jsonify({'success': False, 'message': 'File type not allowed'}), 400



@socketio.on('connect')
def handle_connect():
    if 'user_id' in session:
        room = f"user_{session['user_id']}"
        join_room(room)
        
        conn = get_db_connection()
        db_execute(conn, "UPDATE users SET status = 'Online' WHERE id = ?", (session['user_id'],))
        conn.commit()
        conn.close()
        emit('status_change', {'user_id': session['user_id'], 'status': 'Online'}, broadcast=True)

@socketio.on('disconnect')
def handle_disconnect():
    if 'user_id' in session:
        conn = get_db_connection()
        db_execute(conn, "UPDATE users SET status = 'Offline' WHERE id = ?", (session['user_id'],))
        conn.commit()
        conn.close()
        emit('status_change', {'user_id': session['user_id'], 'status': 'Offline'}, broadcast=True)

@socketio.on('join_room')
def handle_join_room(data):
    patient_id = data.get('patient_id')
    if patient_id:
        room = f"patient_{patient_id}"
        join_room(room)
        print(f"User {session.get('user_id')} joined room {room}")

@socketio.on('leave_room')
def handle_leave_room(data):
    patient_id = data.get('patient_id')
    if patient_id:
        room = f"patient_{patient_id}"
        leave_room(room)
        print(f"User {session.get('user_id')} left room {room}")

@socketio.on('send_message')
def handle_socket_message(data):
    patient_id = data.get('patient_id')
    message_text = data.get('message')
    file_path = data.get('file_path') # Optional attachment
    room = f"patient_{patient_id}"

    if not all([patient_id, 'user_id' in session]) or (not message_text and not file_path):
        return
        
    sender_id = session['user_id']
    username = session.get('username')
    profession = session.get('profession')

    # Save to database
    conn = get_db_connection()
    db_execute(conn, 'INSERT INTO messages (patient_id, sender_id, message, file_path) VALUES (?, ?, ?, ?)', 
                 (patient_id, sender_id, message_text, file_path))
    
    # Auto-transition to In Consultation if current status is Accepted
    patient_status = db_execute(conn, 'SELECT status, patient_user_id FROM patients WHERE id = ?', (patient_id,)).fetchone()
    if patient_status and patient_status['status'] == 'Accepted':
        db_execute(conn, "UPDATE patients SET status = 'In Consultation' WHERE id = ?", (patient_id,))
        socketio.emit('status_update', {'patient_id': patient_id, 'status': 'In Consultation'}, room=room)
        if patient_status['patient_user_id']:
            create_notification(patient_status['patient_user_id'], f"Consultation started: Specialist has sent a message.", url_for('patient_case_view', patient_id=patient_id), patient_id=patient_id, conn=conn)
    
    # Notify the other doctor
    patient = db_execute(conn, 'SELECT rural_doctor_id, specialist_id, patient_name FROM patients WHERE id = ?', (patient_id,)).fetchone()
    if patient:
        other_id = patient['specialist_id'] if sender_id == patient['rural_doctor_id'] else patient['rural_doctor_id']
        if other_id:
            create_notification(other_id, f"New message regarding {patient['patient_name']}", url_for('chat', patient_id=patient_id), patient_id=patient_id, conn=conn)
    
    conn.commit()
    conn.close()

    # Emit message to everyone in the room
    current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    emit('receive_message', {
        'patient_id': patient_id,
        'sender_id': sender_id,
        'username': username,
        'profession': profession,
        'message': message_text,
        'file_path': file_path,
        'timestamp': current_time
    }, room=room)

@app.route('/handle_notification/<int:notif_id>')
def handle_notification(notif_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    conn = get_db_connection()
    notif = db_execute(conn, 'SELECT * FROM notifications WHERE id = ? AND user_id = ?', (notif_id, session['user_id'])).fetchone()
    
    if notif:
        db_execute(conn, 'UPDATE notifications SET read_status = TRUE WHERE id = ?', (notif_id,))
        conn.commit()
        link = notif['link']
        conn.close()
        return redirect(link)
    
    conn.close()
    return redirect(url_for('dashboard'))

@app.route('/mark_notifications_read', methods=['POST'])
def mark_notifications_read():
    if 'user_id' not in session:
        return jsonify({'success': False})
    
    conn = get_db_connection()
    db_execute(conn, 'UPDATE notifications SET read_status = 1 WHERE user_id = ?', (session['user_id'],))
    conn.commit()
    conn.close()
    
    return jsonify({'success': True})

@app.route('/accept_case/<int:patient_id>', methods=['POST'])
def accept_case(patient_id):
    if 'user_id' not in session or session.get('profession') not in SPECIALIST_ROLES:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401
    
    conn = get_db_connection()
    patient = db_execute(conn, 'SELECT * FROM patients WHERE id = ?', (patient_id,)).fetchone()
    if not patient:
        conn.close()
        return jsonify({'success': False, 'message': 'Patient not found'}), 404
        
    db_execute(conn, 'UPDATE patients SET status = ?, specialist_id = ? WHERE id = ?', ('Accepted', session['user_id'], patient_id))
    create_notification(patient['rural_doctor_id'], f"Case Accepted: {patient['patient_name']}", url_for('rural_dashboard'), patient_id=patient_id, conn=conn)
    if patient['patient_user_id']:
        create_notification(patient['patient_user_id'], f"Case Accepted: Dr. {session['username']} has taken your case.", url_for('patient_case_view', patient_id=patient_id), patient_id=patient_id, conn=conn)
    
    conn.commit()
    conn.close()
    return jsonify({'success': True, 'message': 'Case accepted successfully'})

def generate_pdf_report(patient_id, filename, diagnosis, recommendations):
    print(f">>> [PDF-GEN] Starting PDF generation for patient {patient_id} into {filename}", flush=True)
    try:
        conn = get_db_connection()
        patient = db_execute(conn, 'SELECT * FROM patients WHERE id = ?', (patient_id,)).fetchone()
        messages = db_execute(conn, 'SELECT m.message, m.timestamp, u.username FROM messages m JOIN users u ON m.sender_id = u.id WHERE m.patient_id = ? ORDER BY m.timestamp ASC', (patient_id,)).fetchall()
        conn.close()
    except Exception as e:
        print(f">>> [PDF-ERROR] Initial DB fetch failed: {e}", flush=True)
        return None

    if not patient:
        return None

    patient_dict = dict(patient)

    file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    doc = SimpleDocTemplate(file_path, pagesize=letter)
    styles = getSampleStyleSheet()
    elements = []

    # Title
    safe_name = patient_dict.get('patient_name') or 'Unknown Patient'
    elements.append(Paragraph(f"Medical Report: {safe_name}", styles['Title']))
    elements.append(Spacer(1, 12))

    # Patient Info Table
    data = [
        ['Field', 'Value'],
        ['Age', str(patient_dict.get('age') or 'N/A')],
        ['Gender', str(patient_dict.get('gender') or 'N/A')],
        ['Specialty', str(patient_dict.get('specialist_type') or 'N/A')],
        ['Blood Pressure', str(patient_dict.get('blood_pressure') or 'N/A')],
        ['Oxygen Level', str(patient_dict.get('oxygen_level') or 'N/A')],
        ['Heart Rate', str(patient_dict.get('heart_rate') or 'N/A')],
        ['Risk Level', str(patient_dict.get('risk_level') or 'Low')],
    ]
    t = Table(data, colWidths=[200, 300])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('PADDING', (0, 0), (-1, -1), 6)
    ]))
    elements.append(t)
    elements.append(Spacer(1, 24))

    # Diagnosis and Recommendations
    elements.append(Paragraph("Specialist Diagnosis:", styles['Heading2']))
    elements.append(Paragraph(str(diagnosis) if diagnosis else "No diagnosis provided", styles['BodyText']))
    elements.append(Spacer(1, 12))
    elements.append(Paragraph("Recommendations:", styles['Heading2']))
    elements.append(Paragraph(str(recommendations) if recommendations else "No recommendations provided", styles['BodyText']))
    elements.append(Spacer(1, 24))

    # Chat Summary
    elements.append(Paragraph("Consultation Transcript Summary:", styles['Heading2']))
    for m in messages:
        elements.append(Paragraph(f"<b>[{m['timestamp']}] {m['username']}</b>: {m['message']}", styles['BodyText']))
        elements.append(Spacer(1, 6))

    print(f">>> [PDF-GEN] Building document with {len(elements)} elements...", flush=True)
    try:
        doc.build(elements)
        print(f">>> [PDF-SUCCESS] Report {filename} created successfully.", flush=True)
    except Exception as e:
        print(f">>> [PDF-ERROR] doc.build failed: {e}", flush=True)
        traceback.print_exc()
        return None
    return filename

@app.route('/complete_case/<int:patient_id>', methods=['POST'])
def complete_case(patient_id):
    if 'user_id' not in session or session.get('profession') not in SPECIALIST_ROLES:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401
    
    conn = None
    try:
        final_diagnosis = request.form.get('final_diagnosis', 'Consultation concluded.')
        recommendations = request.form.get('recommendations', 'Follow-up as needed.')
        
        conn = get_db_connection()
        patient = db_execute(conn, 'SELECT * FROM patients WHERE id = ? AND specialist_id = ?', (patient_id, session['user_id'])).fetchone()
        
        if not patient:
            conn.close()
            return jsonify({'success': False, 'message': 'Case not found or not assigned to you'}), 404
            
        print(f">>> [TRANS-START] Finalizing case {patient_id}...", flush=True)
        
        # --- Step 1: Main Status Update ---
        try:
            db_execute(conn, 'UPDATE patients SET status = ?, final_diagnosis = ?, final_recommendations = ? WHERE id = ?', 
                         ('Completed', final_diagnosis, recommendations, patient_id))
            conn.commit() # Intermediary commit to ensure we save progress
            print(">>> [TRANS-STEP] Main case status updated to Completed.", flush=True)
        except Exception as e:
            if conn: conn.rollback()
            print(f">>> [TRANS-FAIL] Main update failed: {e}. Attempting fallback...", flush=True)
            try:
                db_execute(conn, 'UPDATE patients SET status = ? WHERE id = ?', ('Completed', patient_id))
                conn.commit()
            except: 
                if conn: conn.rollback()
                return jsonify({'success': False, 'message': f'Database Critical Failure: {e}'}), 500
        
        # --- Step 2: Generate Report ---
        report_filename = f"report_{patient_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}.pdf"
        pdf_status = generate_pdf_report(patient_id, report_filename, final_diagnosis, recommendations)
        if not pdf_status:
            raise Exception("PDF Generation Engine failed to create the document on the server.")
        
        # --- Step 3: Sync Report Filename ---
        try:
            db_execute(conn, 'UPDATE patients SET report_file_path = ?, report_file = ? WHERE id = ?', 
                         (report_filename, report_filename, patient_id))
            conn.commit()
        except Exception as e:
            if conn: conn.rollback()
            print(f">>> [TRANS-FAIL] Report sync failed: {e}. Trying legacy column.", flush=True)
            try:
                db_execute(conn, 'UPDATE patients SET report_file = ? WHERE id = ?', (report_filename, patient_id))
                conn.commit()
            except:
                if conn: conn.rollback()
        
        # --- Step 4: Notifications ---
        try:
            create_notification(patient['rural_doctor_id'], f"Case Completed & Report Generated: {patient['patient_name']}", url_for('rural_dashboard'), patient_id=patient_id, conn=conn)
            if patient['patient_user_id']:
                create_notification(patient['patient_user_id'], f"Consultation Completed. Your final report is ready.", url_for('patient_case_view', patient_id=patient_id), patient_id=patient_id, conn=conn)
            conn.commit()
        except:
            if conn: conn.rollback()
        
        if conn: conn.close()
        
        socketio.emit('status_update', {'patient_id': patient_id, 'status': 'Completed'}, room=f"patient_{patient_id}")
        return jsonify({'success': True, 'message': 'Case completed and report generated'})
        
    except Exception as e:
        if conn:
            try: conn.rollback()
            except: pass
            conn.close()
        traceback.print_exc()
        return jsonify({'success': False, 'message': f"Internal Production Error: {str(e)}"}), 500

@app.route('/generate_report/<int:patient_id>')
def generate_report(patient_id):
    if 'user_id' not in session: return redirect(url_for('login'))
    
    conn = get_db_connection()
    patient = None
    try:
        # Nuclear Tech: Try both columns simultaneously for maximum compatibility
        patient = db_execute(conn, 'SELECT id, report_file_path, report_file FROM patients WHERE id = ?', (patient_id,)).fetchone()
    except Exception as e:
        # CRITICAL: Reset the transaction state before attempting the legacy fallback
        if conn: conn.rollback()
        print(f">>> [DOWNLOAD-WARN] Schema discrepancy: {e}. Resetting transaction for legacy query.", flush=True)
        try:
            # Fallback to absolute legacy version
            patient = db_execute(conn, 'SELECT id, report_file FROM patients WHERE id = ?', (patient_id,)).fetchone()
        except Exception as e2:
            print(f">>> [DOWNLOAD-CRITICAL] Both queries failed: {e2}", flush=True)
            conn.close()
            return f"System Schema Error: {e2}", 500
            
    conn.close()
    
    if not patient:
        return "Case logic failure: Patient record missing.", 404
        
    # Dual-Headed field check
    final_path = None
    try:
        final_path = patient['report_file_path'] if 'report_file_path' in patient.keys() else None
    except: pass
    
    if not final_path:
        try:
            final_path = patient['report_file'] if 'report_file' in patient.keys() else None
        except: pass

    if final_path:
        # Security sanitize the path
        filename = os.path.basename(final_path)
        print(f">>> [DOWNLOAD-SUCCESS] Serving report: {filename}", flush=True)
        return send_from_directory(app.config['UPLOAD_FOLDER'], filename)
        
    return "Report file pointer is empty in database. Please re-complete the case.", 404

@app.route('/api/generate_summary/<int:patient_id>', methods=['GET'])
def api_generate_summary(patient_id):
    if 'user_id' not in session: return jsonify({'summary': "Unauthenticated"}), 401
    from backend.chatbot_logic import fetch_conversation_history, query_openai, is_ai_configured
    import json
    
    try:
        messages = fetch_conversation_history(patient_id)
        if not messages: 
            return jsonify({'summary': "No conversation history available for this case. Try chatting with the patient first."})
        
        if is_ai_configured():
            # Filter and simplify messages to ensure high-quality summary within model window
            clean_msgs = [{"role": m.get('role', 'user'), "content": m.get('message', '')} for m in messages[-15:]]
            prompt = f"Summarize this medical case professionally (Condition, Symptoms, Actions): {json.dumps(clean_msgs)}"
            
            summary = query_openai(prompt, "You are a clinical registrar producing medical case summaries.")
            
            # Catch internal API errors
            if "Error" in summary:
                return jsonify({'summary': f"AI summarization is currently busy. Raw observation: {summary[:50]}..."})
        else:
            summary = f"Summary unavailable: AI configuration required. Total messages: {len(messages)}."
        
        return jsonify({'summary': summary})
    except Exception as e:
        print(f"Summary Error: {str(e)}")
        return jsonify({'summary': "The AI assistant is temporarily unavailable for this summary. Please try again in a few moments."})

@app.route('/api/analyze_scan/<int:patient_id>', methods=['POST'])
def api_analyze_scan(patient_id):
    if 'user_id' not in session or session.get('profession') == 'Patient':
        return jsonify({'success': False, 'message': 'Unauthorized. AI Analysis is for clinical professionals only.'}), 401
        
    conn = get_db_connection()
    patient = db_execute(conn, 'SELECT * FROM patients WHERE id = ?', (patient_id,)).fetchone()
    
    if not patient:
        conn.close()
        return jsonify({'success': False, 'message': 'Patient not found'}), 404
        
    # Simulated AI logic: Predict stroke based on patient ID characteristics for consistent demo
    # In a real app, this would send the DICOM file to a PyTorch/TensorFlow backend.
    if patient_id % 2 == 0:
        prediction = "Possible Stroke Detected"
        severity = "High"
        observations = "- Hyperdense middle cerebral artery sign observed.\n- Loss of insular ribbon.\n- Hypoattenuation in the basal ganglia."
        recommendation = "Immediate neurology consult requires. Consider tPA evaluation or mechanical thrombectomy if within time window."
    else:
        prediction = "No major abnormality detected"
        severity = "Low"
        observations = "- Symmetrical ventricular system.\n- No midline shift.\n- Gray-white matter differentiation is preserved."
        recommendation = "Routine follow-up as per clinical symptoms. No acute intervention required based on current imaging."
        
    report = f"Scan Type: MRI/CT Head\nObservations:\n{observations}\n\nDetected Condition: {prediction}\nSeverity: {severity}\nRecommendation: {recommendation}"
    
    # Simulated AI logic
    if patient_id % 2 == 0:
        prediction = "Possible Stroke Detected"
    else:
        prediction = "No major abnormality detected"
        
    report = f"Scan Analysis Result: {prediction}"
    
    db_execute(conn, 'UPDATE patients SET ai_prediction = ?, scan_analysis_report = ? WHERE id = ?', 
                 (prediction, report, patient_id))
    conn.commit()
    conn.close()
    
    return jsonify({
        'success': True, 
        'prediction': prediction,
        'report': report,
        'severity': severity
    })

@app.route('/api/get_specialists/<specialty>')
def get_specialists(specialty):
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401
    
    conn = get_db_connection()
    doctors = db_execute(conn, 'SELECT id, username, status FROM users WHERE profession = ?', (specialty,)).fetchall()
    conn.close()
    
    doctor_list = [{'id': doc['id'], 'username': doc['username'], 'status': doc['status']} for doc in doctors]
    return jsonify({'success': True, 'doctors': doctor_list})

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000, debug=False)
