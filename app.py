import os
from flask import Flask, render_template, request, redirect, url_for, session, flash, send_file,jsonify
import smtplib
from email.mime.text import MIMEText
from flask_mysqldb import MySQL
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
from datetime import datetime, date
from deep_translator import GoogleTranslator


def send_email_notification(email, description, location):

    message = f"""
New Help Request on HopeBridge

Description: {description}
Location: {location}

Please login to NGO dashboard to respond.
"""

    msg = MIMEText(message)
    msg['Subject'] = "HopeBridge Help Alert"
    msg['From'] = "sweetynora125@gmail.com"
    msg['To'] = email

    server = smtplib.SMTP("smtp.gmail.com",587)
    server.starttls()
    server.login("sweetynora125@gmail.com","sweety12@2005")

    server.send_message(msg)
    server.quit()

def send_ngo_notification(description, location):

    sender_email = "sweetynora125@gmail.com"
    sender_password = "sweety12@2005"

    ngo_email = "kaverikalburgi1627@gmail.com"

    subject = "🚨 New Help Request Detected"

    body = f"""
    A new person needs help.

    Description: {description}
    Location: {location}

    Please check the NGO dashboard.
    """

    msg = MIMEText(body)
    msg['Subject'] = subject
    msg['From'] = sender_email
    msg['To'] = ngo_email

    try:
        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()
        server.login(sender_email, sender_password)
        server.send_message(msg)
        server.quit()
    except Exception as e:
        print("Email error:", e)

# ---------- Config ----------
app = Flask(__name__)
app.secret_key = 'replace_with_a_strong_secret'
app.config['UPLOAD_FOLDER'] = os.path.join('static', 'uploads')
app.config['CERT_FOLDER'] = os.path.join('static', 'certificates')
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['CERT_FOLDER'], exist_ok=True)

# MySQL configuration - update with your DB credentials
app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = 'kalburgi@26_2005'   # put your mysql password
app.config['MYSQL_DB'] = 'hopebridge'
mysql = MySQL(app)

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

# ---------- Helpers ----------
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# AI PRIORITY DETECTION
def detect_priority(text):
    high_keywords = ["urgent", "bleeding", "danger", "attack", "emergency", "help immediately"]
    text = text.lower()
    for word in high_keywords:
        if word in text:
            return "High"
    return "Medium"


# AI CATEGORY DETECTION
def detect_category(text):
    text = text.lower()
    if "child" in text:
        return "Child Welfare"
    elif "woman" in text or "girl" in text:
        return "Women Safety"
    elif "food" in text or "hungry" in text:
        return "Hunger"
    elif "medical" in text or "injury" in text:
        return "Medical Emergency"
    else:
        return "General"

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
    c.drawCentredString(width/2, height - 100, "Helping Hands")
    c.setFont("Helvetica", 12)
    c.drawCentredString(width/2, height - 125, "Social Work Certificate")

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

# ---------- Routes ----------
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/domains')
def domains():
    return render_template("domains.html")

# Signup route
@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        name=request.form.get('name')
        email=request.form.get('email')
        password=request.form.get('password')
        role=request.form.get('role')
        phone=request.form.get('phone')
        city=request.form.get('city')

        if not (name and email and password and role):
            flash("All fields are required.")
            return redirect(url_for('signup'))

        hashed = generate_password_hash(password)
        cur = mysql.connection.cursor()
        try:
            cur.execute(
             "INSERT INTO users(name,email,password,role,phone,city) VALUES(%s,%s,%s,%s,%s,%s)",
              (name,email,hashed,role,phone,city))
            mysql.connection.commit()
            flash("Account created. Please login.")
            return redirect(url_for('login'))
        except Exception as e:
            mysql.connection.rollback()
            flash("Error creating account. Email may already exist.")
        finally: 
            cur.close()
    return render_template('signup.html')

# Login route
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email').strip().lower()
        password = request.form.get('password')
        cur = mysql.connection.cursor()
        cur.execute("SELECT id, name, email, password, role FROM users WHERE email=%s", (email,))
        user = cur.fetchone()
        cur.close()
        if user and check_password_hash(user[3], password):
            session.clear()
            session['user_id'] = user[0]
            session['user_name'] = user[1]
            session['role'] = user[4]
            flash("Logged in successfully.")
            if user[4] == 'ngo':
                return redirect(url_for('ngo_dashboard'))
            else:
                return redirect(url_for('user_dashboard'))
        else:
            flash("Invalid credentials.")
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash("Logged out.")
    return redirect(url_for('index'))

# User dashboard - submit report, view own reports
@app.route('/user_dashboard', methods=['GET', 'POST'])
def user_dashboard():
    if 'user_id' not in session or session.get('role') != 'user':
        flash("Please login as user.")
        return redirect(url_for('login'))

    if request.method == 'POST':
        description = request.form.get('description', '').strip()
        location = request.form.get('location', '').strip()
        description_en = description
        domain = request.form.get('domain')
        priority = detect_priority(description)
        category = detect_category(description)
        photo = request.files.get('photo')
        filename = save_file(photo) if photo and photo.filename else None

        cur = mysql.connection.cursor()
        cur.execute("""
        INSERT INTO reports (user_id, photo, description, description_en, location, priority, category, domain)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
        """, (session['user_id'], filename, description,description_en, location, priority, category, domain))
        cur.execute(
        "SELECT email FROM users WHERE role='ngo' AND city=%s",
        (location,))
        ngos = cur.fetchall()

        if len(ngos)==0:
          cur.execute("SELECT email FROM users WHERE role='ngo'")
          ngos=cur.fetchall()

        for ngo in ngos:
            pass
            #send_email_notification(ngo[0], description, location)
        mysql.connection.commit()
        #send_ngo_notification(description, location)

        cur.close()
        flash("Report submitted.")
        return redirect(url_for('user_dashboard'))

    # fetch user's reports
    cur = mysql.connection.cursor()
    cur.execute("SELECT id, photo, description, location, status, created_at FROM reports WHERE user_id=%s ORDER BY created_at DESC",
                (session['user_id'],))
    reports = cur.fetchall()
    cur.close()
    return render_template('user_dashboard.html', reports=reports)

@app.route('/domain/<domain_name>')
def domain_page(domain_name):

    cur = mysql.connection.cursor()

    cur.execute("SELECT id, description, location, status FROM reports WHERE domain=%s",(domain_name,))
    reports = cur.fetchall()

    cur.execute("SELECT COUNT(*) FROM reports WHERE domain=%s",(domain_name,))
    total = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM reports WHERE domain=%s AND status='Resolved'",(domain_name,))
    resolved = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM reports WHERE domain=%s AND status!='Resolved'",(domain_name,))
    pending = cur.fetchone()[0]

    cur.close()

    return render_template(
        "domain_page.html",
        domain=domain_name,
        reports=reports,
        total=total,
        resolved=resolved,
        pending=pending
    )

# NGO dashboard - view pending reports
@app.route('/ngo_dashboard')
def ngo_dashboard():
    if 'user_id' not in session or session.get('role') != 'ngo':
        flash("Please login as NGO.")
        return redirect(url_for('login'))

    cur = mysql.connection.cursor()
    cur.execute("""
    SELECT r.id, r.photo, r.description, r.location, r.status, r.created_at, 
       r.priority, r.category, u.name AS reporter_name
    FROM reports r
    JOIN users u ON r.user_id = u.id
    GROUP BY r.id
    ORDER BY r.created_at DESC
    """)
    reports = cur.fetchall()
    cur.close()
    return render_template('ngo_dashboard.html', reports=reports)

@app.route('/update_status/<int:report_id>', methods=['POST'])
def update_status(report_id):

    if 'user_id' not in session or session.get('role') != 'ngo':
        return redirect(url_for('login'))

    status = request.form.get('status')

    cur = mysql.connection.cursor()

    cur.execute("UPDATE reports SET status=%s WHERE id=%s",(status,report_id))

    mysql.connection.commit()

    cur.close()

    flash("Status updated successfully")

    return redirect(url_for('ngo_dashboard'))

@app.route('/upload_progress/<int:report_id>', methods=['POST'])
def upload_progress(report_id):

    if 'user_id' not in session or session.get('role') != 'ngo':
        return redirect(url_for('login'))

    photo = request.files['progress_photo']

    if photo:
        filename = photo.filename
        photo.save(os.path.join('static/uploads', filename))

        cur = mysql.connection.cursor()

        cur.execute(
        "UPDATE reports SET progress_photo=%s WHERE id=%s",
        (filename, report_id)
        )
        mysql.connection.commit()

        flash("Progress photo uploaded")

    return redirect(url_for('ngo_dashboard'))

# Add feedback (NGO only)
@app.route('/add_feedback/<int:report_id>', methods=['GET', 'POST'])
def add_feedback(report_id):
    if 'user_id' not in session or session.get('role') != 'ngo':
        flash("Please login as NGO.")
        return redirect(url_for('login'))

    if request.method == 'POST':
        message = request.form.get('message', '').strip()
        photo = request.files.get('photo')
        filename = save_file(photo) if photo and photo.filename else None

        cur = mysql.connection.cursor()
        cur.execute("INSERT INTO feedback (report_id, ngo_id, message, photo) VALUES (%s,%s,%s,%s)",
                    (report_id, session['user_id'], message, filename))
        cur.execute("UPDATE reports SET status='Resolved' WHERE id=%s", (report_id,))
        mysql.connection.commit()

        # generate certificate for the user who reported this
        # fetch reporter name and report description
        cur.execute("SELECT u.name, r.description, r.user_id FROM reports r JOIN users u ON r.user_id = u.id WHERE r.id=%s", (report_id,))
        row = cur.fetchone()
        if row:
            reporter_name = row[0]
            report_desc = row[1] or ""
            cert_file = create_certificate(reporter_name, report_id, report_desc)
            # optionally store certificate filename somewhere if desired

        cur.close()
        flash("Feedback posted and report marked Resolved. Certificate generated for user.")
        return redirect(url_for('ngo_dashboard'))

    # GET: show report info
    cur = mysql.connection.cursor()
    cur.execute("SELECT id, photo, description, location, status FROM reports WHERE id=%s", (report_id,))
    report = cur.fetchone()
    cur.close()
    if not report:
        flash("Report not found.")
        return redirect(url_for('ngo_dashboard'))
    return render_template('add_feedback.html', report=report)

# View feedback (public on report)
@app.route('/view_feedback/<int:report_id>')
def view_feedback(report_id):
    cur = mysql.connection.cursor()
    cur.execute("""
        SELECT f.id, f.message, f.photo, f.date, u.name as ngo_name
        FROM feedback f JOIN users u ON f.ngo_id = u.id
        WHERE f.report_id=%s
        ORDER BY f.date DESC
    """, (report_id,))
    feedbacks = cur.fetchall()

    # also fetch report to display
    cur.execute("SELECT r.id, r.photo, r.description, r.location, r.status, r.created_at, u.name as reporter_name FROM reports r JOIN users u ON r.user_id=u.id WHERE r.id=%s",
                (report_id,))
    report = cur.fetchone()
    cur.close()
    if not report:
        flash("Report not found.")
        return redirect(url_for('index'))

    return render_template('view_feedback.html', feedbacks=feedbacks, report=report)

# Download certificate route
@app.route('/download_certificate/<int:report_id>')
def download_certificate(report_id):

    cert_folder = "certificates"
    os.makedirs(cert_folder, exist_ok=True)

    cert_filename = f"certificate_report_{report_id}.pdf"
    cert_path = os.path.join(cert_folder, cert_filename)

    ngo_name = "HopeBridge"
    recipient_name = "User Name"
    certificate_no = f"HBR-{report_id:04d}"
    today = date.today().strftime("%d-%m-%Y")

    c = canvas.Canvas(cert_path, pagesize=A4)
    width, height = A4

    # Border
    c.rect(30, 30, width-60, height-60)

    # NGO name
    c.setFont("Helvetica-Bold", 30)
    c.drawCentredString(width/2, height-150, ngo_name)

    # Title
    c.setFont("Helvetica-Bold", 24)
    c.drawCentredString(width/2, height-200, "Certificate of Appreciation")

    # Message
    c.setFont("Helvetica", 14)
    c.drawCentredString(width/2, height-280,
        "This certificate is proudly awarded to")

    # Recipient name
    c.setFont("Helvetica-Bold", 22)
    c.drawCentredString(width/2, height-320, recipient_name)

    # Contribution line
    c.setFont("Helvetica", 14)
    c.drawCentredString(width/2, height-360,
        "For contributing to social welfare through HopeBridge.")

    # Certificate number
    c.setFont("Helvetica", 10)
    c.drawString(60, 100, f"Certificate No: {certificate_no}")

    # Date
    c.drawRightString(width-60, 100, f"Date: {today}")

    c.save()

    return send_file(cert_path, as_attachment=True)

# Public listing of resolved reports (optional)
@app.route('/public_feed')
def public_feed():
    cur = mysql.connection.cursor()
    cur.execute("""
        SELECT r.id, r.photo, r.description, r.location, r.status, r.created_at, u.name AS reporter_name
        FROM reports r JOIN users u ON r.user_id = u.id
        WHERE r.status='Resolved'
        ORDER BY r.created_at DESC
    """)
    items = cur.fetchall()
    cur.close()
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
    data = request.get_json(force=True, silent=True) or {}
    user_message = data.get("message", "").strip()
    
    if not user_message:
        return jsonify({"reply": "Please type something."})
    
    reply = nltk_chatbot.respond(user_message)
    
    if not reply:
        reply = "I'm not sure I understood. Could you rephrase?"
    
    return jsonify({"reply": reply})

# ---------- Run ----------
if __name__ == '__main__':
    app.run(debug=True)
