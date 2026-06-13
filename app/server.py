from flask import Flask, request, jsonify, session, send_from_directory
from flask_cors import CORS
import sqlite3
import hashlib
import os
import sys
from datetime import datetime
import pandas as pd

def read_excel_file(file):
    import pandas as pd

    try:
        print("Trying openpyxl...")
        return pd.read_excel(file, engine="openpyxl")

    except Exception as e:
        print("OPENPYXL ERROR:", str(e))
        file.seek(0)

    try:
        print("Trying xlrd...")
        return pd.read_excel(file, engine="xlrd")

    except Exception as e:
        print("XLRD ERROR:", str(e))
        file.seek(0)

    raise ValueError("Unable to read Excel file")

# Import our modules
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from fuzzy_match import find_equipment
from predictor import predict_defect
from llama_chat import chat_with_llama, clear_history

app = Flask(__name__)
app.secret_key = 'ntpc_secret_key_2024'
CORS(app, supports_credentials=True)

# Folder where HTML files are
APP_DIR = os.path.dirname(os.path.abspath(__file__))

# ── Serve HTML files ──
@app.route('/')
def serve_index():
    return send_from_directory(APP_DIR, 'index.html')

@app.route('/chat-page')
def serve_chat():
    return send_from_directory(APP_DIR, 'chat.html')

@app.route('/<path:filename>')
def serve_static(filename):
    return send_from_directory(APP_DIR, filename)

# ── SECURITY CONFIGURATION ──
COMPANY_EMAIL_DOMAIN = '@ntpckorbaint.com'
ADMIN_SECRET_PIN     = 'NTPC@2024#KORBA'
VIEWER_SECRET_PIN    = 'KORBA@VIEW#2024'

# Database path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH  = os.path.join(BASE_DIR, 'database', 'ntpc_records.db')

# ── Helper: hash password ──
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

# ── Helper: validate company email ──
def is_valid_email(email):
    return email.lower().endswith(COMPANY_EMAIL_DOMAIN)

# ── Create database and users table ──
def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    c    = conn.cursor()

    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id       INTEGER PRIMARY KEY,
            email    TEXT UNIQUE,
            password TEXT,
            role     TEXT
        )
    ''')

    # Create upload history table
    c.execute('''
        CREATE TABLE IF NOT EXISTS upload_history (
            id            INTEGER PRIMARY KEY,
            filename      TEXT,
            records_added INTEGER,
            uploaded_by   TEXT,
            uploaded_on   TEXT
        )
    ''')

    # Create new_records table with upload_id column
    c.execute('''
        CREATE TABLE IF NOT EXISTS new_records (
            id              INTEGER PRIMARY KEY,
            equipment       TEXT,
            notif_date      TEXT,
            notif_time      TEXT,
            priority        TEXT,
            notif_type      TEXT,
            functional_loc  TEXT,
            completion_date TEXT,
            completion_time TEXT,
            description     TEXT,
            added_by        TEXT,
            added_on        TEXT,
            upload_id       INTEGER
        )
    ''')

    # Add upload_id column if it doesn't exist (for existing databases)
    try:
        c.execute("ALTER TABLE new_records ADD COLUMN upload_id INTEGER")
        conn.commit()
        print("Added upload_id column to new_records table.")
    except:
        pass  # Column already exists, ignore

    # Default admin
    c.execute(
        "INSERT OR IGNORE INTO users VALUES (1, ?, ?, 'admin')",
        ('admin@ntpckorbaint.com', hash_password('Admin@123'))
    )

    # Default viewer
    c.execute(
        "INSERT OR IGNORE INTO users VALUES (2, ?, ?, 'viewer')",
        ('viewer@ntpckorbaint.com', hash_password('Viewer@123'))
    )

    conn.commit()
    conn.close()
    print("Database ready!")
    print("\nDefault credentials:")
    print("─────────────────────────────────────────")
    print("ADMIN  → email   : admin@ntpckorbaint.com")
    print("         password: Admin@123")
    print("         pin     : NTPC@2024#KORBA")
    print("─────────────────────────────────────────")
    print("VIEWER → email   : viewer@ntpckorbaint.com")
    print("         password: Viewer@123")
    print("         pin     : KORBA@VIEW#2024")
    print("─────────────────────────────────────────")


# ── Login route ──
@app.route('/login', methods=['POST'])
def login():
    data     = request.json
    email    = data.get('email', '').lower().strip()
    password = data.get('password', '')
    role_req = data.get('role', '')

    if not is_valid_email(email):
        return jsonify({
            'success': False,
            'message': f'Only {COMPANY_EMAIL_DOMAIN} emails are allowed'
        })

    conn = sqlite3.connect(DB_PATH)
    c    = conn.cursor()
    c.execute("SELECT * FROM users WHERE email=?", (email,))
    user = c.fetchone()
    conn.close()

    if not user:
        return jsonify({'success': False, 'message': 'Email not registered'})

    if user[3] != role_req:
        return jsonify({
            'success': False,
            'message': f'This email is not registered as {role_req}'
        })

    if user[2] != hash_password(password):
        return jsonify({'success': False, 'message': 'Invalid password'})

    session['email'] = user[1]
    session['role']  = user[3]
    return jsonify({
        'success': True,
        'role'   : user[3],
        'email'  : user[1]
    })

# ── Logout route ──
@app.route('/logout', methods=['POST'])
def logout():
    session.clear()
    clear_history()
    return jsonify({'success': True})

# ── Chat API route ──
@app.route('/api/chat', methods=['POST'])
def chat():
    if 'email' not in session:
        return jsonify({'error': 'Not logged in'}), 401

    user_message = request.json.get('message', '')
    prediction   = None

    keywords = ['predict', 'fail', 'defect', 'when', 'next', 'check', 'cooling', 'pump', 'tower', 'equipment']
    if any(word in user_message.lower() for word in keywords):

        equipment_name, score = find_equipment(user_message)

        if equipment_name and score >= 60:
            result, error = predict_defect(equipment_name)
            if result:
                prediction = (
                    f"ML Model Prediction Result:\n"
                    f"Equipment    : {result['equipment']}\n"
                    f"Risk Level   : {result['risk']}\n"
                    f"Days to next : {result['avg_days']} days\n"
                    f"Expected date: {result['predicted_date']}\n"
                    f"Please explain this result clearly to the engineer."
                )

    reply = chat_with_llama(user_message, prediction)
    return jsonify({'reply': reply})

# ── Check session route ──
@app.route('/check-session', methods=['GET'])
def check_session():
    if 'email' in session:
        return jsonify({
            'logged_in': True,
            'role'     : session['role'],
            'email'    : session['email']
        })
    return jsonify({'logged_in': False})

# ── Serve Add Record page ──
@app.route('/add-record-page')
def serve_add_record():
    return send_from_directory(APP_DIR, 'add_record.html')

# ── Add Record API ──
@app.route('/add-record', methods=['POST'])
def add_record():
    if 'email' not in session:
        return jsonify({'error': 'Not logged in'}), 401
    if session['role'] != 'admin':
        return jsonify({'error': 'Access denied'}), 403

    data = request.json
    conn = sqlite3.connect(DB_PATH)
    c    = conn.cursor()

    c.execute('''
        CREATE TABLE IF NOT EXISTS new_records (
            id              INTEGER PRIMARY KEY,
            equipment       TEXT,
            notif_date      TEXT,
            notif_time      TEXT,
            priority        TEXT,
            notif_type      TEXT,
            functional_loc  TEXT,
            completion_date TEXT,
            completion_time TEXT,
            description     TEXT,
            added_by        TEXT,
            added_on        TEXT,
            upload_id       INTEGER
        )
    ''')

    c.execute('''
        INSERT INTO new_records VALUES (
            NULL, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL
        )
    ''', (
        data['equipment'],
        data['notif_date'],
        data['notif_time'],
        data['priority'],
        data['notif_type'],
        data['functional_loc'],
        data['completion_date'],
        data['completion_time'],
        data['description'],
        session['email'],
        datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    ))

    conn.commit()

    c.execute("SELECT COUNT(*) FROM new_records")
    new_records = c.fetchone()[0]
    conn.close()

    try:
        sys.path.append(os.path.join(BASE_DIR, 'scripts'))
        from retrain import retrain as run_retrain
        success, accuracy = run_retrain()
        retrain_msg = f"Model retrained! Accuracy: {round(accuracy, 2)}%"
    except Exception as e:
        retrain_msg = "Record saved but retraining failed"

    return jsonify({
        'success'    : True,
        'new_records': new_records,
        'retrain_msg': retrain_msg
    })

# ── Training Status API ──
@app.route('/training-status', methods=['GET'])
def training_status():
    if 'email' not in session:
        return jsonify({'error': 'Not logged in'}), 401

    conn = sqlite3.connect(DB_PATH)
    c    = conn.cursor()

    try:
        c.execute("SELECT COUNT(*) FROM new_records")
        new_records = c.fetchone()[0]
    except:
        new_records = 0

    conn.close()

    return jsonify({
        'last_trained' : '27 May 2026',
        'records_used' : 6846,
        'new_records'  : new_records
    })

# ── Retrain API ──
@app.route('/retrain', methods=['POST'])
def retrain():
    if 'email' not in session:
        return jsonify({'error': 'Not logged in'}), 401
    if session['role'] != 'admin':
        return jsonify({'error': 'Access denied'}), 403

    conn = sqlite3.connect(DB_PATH)
    c    = conn.cursor()
    try:
        c.execute("SELECT COUNT(*) FROM new_records")
        new_records = c.fetchone()[0]
    except:
        new_records = 0
    conn.close()

    if new_records == 0:
        return jsonify({
            'success': False,
            'message': 'No new records added yet. Add records before retraining.'
        })

    try:
        sys.path.append(os.path.join(BASE_DIR, 'scripts'))
        from retrain import retrain as run_retrain
        success, accuracy = run_retrain()

        if success:
            return jsonify({
                'success' : True,
                'accuracy': round(accuracy, 2),
                'message' : 'Model retrained successfully!'
            })
        else:
            return jsonify({'success': False, 'message': 'Retraining failed'})

    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})


# ── Get Recent Records ──
@app.route('/recent-records', methods=['GET'])
def recent_records():
    if 'email' not in session:
        return jsonify({'error': 'Not logged in'}), 401

    conn = sqlite3.connect(DB_PATH)
    c    = conn.cursor()

    try:
        c.execute('''
            SELECT id, equipment, notif_date, priority, added_on
            FROM new_records
            ORDER BY id DESC
            LIMIT 5
        ''')
        rows = c.fetchall()
        records = []
        for row in rows:
            records.append({
                'id'        : row[0],
                'equipment' : row[1],
                'notif_date': row[2],
                'priority'  : row[3],
                'added_on'  : row[4]
            })
    except:
        records = []

    conn.close()
    return jsonify({'records': records})

# ── Delete Record ──
@app.route('/delete-record/<int:record_id>', methods=['DELETE'])
def delete_record(record_id):
    if 'email' not in session:
        return jsonify({'error': 'Not logged in'}), 401
    if session['role'] != 'admin':
        return jsonify({'error': 'Access denied'}), 403

    conn = sqlite3.connect(DB_PATH)
    c    = conn.cursor()
    c.execute("DELETE FROM new_records WHERE id=?", (record_id,))
    conn.commit()
    conn.close()

    return jsonify({'success': True})

# ── Edit Record ──
@app.route('/edit-record/<int:record_id>', methods=['PUT'])
def edit_record(record_id):
    if 'email' not in session:
        return jsonify({'error': 'Not logged in'}), 401
    if session['role'] != 'admin':
        return jsonify({'error': 'Access denied'}), 403

    data = request.json
    conn = sqlite3.connect(DB_PATH)
    c    = conn.cursor()

    c.execute('''
        UPDATE new_records SET
            equipment       = ?,
            notif_date      = ?,
            notif_time      = ?,
            priority        = ?,
            notif_type      = ?,
            functional_loc  = ?,
            completion_date = ?,
            completion_time = ?,
            description     = ?
        WHERE id = ?
    ''', (
        data['equipment'],
        data['notif_date'],
        data['notif_time'],
        data['priority'],
        data['notif_type'],
        data['functional_loc'],
        data['completion_date'],
        data['completion_time'],
        data['description'],
        record_id
    ))

    conn.commit()
    conn.close()

    return jsonify({'success': True})

# ── Upcoming Defects API ──
@app.route('/upcoming-defects', methods=['GET'])
def upcoming_defects():
    if 'email' not in session:
        return jsonify({'error': 'Not logged in'}), 401

    months = int(request.args.get('months', 1))

    from predictor import predict_all_equipment
    all_results = predict_all_equipment()

    filtered = [r for r in all_results if r['avg_days'] <= months * 30]

    return jsonify({
        'defects': filtered,
        'total'  : len(filtered),
        'months' : months
    })

# ── Monthly Defects API ──
@app.route('/monthly-defects', methods=['GET'])
def monthly_defects():
    if 'email' not in session:
        return jsonify({'error': 'Not logged in'}), 401

    month = int(request.args.get('month', datetime.now().month))
    year  = int(request.args.get('year',  datetime.now().year))

    from predictor import predict_all_equipment
    all_results = predict_all_equipment()

    filtered = [
        r for r in all_results
        if r['predicted_month'] == month and r['predicted_year'] == year
    ]

    return jsonify({
        'defects': filtered,
        'total'  : len(filtered),
        'month'  : month,
        'year'   : year
    })

# ── Notifications API ──
@app.route('/notifications', methods=['GET'])
def notifications():
    if 'email' not in session:
        return jsonify({'error': 'Not logged in'}), 401

    from predictor import predict_all_equipment
    all_results = predict_all_equipment()

    now           = datetime.now()
    current_month = now.month
    current_year  = now.year

    high_risk = [
        r for r in all_results
        if r['risk'] == 'HIGH'
        and r['predicted_month'] == current_month
        and r['predicted_year']  == current_year
    ]
    medium_risk = [
        r for r in all_results
        if r['risk'] == 'MEDIUM'
        and r['predicted_month'] == current_month
        and r['predicted_year']  == current_year
    ]

    return jsonify({
        'high_risk'   : high_risk[:10],
        'medium_risk' : medium_risk[:10],
        'high_count'  : len(high_risk),
        'medium_count': len(medium_risk),
        'month'       : now.strftime('%B %Y')
    })

# ── Validate Excel Columns ──
@app.route('/validate-excel', methods=['POST'])
def validate_excel():
    if 'email' not in session:
        return jsonify({'error': 'Not logged in'}), 401
    if session['role'] != 'admin':
        return jsonify({'error': 'Access denied'}), 403

    if 'file' not in request.files:
        return jsonify({'success': False, 'message': 'No file uploaded'})

    file = request.files['file']

    try:
        df = read_excel_file(file)

        required_columns = [
            'Notif.date',
            'equipment',
            'Notif. Time',
            'Completion time',
            'Completn date',
            'Priority',
            'Notifictn type',
            'Functional Loc.'
        ]

        missing = [col for col in required_columns if col not in df.columns]

        return jsonify({
            'success'        : True,
            'missing_columns': missing,
            'total_rows'     : len(df),
            'total_cols'     : len(df.columns),
            'columns_found'  : list(df.columns)
        })

    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

# ── Upload Excel and Process ──
@app.route('/upload-excel', methods=['POST'])
def upload_excel():
    if 'email' not in session:
        return jsonify({'error': 'Not logged in'}), 401
    if session['role'] != 'admin':
        return jsonify({'error': 'Access denied'}), 403

    if 'file' not in request.files:
        return jsonify({'success': False, 'message': 'No file uploaded'})

    file = request.files['file']

    try:
        df = read_excel_file(file)

        required_columns = [
            'Notif.date', 'equipment', 'Notif. Time',
            'Completion time', 'Completn date', 'Priority',
            'Notifictn type', 'Functional Loc.'
        ]

        missing_cols = [col for col in required_columns if col not in df.columns]
        if missing_cols:
            return jsonify({
                'success': False,
                'message': f'Missing columns: {missing_cols}'
            })

        critical_columns = [
            'Notif.date',
            'equipment',
            'Priority',
            'Notif. Time',
            'Completn date',
            'Completion time'
        ]

        fillable_columns = {
            'Notifictn type' : 'M2',
            'Functional Loc.': 'UNKNOWN'
        }

        total_rows      = len(df)
        records_added   = 0
        skipped_rows    = []
        autofilled_info = {}

        conn = sqlite3.connect(DB_PATH)
        c    = conn.cursor()
        upload_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        # ── Insert upload_history ONCE with placeholder count ──
        c.execute('''
            INSERT INTO upload_history VALUES (NULL, ?, ?, ?, ?)
        ''', (
            file.filename,
            0,
            session['email'],
            upload_time
        ))
        upload_id = c.lastrowid
        conn.commit()

        c.execute('''
            CREATE TABLE IF NOT EXISTS new_records (
                id              INTEGER PRIMARY KEY,
                equipment       TEXT,
                notif_date      TEXT,
                notif_time      TEXT,
                priority        TEXT,
                notif_type      TEXT,
                functional_loc  TEXT,
                completion_date TEXT,
                completion_time TEXT,
                description     TEXT,
                added_by        TEXT,
                added_on        TEXT,
                upload_id       INTEGER
            )
        ''')

        for idx, row in df.iterrows():
            row_num    = idx + 2
            skip_row   = False
            skip_reason = ''

            for col in critical_columns:
                val = row.get(col, None)
                if val is None or str(val).strip() == '' or str(val).lower() == 'nan':
                    skip_row    = True
                    skip_reason = f'{col} is missing'
                    break

            if skip_row:
                skipped_rows.append({
                    'row'   : row_num,
                    'reason': skip_reason
                })
                continue

            for col, default_val in fillable_columns.items():
                val = row.get(col, None)
                if val is None or str(val).strip() == '' or str(val).lower() == 'nan':
                    df.at[idx, col] = default_val
                    if col not in autofilled_info:
                        autofilled_info[col] = {
                            'default': default_val,
                            'count'  : 0
                        }
                    autofilled_info[col]['count'] += 1

            try:
                # ── Each record tagged with upload_id ──
                c.execute('''
                    INSERT INTO new_records VALUES (
                        NULL, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
                    )
                ''', (
                    str(row['equipment']).strip().upper(),
                    str(row['Notif.date']),
                    str(row['Notif. Time']),
                    str(row['Priority']),
                    str(df.at[idx, 'Notifictn type']),
                    str(df.at[idx, 'Functional Loc.']),
                    str(row['Completn date']),
                    str(row['Completion time']),
                    '',
                    session['email'],
                    datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    upload_id
                ))
                records_added += 1

            except Exception as e:
                skipped_rows.append({
                    'row'   : row_num,
                    'reason': f'Database error: {str(e)}'
                })
                continue

        # ── Update the real records_added count in upload_history ──
        c.execute(
            "UPDATE upload_history SET records_added=? WHERE id=?",
            (records_added, upload_id)
        )
        conn.commit()
        conn.close()

        retrain_status = 'Not triggered'
        if records_added > 0:
            try:
                sys.path.append(os.path.join(BASE_DIR, 'scripts'))
                from retrain import retrain as run_retrain
                success, accuracy = run_retrain()
                retrain_status = f'Success — Accuracy: {round(accuracy, 2)}%'
            except Exception as e:
                retrain_status = f'Failed: {str(e)}'

        autofill_summary = []
        for col, info in autofilled_info.items():
            autofill_summary.append({
                'column' : col,
                'default': info['default'],
                'count'  : info['count']
            })

        return jsonify({
            'success'         : True,
            'total_rows'      : total_rows,
            'records_added'   : records_added,
            'skipped_count'   : len(skipped_rows),
            'autofilled_count': sum(i['count'] for i in autofill_summary),
            'skipped_rows'    : skipped_rows[:20],
            'autofill_summary': autofill_summary,
            'retrain_status'  : retrain_status
        })

    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

# ── Get Recent Uploads ──
@app.route('/recent-uploads', methods=['GET'])
def recent_uploads():
    if 'email' not in session:
        return jsonify({'error': 'Not logged in'}), 401

    conn = sqlite3.connect(DB_PATH)
    c    = conn.cursor()

    try:
        c.execute('''
            CREATE TABLE IF NOT EXISTS upload_history (
                id            INTEGER PRIMARY KEY,
                filename      TEXT,
                records_added INTEGER,
                uploaded_by   TEXT,
                uploaded_on   TEXT
            )
        ''')

        c.execute('''
            SELECT id, filename, records_added, uploaded_by, uploaded_on
            FROM upload_history
            ORDER BY id DESC
            LIMIT 10
        ''')
        rows    = c.fetchall()
        uploads = []
        now     = datetime.now()

        for row in rows:
            uploaded_on  = datetime.strptime(row[4], '%Y-%m-%d %H:%M:%S')
            hours_passed = (now - uploaded_on).total_seconds() / 3600
            can_delete   = hours_passed <= 24
            hours_left   = max(0, 24 - hours_passed)

            uploads.append({
                'id'           : row[0],
                'filename'     : row[1],
                'records_added': row[2],
                'uploaded_by'  : row[3],
                'uploaded_on'  : row[4],
                'can_delete'   : can_delete,
                'hours_left'   : round(hours_left, 1)
            })

    except Exception as e:
        uploads = []

    conn.close()
    return jsonify({'uploads': uploads})

# ── Delete Upload ──
@app.route('/delete-upload/<int:upload_id>', methods=['DELETE'])
def delete_upload(upload_id):
    if 'email' not in session:
        return jsonify({'error': 'Not logged in'}), 401
    if session['role'] != 'admin':
        return jsonify({'error': 'Access denied'}), 403

    conn = sqlite3.connect(DB_PATH)
    c    = conn.cursor()

    try:
        # Check upload exists and is within 24 hours
        c.execute(
            "SELECT uploaded_on FROM upload_history WHERE id=?",
            (upload_id,)
        )
        row = c.fetchone()

        if not row:
            conn.close()
            return jsonify({'success': False, 'message': 'Upload not found'})

        uploaded_on  = datetime.strptime(row[0], '%Y-%m-%d %H:%M:%S')
        hours_passed = (datetime.now() - uploaded_on).total_seconds() / 3600

        if hours_passed > 24:
            conn.close()
            return jsonify({
                'success': False,
                'message': '24 hour deletion window has expired'
            })

        # ── Delete all records belonging to this upload_id ──
        c.execute(
            "DELETE FROM new_records WHERE upload_id=?",
            (upload_id,)
        )
        deleted_records = c.rowcount

        # ── Delete from upload history ──
        c.execute("DELETE FROM upload_history WHERE id=?", (upload_id,))

        conn.commit()
        conn.close()

        # Retrain after deletion
        try:
            sys.path.append(os.path.join(BASE_DIR, 'scripts'))
            from retrain import retrain as run_retrain
            run_retrain()
        except:
            pass

        return jsonify({
            'success'        : True,
            'deleted_records': deleted_records,
            'message'        : f'Upload removed. {deleted_records} records deleted.'
        })

    except Exception as e:
        conn.close()
        return jsonify({'success': False, 'message': str(e)})


if __name__ == '__main__':
    init_db()
    print("\nStarting NTPC Defect Predictor Server...")
    print("Open http://127.0.0.1:5000 in your browser")
    app.run(debug=True, port=5000)