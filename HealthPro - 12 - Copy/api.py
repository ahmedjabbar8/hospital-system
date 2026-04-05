from flask import Blueprint, jsonify, session, request
from config import get_db
import datetime

api_bp = Blueprint('api', __name__)


def _fmt_time(dt):
    if isinstance(dt, (datetime.datetime, datetime.date)):
        return dt.strftime('%I:%M %p')
    if isinstance(dt, str):
        try:
            return datetime.datetime.strptime(dt[:19], '%Y-%m-%d %H:%M:%S').strftime('%I:%M %p')
        except Exception:
            return ''
    return ''


def _wait_min(created_at):
    if not created_at:
        return 0
    now = datetime.datetime.now()
    if isinstance(created_at, str):
        try:
            created_at = datetime.datetime.strptime(created_at[:19], '%Y-%m-%d %H:%M:%S')
        except Exception:
            return 0
    try:
        return max(0, int((now - created_at).total_seconds() / 60))
    except Exception:
        return 0


# ══════════════════════════════════════════════════════════════════════════
@api_bp.route('/api_waiting', methods=['GET'])
def api_waiting():
    conn = get_db()
    if not conn:
        return jsonify({'error': 'Database Connection Error'}), 500

    cur = conn.cursor(dictionary=True)

    # ── Column 1 : Reception + Triage ─────────────────────────────────────
    cur.execute("""
        SELECT a.created_at, p.full_name_ar AS p_name, a.status
        FROM appointments a
        JOIN patients p ON a.patient_id = p.patient_id
        WHERE a.status IN ('scheduled','pending_triage')
          AND DATE(a.appointment_date) = date('now')
        ORDER BY a.created_at ASC
    """)
    reception_list = [
        {
            'name':       r['p_name'],
            'wait':       _wait_min(r['created_at']),
            'entrance':   _fmt_time(r['created_at']),
            'status':     r['status'],
            'sub_status': 'بانتظار الدفع' if (r['status'] or '').lower() == 'scheduled' else 'فحص أولي',
        }
        for r in cur.fetchall()
    ]

    # ── Column 2 : Doctor queue (single query with aggregates) ────────────
    cur.execute("""
        SELECT
            a.appointment_id,
            a.created_at,
            a.status,
            a.is_urgent,
            a.call_status,
            p.full_name_ar  AS p_name,
            u.full_name_ar  AS doc_name,
            (SELECT COUNT(*) FROM lab_requests       lr WHERE lr.appointment_id = a.appointment_id AND lr.status IN ('pending','pending_payment')) AS pend_lab,
            (SELECT COUNT(*) FROM radiology_requests rr WHERE rr.appointment_id = a.appointment_id AND rr.status IN ('pending','pending_payment')) AS pend_rad,
            (SELECT COUNT(*) FROM prescriptions      pr WHERE pr.appointment_id = a.appointment_id AND pr.status IN ('pending','pending_payment')) AS pend_rx,
            (SELECT COUNT(*) FROM lab_requests       lr WHERE lr.appointment_id = a.appointment_id AND lr.status = 'completed') +
            (SELECT COUNT(*) FROM radiology_requests rr WHERE rr.appointment_id = a.appointment_id AND rr.status = 'completed') AS done_cnt
        FROM appointments a
        JOIN patients p ON a.patient_id = p.patient_id
        LEFT JOIN users u ON a.doctor_id = u.user_id
        WHERE a.status IN ('waiting_doctor', 'in_progress')
          AND DATE(a.appointment_date) = date('now')
        ORDER BY a.is_urgent DESC, a.created_at ASC
    """)
    doctor_list = []
    for r in cur.fetchall():
        pending = (r.get('pend_lab') or 0) + (r.get('pend_rad') or 0) + (r.get('pend_rx') or 0)
        doctor_list.append({
            'patient':     r['p_name'],
            'doctor':      r['doc_name'] or 'عام',
            'wait':        _wait_min(r['created_at']),
            'entrance':    _fmt_time(r['created_at']),
            'is_ready':    (r.get('done_cnt') or 0) > 0,
            'is_urgent':   bool(r.get('is_urgent')),
            'status':      r['status'],
            'call_status': r.get('call_status') or 0,
            'in_lab':      pending > 0,
            'pending_cnt': pending
        })

    # ── Column 3 : Medical/Exams queue ────────────────────────────────────
    cur.execute("""
        SELECT
            p.full_name_ar AS p_name,
            a.created_at,
            (SELECT COUNT(*) FROM lab_requests       lr WHERE lr.appointment_id = a.appointment_id AND lr.status IN ('pending','pending_payment')) AS pend_labs,
            (SELECT COUNT(*) FROM radiology_requests rr WHERE rr.appointment_id = a.appointment_id AND rr.status IN ('pending','pending_payment')) AS pend_rads,
            (SELECT COUNT(*) FROM prescriptions      pr WHERE pr.appointment_id = a.appointment_id AND pr.status IN ('pending','pending_payment')) AS pend_pharma
        FROM appointments a
        JOIN patients p ON a.patient_id = p.patient_id
        WHERE a.status NOT IN ('completed','cancelled')
          AND DATE(a.appointment_date) = date('now')
        ORDER BY a.created_at ASC
    """)
    exams_list = []
    for ex in cur.fetchall():
        pl = ex.get('pend_labs') or 0
        pr = ex.get('pend_rads') or 0
        pp = ex.get('pend_pharma') or 0
        if pl + pr + pp == 0:
            continue   # nothing pending – skip
        exams_list.append({
            'patient':    ex['p_name'],
            'entrance':   _fmt_time(ex['created_at']),
            'status_msg': 'قيد الانتظار',
            'has_lab':    pl > 0,
            'has_rad':    pr > 0,
            'has_pharma': pp > 0,
        })

    return jsonify({'reception': reception_list, 'doctor': doctor_list, 'medical': exams_list})


# ══════════════════════════════════════════════════════════════════════════
@api_bp.route('/api_ping', methods=['GET'])
def api_ping():
    import time
    return jsonify({'status': 'ok', 'time': int(time.time())})


# ══════════════════════════════════════════════════════════════════════════
@api_bp.route('/api_patient_search', methods=['GET'])
def api_patient_search():
    if not session.get('user_id'):
        return jsonify({'error': 'Unauthorized'}), 401
    q = request.args.get('q', '').strip()
    include_all = request.args.get('all', '0') == '1'
    if not q:
        return jsonify([])
    q_param = f"%{q}%"
    conn = get_db()
    if not conn:
        return jsonify([])
    cur = conn.cursor(dictionary=True)
    
    if include_all:
        cur.execute("""
            SELECT p.patient_id, p.full_name_ar, p.file_number, p.national_id
            FROM patients p
            WHERE (p.full_name_ar LIKE %s OR p.file_number LIKE %s OR p.national_id LIKE %s)
            LIMIT 10
        """, (q_param, q_param, q_param))
    else:
        cur.execute("""
            SELECT p.patient_id, p.full_name_ar, p.file_number, p.national_id
            FROM patients p
            WHERE (p.full_name_ar LIKE %s OR p.file_number LIKE %s OR p.national_id LIKE %s)
              AND NOT EXISTS (
                  SELECT 1 FROM appointments a
                  WHERE a.patient_id = p.patient_id
                    AND DATE(a.appointment_date) = date('now')
                    AND a.status NOT IN ('completed','cancelled')
              )
            LIMIT 10
        """, (q_param, q_param, q_param))

    return jsonify(cur.fetchall())


# ══════════════════════════════════════════════════════════════════════════
@api_bp.route('/api_get_appointment', methods=['GET'])
def api_get_appointment():
    appt_id = request.args.get('id')
    if not appt_id:
        return jsonify({'success': False})
    conn = get_db()
    if not conn:
        return jsonify({'success': False})
    cur = conn.cursor(dictionary=True)
    cur.execute("SELECT * FROM appointments WHERE appointment_id = %s", (appt_id,))
    row = cur.fetchone()
    if row:
        for k, v in row.items():
            if isinstance(v, datetime.datetime):
                row[k] = v.strftime('%Y-%m-%d %H:%M:%S')
            elif isinstance(v, datetime.date):
                row[k] = v.strftime('%Y-%m-%d')
        return jsonify({'success': True, 'data': row})
    return jsonify({'success': False})


# ══════════════════════════════════════════════════════════════════════════
@api_bp.route('/api_update_appointment', methods=['POST'])
def api_update_appointment():
    appt_id = request.form.get('id')
    if not appt_id:
        return jsonify({'success': False})
    date   = request.form.get('date')
    status = request.form.get('status')
    conn = get_db()
    if not conn:
        return jsonify({'success': False, 'message': 'DB Error'})
    try:
        cur = conn.cursor()
        cur.execute("UPDATE appointments SET appointment_date=%s, status=%s WHERE appointment_id=%s",
                    (date, status, appt_id))
        conn.commit()
        return jsonify({'success': True, 'message': ''})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})


# ══════════════════════════════════════════════════════════════════════════
@api_bp.route('/api_cancel_appointment', methods=['POST'])
def api_cancel_appointment():
    if not session.get('user_id'):
        return jsonify({'success': False, 'message': 'Unauthorized'})
    aid = request.form.get('id')
    if not aid:
        return jsonify({'success': False, 'message': 'Invalid Request'})
    conn = get_db()
    if not conn:
        return jsonify({'success': False, 'message': 'DB Error'})
    cur = conn.cursor()
    cur.execute("UPDATE appointments SET status='cancelled' WHERE appointment_id=%s AND status!='completed'", (aid,))
    conn.commit()
    return jsonify({'success': cur.lastrowid is not None or True})


# ══════════════════════════════════════════════════════════════════════════
@api_bp.route('/api_barcode_book', methods=['GET'])
def api_barcode_book():
    if not session.get('user_id'):
        return jsonify({'success': False, 'message': 'Unauthorized'})
    barcode = request.args.get('barcode', '').strip()
    if not barcode:
        return jsonify({'success': False, 'message': 'الباركود فارغ'})
    conn = get_db()
    if not conn:
        return jsonify({'success': False, 'message': 'DB Error'})
    cur = conn.cursor(dictionary=True)
    cur.execute("SELECT patient_id, full_name_ar FROM patients WHERE file_number=%s OR national_id=%s LIMIT 1",
                (barcode, barcode))
    patient = cur.fetchone()
    if not patient:
        return jsonify({'success': False, 'message': 'لم يتم العثور على مريض'})
    pid = patient['patient_id']
    cur.execute("""
        SELECT department_id, doctor_id, appointment_date
        FROM appointments WHERE patient_id=%s ORDER BY appointment_id DESC LIMIT 1
    """, (pid,))
    last = cur.fetchone()
    dept_id   = (last or {}).get('department_id') or 1
    doctor_id = (last or {}).get('doctor_id') or 1
    last_date = (last or {}).get('appointment_date')
    now = datetime.datetime.now()
    if isinstance(last_date, (datetime.date, datetime.datetime)):
        last_dt = datetime.datetime.combine(last_date, datetime.time()) if isinstance(last_date, datetime.date) else last_date
    elif isinstance(last_date, str):
        try:
            last_dt = datetime.datetime.strptime(last_date[:10], '%Y-%m-%d')
        except Exception:
            last_dt = datetime.datetime(2000, 1, 1)
    else:
        last_dt = datetime.datetime(2000, 1, 1)
    is_free = 1 if 0 <= (now - last_dt).days <= 7 else 0
    try:
        cur.execute("""
            INSERT INTO appointments (patient_id, doctor_id, department_id, appointment_date, status, is_free)
            VALUES (%s, %s, %s, date('now'), 'scheduled', %s)
        """, (pid, doctor_id, dept_id, is_free))
        conn.commit()
        msg = f"تم حجز موعد لـ {patient['full_name_ar']}" + (" (مراجعة مجانية)" if is_free else "")
        return jsonify({'success': True, 'message': msg, 'is_free': is_free})
    except Exception as e:
        return jsonify({'success': False, 'message': 'فشل الحجز'})


# ══════════════════════════════════════════════════════════════════════════
@api_bp.route('/api_chat', methods=['GET', 'POST'])
def api_chat():
    if not session.get('user_id'):
        return jsonify({'success': False}), 401
    my_id = session['user_id']
    conn = get_db()
    if not conn:
        return jsonify({'success': False, 'error': 'Database Connection Error'}), 500
    cur = conn.cursor(dictionary=True)
    if request.method == 'POST':
        receiver_id = int(request.form.get('receiver_id', 0))
        message     = request.form.get('message', '')
        cur.execute("INSERT INTO chat_messages (sender_id, receiver_id, message) VALUES (%s,%s,%s)",
                    (my_id, receiver_id, message))
        conn.commit()
        return jsonify({'success': True})
    # GET
    friend_id  = int(request.args.get('with', 0))
    get_status = request.args.get('get_status') is not None
    response   = {}
    if friend_id > 0:
        cur.execute("""
            SELECT * FROM chat_messages
            WHERE (sender_id=%s AND receiver_id=%s) OR (sender_id=%s AND receiver_id=%s)
            ORDER BY created_at ASC
        """, (my_id, friend_id, friend_id, my_id))
        response['messages'] = [
            {'text': m['message'],
             'type': 'sent' if m['sender_id'] == my_id else 'received',
             'time': _fmt_time(m['created_at'])}
            for m in cur.fetchall()
        ]
    if get_status:
        cur.execute("SELECT user_id, last_activity, current_task, active_patient_name FROM users WHERE is_active=1")
        now = datetime.datetime.now()
        statuses = {}
        for u in cur.fetchall():
            la = u['last_activity']
            online = False
            if la:
                if isinstance(la, str):
                    try:
                        la = datetime.datetime.strptime(la[:19], '%Y-%m-%d %H:%M:%S')
                    except Exception:
                        la = None
                if la and isinstance(la, datetime.datetime):
                    online = (now - la).total_seconds() < 45
            statuses[u['user_id']] = {
                'online': online, 'task': u['current_task'], 'patient': u['active_patient_name']
            }
        response['statuses'] = statuses
    return jsonify(response)


# ══════════════════════════════════════════════════════════════════════════
@api_bp.route('/api_recall', methods=['POST'])
def api_recall():
    if not session.get('user_id'):
        return jsonify({'success': False, 'error': 'Unauthorized'})
    appt_id = int(request.form.get('id', 0))
    action  = request.form.get('action', '')
    if appt_id <= 0:
        return jsonify({'success': False, 'error': 'Invalid ID'})
    conn = get_db()
    if not conn:
        return jsonify({'success': False, 'error': 'DB Error'})
    cur = conn.cursor()
    if action == 'trigger':
        cur.execute("UPDATE appointments SET call_status=1 WHERE appointment_id=%s", (appt_id,))
    elif action == 'complete':
        cur.execute("UPDATE appointments SET call_status=2 WHERE appointment_id=%s", (appt_id,))
    elif action == 'cancel':
        cur.execute("UPDATE appointments SET call_status=0 WHERE appointment_id=%s", (appt_id,))
    else:
        return jsonify({'success': False, 'error': 'Invalid action'})
    conn.commit()
    return jsonify({'success': True})


# ══════════════════════════════════════════════════════════════════════════
@api_bp.route('/api_server_stats', methods=['GET'])
def api_server_stats():
    try:
        import psutil
        return jsonify({'cpu': int(psutil.cpu_percent(interval=None)),
                        'ram': int(psutil.virtual_memory().percent)})
    except Exception:
        return jsonify({'cpu': 0, 'ram': 0})


# ══════════════════════════════════════════════════════════════════════════
@api_bp.route('/api_edit_lab_price', methods=['POST'])
def api_edit_lab_price():
    if not session.get('user_id'):
        return jsonify({'status': 'error', 'msg': 'Unauthorized'}), 401
    test_id   = int(request.form.get('test_id', 0))
    new_price = float(request.form.get('new_price', 0))
    conn = get_db()
    if not conn:
        return jsonify({'status': 'error', 'msg': 'DB Error'})
    try:
        cur = conn.cursor()
        cur.execute("UPDATE lab_tests SET price=%s WHERE test_id=%s", (new_price, test_id))
        conn.commit()
        return jsonify({'status': 'success', 'msg': 'تم تعديل السعر بنجاح'})
    except Exception as e:
        return jsonify({'status': 'error', 'msg': str(e)})


# ══════════════════════════════════════════════════════════════════════════
@api_bp.route('/api_toggle_lab_active', methods=['POST'])
def api_toggle_lab_active():
    if not session.get('user_id'):
        return jsonify({'status': 'error', 'msg': 'Unauthorized'}), 401
    test_id = int(request.form.get('test_id', 0))
    active  = int(request.form.get('active', 0))
    conn = get_db()
    if not conn:
        return jsonify({'status': 'error', 'msg': 'DB Error'})
    try:
        cur = conn.cursor()
        cur.execute("UPDATE lab_tests SET is_active=%s WHERE test_id=%s", (active, test_id))
        conn.commit()
        return jsonify({'status': 'success', 'msg': 'تم تحديث حالة التفعيل'})
    except Exception as e:
        return jsonify({'status': 'error', 'msg': str(e)})

# ══════════════════════════════════════════════════════════════════════════
@api_bp.route('/api_dashboard_counts', methods=['GET'])
def api_dashboard_counts():
    if not session.get('user_id'):
        return jsonify({'error': 'Unauthorized'}), 401
    
    role = session.get('role', '')
    user_id = session.get('user_id')
    is_admin = (role == 'admin')
    
    conn = get_db()
    if not conn:
        return jsonify({'error': 'Database Connection Error'}), 500
    cursor = conn.cursor()
    
    # Appointments
    cursor.execute("""
        SELECT
            SUM(CASE WHEN status='scheduled'      THEN 1 ELSE 0 END) AS q_scheduled,
            SUM(CASE WHEN status='pending_triage' THEN 1 ELSE 0 END) AS q_triage,
            SUM(CASE WHEN status='waiting_doctor' AND (doctor_id = ? OR ? = 1) THEN 1 ELSE 0 END) AS q_doctor,
            SUM(CASE WHEN status='completed'      THEN 1 ELSE 0 END) AS q_done
        FROM appointments
        WHERE DATE(appointment_date) = date('now')
    """, (user_id, 1 if is_admin else 0))
    row = cursor.fetchone()
    
    # Labs
    cursor.execute("SELECT COUNT(*) FROM lab_requests WHERE status='pending' AND DATE(created_at) = date('now')")
    q_labs = int((cursor.fetchone() or [0])[0] or 0)
    
    # Rads
    cursor.execute("SELECT COUNT(*) FROM radiology_requests WHERE status='pending' AND DATE(created_at) = date('now')")
    q_rads = int((cursor.fetchone() or [0])[0] or 0)
    
    # Pharmacy
    cursor.execute("""
        SELECT COUNT(*) FROM prescriptions 
        WHERE status IN ('pending','pending_payment') AND DATE(created_at) = date('now')
    """)
    q_pharmacy = int((cursor.fetchone() or [0])[0] or 0)
    
    # Nursing
    q_nursing = 0
    try:
        cursor.execute("""
            SELECT COUNT(*) FROM lab_requests l
            LEFT JOIN nursing_lab_collections nc ON nc.request_id = l.request_id
            WHERE l.status IN ('pending','pending_payment')
              AND nc.request_id IS NULL
              AND DATE(l.created_at) = date('now')
        """)
        q_nursing = int((cursor.fetchone() or [0])[0] or 0)
    except:
        pass
        
    return jsonify({
        'scheduled': int(row[0] or 0),
        'triage':    int(row[1] or 0),
        'doctor':    int(row[2] or 0),
        'done':      int(row[3] or 0),
        'labs':      q_labs,
        'rads':      q_rads,
        'pharmacy':  q_pharmacy,
        'nursing':   q_nursing
    })
