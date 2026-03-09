import os
from flask import Flask, render_template, request, redirect, url_for, session, flash, send_file, jsonify
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from datetime import datetime
import mysql.connector
import pickle
import math


# ---------- Load ML Model ----------
vectorizer, model = pickle.load(open("priority_model.pkl", "rb"))

# ---------- Config ----------
app = Flask(__name__)
app.secret_key = 'replace_with_a_strong_secret'
app.config['UPLOAD_FOLDER'] = os.path.join('static', 'uploads')
app.config['CERT_FOLDER'] = os.path.join('static', 'certificates')
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['CERT_FOLDER'], exist_ok=True)

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}   



# ---------- Helpers ----------
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def save_file(file_storage):
    if file_storage and allowed_file(file_storage.filename):
        filename = secure_filename(f"{int(datetime.utcnow().timestamp())}_{file_storage.filename}")
        path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file_storage.save(path)
        return filename
    return None

def create_certificate(user_name, report_id, report_desc):
    cert_filename = f"certificate_report_{report_id}.pdf"
    cert_path = os.path.join(app.config['CERT_FOLDER'], cert_filename)
    c = canvas.Canvas(cert_path, pagesize=A4)
    width, height = A4

    c.setFont("Helvetica-Bold", 20)
    c.drawCentredString(width / 2, height - 100, "Helping Hands")
    c.setFont("Helvetica", 12)
    c.drawCentredString(width / 2, height - 125, "Social Work Certificate")

    c.setFont("Helvetica", 11)
    text_lines = [
        f"Certificate issued to: {user_name}",
        "",
        f"Report ID: {report_id}",
        "",
        "This certifies that the user reported a case which was followed up by a registered NGO",
        "",
        "Report description:",
        report_desc,
        "",
        f"Issued on: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}",
        "",
        "Verified by: Helping Hands"
    ]
    y = height - 170
    for line in text_lines:
        c.drawString(80, y, line)
        y -= 18

    c.showPage()
    c.save()
    return cert_filename

def get_db_connection():
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password="sweety@12",
        database="hopebridge"
    )

def haversine(lat1, lon1, lat2, lon2):
    R = 6371  # km
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

# ---------- Routes ----------

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/signup', methods=['GET','POST'])
def signup():
    if request.method=='POST':
        name = request.form.get('name','').strip()
        email = request.form.get('email','').strip().lower()
        password = request.form.get('password','')
        role = request.form.get('role')
        if not (name and email and password and role):
            flash("All fields are required.")
            return redirect(url_for('signup'))
        hashed = generate_password_hash(password)
        mydb = get_db_connection()
        cur = mydb.cursor()
        try:
            cur.execute("INSERT INTO users (name,email,password,role) VALUES (%s,%s,%s,%s)", 
                        (name,email,hashed,role))
            mydb.commit()
            flash("Account created. Please login.")
            return redirect(url_for('login'))
        except:
            mydb.rollback()
            flash("Error creating account. Email may already exist.")
        finally:
            cur.close()
            mydb.close()
    return render_template('signup.html')

@app.route('/login', methods=['GET','POST'])
def login():
    if request.method=='POST':
        email = request.form.get('email','').strip().lower()
        password = request.form.get('password','')
        mydb = get_db_connection()
        cur = mydb.cursor()
        cur.execute("SELECT id,name,email,password,role FROM users WHERE email=%s",(email,))
        user = cur.fetchone()
        cur.close()
        mydb.close()
        if user and check_password_hash(user[3], password):
            session.clear()
            session['user_id'] = user[0]
            session['user_name'] = user[1]
            session['role'] = user[4]
            flash("Logged in successfully.")
            return redirect(url_for('ngo_dashboard') if user[4]=='ngo' else url_for('user_dashboard'))
        else:
            flash("Invalid credentials.")
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash("Logged out.")
    return redirect(url_for('index'))

# ---------- User Dashboard ----------
@app.route('/user_dashboard', methods=['GET','POST'])
def user_dashboard():
    if 'user_id' not in session or session.get('role')!='user':
        flash("Please login as user.")
        return redirect(url_for('login'))
    mydb = get_db_connection()
    cur = mydb.cursor()
    if request.method=='POST':
        description = request.form.get('description','').strip()
        location = request.form.get('location','').strip()
        photo = request.files.get('photo')
        filename = save_file(photo) if photo and photo.filename else None

        # ML priority
        priority = model.predict(vectorizer.transform([description]))[0]

        cur.execute("INSERT INTO reports (user_id, photo, description, location, priority) VALUES (%s,%s,%s,%s,%s)",
                    (session['user_id'], filename, description, location, priority))
        mydb.commit()

        # Assign nearest NGO
        try:
            if location:
                user_lat,user_lon = map(float, location.split(','))
                cur.execute("SELECT id, latitude, longitude FROM users WHERE role='ngo' AND latitude IS NOT NULL AND longitude IS NOT NULL")
                ngos = cur.fetchall()
                nearest_ngo = None
                min_distance = float('inf')
                for ngo in ngos:
                    ngo_id,ngo_lat,ngo_lon = ngo
                    dist = haversine(user_lat,user_lon,float(ngo_lat),float(ngo_lon))
                    if dist<min_distance:
                        min_distance = dist
                        nearest_ngo = ngo_id
                if nearest_ngo:
                    cur.execute("UPDATE reports SET assigned_ngo=%s WHERE id=%s",(nearest_ngo,cur.lastrowid))
                    mydb.commit()
        except Exception as e:
            print("Error assigning nearest NGO:", e)

        flash("Report submitted.")
        return redirect(url_for('user_dashboard'))

    cur.execute("SELECT id, photo, description, location, status, created_at, priority FROM reports WHERE user_id=%s ORDER BY created_at DESC",
                (session['user_id'],))
    reports = cur.fetchall()
    cur.close()
    mydb.close()
    return render_template('user_dashboard.html', reports=reports)

# ---------- NGO Dashboard ----------
@app.route('/ngo_dashboard')
def ngo_dashboard():
    if 'user_id' not in session or session.get('role')!='ngo':
        flash("Please login as NGO.")
        return redirect(url_for('login'))
    mydb = get_db_connection()
    cur = mydb.cursor()
    cur.execute("""
        SELECT r.id, r.photo, r.description, r.location, r.status, r.created_at, r.priority, u.name AS reporter_name
        FROM reports r JOIN users u ON r.user_id=u.id
        WHERE r.assigned_ngo=%s OR r.assigned_ngo IS NULL
        ORDER BY r.created_at DESC
    """,(session['user_id'],))
    reports = cur.fetchall()
    cur.close()
    mydb.close()
    return render_template('ngo_dashboard.html', reports=reports)

# ---------- Add Feedback ----------
@app.route('/add_feedback/<int:report_id>', methods=['GET','POST'])
def add_feedback(report_id):
    if 'user_id' not in session or session.get('role')!='ngo':
        flash("Please login as NGO.")
        return redirect(url_for('login'))
    mydb = get_db_connection()
    cur = mydb.cursor()
    if request.method=='POST':
        message = request.form.get('message','').strip()
        photo = request.files.get('photo')
        filename = save_file(photo) if photo and photo.filename else None

        cur.execute("INSERT INTO feedback (report_id, ngo_id, message, photo) VALUES (%s,%s,%s,%s)",
                    (report_id, session['user_id'], message, filename))
        cur.execute("UPDATE reports SET status='Resolved' WHERE id=%s",(report_id,))
        mydb.commit()

        cur.execute("SELECT u.name, r.description FROM reports r JOIN users u ON r.user_id=u.id WHERE r.id=%s",(report_id,))
        row = cur.fetchone()
        if row:
            reporter_name, report_desc = row
            create_certificate(reporter_name, report_id, report_desc or "")

        cur.close()
        mydb.close()
        flash("Feedback posted and report marked Resolved.")
        return redirect(url_for('ngo_dashboard'))

    cur.execute("SELECT id, photo, description, location, status FROM reports WHERE id=%s",(report_id,))
    report = cur.fetchone()
    cur.close()
    mydb.close()
    if not report:
        flash("Report not found.")
        return redirect(url_for('ngo_dashboard'))
    return render_template('add_feedback.html', report=report)

# ---------- View Feedback ----------
@app.route('/view_feedback/<int:report_id>')
def view_feedback(report_id):
    mydb = get_db_connection()
    cur = mydb.cursor()
    cur.execute("""
        SELECT f.id, f.message, f.photo, f.date, u.name AS ngo_name
        FROM feedback f JOIN users u ON f.ngo_id=u.id
        WHERE f.report_id=%s ORDER BY f.date DESC
    """,(report_id,))
    feedbacks = cur.fetchall()

    cur.execute("""
        SELECT r.id, r.photo, r.description, r.location, r.status, r.created_at, r.priority, u.name AS reporter_name
        FROM reports r JOIN users u ON r.user_id=u.id WHERE r.id=%s
    """,(report_id,))
    report = cur.fetchone()
    cur.close()
    mydb.close()
    if not report:
        flash("Report not found.")
        return redirect(url_for('index'))
    return render_template('view_feedback.html', feedbacks=feedbacks, report=report)

# ---------- Download Certificate ----------
@app.route('/download_certificate/<int:report_id>')
def download_certificate(report_id):
    cert_filename = f"certificate_report_{report_id}.pdf"
    cert_path = os.path.join(app.config['CERT_FOLDER'], cert_filename)
    if os.path.exists(cert_path):
        return send_file(cert_path, as_attachment=True)
    flash("Certificate not found.")
    return redirect(url_for('user_dashboard'))

# ---------- Public Feed ----------
@app.route('/public_feed')
def public_feed():
    mydb = get_db_connection()
    cur = mydb.cursor()
    cur.execute("""
        SELECT r.id, r.photo, r.description, r.location, r.status, r.created_at, u.name AS reporter_name
        FROM reports r JOIN users u ON r.user_id=u.id
        WHERE r.status='Resolved'
        ORDER BY r.created_at DESC
    """)
    items = cur.fetchall()
    cur.close()
    mydb.close()
    return render_template('public_feed.html', items=items)




from nltk.chat.util import Chat, reflections

# Define your patterns
pairs = [
    # Greetings
    [
        r"hi|hello|hey|greetings|good morning|good afternoon|good evening",
        ["Hello! How can I help you today?", "Hi there! Need assistance?", "Greetings! How may I support you?"]
    ],
     # Affirmative responses
    [
        r"yes|yeah|yep|sure|ok|okay|alright",
        ["Great! How can I assist you further?", "Okay, tell me more.", "Alright, what would you like to know?"]
    ],  
    
    # Negative responses
    [
        r"no|nope|not really|no thanks",
        ["No problem! If you change your mind, I'm here to help.", "Okay, feel free to ask if you need anything later."]
    ],
    


    # Who are you / what is this platform
    [
        r"who are you|what is your name|what are you",
        ["I'm HopeBridge Assistant, your guide to social support services.", "I'm Hope, your AI helper on the HopeBridge platform."]
    ],
    [
        r"what is (this|HopeBridge|the platform)",
        ["HopeBridge connects people in need with verified NGOs and social workers. You can report issues, get help, and track resolution."]
    ],
    
    # Reporting an issue
    [
        r"how (do|can) I (report|register|submit) (a|an) (issue|problem|complaint)",
        ["To report an issue, log in as a user, go to your dashboard, and fill out the report form. You can add a description, location, and photo."]
    ],
    [
        r"what (kind of|type of) issues can I report",
        ["You can report any social issue such as homelessness, food insecurity, domestic problems, child welfare, elderly care, or any community concern."]
    ],
    
    # NGOs
    [
        r"how (do|can) I (find|contact|reach) (a|an) NGO",
        ["Once you submit a report, our system assigns the nearest registered NGO to follow up. You can also view resolved cases in the public feed."]
    ],
    [
        r"(are there|is there) (any|) NGOs near me",
        ["NGOs are assigned based on your location when you submit a report. Make sure your location is accurate in the report form."]
    ],
    
    # Help / assistance
    [
        r"I need help|can you help me|I have a problem",
        ["Of course! Please tell me more about your situation, or go to your dashboard and create a report."]
    ],
    [
        r"help (with|for) (.*)",
        ["I'm here to assist. Could you provide more details? If it's urgent, please submit a report with full information."]
    ],
    
    # Account and login
    [
        r"how (do|can) I (sign up|register|create account)",
        ["You can sign up by clicking the 'Sign Up' button on the homepage. Choose your role: User (seeking help) or NGO (offering help)."]
    ],
    [
        r"I forgot my password",
        ["On the login page, click 'Forgot Password' (if implemented) or contact support to reset your password."]
    ],
    
    # Feedback / certificate
    [
        r"how (do|can) I (give|leave) feedback",
        ["After an NGO resolves your report, they will add feedback. You can view it in the report details."]
    ],
    [
        r"(what is|)certificate",
        ["When a report is resolved, you receive a certificate of assistance. You can download it from your dashboard."]
    ],
    
    # General info
    [
        r"(what services do you offer|what can you do)",
        ["I can help you navigate HopeBridge: report issues, find NGOs, track your cases, and answer questions about social support."]
    ],
    
    # Thanks
    [
        r"thank you|thanks|thank you so much",
        ["You're welcome! If you need anything else, just ask.", "Happy to help! Stay safe."]
    ],
    
    # Goodbye
    [
        r"bye|goodbye|see you|talk to you later",
        ["Goodbye! Take care.", "See you soon. Remember, we're here to help."]
    ],
    
    # Fallback for unknown queries
    [
        r"(.*)",
        ["I'm not sure I understood. Could you rephrase? You can also try asking about reporting, NGOs, or account help."]
    ]
]

# Create the chatbot instance
nltk_chatbot = Chat(pairs, reflections)  


@app.route("/chatbot", methods=["POST"])
def chatbot():
    user_message = request.json.get("message", "")
    reply = nltk_chatbot.respond(user_message)
    return jsonify({"reply": reply})


# ---------- Run ----------
if __name__ == '__main__':
    app.run(debug=True)