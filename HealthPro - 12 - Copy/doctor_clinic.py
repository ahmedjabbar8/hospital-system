from flask import Blueprint, session, redirect, url_for, render_template_string
from config import get_db, can_access
from header import header_html
from footer import footer_html

doctor_clinic_bp = Blueprint('doctor_clinic', __name__)

@doctor_clinic_bp.route('/doctor_clinic')
def doctor_clinic():
    if not session.get('user_id') or not can_access('doctor'):
        return redirect(url_for('login.login'))
        
    doctor_id = session.get('user_id')
    is_admin = (session.get('role') == 'admin')
    
    conn = get_db()
    if not conn:
        return "Database Connection Error"
        
    cursor = conn.cursor(dictionary=True)
    
    # Enhanced Query to detect returning patients and their last visit
    base_sql = """
        SELECT a.*, p.full_name_ar as p_name, p.file_number, p.gender, p.photo,
        t.blood_pressure, t.temperature, t.pulse, t.oxygen,
        (SELECT COUNT(*) FROM appointments a2 WHERE a2.patient_id = a.patient_id AND a2.status = 'completed') as past_visits,
        (SELECT MAX(appointment_date) FROM appointments a3 WHERE a3.patient_id = a.patient_id AND a3.status = 'completed' AND a3.appointment_id < a.appointment_id) as last_visit_date,
        (SELECT COUNT(*) FROM lab_requests       lr WHERE lr.appointment_id = a.appointment_id AND lr.status IN ('pending','pending_payment')) AS pend_lab,
        (SELECT COUNT(*) FROM radiology_requests rr WHERE rr.appointment_id = a.appointment_id AND rr.status IN ('pending','pending_payment')) AS pend_rad,
        (SELECT COUNT(*) FROM prescriptions      pr WHERE pr.appointment_id = a.appointment_id AND pr.status IN ('pending','pending_payment')) AS pend_rx
        FROM appointments a 
        JOIN patients p ON a.patient_id = p.patient_id 
        LEFT JOIN triage t ON a.appointment_id = t.appointment_id
        WHERE a.status IN ('waiting_doctor', 'in_progress') 
        AND DATE(a.appointment_date) = date('now')
    """
    
    if is_admin:
        sql = base_sql + " ORDER BY a.is_urgent DESC, a.created_at ASC"
        cursor.execute(sql)
    else:
        sql = base_sql + " AND a.doctor_id = %s ORDER BY a.is_urgent DESC, a.created_at ASC"
        cursor.execute(sql, (doctor_id,))
        
    waiting = cursor.fetchall()
    
    # Quick Stats for the header
    stats = {
        'total': len(waiting),
        'urgent': len([r for r in waiting if r['is_urgent']]),
        'in_lab': len([r for r in waiting if (r['pend_lab'] or 0) + (r['pend_rad'] or 0) + (r['pend_rx'] or 0) > 0]),
    }


    html = header_html + """
    <style>
        :root {
            --bg-body: #f4f7fa;
            --bg-card: rgba(255, 255, 255, 0.95);
            --text-main: #1a1c1e;
            --text-muted: #6c757d;
            --border: rgba(0, 0, 0, 0.05);
            --accent: #007aff;
            --accent-soft: rgba(0, 122, 255, 0.08);
            --glass-border: rgba(255, 255, 255, 0.5);
        }

        [data-theme='dark'] .clinic-stage {
            --bg-body: #1a0b1d;
            --bg-card: #1a0b1d;
            --text-main: #ffffff;
            --text-muted: #a0aec0;
            --border: rgba(255, 255, 255, 0.04);
            --accent: #d07afb;
            --accent-soft: rgba(208, 122, 251, 0.05);
            --glass-border: transparent;
        }

        .clinic-stage {
            background-color: transparent;
            min-height: 100vh;
            padding: 1rem 0;
            font-family: 'Outfit', 'Inter', sans-serif;
            color: var(--text-main);
        }


        .modern-list {
            max-width: 1300px;
            margin: 0 auto;
            background: var(--bg-card);
            border-radius: 20px;
            border: 1px solid var(--border);
            overflow: hidden;
        }

        [data-theme='dark'] .modern-list {
            box-shadow: none;
            border-color: rgba(255,255,255,0.03);
        }

        .p-item {
            display: grid;
            grid-template-columns: 50px 2.8fr 1.6fr 100px 320px;
            align-items: center;
            padding: 0.8rem 1.5rem;
            border-bottom: 1px solid var(--border);
            transition: all 0.2s ease;
            position: relative;
        }

        .p-item:hover { background: var(--accent-soft); }

        .p-head-row {
            background: rgba(0,0,0,0.02);
            font-weight: 800; color: var(--text-muted);
            font-size: 0.7rem; text-transform: uppercase; letter-spacing: 1px;
            padding: 0.6rem 1.5rem;
        }
        [data-theme='dark'] .p-head-row { background: rgba(255,255,255,0.02); }

        .num-tag {
            width: 28px; height: 28px;
            background: var(--bg-body);
            border-radius: 8px;
            display: flex; align-items: center; justify-content: center;
            font-weight: 800; color: var(--text-muted);
            font-size: 0.7rem; border: 1px solid var(--border);
        }

        .p-profile { display: flex; align-items: center; gap: 10px; }
        .p-img { 
            width: 40px; height: 40px; border-radius: 10px; 
            object-fit: cover; border: 2px solid #fff;
            box-shadow: 0 3px 6px rgba(0,0,0,0.03);
        }
        .p-data h6 { margin: 0; font-weight: 700; color: var(--text-main); font-size: 0.95rem; }
        .p-data p { margin: 0; font-size: 0.7rem; color: var(--text-muted); font-weight: 500; }

        .v-grid { display: flex; gap: 6px; }
        .v-pill {
            background: var(--bg-body);
            padding: 3px 8px; border-radius: 6px;
            border: 1px solid var(--border);
            font-size: 0.7rem; font-weight: 700;
            display: flex; align-items: center; gap: 5px;
        }

        .status-pill-pro {
            font-size: 0.65rem; font-weight: 800;
            padding: 5px 12px; border-radius: 50px;
            display: flex; align-items: center; gap: 5px;
            width: fit-content; margin: 0 auto;
        }
        .st-waiting { background: #ecfdf5; color: #059669; }
        .st-lab { background: #f0f9ff; color: #0284c7; }
        .st-doing { background: #fffbeb; color: #d97706; }

        .btns-container { display: flex; gap: 8px; justify-content: flex-end; align-items: center; }

        .btn-tool {
            width: 36px; height: 36px; border-radius: 10px;
            background: var(--bg-card); border: 1px solid var(--border);
            color: var(--text-muted); display: flex; align-items: center; 
            justify-content: center; transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
            cursor: pointer; font-size: 0.9rem; text-decoration: none;
        }
        .btn-tool:hover {
            background: var(--accent); color: white;
            transform: translateY(-3px);
            box-shadow: 0 5px 15px var(--accent-soft);
        }
        .btn-tool:active { transform: scale(0.9); }

        .btn-px {
            border: none; border-radius: 12px; padding: 10px 18px;
            font-weight: 800; font-size: 0.8rem; color: white;
            display: flex; align-items: center; gap: 8px;
            transition: all 0.3s; text-decoration: none;
        }
        .btn-call-st { background: #6366f1; }
        .btn-call-can { background: #f43f5e; }
        .btn-enter-st { background: #007aff; }

        .btn-px:hover { transform: translateY(-2px); filter: brightness(1.1); box-shadow: 0 5px 15px rgba(0,0,0,0.1); }
        .btn-px:hover i { animation: fa-bounce 0.8s infinite; }

        /* Custom Animations */
        @keyframes fa-bounce {
            0%, 100% { transform: translateY(0); }
            50% { transform: translateY(-3px); }
        }
        @keyframes fa-shake {
            0%, 100% { transform: rotate(0); }
            25% { transform: rotate(10deg); }
            75% { transform: rotate(-10deg); }
        }
        @keyframes fa-spin-custom {
            from { transform: rotate(0); }
            to { transform: rotate(360deg); }
        }

        .btn-tool:hover .fa-edit { animation: fa-shake 0.5s infinite; }
        .btn-tool:hover .fa-print { animation: fa-spin-custom 2s infinite linear; }
        .btn-tool:hover .fa-folder-open { animation: fa-bounce 0.8s infinite; }

        .urgent-glow {
            position: absolute; right: 0; top: 10px; bottom: 10px; width: 3px;
            background: #f43f5e; border-radius: 0 3px 3px 0;
            box-shadow: 0 0 8px rgba(244, 63, 94, 0.3);
        }
    </style>

    <div class="clinic-stage" id="clinicRoot">
        <div class="container-fluid px-lg-5">
            <div class="modern-list animate__animated animate__fadeIn">
                <div class="p-item p-head-row">
                    <div class="text-center">#</div>
                    <div>بيانات المراجع</div>
                    <div>المؤشرات الحيوية</div>
                    <div class="text-center">الحالة</div>
                    <div class="text-center">الإجراءات</div>
                </div>

                {% if waiting %}
                    {% for r in waiting %}
                        {% set in_lab = (r.pend_lab or 0) + (r.pend_rad or 0) + (r.pend_rx or 0) > 0 %}
                        <div class="p-item">
                            {% if r.is_urgent %}
                                <div class="urgent-glow"></div>
                            {% endif %}
                            
                            <div class="text-center">
                                <div class="num-tag">{{ loop.index }}</div>
                            </div>
                            
                            <div class="p-profile">
                                {% if r.photo %}
                                    <img src="/{{ r.photo }}" class="p-img">
                                {% else %}
                                    <div class="p-img d-flex align-items-center justify-content-center bg-light text-muted">
                                        <i class="fas fa-user-circle fa-lg"></i>
                                    </div>
                                {% endif %}
                                <div class="p-data">
                                    <h6>{{ r.p_name }}</h6>
                                    <p>{{ r.file_number }} | {{ 'ذكر' if r.gender == 'male' else 'أنثى' }}</p>
                                </div>
                            </div>

                            <div class="v-grid">
                                <div class="v-pill" title="الضغط"><i class="fas fa-heartbeat text-danger"></i> {{ r.blood_pressure or '--' }}</div>
                                <div class="v-pill" title="الحرارة"><i class="fas fa-thermometer-half text-warning"></i> {{ r.temperature or '--' }}°</div>
                                <div class="v-pill" title="النبض"><i class="fas fa-tint text-info"></i> {{ r.pulse or '--' }}</div>
                            </div>

                            <div class="text-center">
                                {% if in_lab %}
                                    <span class="status-pill-pro st-lab"><i class="fas fa-flask"></i> المختبر</span>
                                {% elif r.status == 'in_progress' %}
                                    <span class="status-pill-pro st-doing"><i class="fas fa-user-md"></i> معاينة</span>
                                {% else %}
                                    <span class="status-pill-pro st-waiting"><i class="fas fa-clock"></i> انتظار</span>
                                {% endif %}
                            </div>

                            <div class="btns-container">
                                <a href="/patient_file/{{ r.patient_id }}" class="btn-tool" title="سجل المريض">
                                    <i class="fas fa-folder-open"></i>
                                </a>
                                <div onclick="window.print()" class="btn-tool" title="طباعة">
                                    <i class="fas fa-print"></i>
                                </div>
                                <div class="btn-tool" title="ملاحظة سريعة">
                                    <i class="fas fa-edit"></i>
                                </div>
                                
                                <div class="vr mx-1 opacity-25" style="height: 20px;"></div>

                                {% if r.call_status == 1 %}
                                    <button onclick="handleClinicCall({{ r.appointment_id }}, 'cancel', this)" class="btn-px btn-call-can">
                                        <i class="fas fa-microphone-slash"></i> إلغاء
                                    </button>
                                {% else %}
                                    <button onclick="handleClinicCall({{ r.appointment_id }}, 'trigger', this)" class="btn-px btn-call-st">
                                        <i class="fas fa-bullhorn"></i> استدعاء
                                    </button>
                                {% endif %}
                                <a href="{{ url_for('consultation.consultation') }}?id={{ r.appointment_id }}" class="btn-px btn-enter-st">
                                    <i class="fas fa-sign-in-alt"></i> دخول
                                </a>
                            </div>
                        </div>
                    {% endfor %}
                {% else %}
                    <div class="text-center py-5 opacity-50">
                        <i class="fas fa-user-check fa-4x mb-3 text-muted"></i>
                        <h6>العارضة خالية حالياً</h6>
                    </div>
                {% endif %}
            </div>
        </div>
    </div>

    <script>
    function handleClinicCall(apptId, action, btn) {
        btn.disabled = true;
        const oldBody = btn.innerHTML;
        btn.innerHTML = '<i class="fas fa-circle-notch fa-spin"></i>';
        
        var fd = new FormData();
        fd.append('id', apptId);
        fd.append('action', action);
        
        fetch("{{ url_for('api.api_recall') }}", {
            method: 'POST',
            body: fd
        }).then(res => res.json()).then(data => {
            if(data.success) location.reload();
            else { alert('حدث خطأ'); btn.disabled = false; btn.innerHTML = oldBody; }
        }).catch(e => { btn.disabled = false; btn.innerHTML = oldBody; });
    }
    </script>

    </script>
    """ + footer_html
    
    import datetime
    date_str = datetime.date.today().strftime('%Y-%m-%d')
    return render_template_string(html, waiting=waiting, stats=stats, date_str=date_str)
