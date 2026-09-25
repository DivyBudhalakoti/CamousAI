import sqlite3
import time
import os
from datetime import datetime
from flask import Flask, request, redirect, session, render_template_string, send_from_directory
from werkzeug.utils import secure_filename
from google import genai

app = Flask(__name__)
app.secret_key = "campusai123"

# Folder for uploaded PDF files
UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024

# Open SQLite database
database = sqlite3.connect("campusai.db")
database.execute("PRAGMA foreign_keys = ON")

# Create tables
database.execute("""
CREATE TABLE IF NOT EXISTS users (
    username TEXT PRIMARY KEY,
    password TEXT,
    role TEXT,
    name TEXT,
    user_id TEXT
)
""")

database.execute("""
CREATE TABLE IF NOT EXISTS students (
    roll TEXT PRIMARY KEY,
    name TEXT,
    department TEXT,
    semester TEXT
)
""")

database.execute("""
CREATE TABLE IF NOT EXISTS teachers (
    teacher_id TEXT PRIMARY KEY,
    name TEXT,
    department TEXT
)
""")

database.execute("""
CREATE TABLE IF NOT EXISTS attendance (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    roll TEXT,
    subject TEXT,
    attendance TEXT
)
""")

database.execute("""
CREATE TABLE IF NOT EXISTS marks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    roll TEXT,
    subject TEXT,
    marks TEXT
)
""")

database.execute("""
CREATE TABLE IF NOT EXISTS assignments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    subject TEXT,
    assignment TEXT,
    deadline TEXT,
    pdf TEXT,
    department TEXT
)
""")

database.execute("""
CREATE TABLE IF NOT EXISTS notices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    notice TEXT,
    pdf TEXT,
    department TEXT
)
""")

database.execute("""
CREATE TABLE IF NOT EXISTS timetable (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    department TEXT,
    day TEXT,
    subject TEXT,
    file TEXT
)
""")

database.execute("""
CREATE TABLE IF NOT EXISTS complaints (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    roll TEXT,
    name TEXT,
    complaint TEXT,
    status TEXT
)
""")

# Add timetable file column if an older database is being used
if "file" not in [row[1] for row in database.execute("PRAGMA table_info(timetable)").fetchall()]:
    database.execute("ALTER TABLE timetable ADD COLUMN file TEXT")

# Add PDF columns if an older database is being used
database.execute("ALTER TABLE assignments ADD COLUMN pdf TEXT") if "pdf" not in [row[1] for row in database.execute("PRAGMA table_info(assignments)").fetchall()] else None
database.execute("ALTER TABLE notices ADD COLUMN pdf TEXT") if "pdf" not in [row[1] for row in database.execute("PRAGMA table_info(notices)").fetchall()] else None
database.execute("ALTER TABLE notices ADD COLUMN notice_date TEXT") if "notice_date" not in [row[1] for row in database.execute("PRAGMA table_info(notices)").fetchall()] else None
database.execute("ALTER TABLE assignments ADD COLUMN department TEXT") if "department" not in [row[1] for row in database.execute("PRAGMA table_info(assignments)").fetchall()] else None
database.execute("ALTER TABLE notices ADD COLUMN department TEXT") if "department" not in [row[1] for row in database.execute("PRAGMA table_info(notices)").fetchall()] else None

# Create the requested initial CampusAI data only when the database is empty.
# Existing data is preserved when the application is restarted.
if database.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0:
    # Students
    students_data = [
        ("101", "Divy", "CSE", "5"),
        ("102", "Tapasya", "CSE", "5"),
        ("103", "Bhanu", "CSE", "5"),
        ("104", "Anjali", "CSE", "5"),
        ("105", "Pankaj", "CSE", "5"),
        ("201", "Rudra", "ELECTRONICS", "5"),
        ("202", "Saksham", "ELECTRONICS", "5"),
        ("203", "Arjun", "ELECTRONICS", "5"),
        ("204", "Abhishek", "ELECTRONICS", "5"),
        ("205", "Karan", "ELECTRONICS", "5"),
        ("206", "Satyam", "ELECTRONICS", "5")
    ]
    
    for student in students_data:
        database.execute("INSERT INTO students VALUES (?, ?, ?, ?)", student)
        roll, name, department, semester = student
        username = name.lower()
        database.execute(
            "INSERT INTO users VALUES (?, ?, ?, ?, ?)",
            (username, "1234", "student", name, roll)
        )
    
    # Teachers
    teachers_data = [
        ("T001", "Mrs. Meenaxi", "CSE"),
        ("T002", "Mr. Rajesh", "CSE"),
        ("T003", "Mrs. Jyoti", "CSE"),
        ("T004", "Mr. Himanshu", "CSE"),
        ("T005", "Mr. Dharmendra", "ELECTRONICS"),
        ("T006", "Mrs. Lata", "ELECTRONICS"),
        ("T007", "Mr. Ashish", "ELECTRONICS"),
        ("T008", "Mr. Shyam", "ELECTRONICS")
    ]
    
    for teacher in teachers_data:
        database.execute("INSERT INTO teachers VALUES (?, ?, ?)", teacher)
        teacher_id, name, department = teacher
        username = teacher_id.lower()
        database.execute(
            "INSERT INTO users VALUES (?, ?, ?, ?, ?)",
            (username, "1234", "teacher", name, teacher_id)
        )
    
    # HODs
    database.execute(
        "INSERT INTO users VALUES (?, ?, ?, ?, ?)",
        ("hod_cse", "1234", "hod", "Mr. Bhaskar", "H001")
    )
    database.execute(
        "INSERT INTO users VALUES (?, ?, ?, ?, ?)",
        ("hod_electronics", "1234", "hod", "Mr. Saurabh", "H002")
    )
    
    # Principal
    database.execute(
        "INSERT INTO users VALUES (?, ?, ?, ?, ?)",
        ("principal", "1234", "principal", "Mr. Sumit Kumar", "P001")
    )
    
    database.commit()
    database.close()
    

# Open database when required
def get_database():
    database = sqlite3.connect("campusai.db")
    database.execute("PRAGMA foreign_keys = ON")
    return database


# Ask Gemini AI according to the logged-in role and allowed database data
def ask_ai(question, role, user_id):
    try:
        client = genai.Client()

        database = get_database()
        data = ""

        if role == "student":
            student = database.execute(
                "SELECT roll, name, department, semester FROM students WHERE roll=?",
                (user_id,)
            ).fetchone()

            attendance_rows = database.execute(
                "SELECT subject, attendance FROM attendance WHERE roll=?",
                (user_id,)
            ).fetchall()

            marks_rows = database.execute(
                "SELECT subject, marks FROM marks WHERE roll=?",
                (user_id,)
            ).fetchall()

            data = "Student information: " + str(student)
            data += "\nStudent attendance: " + str(attendance_rows)
            data += "\nStudent marks: " + str(marks_rows)

        elif role == "teacher":
            teacher = database.execute(
                "SELECT name, department FROM teachers WHERE teacher_id=?",
                (user_id,)
            ).fetchone()

            department = teacher[1] if teacher else "CSE"

            students = database.execute(
                "SELECT roll, name, department, semester FROM students WHERE department=?",
                (department,)
            ).fetchall()

            attendance_rows = database.execute(
                "SELECT roll, subject, attendance FROM attendance WHERE roll IN (SELECT roll FROM students WHERE department=?)",
                (department,)
            ).fetchall()

            data = "Teacher information: " + str(teacher)
            data += "\nAuthorized students: " + str(students)
            data += "\nAuthorized attendance: " + str(attendance_rows)

        elif role == "hod":
            # Select the department according to the logged-in HOD.
            department = "CSE" if user_id == "H001" else "ELECTRONICS"

            students = database.execute(
                "SELECT roll, name, department, semester FROM students WHERE department=?",
                (department,)
            ).fetchall()

            teachers = database.execute(
                "SELECT teacher_id, name, department FROM teachers WHERE department=?",
                (department,)
            ).fetchall()

            attendance_rows = database.execute(
                "SELECT roll, subject, attendance FROM attendance WHERE roll IN (SELECT roll FROM students WHERE department=?)",
                (department,)
            ).fetchall()

            data = "HOD department: " + department
            data += "\nDepartment students: " + str(students)
            data += "\nDepartment teachers: " + str(teachers)
            data += "\nDepartment attendance: " + str(attendance_rows)

        elif role == "principal":
            students = database.execute(
                "SELECT roll, name, department, semester FROM students"
            ).fetchall()

            teachers = database.execute(
                "SELECT teacher_id, name, department FROM teachers"
            ).fetchall()

            attendance_rows = database.execute(
                "SELECT roll, subject, attendance FROM attendance"
            ).fetchall()

            data = "College students: " + str(students)
            data += "\nCollege teachers: " + str(teachers)
            data += "\nCollege attendance: " + str(attendance_rows)

        database.close()

        if role == "student":
            instruction = """You are CampusAI Student Assistant. Help the student with study, programming, assignments, exam preparation and college-learning questions. Explain answers simply. Never reveal information about other students. Only use the student's own data supplied below for personal college information."""
        elif role == "teacher":
            instruction = """You are CampusAI Teacher Assistant. Help teachers with lesson plans, quizzes, assignments and student performance. The teacher may only access students and attendance from their own department. Never reveal information from another department."""
        elif role == "hod":
            instruction = """You are CampusAI HOD Assistant. Help with department-level attendance, student performance, teachers, assessments and reports. The HOD may only access their own department data supplied below. Never reveal data from another department."""
        else:
            instruction = """You are CampusAI Principal Assistant. Help with college-level management, departments, students, teachers, attendance, complaints, notices, reports and academic planning. The principal is authorized to use college-wide data supplied below."""

        prompt = instruction + "\n\nAUTHORIZED DATABASE INFORMATION:\n" + data + "\n\nUSER QUESTION:\n" + question

        # Gemini can temporarily return 503 when the model is busy.
        # Try the main model a few times before using a fallback model.
        models_to_try = ["gemini-3.8-flash", "gemini-3.7-flash", "gemini-3.6-flash", "gemini-3.5-flash"]
        last_error = None

        for model_name in models_to_try:
            for attempt in range(3):
                try:
                    response = client.models.generate_content(
                        model=model_name,
                        contents=prompt
                    )

                    if response.text:
                        return response.text.strip()

                    last_error = Exception("Gemini returned an empty response.")

                except Exception as error:
                    last_error = error
                    error_text = str(error).lower()

                    # Retry temporary server/capacity problems with exponential backoff.
                    if "503" in error_text or "unavailable" in error_text or "500" in error_text or "504" in error_text:
                        if attempt < 2:
                            wait_seconds = 2 ** attempt
                            print(f"Gemini temporary error on {model_name}. Retry {attempt + 1}/2 after {wait_seconds}s...")
                            time.sleep(wait_seconds)
                            continue
                    break

        print("GEMINI ERROR:", last_error)
        error_text = str(last_error).lower() if last_error else ""

        if "api key" in error_text or "authentication" in error_text or "unauthorized" in error_text:
            return "Gemini connection error: API key authentication failed. Check your GEMINI_API_KEY."
        elif "quota" in error_text or "rate limit" in error_text or "resource exhausted" in error_text:
            return "Gemini connection error: API quota or rate limit reached. Please try again later."
        elif "503" in error_text or "unavailable" in error_text:
            return "Gemini is temporarily busy. Please wait a moment and try again."
        elif "404" in error_text or "not found" in error_text:
            return "Gemini connection error: The selected model is currently unavailable."
        elif "permission" in error_text or "forbidden" in error_text:
            return "Gemini connection error: This API key does not have permission to use the model."
        elif "connection" in error_text or "timeout" in error_text:
            return "Gemini connection error: Could not reach Google's API. Check your internet connection."
        else:
            return "Gemini could not process the request right now. Please try again."

    except Exception as error:
        print("GEMINI ERROR:", error)
        return "Gemini could not process the request right now. Please try again."


# Common page design
page = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>CampusAI</title>
    <style>
        * { box-sizing: border-box; }

        :root {
            --bg: #080b14;
            --panel: #111827;
            --panel2: #151d2e;
            --border: #263247;
            --text: #f1f5f9;
            --muted: #94a3b8;
            --blue: #38bdf8;
            --purple: #8b5cf6;
            --green: #34d399;
            --red: #f87171;
        }

        body {
            font-family: Arial, Helvetica, sans-serif;
            margin: 0;
            min-height: 100vh;
            background: radial-gradient(circle at top right, #172554 0%, transparent 35%),
                        radial-gradient(circle at bottom left, #1e1b4b 0%, transparent 35%),
                        var(--bg);
            color: var(--text);
        }

        .header {
            background: rgba(10, 15, 28, 0.94);
            border-bottom: 1px solid var(--border);
            padding: 18px 6%;
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 20px;
            position: sticky;
            top: 0;
            z-index: 10;
            backdrop-filter: blur(12px);
            box-shadow: 0 8px 30px rgba(0,0,0,0.25);
        }

        .brand { display: flex; align-items: center; gap: 12px; }
        .brand-logo {
            width: 44px; height: 44px; border-radius: 13px;
            display: flex; align-items: center; justify-content: center;
            font-weight: bold; font-size: 21px; color: white;
            background: linear-gradient(135deg, var(--blue), var(--purple));
            box-shadow: 0 0 22px rgba(56,189,248,0.25);
        }
        .brand h1 { margin: 0; font-size: 23px; letter-spacing: .3px; }
        .header-info { text-align: right; }
        .header-info p { margin: 2px 0; color: var(--muted); font-size: 13px; }
        .role-badge {
            display: inline-block; padding: 5px 10px; border-radius: 999px;
            color: #dbeafe; background: rgba(59,130,246,0.15);
            border: 1px solid rgba(56,189,248,0.25); font-size: 12px;
        }

        .box {
            background: rgba(17, 24, 39, 0.88);
            width: 90%; max-width: 1180px;
            margin: 34px auto; padding: 32px;
            border: 1px solid var(--border);
            border-radius: 22px;
            box-shadow: 0 20px 55px rgba(0,0,0,0.28);
        }

        h2 { margin-top: 0; font-size: 27px; }
        h3 { color: #c4b5fd; }
        p, label { color: #cbd5e1; }
        .subtitle { color: var(--muted); margin-bottom: 25px; }

        .login-box { max-width: 470px; text-align: center; margin: 30px auto; }
        .logo-circle {
            width: 82px; height: 82px; margin: 0 auto 18px; border-radius: 24px;
            background: linear-gradient(135deg, var(--blue), var(--purple));
            color: white; display: flex; align-items: center; justify-content: center;
            font-size: 36px; font-weight: bold;
            box-shadow: 0 0 35px rgba(139,92,246,0.25);
        }

        input, select, textarea {
            width: 100%; padding: 13px 15px; margin: 7px 0 15px;
            border: 1px solid var(--border); border-radius: 11px;
            font-size: 15px; outline: none; background: #0b1220; color: var(--text);
        }
        input::placeholder, textarea::placeholder { color: #64748b; }
        input:focus, select:focus, textarea:focus {
            border-color: var(--blue);
            box-shadow: 0 0 0 3px rgba(56,189,248,0.10), 0 0 18px rgba(56,189,248,0.08);
        }

        button {
            background: linear-gradient(135deg, #2563eb, #7c3aed);
            color: white; border: 0; padding: 11px 17px; margin: 5px;
            cursor: pointer; border-radius: 10px; font-size: 14px; font-weight: 600;
            transition: .2s; box-shadow: 0 7px 18px rgba(37,99,235,0.18);
        }
        button:hover { transform: translateY(-2px); box-shadow: 0 10px 24px rgba(56,189,248,0.20); }
        a { text-decoration: none; }

        .menu {
            display: inline-flex; width: calc(25% - 12px); min-width: 190px;
            margin: 6px; vertical-align: top;
        }
        .menu button {
            width: 100%; min-height: 52px; margin: 0;
            display: flex; align-items: center; justify-content: center;
            text-align: center;
        }
        .dashboard-actions {
            display: flex; flex-wrap: wrap; gap: 4px;
            margin-top: 20px; padding: 16px;
            background: rgba(8,11,20,0.55); border: 1px solid var(--border);
            border-radius: 16px;
        }

        .dashboard-title {
            display: flex; align-items: center; justify-content: space-between;
            gap: 15px; flex-wrap: wrap;
        }
        .dashboard-title .branch-label {
            padding: 7px 12px; border-radius: 999px;
            background: rgba(139,92,246,0.12);
            border: 1px solid rgba(139,92,246,0.25);
            color: #c4b5fd; font-size: 12px;
        }
        .menu button {
            position: relative; overflow: hidden;
        }
        .menu button::after {
            content: ""; position: absolute; left: 0; bottom: 0;
            width: 0; height: 3px; background: var(--blue); transition: .25s;
        }
        .menu button:hover::after { width: 100%; }
        .quick-note {
            margin-top: 16px; padding: 12px 14px; border-radius: 12px;
            background: rgba(56,189,248,0.06); border: 1px solid rgba(56,189,248,0.15);
            color: var(--muted); font-size: 13px;
        }

        .card {
            display: inline-block; vertical-align: top; width: 30%; min-width: 220px;
            margin: 1%; padding: 20px; border-radius: 16px;
            background: linear-gradient(145deg, #151d2e, #0f1726);
            border: 1px solid var(--border);
            box-shadow: inset 0 1px rgba(255,255,255,0.03);
        }
        .card:hover { border-color: #3b82f6; transform: translateY(-2px); }

        .answer {
            background: #0b1322; border: 1px solid #263a58;
            border-left: 5px solid var(--blue); padding: 18px; border-radius: 12px;
            white-space: pre-wrap; line-height: 1.7; color: #dbeafe;
        }

        table { width: 100%; border-collapse: collapse; overflow: hidden; border-radius: 12px; }
        th { background: linear-gradient(135deg, #1d4ed8, #6d28d9); color: white; }
        th, td { padding: 12px; border: 1px solid var(--border); text-align: left; }
        td { color: #dbe4f0; background: #101827; }
        tr:nth-child(even) td { background: #0d1522; }

        .danger { background: linear-gradient(135deg, #dc2626, #991b1b); }
        .success { background: linear-gradient(135deg, #059669, #047857); }
        .message {
            padding: 13px; border-radius: 10px; background: rgba(245,158,11,0.10);
            color: #fbbf24; border: 1px solid rgba(245,158,11,0.22); margin-bottom: 15px;
        }
        .feature-title { color: #93c5fd; }

        @media (max-width: 900px) {
            .menu { width: calc(33.33% - 12px); }
        }
        @media (max-width: 650px) {
            .header { position: static; padding: 16px 5%; }
            .header-info { display: none; }
            .box { width: 94%; padding: 20px; margin: 20px auto; }
            .card { width: 100%; margin: 6px 0; }
            .menu { width: 100%; margin: 5px 0; }
        }
    </style>
</head>
<body>
<div class="header">
    <div class="brand">
        <div class="brand-logo">C</div>
        <div>
            <h1>CampusAI</h1>
            <p style="margin:3px 0 0;color:#64748b;font-size:12px;">Smart College Management</p>
        </div>
    </div>
    <div class="header-info">
        {% if session.get("name") %}
            <p>Welcome, <b style="color:#f8fafc;">{{ session.get("name") }}</b></p>
            <span class="role-badge">{{ session.get("role")|title }}</span>
        {% else %}
            <p>AI Powered Campus Platform</p>
        {% endif %}
    </div>
</div>

<div class="box">
    {{ content|safe }}
</div>
</body>
</html>
"""

@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        database = get_database()

        user = database.execute(
            "SELECT username, role, name, user_id FROM users WHERE username=? AND password=?",
            (username, password)
        ).fetchone()

        database.close()

        if user:
            session["username"] = user[0]
            session["role"] = user[1]
            session["name"] = user[2]
            session["user_id"] = user[3]

            return redirect("/dashboard")

        return render_template_string(
            page,
            content="""
            <h2>Login</h2>
            <p>Invalid username or password.</p>
            <a href="/"><button>Try Again</button></a>
            """
        )

    return render_template_string(
        page,
        content="""
        <div class="login-box">
            <div class="logo-circle">C</div>
            <h2>Welcome to CampusAI</h2>
            <p class="subtitle">One smart platform for students, teachers, HODs and principals.</p>

            <form method="post">
                <label><b>Username</b></label>
                <input type="text" name="username" placeholder="Enter your username" required>

                <label><b>Password</b></label>
                <input type="password" name="password" placeholder="Enter your password" required>

                <button type="submit">Login to CampusAI</button>
            </form>

            <p class="subtitle">Use your assigned college login credentials.</p>
        </div>
        """
    )


@app.route("/dashboard")
def dashboard():
    if "username" not in session:
        return redirect("/")

    role = session["role"]

    if role == "student":
        menu = """
        <div class="dashboard-title"><h2>👨‍🎓 Student Dashboard</h2><span class="branch-label">🏫 CSE / Electronics</span></div>
        <div class="dashboard-actions">
        <a class="menu" href="/profile"><button>👤 View Profile</button></a>
        <a class="menu" href="/timetable"><button>📅 Timetable</button></a>
        <a class="menu" href="/assignments"><button>📝 Assignments</button></a>
        <a class="menu" href="/marks"><button>📊 My Marks</button></a>
        <a class="menu" href="/attendance"><button>📈 My Attendance</button></a>
        <a class="menu" href="/notices"><button>🔔 Notices</button></a>
        <a class="menu" href="/complaint"><button>📩 Submit Complaint</button></a>
        <a class="menu" href="/my_complaints"><button>🔎 Track Complaints</button></a>
        <a class="menu" href="/ai"><button>🤖 Ask AI Assistant</button></a>
        """

    elif role == "teacher":
        menu = """
        <div class="dashboard-title"><h2>👨‍🏫 Teacher Dashboard</h2><span class="branch-label">🏫 CSE / Electronics</span></div>
        <div class="dashboard-actions">
        <a class="menu" href="/profile"><button>👤 View Profile</button></a>
        <a class="menu" href="/students"><button>👥 View Students</button></a>
        <a class="menu" href="/mark_attendance"><button>✅ Mark Attendance</button></a>
        <a class="menu" href="/enter_marks"><button>📝 Enter Marks</button></a>
        <a class="menu" href="/performance"><button>📊 Performance</button></a>
        <a class="menu" href="/assignment"><button>📚 Create Assignment</button></a>
        <a class="menu" href="/notice"><button>🔔 Post Notice</button></a>
        <a class="menu" href="/ai"><button>🤖 Teacher AI</button></a>
        """

    elif role == "hod":
        menu = """
        <div class="dashboard-title"><h2>👔 HOD Dashboard</h2><span class="branch-label">🏢 {{ "CSE" if session.get("user_id") == "H001" else "ELECTRONICS" }} Department</span></div>
        <div class="dashboard-actions">
        <a class="menu" href="/department"><button>🏢 Department Dashboard</button></a>
        <a class="menu" href="/timetable"><button>📅 Manage Timetable</button></a>
        <a class="menu" href="/students"><button>👥 View Students</button></a>
        <a class="menu" href="/teachers"><button>👨‍🏫 View Teachers</button></a>
        <a class="menu" href="/all_attendance"><button>📈 View Attendance</button></a>
        <a class="menu" href="/all_marks"><button>📊 View Marks</button></a>
        <a class="menu" href="/all_complaints"><button>📩 View Complaints</button></a>
        <a class="menu" href="/notice"><button>📢 Department Notice</button></a>
        <a class="menu" href="/ai"><button>🤖 HOD AI</button></a>
        """

    else:
        menu = """
        <div class="dashboard-title"><h2>👨‍💼 Principal Dashboard</h2><span class="branch-label">🏫 2 Branches</span></div>
        <div class="dashboard-actions">
        <a class="menu" href="/college"><button>🏫 College Dashboard</button></a>
        <a class="menu" href="/timetable?department=CSE"><button>📅 CSE Timetable</button></a>
        <a class="menu" href="/timetable?department=ELECTRONICS"><button>⚡ Electronics Timetable</button></a>
        <a class="menu" href="/students"><button>👥 View Students</button></a>
        <a class="menu" href="/teachers"><button>👨‍🏫 View Teachers</button></a>
        <a class="menu" href="/all_attendance"><button>📈 View Attendance</button></a>
        <a class="menu" href="/all_marks"><button>📊 View Marks</button></a>
        <a class="menu" href="/all_complaints"><button>📩 View Complaints</button></a>
        <a class="menu" href="/notice"><button>📢 College Notice</button></a>
        <a class="menu" href="/add_student"><button>➕ Add Student</button></a>
        <a class="menu" href="/remove_student"><button>➖ Remove Student</button></a>
        <a class="menu" href="/ai"><button>🤖 Principal AI</button></a>
        """

    menu += """
    <br><br>
    <a href="/change_password"><button>🔐 Change Password</button></a>
    <a href="/logout"><button class="danger">🚪 Logout</button></a>
    """

    return render_template_string(page, content=menu)


@app.route("/profile")
def profile():
    database = get_database()

    if session["role"] == "student":
        student = database.execute(
            "SELECT roll, name, department, semester FROM students WHERE roll=?",
            (session["user_id"],)
        ).fetchone()

        content = f"""
        <h2>Student Profile</h2>
        <p>Name: {student[1]}</p>
        <p>Roll No: {student[0]}</p>
        <p>Department: {student[2]}</p>
        <p>Semester: {student[3]}</p>
        """

    else:
        content = f"""
        <h2>Profile</h2>
        <p>Name: {session["name"]}</p>
        <p>Role: {session["role"]}</p>
        <p>ID: {session["user_id"]}</p>
        """

    database.close()

    content += '<br><a href="/dashboard"><button>Back</button></a>'

    return render_template_string(page, content=content)


@app.route("/timetable", methods=["GET", "POST"])
def timetable():
    if "username" not in session:
        return redirect("/")

    database = get_database()

    if session["role"] == "student":
        row = database.execute("SELECT department FROM students WHERE roll=?", (session["user_id"],)).fetchone()
        department_name = row[0] if row else "CSE"
    elif session["role"] == "teacher":
        row = database.execute("SELECT department FROM teachers WHERE teacher_id=?", (session["user_id"],)).fetchone()
        department_name = row[0] if row else "CSE"
    elif session["role"] == "hod":
        department_name = "CSE" if session["user_id"] == "H001" else "ELECTRONICS"
    else:
        department_name = request.args.get("department", "CSE")
        if department_name not in ["CSE", "ELECTRONICS"]:
            department_name = "CSE"

    if request.method == "POST" and session["role"] == "hod":
        action = request.form.get("action")

        if action == "add":
            day = request.form["day"]
            subject = request.form["subject"]
            database.execute(
                "INSERT INTO timetable (department, day, subject, file) VALUES (?, ?, ?, ?)",
                (department_name, day, subject, "")
            )
            database.commit()

        elif action == "upload":
            timetable_file = request.files.get("timetable_file")

            if not timetable_file or timetable_file.filename == "":
                database.close()
                return render_template_string(page, content="""<h2>Timetable</h2><div class="message">Please select a JPG, JPEG, PNG or PDF timetable file.</div><a href="/timetable"><button>Back</button></a>""")

            original_name = timetable_file.filename.lower()
            allowed_extensions = [".jpg", ".jpeg", ".png", ".pdf"]
            if not any(original_name.endswith(ext) for ext in allowed_extensions):
                database.close()
                return render_template_string(page, content="""<h2>Timetable</h2><div class="message">Only JPG, JPEG, PNG and PDF files are allowed.</div><a href="/timetable"><button>Back</button></a>""")

            file_name = secure_filename(timetable_file.filename)
            base, extension = os.path.splitext(file_name)
            file_name = base + "_" + datetime.now().strftime("%Y%m%d%H%M%S") + extension
            timetable_file.save(os.path.join(app.config["UPLOAD_FOLDER"], file_name))

            database.execute(
                "INSERT INTO timetable (department, day, subject, file) VALUES (?, ?, ?, ?)",
                (department_name, "", "Uploaded Timetable", file_name)
            )
            database.commit()

        elif action == "delete":
            timetable_id = request.form["timetable_id"]
            file_row = database.execute(
                "SELECT file FROM timetable WHERE id=? AND department=?",
                (timetable_id, department_name)
            ).fetchone()

            database.execute(
                "DELETE FROM timetable WHERE id=? AND department=?",
                (timetable_id, department_name)
            )
            database.commit()

            if file_row and file_row[0]:
                file_path = os.path.join(app.config["UPLOAD_FOLDER"], file_row[0])
                if os.path.exists(file_path):
                    os.remove(file_path)

    rows = database.execute(
        "SELECT id, day, subject, file FROM timetable WHERE department=? ORDER BY id",
        (department_name,)
    ).fetchall()
    database.close()

    content = f"<div class='dashboard-title'><h2>📅 {department_name} Timetable</h2><span class='branch-label'>Department Timetable</span></div>"

    if session["role"] == "hod":
        content += """
        <h3>Add Timetable Entry</h3>
        <form method="post">
            <input type="hidden" name="action" value="add">
            <select name="day" required>
                <option value="Monday">Monday</option>
                <option value="Tuesday">Tuesday</option>
                <option value="Wednesday">Wednesday</option>
                <option value="Thursday">Thursday</option>
                <option value="Friday">Friday</option>
                <option value="Saturday">Saturday</option>
            </select>
            <input name="subject" placeholder="Subject" required>
            <button type="submit">➕ Add to Timetable</button>
        </form>

        <h3>Upload Timetable</h3>
        <p>You can upload the complete timetable as <b>JPG, JPEG, PNG or PDF</b>.</p>
        <form method="post" enctype="multipart/form-data">
            <input type="hidden" name="action" value="upload">
            <input type="file" name="timetable_file" accept=".jpg,.jpeg,.png,.pdf,image/jpeg,image/png,application/pdf" required>
            <button type="submit">📤 Upload Timetable</button>
        </form>
        """

    if rows:
        content += "<h3>Timetable</h3><table><tr><th>Day</th><th>Subject / File</th>" + ("<th>Action</th>" if session["role"] == "hod" else "") + "</tr>"
        for row in rows:
            content += "<tr><td>" + (row[1] if row[1] else "📎 File") + "</td><td>"
            if row[3]:
                extension = os.path.splitext(row[3])[1].lower()
                if extension == ".pdf":
                    content += '<a href="/timetable_file/' + row[3] + '" target="_blank"><button>📄 View PDF Timetable</button></a>'
                else:
                    content += '<a href="/timetable_file/' + row[3] + '" target="_blank"><button>🖼️ View Timetable Image</button></a>'
            else:
                content += row[2]
            content += "</td>"
            if session["role"] == "hod":
                content += "<td><form method='post' style='display:inline'><input type='hidden' name='action' value='delete'><input type='hidden' name='timetable_id' value='" + str(row[0]) + "'><button class='danger' type='submit'>🗑️ Delete</button></form></td>"
            content += "</tr>"
        content += "</table>"
    else:
        content += "<p>No timetable entries or uploaded timetable found for this department yet.</p>"

    content += '<br><a href="/dashboard"><button>Back</button></a>'
    return render_template_string(page, content=content)


@app.route("/timetable_file/<filename>")
def timetable_file(filename):
    if "username" not in session:
        return redirect("/")

    if not filename.lower().endswith((".jpg", ".jpeg", ".png", ".pdf")):
        return "Invalid timetable file."

    return send_from_directory(app.config["UPLOAD_FOLDER"], filename)


@app.route("/students")
def students():
    if "username" not in session:
        return redirect("/")

    database = get_database()
    role = session["role"]

    if role == "student":
        database.close()
        return render_template_string(page, content="""<h2>Access Restricted</h2><div class="message">Students can only view their own information.</div><a href="/dashboard"><button>Back</button></a>""")

    if role == "teacher":
        teacher = database.execute("SELECT department FROM teachers WHERE teacher_id=?", (session["user_id"],)).fetchone()
        department = teacher[0] if teacher else "CSE"
        rows = database.execute("SELECT roll, name, department, semester FROM students WHERE department=?", (department,)).fetchall()
        heading = "My Assigned Department Students - " + department
    elif role == "hod":
        department = "CSE" if session["user_id"] == "H001" else "ELECTRONICS"
        rows = database.execute("SELECT roll, name, department, semester FROM students WHERE department=?", (department,)).fetchall()
        heading = "Department Students - " + department
    else:
        rows = database.execute("SELECT roll, name, department, semester FROM students").fetchall()
        heading = "All College Students"

    database.close()
    content = "<h2>" + heading + "</h2><table><tr><th>Roll</th><th>Name</th><th>Department</th><th>Semester</th></tr>"
    for row in rows:
        content += "<tr><td>" + row[0] + "</td><td>" + row[1] + "</td><td>" + row[2] + "</td><td>" + row[3] + "</td></tr>"
    content += "</table><br><a href='/dashboard'><button>Back</button></a>"
    return render_template_string(page, content=content)

@app.route("/teachers")
def teachers():
    if "username" not in session:
        return redirect("/")

    if session["role"] == "student":
        return render_template_string(page, content="""<h2>Access Restricted</h2><div class="message">Students cannot view teacher management data.</div><a href="/dashboard"><button>Back</button></a>""")

    database = get_database()

    if session["role"] == "teacher":
        teacher = database.execute("SELECT department FROM teachers WHERE teacher_id=?", (session["user_id"],)).fetchone()
        department = teacher[0] if teacher else "CSE"
        rows = database.execute("SELECT teacher_id, name, department FROM teachers WHERE department=?", (department,)).fetchall()
        heading = "Teachers in My Department - " + department
    elif session["role"] == "hod":
        department = "CSE" if session["user_id"] == "H001" else "ELECTRONICS"
        rows = database.execute("SELECT teacher_id, name, department FROM teachers WHERE department=?", (department,)).fetchall()
        heading = "Department Teachers - " + department
    else:
        rows = database.execute("SELECT teacher_id, name, department FROM teachers").fetchall()
        heading = "All College Teachers"

    database.close()
    content = "<h2>" + heading + "</h2><table><tr><th>ID</th><th>Name</th><th>Department</th></tr>"
    for row in rows:
        content += "<tr><td>" + row[0] + "</td><td>" + row[1] + "</td><td>" + row[2] + "</td></tr>"
    content += "</table><br><a href='/dashboard'><button>Back</button></a>"
    return render_template_string(page, content=content)

@app.route("/marks")
def marks():
    database = get_database()

    rows = database.execute(
        "SELECT subject, marks FROM marks WHERE roll=?",
        (session["user_id"],)
    ).fetchall()

    database.close()

    content = "<h2>My Marks</h2>"

    if len(rows) == 0:
        content += "<p>No marks found.</p>"

    for row in rows:
        content += "<p>" + row[0] + " : " + row[1] + "</p>"

    content += '<a href="/dashboard"><button>Back</button></a>'

    return render_template_string(page, content=content)


@app.route("/attendance")
def attendance():
    database = get_database()

    rows = database.execute(
        "SELECT subject, attendance FROM attendance WHERE roll=?",
        (session["user_id"],)
    ).fetchall()

    database.close()

    content = "<h2>My Attendance</h2>"

    if len(rows) == 0:
        content += "<p>No attendance found.</p>"

    for row in rows:
        content += "<p>" + row[0] + " : " + row[1] + "</p>"

    content += '<a href="/dashboard"><button>Back</button></a>'

    return render_template_string(page, content=content)


@app.route("/assignments")
def assignments():
    database = get_database()
    if session["role"] == "student":
        student = database.execute("SELECT department FROM students WHERE roll=?", (session["user_id"],)).fetchone()
        department = student[0] if student else "CSE"
        rows = database.execute("SELECT subject, assignment, deadline, pdf, department FROM assignments WHERE department=? OR department='ALL' ORDER BY id DESC", (department,)).fetchall()
    elif session["role"] == "teacher":
        teacher = database.execute("SELECT department FROM teachers WHERE teacher_id=?", (session["user_id"],)).fetchone()
        department = teacher[0] if teacher else "CSE"
        rows = database.execute("SELECT subject, assignment, deadline, pdf, department FROM assignments WHERE department=? OR department='ALL' ORDER BY id DESC", (department,)).fetchall()
    elif session["role"] == "hod":
        department = "CSE" if session["user_id"] == "H001" else "ELECTRONICS"
        rows = database.execute("SELECT subject, assignment, deadline, pdf, department FROM assignments WHERE department=? OR department='ALL' ORDER BY id DESC", (department,)).fetchall()
    else:
        rows = database.execute("SELECT subject, assignment, deadline, pdf, department FROM assignments ORDER BY id DESC").fetchall()
    database.close()

    content = "<h2>Assignments</h2>"

    if len(rows) == 0:
        content += "<p>No assignments available.</p>"

    for row in rows:
        content += "<div class='card'><h3>" + row[0] + "</h3>"
        content += "<p>" + row[1] + "</p>"
        content += "<p><b>Deadline:</b> " + row[2] + "</p>"
        if row[3]:
            content += '<a href="/pdf/assignment/' + row[3] + '" target="_blank"><button>📄 View PDF</button></a>'
        content += "</div>"

    content += '<a href="/dashboard"><button>Back</button></a>'

    return render_template_string(page, content=content)


@app.route("/mark_attendance", methods=["GET", "POST"])
def mark_attendance():
    if request.method == "POST":
        roll = request.form["roll"]
        subject = request.form["subject"]
        attendance = request.form["attendance"]

        database = get_database()

        if session["role"] == "teacher":
            teacher = database.execute("SELECT department FROM teachers WHERE teacher_id=?", (session["user_id"],)).fetchone()
            department = teacher[0] if teacher else "CSE"
            student = database.execute("SELECT roll FROM students WHERE roll=? AND department=?", (roll, department)).fetchone()
            if student is None:
                database.close()
                return render_template_string(page, content="""<h2>Access Restricted</h2><div class="message">You can only mark attendance for students in your department.</div><a href="/mark_attendance"><button>Try Again</button></a>""")

        database.execute(
            "INSERT INTO attendance (roll, subject, attendance) VALUES (?, ?, ?)",
            (roll, subject, attendance + "%")
        )

        database.commit()
        database.close()

        return redirect("/dashboard")

    content = """
    <h2>Mark Attendance</h2>
    <form method="post">
        <input name="roll" placeholder="Student Roll Number" required>
        <input name="subject" placeholder="Subject" required>
        <input name="attendance" placeholder="Attendance Percentage" required>
        <button type="submit">Save Attendance</button>
    </form>
    <a href="/dashboard"><button>Back</button></a>
    """

    return render_template_string(page, content=content)


@app.route("/enter_marks", methods=["GET", "POST"])
def enter_marks():
    if request.method == "POST":
        roll = request.form["roll"]
        subject = request.form["subject"]
        marks = request.form["marks"]

        database = get_database()

        if session["role"] == "teacher":
            teacher = database.execute("SELECT department FROM teachers WHERE teacher_id=?", (session["user_id"],)).fetchone()
            department = teacher[0] if teacher else "CSE"
            student = database.execute("SELECT roll FROM students WHERE roll=? AND department=?", (roll, department)).fetchone()
            if student is None:
                database.close()
                return render_template_string(page, content="""<h2>Access Restricted</h2><div class="message">You can only enter marks for students in your department.</div><a href="/enter_marks"><button>Try Again</button></a>""")

        database.execute(
            "INSERT INTO marks (roll, subject, marks) VALUES (?, ?, ?)",
            (roll, subject, marks)
        )

        database.commit()
        database.close()

        return redirect("/dashboard")

    content = """
    <h2>Enter Marks</h2>
    <form method="post">
        <input name="roll" placeholder="Student Roll Number" required>
        <input name="subject" placeholder="Subject" required>
        <input name="marks" placeholder="Marks" required>
        <button type="submit">Save Marks</button>
    </form>
    <a href="/dashboard"><button>Back</button></a>
    """

    return render_template_string(page, content=content)


@app.route("/performance", methods=["GET", "POST"])
def performance():
    if request.method == "POST":
        roll = request.form["roll"]

        database = get_database()

        marks = database.execute(
            "SELECT subject, marks FROM marks WHERE roll=?",
            (roll,)
        ).fetchall()

        attendance = database.execute(
            "SELECT subject, attendance FROM attendance WHERE roll=?",
            (roll,)
        ).fetchall()

        database.close()

        content = "<h2>Student Performance</h2><h3>Marks</h3>"

        for row in marks:
            content += "<p>" + row[0] + " : " + row[1] + "</p>"

        content += "<h3>Attendance</h3>"

        for row in attendance:
            content += "<p>" + row[0] + " : " + row[1] + "</p>"

        content += '<br><a href="/dashboard"><button>Back</button></a>'

        return render_template_string(page, content=content)

    content = """
    <h2>Student Performance</h2>
    <form method="post">
        <input name="roll" placeholder="Student Roll Number" required>
        <button type="submit">View Performance</button>
    </form>
    <a href="/dashboard"><button>Back</button></a>
    """

    return render_template_string(page, content=content)


@app.route("/assignment", methods=["GET", "POST"])
def assignment():
    if request.method == "POST":
        subject = request.form["subject"]
        assignment_text = request.form["assignment"]
        deadline = request.form["deadline"]
        pdf = request.files.get("pdf")
        pdf_name = ""

        if pdf and pdf.filename != "":
            if not pdf.filename.lower().endswith(".pdf"):
                return render_template_string(page, content="""<h2>Create Assignment</h2><div class="message">Only PDF files are allowed.</div><a href="/assignment"><button>Try Again</button></a>""")
            pdf_name = secure_filename(pdf.filename)
            pdf.save(os.path.join(app.config["UPLOAD_FOLDER"], pdf_name))

        database = get_database()

        if session["role"] == "teacher":
            teacher = database.execute("SELECT department FROM teachers WHERE teacher_id=?", (session["user_id"],)).fetchone()
            department = teacher[0] if teacher else "CSE"
        elif session["role"] == "hod":
            department = "CSE" if session["user_id"] == "H001" else "ELECTRONICS"
        else:
            department = "ALL"

        database.execute(
            "INSERT INTO assignments (subject, assignment, deadline, pdf, department) VALUES (?, ?, ?, ?, ?)",
            (subject, assignment_text, deadline, pdf_name, department)
        )

        database.commit()
        database.close()

        return redirect("/dashboard")

    content = """
    <h2>Create Assignment</h2>
    <form method="post" enctype="multipart/form-data">
        <input name="subject" placeholder="Subject" required>
        <input name="assignment" placeholder="Assignment" required>
        <input name="deadline" placeholder="Deadline" required>
        <label>Attach Assignment PDF (optional)</label>
        <input type="file" name="pdf" accept="application/pdf,.pdf">
        <button type="submit">Save Assignment</button>
    </form>
    <a href="/dashboard"><button>Back</button></a>
    """

    return render_template_string(page, content=content)


@app.route("/notice", methods=["GET", "POST"])
def notice():
    if request.method == "POST":
        notice_text = request.form["notice"]
        pdf = request.files.get("pdf")
        pdf_name = ""

        if pdf and pdf.filename != "":
            if not pdf.filename.lower().endswith(".pdf"):
                return render_template_string(page, content="""<h2>Post Notice</h2><div class="message">Only PDF files are allowed.</div><a href="/notice"><button>Try Again</button></a>""")
            pdf_name = secure_filename(pdf.filename)
            pdf.save(os.path.join(app.config["UPLOAD_FOLDER"], pdf_name))

        database = get_database()

        if session["role"] == "teacher":
            teacher = database.execute("SELECT department FROM teachers WHERE teacher_id=?", (session["user_id"],)).fetchone()
            department = teacher[0] if teacher else "CSE"
        elif session["role"] == "hod":
            department = "CSE" if session["user_id"] == "H001" else "ELECTRONICS"
        else:
            department = "ALL"

        database.execute(
            "INSERT INTO notices (notice, pdf, notice_date, department) VALUES (?, ?, ?, ?)",
            (session["role"].title() + ": " + session["name"] + " - " + notice_text, pdf_name, datetime.now().strftime("%d-%m-%Y"), department)
        )

        database.commit()
        database.close()

        return redirect("/dashboard")

    content = """
    <h2>Post Notice</h2>
    <form method="post" enctype="multipart/form-data">
        <textarea name="notice" placeholder="Enter notice" required></textarea>
        <label>Attach Notice PDF (optional)</label>
        <input type="file" name="pdf" accept="application/pdf,.pdf">
        <button type="submit">Save Notice</button>
    </form>
    <a href="/dashboard"><button>Back</button></a>
    """

    return render_template_string(page, content=content)


@app.route("/notices")
def notices():
    database = get_database()

    if session["role"] == "student":
        student = database.execute("SELECT department FROM students WHERE roll=?", (session["user_id"],)).fetchone()
        department = student[0] if student else "CSE"
        rows = database.execute("SELECT notice, pdf, notice_date, department FROM notices WHERE department=? OR department='ALL' ORDER BY id DESC", (department,)).fetchall()
    elif session["role"] == "teacher":
        teacher = database.execute("SELECT department FROM teachers WHERE teacher_id=?", (session["user_id"],)).fetchone()
        department = teacher[0] if teacher else "CSE"
        rows = database.execute("SELECT notice, pdf, notice_date, department FROM notices WHERE department=? OR department='ALL' ORDER BY id DESC", (department,)).fetchall()
    elif session["role"] == "hod":
        department = "CSE" if session["user_id"] == "H001" else "ELECTRONICS"
        rows = database.execute("SELECT notice, pdf, notice_date, department FROM notices WHERE department=? OR department='ALL' ORDER BY id DESC", (department,)).fetchall()
    else:
        rows = database.execute("SELECT notice, pdf, notice_date, department FROM notices ORDER BY id DESC").fetchall()

    database.close()

    content = "<h2>Notices</h2>"

    for row in rows:
        content += "<div class='card'><p><b>📅 Date:</b> " + (row[2] or "") + "</p><p>" + row[0] + "</p>"
        if row[1]:
            content += '<a href="/pdf/notice/' + row[1] + '" target="_blank"><button>📄 View PDF</button></a>'
        content += "</div>"

    content += '<a href="/dashboard"><button>Back</button></a>'

    return render_template_string(page, content=content)


@app.route("/pdf/<pdf_type>/<filename>")
def view_pdf(pdf_type, filename):
    # Only allow PDF files from the upload folder
    if not filename.lower().endswith(".pdf"):
        return "Only PDF files are allowed."

    if pdf_type not in ["assignment", "notice"]:
        return "Invalid PDF type."

    return send_from_directory(app.config["UPLOAD_FOLDER"], filename)


@app.route("/complaint", methods=["GET", "POST"])
def complaint():
    if request.method == "POST":
        complaint_text = request.form["complaint"]

        database = get_database()

        database.execute(
            "INSERT INTO complaints (roll, name, complaint, status) VALUES (?, ?, ?, ?)",
            (session["user_id"], session["name"], complaint_text, "Pending")
        )

        database.commit()
        database.close()

        return redirect("/dashboard")

    content = """
    <h2>Submit Complaint</h2>
    <form method="post">
        <textarea name="complaint" placeholder="Enter your complaint" required></textarea>
        <button type="submit">Submit Complaint</button>
    </form>
    <a href="/dashboard"><button>Back</button></a>
    """

    return render_template_string(page, content=content)


@app.route("/my_complaints")
def my_complaints():
    database = get_database()

    rows = database.execute(
        "SELECT complaint, status FROM complaints WHERE roll=?",
        (session["user_id"],)
    ).fetchall()

    database.close()

    content = "<h2>My Complaints</h2>"

    for row in rows:
        content += "<p>Complaint: " + row[0] + "</p>"
        content += "<p>Status: " + row[1] + "</p><hr>"

    content += '<a href="/dashboard"><button>Back</button></a>'

    return render_template_string(page, content=content)


@app.route("/all_attendance")
def all_attendance():
    if "username" not in session:
        return redirect("/")

    if session["role"] == "student":
        return render_template_string(page, content="""<h2>Access Restricted</h2><div class="message">Students can only view their own attendance.</div><a href="/dashboard"><button>Back</button></a>""")

    database = get_database()

    if session["role"] == "teacher":
        teacher = database.execute("SELECT department FROM teachers WHERE teacher_id=?", (session["user_id"],)).fetchone()
        department = teacher[0] if teacher else "CSE"
        rows = database.execute("SELECT roll, subject, attendance FROM attendance WHERE roll IN (SELECT roll FROM students WHERE department=?)", (department,)).fetchall()
        heading = "My Department Attendance - " + department
    elif session["role"] == "hod":
        department = "CSE" if session["user_id"] == "H001" else "ELECTRONICS"
        rows = database.execute("SELECT roll, subject, attendance FROM attendance WHERE roll IN (SELECT roll FROM students WHERE department=?)", (department,)).fetchall()
        heading = "Department Attendance - " + department
    else:
        rows = database.execute("SELECT roll, subject, attendance FROM attendance").fetchall()
        heading = "College Attendance"

    database.close()
    content = "<h2>" + heading + "</h2><table><tr><th>Roll</th><th>Subject</th><th>Attendance</th></tr>"
    for row in rows:
        content += "<tr><td>" + row[0] + "</td><td>" + row[1] + "</td><td>" + row[2] + "</td></tr>"
    content += "</table><br><a href='/dashboard'><button>Back</button></a>"
    return render_template_string(page, content=content)

@app.route("/all_marks")
def all_marks():
    if "username" not in session:
        return redirect("/")

    if session["role"] == "student":
        return render_template_string(page, content="""<h2>Access Restricted</h2><div class="message">Students can only view their own marks.</div><a href="/dashboard"><button>Back</button></a>""")

    database = get_database()

    if session["role"] == "teacher":
        teacher = database.execute("SELECT department FROM teachers WHERE teacher_id=?", (session["user_id"],)).fetchone()
        department = teacher[0] if teacher else "CSE"
        rows = database.execute("SELECT roll, subject, marks FROM marks WHERE roll IN (SELECT roll FROM students WHERE department=?)", (department,)).fetchall()
        heading = "My Department Marks - " + department
    elif session["role"] == "hod":
        department = "CSE" if session["user_id"] == "H001" else "ELECTRONICS"
        rows = database.execute("SELECT roll, subject, marks FROM marks WHERE roll IN (SELECT roll FROM students WHERE department=?)", (department,)).fetchall()
        heading = "Department Marks - " + department
    else:
        rows = database.execute("SELECT roll, subject, marks FROM marks").fetchall()
        heading = "College Marks"

    database.close()
    content = "<h2>" + heading + "</h2><table><tr><th>Roll</th><th>Subject</th><th>Marks</th></tr>"
    for row in rows:
        content += "<tr><td>" + row[0] + "</td><td>" + row[1] + "</td><td>" + row[2] + "</td></tr>"
    content += "</table><br><a href='/dashboard'><button>Back</button></a>"
    return render_template_string(page, content=content)

@app.route("/all_complaints", methods=["GET", "POST"])
def all_complaints():
    if "username" not in session:
        return redirect("/")

    database = get_database()

    # Only the principal can approve or reject complaints.
    if request.method == "POST" and session["role"] == "principal":
        complaint_id = request.form["complaint_id"]
        action = request.form["action"]
        if action == "approve":
            database.execute("UPDATE complaints SET status='Approved' WHERE id=?", (complaint_id,))
        elif action == "reject":
            database.execute("UPDATE complaints SET status='Rejected' WHERE id=?", (complaint_id,))
        database.commit()

    if session.get("role") == "hod":
        department_name = "CSE" if session["user_id"] == "H001" else "ELECTRONICS"
        rows = database.execute(
            "SELECT id, roll, name, complaint, status FROM complaints WHERE roll IN (SELECT roll FROM students WHERE department=?) ORDER BY id DESC",
            (department_name,)
        ).fetchall()
        heading = "Complaints - " + department_name + " Department"
    else:
        rows = database.execute(
            "SELECT id, roll, name, complaint, status FROM complaints ORDER BY id DESC"
        ).fetchall()
        heading = "College Complaints"

    database.close()

    content = "<h2>" + heading + "</h2>"

    if not rows:
        content += "<p>No complaints found.</p>"

    for row in rows:
        content += "<div class='card'><p><b>Roll:</b> " + row[1] + "</p>"
        content += "<p><b>Name:</b> " + row[2] + "</p>"
        content += "<p><b>Complaint:</b> " + row[3] + "</p>"
        content += "<p><b>Status:</b> " + row[4] + "</p>"
        if session.get("role") == "principal" and row[4] == "Pending":
            content += "<form method='post' style='display:inline'><input type='hidden' name='complaint_id' value='" + str(row[0]) + "'><input type='hidden' name='action' value='approve'><button class='success' type='submit'>✅ Approve</button></form>"
            content += "<form method='post' style='display:inline'><input type='hidden' name='complaint_id' value='" + str(row[0]) + "'><input type='hidden' name='action' value='reject'><button class='danger' type='submit'>❌ Reject</button></form>"
        content += "</div>"

    content += '<br><a href="/dashboard"><button>Back</button></a>'
    return render_template_string(page, content=content)


@app.route("/department")
def department():
    if "username" not in session or session["role"] != "hod":
        return redirect("/dashboard")

    department_name = "CSE" if session["user_id"] == "H001" else "ELECTRONICS"
    database = get_database()

    student_count = database.execute(
        "SELECT COUNT(*) FROM students WHERE department=?", (department_name,)
    ).fetchone()[0]

    teacher_count = database.execute(
        "SELECT COUNT(*) FROM teachers WHERE department=?", (department_name,)
    ).fetchone()[0]

    database.close()

    content = f"""
    <h2>Department Dashboard</h2>
    <p>Department: {department_name}</p>
    <p>Students: {student_count}</p>
    <p>Teachers: {teacher_count}</p>
    <a href="/dashboard"><button>Back</button></a>
    """

    return render_template_string(page, content=content)


@app.route("/college")
def college():
    database = get_database()

    student_count = database.execute(
        "SELECT COUNT(*) FROM students"
    ).fetchone()[0]

    teacher_count = database.execute(
        "SELECT COUNT(*) FROM teachers"
    ).fetchone()[0]

    database.close()

    content = f"""
    <h2>College Dashboard</h2>
    <p>Total Students: {student_count}</p>
    <p>Total Teachers: {teacher_count}</p>
    <p>Departments: 2</p><p>🏫 CSE &nbsp; | &nbsp; ⚡ ELECTRONICS</p>
    <a href="/dashboard"><button>Back</button></a>
    """

    return render_template_string(page, content=content)


# Principal can add a new student
@app.route("/add_student", methods=["GET", "POST"])
def add_student():
    if session["role"] != "principal":
        return redirect("/dashboard")

    if request.method == "POST":
        roll = request.form["roll"]
        name = request.form["name"]
        department = request.form["department"]
        semester = request.form["semester"]
        username = request.form["username"]
        password = request.form["password"]

        database = get_database()

        try:
            database.execute(
                "INSERT INTO students VALUES (?, ?, ?, ?)",
                (roll, name, department, semester)
            )

            database.execute(
                "INSERT INTO users VALUES (?, ?, ?, ?, ?)",
                (username, password, "student", name, roll)
            )

            database.commit()
            message = "New student added successfully."

        except sqlite3.IntegrityError:
            message = "Student roll number or username already exists."

        database.close()

        content = f"""
        <h2>Add New Student</h2>
        <p>{message}</p>
        <a href="/dashboard"><button>Back to Dashboard</button></a>
        """

        return render_template_string(page, content=content)

    content = """
    <h2>Add New Student</h2>

    <form method="post">
        <input name="roll" placeholder="Roll Number" required>
        <input name="name" placeholder="Student Name" required>
        <label><b>Department</b></label>
        <select name="department" required>
            <option value="CSE">CSE</option>
            <option value="ELECTRONICS">ELECTRONICS</option>
        </select>
        <input name="semester" placeholder="Semester" required>
        <input name="username" placeholder="Login Username" required>
        <input name="password" placeholder="Login Password" required>

        <button type="submit">Add Student</button>
    </form>

    <a href="/dashboard"><button>Back</button></a>
    """

    return render_template_string(page, content=content)


# Principal can remove a student
@app.route("/remove_student", methods=["GET", "POST"])
def remove_student():
    if session["role"] != "principal":
        return redirect("/dashboard")

    if request.method == "POST":
        roll = request.form["roll"]

        database = get_database()

        student = database.execute(
            "SELECT name FROM students WHERE roll=?",
            (roll,)
        ).fetchone()

        if student:
            database.execute(
                "DELETE FROM students WHERE roll=?",
                (roll,)
            )

            database.execute(
                "DELETE FROM users WHERE role='student' AND user_id=?",
                (roll,)
            )

            database.execute(
                "DELETE FROM marks WHERE roll=?",
                (roll,)
            )

            database.execute(
                "DELETE FROM attendance WHERE roll=?",
                (roll,)
            )

            database.execute(
                "DELETE FROM complaints WHERE roll=?",
                (roll,)
            )

            database.commit()
            message = "Student removed successfully."

        else:
            message = "Student roll number not found."

        database.close()

        content = f"""
        <h2>Remove Student</h2>
        <p>{message}</p>
        <a href="/dashboard"><button>Back to Dashboard</button></a>
        """

        return render_template_string(page, content=content)

    content = """
    <h2>Remove Student</h2>

    <form method="post">
        <input name="roll" placeholder="Student Roll Number" required>
        <button type="submit">Remove Student</button>
    </form>

    <a href="/dashboard"><button>Back</button></a>
    """

    return render_template_string(page, content=content)


# AI page
@app.route("/ai", methods=["GET", "POST"])
def ai():
    if "username" not in session:
        return redirect("/")

    answer = ""

    if request.method == "POST":
        question = request.form["question"]
        answer = ask_ai(question, session["role"], session["user_id"])

    if session["role"] == "student":
        title = "AI Study Assistant"
        example = "Example: Explain pointers in C in simple language."

    elif session["role"] == "teacher":
        title = "AI Teacher Assistant"
        example = "Example: Create a 10-question quiz on Python."

    elif session["role"] == "hod":
        title = "AI HOD Assistant"
        example = "Example: How can I improve attendance in my department?"

    else:
        title = "AI Principal Assistant"
        example = "Example: Give ideas to improve college academic performance."

    content = f"""
    <h2>{title}</h2>

    <p>{example}</p>

    <form method="post">
        <textarea name="question" placeholder="Ask your question..." required></textarea>
        <button type="submit">Ask AI</button>
    </form>
    """

    if answer != "":
        content += "<h3>AI Answer</h3>"
        content += '<div class="answer">' + answer + "</div>"

    content += '<br><a href="/dashboard"><button>Back</button></a>'

    return render_template_string(page, content=content)


@app.route("/change_password", methods=["GET", "POST"])
def change_password():
    if "username" not in session:
        return redirect("/")

    if request.method == "POST":
        current_password = request.form["current_password"]
        new_password = request.form["new_password"]
        confirm_password = request.form["confirm_password"]

        if new_password != confirm_password:
            content = """
            <h2>Change Password</h2>
            <div class="message">New password and confirm password do not match.</div>
            <a href="/change_password"><button>Try Again</button></a>
            <a href="/dashboard"><button>Back</button></a>
            """
            return render_template_string(page, content=content)

        database = get_database()
        user = database.execute(
            "SELECT password FROM users WHERE username=?",
            (session["username"],)
        ).fetchone()

        if user is None or user[0] != current_password:
            database.close()
            content = """
            <h2>Change Password</h2>
            <div class="message">Current password is incorrect.</div>
            <a href="/change_password"><button>Try Again</button></a>
            <a href="/dashboard"><button>Back</button></a>
            """
            return render_template_string(page, content=content)

        if len(new_password) < 4:
            database.close()
            content = """
            <h2>Change Password</h2>
            <div class="message">New password must contain at least 4 characters.</div>
            <a href="/change_password"><button>Try Again</button></a>
            <a href="/dashboard"><button>Back</button></a>
            """
            return render_template_string(page, content=content)

        database.execute(
            "UPDATE users SET password=? WHERE username=?",
            (new_password, session["username"])
        )
        database.commit()
        database.close()

        content = """
        <h2>Password Changed Successfully</h2>
        <p>Your password has been updated.</p>
        <a href="/dashboard"><button>Back to Dashboard</button></a>
        """
        return render_template_string(page, content=content)

    content = """
    <h2>Change Password</h2>
    <p>Update the password for your CampusAI account.</p>

    <form method="post">
        <label>Current Password</label>
        <input type="password" name="current_password" placeholder="Enter current password" required>

        <label>New Password</label>
        <input type="password" name="new_password" placeholder="Enter new password" required>

        <label>Confirm New Password</label>
        <input type="password" name="confirm_password" placeholder="Enter new password again" required>

        <button type="submit">Change Password</button>
    </form>

    <a href="/dashboard"><button>Back</button></a>
    """

    return render_template_string(page, content=content)


@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")


if __name__ == "__main__":
    import os

if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 5000))
    )
