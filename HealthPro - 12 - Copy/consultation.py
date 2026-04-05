from flask import Blueprint, session, redirect, url_for, request, flash, render_template_string
from config import get_db, can_access
from header import header_html
from footer import footer_html
import datetime
import json

consultation_bp = Blueprint('consultation', __name__)

@consultation_bp.route('/consultation', methods=['GET', 'POST'])
def consultation():
    if not session.get('user_id'):
        return redirect(url_for('login.login'))

    appt_id = request.args.get('id')
    if not appt_id:
        return redirect(url_for('doctor_clinic.doctor_clinic'))

    conn = get_db()
    if not conn:
        return "Database Connection Error"

    cursor = conn.cursor(dictionary=True)

    sql = """
        SELECT a.*, p.*, t.blood_pressure, t.temperature, t.pulse, t.weight, t.height, t.oxygen, t.nurse_notes as triage_notes
        FROM appointments a
        JOIN patients p ON a.patient_id = p.patient_id
        LEFT JOIN triage t ON a.appointment_id = t.appointment_id
        WHERE a.appointment_id = %s
    """
    cursor.execute(sql, (appt_id,))
    data = cursor.fetchone()

    if not data:
        conn.close()
        return redirect(url_for('doctor_clinic.doctor_clinic'))

    p_name = data.get('full_name_ar', 'مريض')
    cursor.execute("UPDATE users SET current_task = 'معاينة طبية جارية', active_patient_name = %s WHERE user_id = %s",
                   (p_name, session['user_id']))
    
    # Update status to 'in_progress' so the Monitor knows the patient is with the doctor
    if data['status'] == 'waiting_doctor':
        cursor.execute("UPDATE appointments SET status = 'in_progress' WHERE appointment_id = %s", (appt_id,))
    
    conn.commit()

    patient_id = data['patient_id']
    doctor_id  = session['user_id']

    cursor.execute("SELECT * FROM system_settings WHERE setting_key LIKE 'price_%'")
    prices_res = cursor.fetchall()
    prices = {pr['setting_key']: pr['setting_value'] for pr in prices_res}

    lab_price = float(prices.get('price_lab_default', 15000))
    rad_price = float(prices.get('price_rad_default', 30000))
    rx_price  = float(prices.get('price_rx_default',  5000))
    if lab_price <= 0: lab_price = 15000
    if rad_price <= 0: rad_price = 30000
    if rx_price  <= 0: rx_price  = 5000

    if request.method == 'POST':
        if 'send_labs' in request.form:
            selected_tests = request.form.getlist('selected_tests[]')
            if selected_tests:
                for test in selected_tests:
                    cursor.execute("SELECT price FROM lab_tests WHERE test_name = %s", (test,))
                    p_row = cursor.fetchone()
                    this_price = p_row['price'] if p_row else lab_price
                    cursor.execute("""
                        INSERT INTO lab_requests (appointment_id, patient_id, doctor_id, test_type, price, status)
                        VALUES (%s, %s, %s, %s, %s, 'pending_payment')
                    """, (appt_id, patient_id, doctor_id, test, this_price))
                conn.commit()
                flash("تم إرسال التحاليل بنجاح للمحاسبة", "info")

        elif 'send_rads' in request.form:
            selected_scans = request.form.getlist('selected_scans[]')
            if selected_scans:
                for scan in selected_scans:
                    cursor.execute("SELECT price FROM radiology_tests WHERE test_name = %s", (scan,))
                    r_p_row = cursor.fetchone()
                    this_rad_price = r_p_row['price'] if r_p_row else rad_price
                    cursor.execute("""
                        INSERT INTO radiology_requests (appointment_id, patient_id, doctor_id, scan_type, price, status)
                        VALUES (%s, %s, %s, %s, %s, 'pending_payment')
                    """, (appt_id, patient_id, doctor_id, scan, this_rad_price))
                conn.commit()
                flash("تم إرسال طلبات الأشعة للمحاسبة", "info")

        elif 'send_ref' in request.form:
            to_dept = request.form.get('to_dept')
            reason  = request.form.get('reason')
            if to_dept:
                cursor.execute("""
                    INSERT INTO referrals (appointment_id, patient_id, from_doctor_id, to_department_id, reason)
                    VALUES (%s, %s, %s, %s, %s)
                """, (appt_id, patient_id, doctor_id, to_dept, reason))
                conn.commit()
                flash("تم إحالة المريض بنجاح", "warning")

        elif 'finish_visit' in request.form:
            ass  = request.form.get('assessment', '')
            sub  = request.form.get('notes', '')
            meds = request.form.get('rx', '')
            cursor.execute("""
                INSERT INTO consultations (patient_id, doctor_id, appointment_id, subjective, assessment, plan)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (patient_id, doctor_id, appt_id, sub, ass, meds))
            if meds:
                cursor.execute("""
                    INSERT INTO prescriptions (appointment_id, patient_id, doctor_id, medicine_name, price, status)
                    VALUES (%s, %s, %s, %s, %s, 'pending_payment')
                """, (appt_id, patient_id, doctor_id, meds, rx_price))
            cursor.execute("UPDATE appointments SET status = 'completed', completed_at = NOW() WHERE appointment_id = %s", (appt_id,))
            conn.commit()
            flash("تم إنهاء الزيارة وحفظ الملف الطبي", "success")
            conn.close()
            return redirect(url_for('doctor_clinic.doctor_clinic'))

        elif 'book_followup' in request.form:
            followup_date = request.form.get('followup_date')
            if followup_date:
                try:
                    f_date   = datetime.datetime.strptime(followup_date, '%Y-%m-%d').date()
                    now_date = datetime.date.today()
                    diff     = (f_date - now_date).days
                    is_free  = 1 if 0 <= diff <= 7 else 0
                    cursor.execute("""
                        INSERT INTO appointments (patient_id, doctor_id, department_id, appointment_date, status, is_free)
                        VALUES (%s, %s, %s, %s, 'scheduled', %s)
                    """, (patient_id, doctor_id, data['department_id'], followup_date, is_free))
                    conn.commit()
                    msg = f"تم حجز موعد مراجعة {followup_date} {'(مجاني)' if is_free else '(استشارة عادية)'}"
                    flash(msg, "success" if is_free else "info")
                except Exception as e:
                    flash(f"خطأ في التاريخ: {str(e)}", "danger")

    # ── Master data lists ──
    def safe_decode(text):
        if not text: return ""
        if isinstance(text, bytes):
            try:    text = text.decode('utf-8')
            except:
                try: text = text.decode('cp1256')
                except: text = str(text)
        else:
            text = str(text)
        return text.replace('\ufffd', '').replace('\u0000', '').strip()

    cursor.execute("SELECT test_name FROM lab_tests WHERE is_active = 1 ORDER BY test_name ASC")
    lab_list = [safe_decode(r['test_name']) for r in cursor.fetchall()]
    for dl in ['CBC','FBS','HBA1C','Urea','Creatinine','SGOT','SGPT','Lipid Profile','TSH','Vitamin D','CRP','Urine R/E','Stool R/E','H. Pylori','PSA']:
        if dl not in lab_list: lab_list.append(dl)

    cursor.execute("SELECT test_name FROM radiology_tests WHERE is_active = 1 ORDER BY test_name ASC")
    rad_list = [safe_decode(r['test_name']) for r in cursor.fetchall()]
    for dr in ['X-Ray Chest','U/S Abdomen','CT Brain','MRI Brain','X-Ray Knee','U/S Pelvis']:
        if dr not in rad_list: rad_list.append(dr)

    cursor.execute("SELECT * FROM lab_requests       WHERE appointment_id = %s", (appt_id,))
    curr_labs = cursor.fetchall()
    cursor.execute("SELECT * FROM radiology_requests WHERE appointment_id = %s", (appt_id,))
    curr_rads = cursor.fetchall()
    cursor.execute("SELECT * FROM departments WHERE department_type = 'medical'")
    depts = cursor.fetchall()
    cursor.execute("""
        SELECT c.*, u.full_name_ar as doc_name
        FROM consultations c
        JOIN users u ON c.doctor_id = u.user_id
        WHERE c.patient_id = %s ORDER BY c.created_at DESC
    """, (patient_id,))
    history = cursor.fetchall()

    diag_list = ['J06.9 (Acute upper respiratory infection)', 'I10 (Essential hypertension)', 
                 'E11.9 (Type 2 diabetes mellitus)', 'M54.5 (Low back pain)', 
                 'R51 (Headache)', 'K21.9 (Gastro-esophageal reflux disease)', 
                 'J45.9 (Asthma, unspecified)', 'N39.0 (Urinary tract infection)', 
                 'B34.9 (Viral infection, unspecified)', 'D64.9 (Anemia, unspecified)',
                 'Influenza','Acute Pharyngitis','Gastroenteritis','Hypertension','Diabetes Mellitus Type 2',
                 'Bronchial Asthma','Urinary Tract Infection (UTI)','Migraine','Tension Headache','Back Pain',
                 'Upper Respiratory Tract Infection','Anemia','Allergic Rhinitis','Otitis Media','Acute Sinusitis']
    med_list  = ['Paracetamol 500mg','Amoxicillin 500mg','Ibuprofen 400mg','Omeprazole 20mg','Metformin 500mg',
                 'Loratadine 10mg','Salbutamol Inhaler','Azithromycin 250mg','Ciprofloxacin 500mg','Augmentin 625mg',
                 'Buscopan 10mg','Panadol Extra','Cough Syrup','Vitamin C 1000mg','Diclofenac 50mg']

    cursor.execute("""
        SELECT lr.*, u.full_name_ar as doc_name 
        FROM lab_requests lr 
        LEFT JOIN users u ON lr.doctor_id = u.user_id 
        WHERE lr.patient_id = %s AND lr.result IS NOT NULL AND lr.result != ''
        ORDER BY lr.created_at DESC
    """, (patient_id,))
    lab_history = cursor.fetchall()

    cursor.execute("""
        SELECT rr.*, u.full_name_ar as doc_name 
        FROM radiology_requests rr 
        LEFT JOIN users u ON rr.doctor_id = u.user_id 
        WHERE rr.patient_id = %s AND rr.report IS NOT NULL AND rr.report != ''
        ORDER BY rr.created_at DESC
    """, (patient_id,))
    rad_history = cursor.fetchall()


    html = header_html + """

    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
        body { background:#f0f2f5; font-family:'Inter',sans-serif; }

        /* Sidebar */
        .hp-sidebar {
            background: linear-gradient(160deg, #0f2027, #203a43, #2c5364);
            border-radius: 22px; color:#fff; position: sticky; top: 76px; overflow: hidden;
        }
        .hp-sidebar::before {
            content:''; position:absolute; width:200px; height:200px;
            background:rgba(255,255,255,0.04); border-radius:50%;
            top:-50px; right:-50px; pointer-events:none;
        }
        .avatar-circle {
            width:78px; height:78px; border-radius:50%; margin:0 auto 14px;
            background: linear-gradient(135deg,#43e97b,#38f9d7);
            display:flex; align-items:center; justify-content:center;
            font-size:2rem; color:#fff;
            box-shadow: 0 8px 24px rgba(67,233,123,0.35);
        }
        .vital-row {
            background:rgba(255,255,255,0.09); border-radius:12px;
            padding:10px 14px; margin-bottom:8px;
            display:flex; align-items:center; gap:10px;
        }
        .vital-icon {
            width:34px; height:34px; border-radius:9px;
            display:flex; align-items:center; justify-content:center; font-size:0.88rem;
        }
        .vital-label { font-size:0.68rem; opacity:0.55; }
        .vital-val   { font-size:0.95rem; font-weight:700; }

        /* Tabs */
        .hp-tabs {
            background:#fff; border-radius:18px; padding:5px;
            display:flex; flex-wrap:wrap; gap:4px;
            box-shadow:0 2px 12px rgba(0,0,0,0.06); margin-bottom:22px;
        }
        .hp-tab {
            border:none; border-radius:13px; padding:9px 18px;
            font-size:0.84rem; font-weight:600; color:#888;
            background:transparent; cursor:pointer; transition:all .2s;
            display:flex; align-items:center; gap:7px; white-space:nowrap;
        }
        .hp-tab .cnt {
            background:#e9e9ef; color:#888; border-radius:20px;
            padding:1px 8px; font-size:0.72rem; font-weight:700; transition:all .2s;
        }
        .hp-tab.active {
            background:linear-gradient(135deg,#667eea,#764ba2);
            color:#fff; box-shadow:0 4px 14px rgba(102,126,234,.35);
        }
        .hp-tab.active .cnt { background:rgba(255,255,255,0.3); color:#fff; }

        /* Cards */
        .hp-card {
            background:#fff; border-radius:18px; padding:24px;
            box-shadow:0 2px 14px rgba(0,0,0,0.045); margin-bottom:18px;
        }
        .hp-card-title {
            font-size:0.92rem; font-weight:700; color:#1c1c1e;
            margin-bottom:14px; display:flex; align-items:center; gap:10px;
        }
        .title-icon {
            width:32px; height:32px; border-radius:9px;
            display:flex; align-items:center; justify-content:center; font-size:0.82rem;
        }

        /* Inputs */
        .hp-field {
            width:100%; border:2px solid #eef0f5; border-radius:13px;
            padding:12px 16px; font-size:0.93rem; background:#fafbff;
            transition:border-color .2s; color:#1c1c1e;
            font-family:'Inter',sans-serif;
        }
        .hp-field:focus { outline:none; border-color:#667eea; background:#fff; }
        textarea.hp-field { resize:vertical; }

        /* Search wrapper */
        .search-wrap { position:relative; }
        .search-wrap .s-icon {
            position:absolute; right:14px; top:50%; transform:translateY(-50%);
            color:#bbb; font-size:0.9rem; pointer-events:none;
        }
        .search-wrap .hp-field { padding-right:40px; }

        /* Grid */
        .items-grid {
            display:grid;
            grid-template-columns:repeat(auto-fill, minmax(148px,1fr));
            gap:7px; max-height:220px; overflow-y:auto; padding:2px;
        }
        .g-item {
            background:#f7f8ff; border:1.5px solid #e6e8f5; border-radius:11px;
            padding:9px 10px; cursor:pointer; font-size:0.8rem; font-weight:600;
            color:#555; text-align:center; transition:all .18s; user-select:none;
        }
        .g-item:hover {
            background:linear-gradient(135deg,#667eea,#764ba2);
            color:#fff; border-color:transparent;
            transform:translateY(-2px); box-shadow:0 5px 14px rgba(102,126,234,.28);
        }

        /* Tags */
        .tags-area {
            min-height:68px; background:#f8f9ff; border-radius:13px;
            padding:10px; display:flex; flex-wrap:wrap; gap:7px;
            align-content:flex-start; border:2px dashed #dde0f5; margin:14px 0;
        }
        .tags-area .empty-hint {
            width:100%; text-align:center; color:#c5c7d8; font-size:0.82rem; padding:8px 0;
        }
        .hp-tag {
            background:linear-gradient(135deg,#eef0ff,#f0eaff);
            color:#667eea; border:1.5px solid #cdd0f5;
            border-radius:20px; padding:5px 13px;
            font-size:0.8rem; font-weight:700;
            display:inline-flex; align-items:center; gap:7px;
        }
        .hp-tag .x { cursor:pointer; color:#e74c3c; font-size:0.72rem; transition:.15s; }
        .hp-tag .x:hover { transform:scale(1.4); }

        /* Buttons */
        .hp-btn {
            display:block; width:100%; padding:13px; border:none;
            border-radius:13px; font-size:0.97rem; font-weight:700;
            cursor:pointer; transition:all .2s; letter-spacing:.3px;
        }
        .hp-btn-primary {
            background:linear-gradient(135deg,#667eea,#764ba2);
            color:#fff; box-shadow:0 6px 18px rgba(102,126,234,.3);
        }
        .hp-btn-primary:hover { transform:translateY(-2px); box-shadow:0 10px 26px rgba(102,126,234,.42); }
        .hp-btn-labs  { background:linear-gradient(135deg,#007aff,#5856d6); color:#fff; }
        .hp-btn-rads  { background:linear-gradient(135deg,#5ac8fa,#007aff); color:#fff; }
        .hp-btn-ref   { background:linear-gradient(135deg,#f39c12,#e67e22); color:#fff; }
        .hp-btn-fup   { background:linear-gradient(135deg,#27ae60,#2ecc71); color:#fff; }
        .hp-btn:disabled { background:#e5e5ea; color:#aaa; cursor:not-allowed; box-shadow:none; transform:none; }
        .hp-btn:not(:disabled):hover { filter:brightness(1.06); }

        /* Sidebar btn */
        .sidebar-btn {
            display:block; width:100%; padding:11px; border-radius:12px; border:none;
            font-size:0.88rem; font-weight:700; cursor:pointer; text-align:center;
            transition:all .2s; text-decoration:none;
        }

        /* Modal */
        .hist-item {
            background:#fff; border-radius:14px; border:1.5px solid #f0f0f8;
            padding:16px; margin-bottom:10px; transition:border-color .2s;
        }
        .hist-item:hover { border-color:#667eea; }
    </style>

    <div class="container-fluid px-3 px-md-4 py-4" style="max-width:1500px;margin:0 auto;">
        <div class="row g-4">

            <!-- ══════ SIDEBAR ══════ -->
            <div class="col-lg-3">
                <div class="hp-sidebar p-4 position-relative">

                    <div class="avatar-circle">
                        <i class="fas fa-user-injured"></i>
                    </div>
                    <div class="text-center mb-4">
                        <h5 class="fw-bold mb-1" style="font-size:1rem;">{{ data.full_name_ar }}</h5>
                        <span class="badge rounded-pill px-3 py-1" style="background:rgba(255,255,255,0.14);font-size:0.75rem;">
                            <i class="fas fa-id-badge me-1"></i>{{ data.file_number }}
                        </span>
                    </div>

                    <div class="mb-4">
                        <div class="vital-row">
                            <div class="vital-icon" style="background:rgba(255,80,80,.2);color:#ff6b6b;"><i class="fas fa-heartbeat"></i></div>
                            <div><div class="vital-label">ضغط الدم</div><div class="vital-val">{{ data.blood_pressure or '--/--' }}</div></div>
                        </div>
                        <div class="vital-row">
                            <div class="vital-icon" style="background:rgba(255,180,0,.2);color:#ffc600;"><i class="fas fa-thermometer-half"></i></div>
                            <div><div class="vital-label">الحرارة</div><div class="vital-val">{{ data.temperature or '--' }} °C</div></div>
                        </div>
                        <div class="vital-row">
                            <div class="vital-icon" style="background:rgba(52,199,89,.2);color:#4cd964;"><i class="fas fa-tachometer-alt"></i></div>
                            <div><div class="vital-label">النبض</div><div class="vital-val">{{ data.pulse or '--' }} bpm</div></div>
                        </div>
                        <div class="vital-row">
                            <div class="vital-icon" style="background:rgba(90,200,250,.2);color:#5ac8fa;"><i class="fas fa-lungs"></i></div>
                            <div><div class="vital-label">الأكسجين</div><div class="vital-val">{{ data.oxygen or '--' }} %</div></div>
                        </div>
                    </div>

                    {% if data.allergies %}
                    <div class="mb-3 p-3 rounded-4" style="background:rgba(255,59,48,0.15); border:1px solid rgba(255,59,48,0.3);">
                        <div class="small fw-bold text-danger mb-1"><i class="fas fa-exclamation-triangle me-1"></i> تنبيه: الحساسية</div>
                        <div class="small fw-bold">{{ data.allergies }}</div>
                    </div>
                    {% endif %}

                    {% if data.medical_history %}
                    <div class="mb-4 p-3 rounded-4" style="background:rgba(255,255,255,0.08); border:1px solid rgba(255,255,255,0.1);">
                        <div class="small fw-bold opacity-50 mb-1"><i class="fas fa-notes-medical me-1"></i> التاريخ المرضي</div>
                        <div class="small">{{ data.medical_history }}</div>
                    </div>
                    {% endif %}

                    <button class="sidebar-btn mb-2" style="background:rgba(255,255,255,0.12);color:#fff;"
                            data-bs-toggle="modal" data-bs-target="#historyModal">
                        <i class="fas fa-history me-2"></i>السجل الطبي السابق
                    </button>
                    <a href="/patient_file?id={{ data.patient_id }}" target="_blank"
                       class="sidebar-btn mb-2" style="background:rgba(255,255,255,0.06);color:rgba(255,255,255,.65);">
                        <i class="fas fa-external-link-alt me-1"></i> الملف الطبي الكامل
                    </a>
                    <a href="/waiting_list" target="_blank"
                       class="sidebar-btn" style="background:linear-gradient(135deg,#27ae60,#2ecc71);color:#fff;box-shadow:0 4px 15px rgba(39,174,96,0.3);">
                        <i class="fas fa-tv me-1"></i> شاشة المراقبة
                    </a>
                </div>
            </div>

            <!-- ══════ MAIN ══════ -->
            <div class="col-lg-9">

                <!-- Tabs -->
                <div class="hp-tabs">
                    <button type="button" class="hp-tab active" data-hp-target="t-exam"><i class="fas fa-stethoscope"></i> المعاينة</button>
                    <button type="button" class="hp-tab"        data-hp-target="t-labs"><i class="fas fa-flask"></i> المختبر <span class="cnt" id="labBadge">0</span></button>
                    <button type="button" class="hp-tab"        data-hp-target="t-rads"><i class="fas fa-radiation"></i> الأشعة <span class="cnt" id="radBadge">0</span></button>
                    <button type="button" class="hp-tab"        data-hp-target="t-ref"><i class="fas fa-share-alt"></i> إحالة</button>
                    <button type="button" class="hp-tab"        data-hp-target="t-fup"><i class="fas fa-calendar-check"></i> مراجعة</button>
                    <button type="button" class="hp-tab"        data-hp-target="t-res"><i class="fas fa-microscope"></i> نتائج الفحوصات</button>
                </div>

                <!-- ─── EXAM ─── -->
                <div id="t-exam" class="hp-tab-pane">
                    <form method="POST">

                        <div class="hp-card">
                            <div class="hp-card-title">
                                <span class="title-icon" style="background:#eef0ff;color:#667eea;"><i class="fas fa-file-medical-alt"></i></span>
                                الشكوى والملاحظات السريرية
                            </div>
                            <textarea name="notes" class="hp-field" rows="5"
                                      placeholder="اكتب الأعراض، المدة، الشدة..." required></textarea>
                        </div>

                        <div class="hp-card">
                            <div class="hp-card-title">
                                <span class="title-icon" style="background:#fff0f0;color:#e74c3c;"><i class="fas fa-stethoscope"></i></span>
                                التشخيص النهائي (Assessment)
                            </div>
                            <div class="search-wrap">
                                <input type="text" name="assessment"
                                       list="diagDatalist" class="hp-field"
                                       placeholder="اكتب أو ابحث عن التشخيص من أول حرف..."
                                       required autocomplete="on">
                                <i class="fas fa-search s-icon"></i>
                            </div>
                            <datalist id="diagDatalist">
                                {% for d in diag_list %}<option value="{{ d }}">{% endfor %}
                            </datalist>
                        </div>

                        <div class="hp-card">
                            <div class="hp-card-title" style="flex-wrap:wrap;gap:8px;">
                                <span class="title-icon" style="background:#f0fff4;color:#27ae60;"><i class="fas fa-pills"></i></span>
                                الخطة العلاجية والوصفة الطبية (Rx)
                                <div class="dropdown ms-auto">
                                    <button type="button" class="btn btn-sm rounded-pill fw-semibold"
                                            style="background:#f0fff4;color:#27ae60;font-size:0.8rem;"
                                            data-bs-toggle="dropdown">
                                        <i class="fas fa-magic me-1"></i>قوالب جاهزة
                                    </button>
                                    <ul class="dropdown-menu dropdown-menu-end shadow border-0 rounded-4 p-2">
                                        <li><button type="button" class="dropdown-item rounded-3 py-2"
                                            onclick="hpUseTpl('Paracetamol 500mg - 3x daily\\nAmoxicillin 500mg - every 8h\\nRest for 3 days')">
                                            🤒 Flu / Fever</button></li>
                                        <li><button type="button" class="dropdown-item rounded-3 py-2"
                                            onclick="hpUseTpl('Buscopan 10mg - 3x daily\\nAntacid - 10ml after meals\\nAvoid spicy food')">
                                            😣 Stomach Ache</button></li>
                                        <li><button type="button" class="dropdown-item rounded-3 py-2"
                                            onclick="hpUseTpl('Cough Syrup 5ml - 3x daily\\nVitamin C 1000mg once daily\\nSteam inhalation')">
                                            🤧 Cough / Cold</button></li>
                                    </ul>
                                </div>
                            </div>
                            <div class="search-wrap mb-3">
                                <input type="text" id="medInput" list="medDatalist" class="hp-field"
                                       placeholder="ابحث عن دواء واضغط Enter لإضافته للوصفة..."
                                       autocomplete="on">
                                <i class="fas fa-pills s-icon" style="color:#27ae60;"></i>
                            </div>
                            <datalist id="medDatalist">
                                {% for m in med_list %}<option value="{{ m }}">{% endfor %}
                            </datalist>
                            <textarea name="rx" id="rxArea" class="hp-field" rows="4"
                                      placeholder="الوصفة الطبية وتعليمات العلاج..."></textarea>
                        </div>

                        <button type="submit" name="finish_visit" class="hp-btn hp-btn-primary" style="font-size:1rem;">
                            <i class="fas fa-file-signature me-2"></i>إنهاء المعاينة وحفظ السجل الطبي
                        </button>
                    </form>
                </div>

                <!-- ─── LABS ─── -->
                <div id="t-labs" class="hp-tab-pane" style="display:none;">
                    <div class="hp-card">
                        <div class="hp-card-title">
                            <span class="title-icon" style="background:#eef4ff;color:#007aff;"><i class="fas fa-flask"></i></span>
                            طلب فحوصات مخبرية
                            <span class="badge rounded-pill ms-auto px-3" style="background:#eef4ff;color:#007aff;">
                                <i class="fas fa-vials me-1"></i>اختر من الشبكة أو ابحث
                            </span>
                        </div>

                        <div class="search-wrap mb-3 d-flex gap-2">
                            <div class="position-relative flex-grow-1">
                                <input type="text" id="labSearch" class="hp-field w-100"
                                       placeholder="ابحث من أول حرف... (مثال: c أو CBC)"
                                       autocomplete="off">
                                <i class="fas fa-search s-icon"></i>
                            </div>
                            <button type="button" id="labAddBtn" class="btn hp-btn-labs m-0" style="width:auto; padding:0 24px; border-radius:13px;"><i class="fas fa-plus me-1"></i>إضافة</button>
                        </div>

                        <div class="items-grid" id="labGrid">
                            {% for item in lab_list %}
                            <div class="g-item" data-val="{{ item }}">{{ item }}</div>
                            {% endfor %}
                        </div>

                        <div class="tags-area" id="selectedLabs">
                            <div class="empty-hint"><i class="fas fa-mouse-pointer me-1"></i>انقر على فحص أو ابحث ثم Enter لإضافته</div>
                        </div>

                        <form method="POST">
                            <div id="labHidden"></div>
                            <button type="submit" name="send_labs" class="hp-btn hp-btn-labs" id="labSubmitBtn" disabled>
                                <i class="fas fa-paper-plane me-2"></i>إرسال طلبات المختبر (<span id="labCount">0</span> فحص)
                            </button>
                        </form>
                    </div>
                </div>

                <!-- ─── RADS ─── -->
                <div id="t-rads" class="hp-tab-pane" style="display:none;">
                    <div class="hp-card">
                        <div class="hp-card-title">
                            <span class="title-icon" style="background:#e8f9ff;color:#5ac8fa;"><i class="fas fa-x-ray"></i></span>
                            طلب فحوصات شعاعية
                            <span class="badge rounded-pill ms-auto px-3" style="background:#e8f9ff;color:#5ac8fa;">
                                <i class="fas fa-radiation me-1"></i>اختر من الشبكة أو ابحث
                            </span>
                        </div>

                        <div class="search-wrap mb-3 d-flex gap-2">
                            <div class="position-relative flex-grow-1">
                                <input type="text" id="radSearch" class="hp-field w-100"
                                       placeholder="ابحث من أول حرف... (مثال: x أو CT)"
                                       autocomplete="off">
                                <i class="fas fa-search s-icon"></i>
                            </div>
                            <button type="button" id="radAddBtn" class="btn hp-btn-rads m-0" style="width:auto; padding:0 24px; border-radius:13px;"><i class="fas fa-plus me-1"></i>إضافة</button>
                        </div>

                        <div class="items-grid" id="radGrid">
                            {% for item in rad_list %}
                            <div class="g-item" data-val="{{ item }}">{{ item }}</div>
                            {% endfor %}
                        </div>

                        <div class="tags-area" id="selectedRads">
                            <div class="empty-hint"><i class="fas fa-mouse-pointer me-1"></i>انقر على أشعة أو ابحث ثم Enter لإضافتها</div>
                        </div>

                        <form method="POST">
                            <div id="radHidden"></div>
                            <button type="submit" name="send_rads" class="hp-btn hp-btn-rads" id="radSubmitBtn" disabled>
                                <i class="fas fa-paper-plane me-2"></i>إرسال طلبات الأشعة (<span id="radCount">0</span> فحص)
                            </button>
                        </form>
                    </div>
                </div>

                <!-- ─── REFERRAL ─── -->
                <div id="t-ref" class="hp-tab-pane" style="display:none;">
                    <div class="hp-card">
                        <div class="hp-card-title">
                            <span class="title-icon" style="background:#fff8e1;color:#f39c12;"><i class="fas fa-share-alt"></i></span>
                            تحويل المريض إلى عيادة أخرى
                        </div>
                        <form method="POST">
                            <div class="row g-3">
                                <div class="col-md-6">
                                    <label class="fw-semibold small text-muted mb-1">العيادة المحول إليها</label>
                                    <select name="to_dept" class="hp-field">
                                        {% for d in depts %}
                                        <option value="{{ d.department_id }}">{{ d.department_name_ar }}</option>
                                        {% endfor %}
                                    </select>
                                </div>
                                <div class="col-12">
                                    <label class="fw-semibold small text-muted mb-1">سبب التحويل</label>
                                    <textarea name="reason" class="hp-field" rows="3" placeholder="لماذا يتم تحويل المريض؟"></textarea>
                                </div>
                                <div class="col-12">
                                    <button type="submit" name="send_ref" class="hp-btn hp-btn-ref">
                                        <i class="fas fa-check-circle me-2"></i>تأكيد عملية الإحالة
                                    </button>
                                </div>
                            </div>
                        </form>
                    </div>
                </div>

                <!-- ─── FOLLOWUP ─── -->
                <div id="t-fup" class="hp-tab-pane" style="display:none;">
                    <div class="hp-card text-center">
                        <div class="hp-card-title" style="justify-content:center;">
                            <span class="title-icon" style="background:#f0fff4;color:#27ae60;"><i class="fas fa-calendar-check"></i></span>
                            تحديد موعد مراجعة (Follow-up)
                        </div>
                        <p class="text-muted small mb-4">إذا كان التاريخ خلال 7 أيام، يكون باص المراجعة مجانياً.</p>
                        <form method="POST" style="max-width:360px;margin:0 auto;">
                            <div class="mb-4">
                                <label class="fw-semibold small text-muted mb-1 d-block">تاريخ المراجعة</label>
                                <input type="date" name="followup_date" class="hp-field text-center"
                                       value="{{ followup_date_val }}" min="{{ today_date }}">
                            </div>
                            <button type="submit" name="book_followup" class="hp-btn hp-btn-fup">
                                <i class="fas fa-calendar-plus me-2"></i>تأكيد حجز موعد المراجعة
                            </button>
                        </form>
                    </div>
                </div>

                <!-- ─── RESULTS ─── -->
                <div id="t-res" class="hp-tab-pane" style="display:none;">
                    <div class="row g-3">
                        <div class="col-md-6">
                            <div class="hp-card" style="padding:20px;">
                                <div class="hp-card-title text-primary align-items-center d-flex mb-3">
                                    <div class="title-icon" style="background:#eef4ff;color:#007aff;"><i class="fas fa-flask"></i></div>
                                    <span class="ms-2">النتائج المختبرية ({{ lab_history|length }})</span>
                                </div>
                                <div style="max-height:450px; overflow-y:auto; padding-right:5px;">
                                    {% if lab_history %}
                                        {% for lr in lab_history %}
                                        <div style="background:#fcfdff; border:1px solid #eef0f5; border-radius:12px; padding:12px; margin-bottom:12px; box-shadow:0 1px 4px rgba(0,0,0,0.02)">
                                            <div class="d-flex justify-content-between align-items-center mb-2">
                                                <span class="badge bg-light text-dark border">د. {{ lr.doc_name }}</span>
                                                <span class="small text-muted" style="font-size:0.75rem;">
                                                    {% if lr.created_at and lr.created_at.__class__.__name__ == 'datetime' %}
                                                        {{ lr.created_at.strftime('%Y-%m-%d | %I:%M %p') }}
                                                    {% else %}{{ lr.created_at }}{% endif %}
                                                </span>
                                            </div>
                                            <div class="fw-bold mb-2" style="color:#007aff; font-size:0.9rem;">{{ lr.test_type }}</div>
                                            <div class="small p-2 rounded" style="background:#fff; border:1px dashed #cdd0f5; color:#333; white-space:pre-wrap;">{{ lr.result }}</div>
                                        </div>
                                        {% endfor %}
                                    {% else %}
                                        <div class="text-center text-muted small py-4">
                                            <i class="fas fa-vial fa-2x mb-2" style="color:#eef0f5;"></i><br>
                                            لا توجد نتائج مختبرية سابقة
                                        </div>
                                    {% endif %}
                                </div>
                            </div>
                        </div>

                        <div class="col-md-6">
                            <div class="hp-card" style="padding:20px;">
                                <div class="hp-card-title text-info align-items-center d-flex mb-3">
                                    <div class="title-icon" style="background:#e8f9ff;color:#5ac8fa;"><i class="fas fa-radiation"></i></div>
                                    <span class="ms-2">تقارير الأشعة ({{ rad_history|length }})</span>
                                </div>
                                <div style="max-height:450px; overflow-y:auto; padding-right:5px;">
                                    {% if rad_history %}
                                        {% for rr in rad_history %}
                                        <div style="background:#fffafc; border:1px solid #f0e6ea; border-radius:12px; padding:12px; margin-bottom:12px; box-shadow:0 1px 4px rgba(0,0,0,0.02)">
                                            <div class="d-flex justify-content-between align-items-center mb-2">
                                                <span class="badge bg-light text-dark border">د. {{ rr.doc_name }}</span>
                                                <span class="small text-muted" style="font-size:0.75rem;">
                                                    {% if rr.created_at and rr.created_at.__class__.__name__ == 'datetime' %}
                                                        {{ rr.created_at.strftime('%Y-%m-%d | %I:%M %p') }}
                                                    {% else %}{{ rr.created_at }}{% endif %}
                                                </span>
                                            </div>
                                            <div class="fw-bold mb-2" style="color:#e6528d; font-size:0.9rem;">{{ rr.scan_type }}</div>
                                            <div class="small p-2 rounded mb-2" style="background:#fff; border:1px dashed #f0e6ea; color:#333; white-space:pre-wrap;">{{ rr.report }}</div>
                                            {% if rr.image_path %}
                                            <a href="{{ url_for('static', filename='uploads/' ~ rr.image_path) }}" target="_blank" class="btn btn-sm" style="background:#ffeef4; color:#e6528d; border-radius:8px; font-weight:600;"><i class="fas fa-image me-1"></i> عرض الصورة</a>
                                            {% endif %}
                                        </div>
                                        {% endfor %}
                                    {% else %}
                                        <div class="text-center text-muted small py-4">
                                            <i class="fas fa-x-ray fa-2x mb-2" style="color:#f0e6ea;"></i><br>
                                            لا توجد تقارير أشعة سابقة
                                        </div>
                                    {% endif %}
                                </div>
                            </div>
                        </div>
                    </div>
                </div>

            </div><!-- col-lg-9 -->
        </div><!-- row -->
    </div><!-- container -->

    <!-- History Modal -->
    <div class="modal fade" id="historyModal">
        <div class="modal-dialog modal-xl modal-dialog-centered">
            <div class="modal-content border-0" style="border-radius:22px;overflow:hidden;">
                <div class="modal-header p-4"
                     style="background:linear-gradient(135deg,#0f2027,#2c5364);">
                    <h5 class="modal-title fw-bold text-white">
                        <i class="fas fa-history me-2"></i>السجل الطبي والزيارات السابقة
                    </h5>
                    <button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal"></button>
                </div>
                <div class="modal-body p-4" style="background:#f8f9ff;max-height:75vh;overflow-y:auto;">
                    {% for h in history %}
                    <div class="hist-item">
                        <div class="d-flex justify-content-between align-items-center mb-2">
                            <span class="badge rounded-pill px-3 py-1"
                                  style="background:#eef0ff;color:#667eea;font-size:0.78rem;">
                                {% if h.created_at and h.created_at.__class__.__name__ == 'datetime' %}
                                    {{ h.created_at.strftime('%Y-%m-%d') }}
                                {% else %}{{ h.created_at if h.created_at else '' }}{% endif %}
                            </span>
                            <span class="badge bg-light text-dark border">د. {{ h.doc_name }}</span>
                        </div>
                        <div class="fw-bold mb-1" style="color:#e74c3c;font-size:0.9rem;">
                            <i class="fas fa-stethoscope me-1"></i>{{ h.assessment }}
                        </div>
                        {% if h.subjective %}
                        <div class="small text-muted border-top pt-2 mt-2">{{ h.subjective }}</div>
                        {% endif %}
                        {% if h.plan %}
                        <div class="small mt-2 p-2 rounded-3" style="background:#f0fff4;color:#27ae60;">
                            <i class="fas fa-pills me-1"></i>{{ h.plan }}
                        </div>
                        {% endif %}
                    </div>
                    {% else %}
                    <div class="text-center py-5">
                        <i class="fas fa-file-medical fa-4x mb-3" style="color:#ccc;"></i>
                        <h6 class="text-muted">لا يوجد سجل تاريخي سابق لهذا المريض</h6>
                    </div>
                    {% endfor %}
                </div>
            </div>
        </div>
    </div>

    <script>
    /* ════════════════════════════════════
       HealthPro Consultation v4 - Event Delegation JS
       ════════════════════════════════════ */

    if (!window.hpConsultationBound) {
        window.hpConsultationBound = true;
        window.hpTagStore = { selectedLabs: [], selectedRads: [] };

        window.hpAddTag = function(val, areaId, hiddenId, countId, badgeId, btnId, paramName) {
            val = val.trim();
            if (!val) return;
            if (window.hpTagStore[areaId].indexOf(val) !== -1) return;
            window.hpTagStore[areaId].push(val);

            var area = document.getElementById(areaId);
            if (!area) return;
            var hint = area.querySelector('.empty-hint');
            if (hint) hint.remove();

            var tag = document.createElement('div');
            tag.className = 'hp-tag';
            tag.setAttribute('data-v', val);
            tag.innerHTML = '<span>' + val + '</span>'
                + '<input type="hidden" name="' + paramName + '" value="' + val + '">'
                + '<i class="fas fa-times-circle x" onclick="hpRemoveTag(\\'' + val.replace(/'/g,"\\\\'") + '\\',\\'' + areaId + '\\',\\'' + countId + '\\',\\'' + badgeId + '\\',\\'' + btnId + '\\')"></i>';
            area.appendChild(tag);

            var hiddenCont = document.getElementById(hiddenId);
            if (hiddenCont) {
                var h = document.createElement('input');
                h.type = 'hidden'; h.name = paramName; h.value = val; h.setAttribute('data-v', val);
                hiddenCont.appendChild(h);
            }
            window.hpUpdateCount(areaId, countId, badgeId, btnId);
        };

        window.hpRemoveTag = function(val, areaId, countId, badgeId, btnId) {
            window.hpTagStore[areaId] = window.hpTagStore[areaId].filter(function(v){ return v !== val; });
            var area = document.getElementById(areaId);
            if (!area) return;
            area.querySelectorAll('.hp-tag').forEach(function(t){
                if (t.getAttribute('data-v') === val) t.remove();
            });
            if (window.hpTagStore[areaId].length === 0) {
                area.innerHTML = '<div class="empty-hint"><i class="fas fa-mouse-pointer me-1"></i>انقر على فحص أو ابحث ثم Enter لإضافته</div>';
            }
            window.hpUpdateCount(areaId, countId, badgeId, btnId);
        };

        window.hpUpdateCount = function(areaId, countId, badgeId, btnId) {
            var n = window.hpTagStore[areaId].length;
            var c = document.getElementById(countId);  if (c) c.textContent = n;
            var b = document.getElementById(badgeId);  if (b) b.textContent = n;
            var btn = document.getElementById(btnId);  if (btn) btn.disabled = (n === 0);
        };

        window.hpAppendMed = function(val) {
            var rxArea = document.getElementById('rxArea');
            var medInp = document.getElementById('medInput');
            val = val.trim();
            if (!val || !rxArea) return;
            var cur = rxArea.value.trim();
            rxArea.value = cur ? cur + '\\n' + val + ' - ' : val + ' - ';
            if(medInp) medInp.value = '';
            rxArea.focus();
        };

        window.hpUseTpl = function(text) {
            var rxArea = document.getElementById('rxArea');
            if (rxArea) rxArea.value = text;
        };

        // Event delegation for clicks (Tabs, Add Buttons, Grid Items)
        document.addEventListener('click', function(e) {
            // Tab switching
            var tabBtn = e.target.closest('.hp-tab');
            if (tabBtn) {
                document.querySelectorAll('.hp-tab').forEach(function(b){ b.classList.remove('active'); });
                document.querySelectorAll('.hp-tab-pane').forEach(function(p){ p.style.display = 'none'; });
                tabBtn.classList.add('active');
                var target = document.getElementById(tabBtn.getAttribute('data-hp-target'));
                if (target) target.style.display = 'block';
                return;
            }

            // Grid Items
            var gItem = e.target.closest('.g-item');
            if (gItem) {
                var gridId = gItem.parentElement.id;
                if (gridId === 'labGrid') {
                    window.hpAddTag(gItem.getAttribute('data-val'), 'selectedLabs', 'labHidden', 'labCount', 'labBadge', 'labSubmitBtn', 'selected_tests[]');
                } else if (gridId === 'radGrid') {
                    window.hpAddTag(gItem.getAttribute('data-val'), 'selectedRads', 'radHidden', 'radCount', 'radBadge', 'radSubmitBtn', 'selected_scans[]');
                }
                return;
            }

            // Add Actions
            if (e.target.closest('#labAddBtn')) {
                var labInp = document.getElementById('labSearch');
                if (labInp && labInp.value.trim()) {
                    window.hpAddTag(labInp.value.trim(), 'selectedLabs', 'labHidden', 'labCount', 'labBadge', 'labSubmitBtn', 'selected_tests[]');
                    labInp.value = '';
                    document.querySelectorAll('#labGrid .g-item').forEach(function(i){ i.style.display = '';});
                }
            } else if (e.target.closest('#radAddBtn')) {
                var radInp = document.getElementById('radSearch');
                if (radInp && radInp.value.trim()) {
                    window.hpAddTag(radInp.value.trim(), 'selectedRads', 'radHidden', 'radCount', 'radBadge', 'radSubmitBtn', 'selected_scans[]');
                    radInp.value = '';
                    document.querySelectorAll('#radGrid .g-item').forEach(function(i){ i.style.display = '';});
                }
            }
        });

        // Search filtering logic
        document.addEventListener('input', function(e) {
            if (e.target.id === 'labSearch') {
                var q1 = e.target.value.toLowerCase().trim();
                document.querySelectorAll('#labGrid .g-item').forEach(function(item) {
                    var txt = (item.getAttribute('data-val') || '').toLowerCase();
                    item.style.display = txt.includes(q1) ? '' : 'none';
                });
            } else if (e.target.id === 'radSearch') {
                var q2 = e.target.value.toLowerCase().trim();
                document.querySelectorAll('#radGrid .g-item').forEach(function(item) {
                    var txt = (item.getAttribute('data-val') || '').toLowerCase();
                    item.style.display = txt.includes(q2) ? '' : 'none';
                });
            }
        });

        // Enter key to add tags and meds
        document.addEventListener('keydown', function(e) {
            if (e.key === 'Enter') {
                if (e.target.id === 'labSearch') {
                    e.preventDefault();
                    var v1 = e.target.value.trim();
                    if (v1) {
                        window.hpAddTag(v1, 'selectedLabs', 'labHidden', 'labCount', 'labBadge', 'labSubmitBtn', 'selected_tests[]');
                        e.target.value = '';
                        document.querySelectorAll('#labGrid .g-item').forEach(function(i){ i.style.display = ''; });
                    }
                } else if (e.target.id === 'radSearch') {
                    e.preventDefault();
                    var v2 = e.target.value.trim();
                    if (v2) {
                        window.hpAddTag(v2, 'selectedRads', 'radHidden', 'radCount', 'radBadge', 'radSubmitBtn', 'selected_scans[]');
                        e.target.value = '';
                        document.querySelectorAll('#radGrid .g-item').forEach(function(i){ i.style.display = ''; });
                    }
                } else if (e.target.id === 'medInput') {
                    e.preventDefault();
                    window.hpAppendMed(e.target.value);
                }
            }
        });

        document.addEventListener('change', function(e) {
            if (e.target.id === 'medInput') {
                window.hpAppendMed(e.target.value);
            }
        });
    } else {
        // Reset state on PJAX reload
        window.hpTagStore = { selectedLabs: [], selectedRads: [] };
    }
    </script>
    """ + footer_html

    today_date        = datetime.datetime.now().strftime('%Y-%m-%d')
    followup_date_val = (datetime.datetime.now() + datetime.timedelta(days=7)).strftime('%Y-%m-%d')

    try:
        return render_template_string(
            html, data=data, curr_labs=curr_labs, curr_rads=curr_rads,
            lab_list=lab_list, rad_list=rad_list, depts=depts, history=history,
            lab_history=lab_history, rad_history=rad_history,
            today_date=today_date, followup_date_val=followup_date_val,
            lab_json=json.dumps(lab_list), rad_json=json.dumps(rad_list),
            diag_json=json.dumps(diag_list), med_json=json.dumps(med_list)
        )
    except Exception as e:
        return f"<pre>Error: {e}</pre>"
