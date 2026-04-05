from flask import Blueprint, session, redirect, url_for, request, flash, render_template_string
from config import get_db, can_access
from header import header_html
from footer import footer_html
import os

triage_bp = Blueprint('triage', __name__)

@triage_bp.route('/triage', methods=['GET', 'POST'])
def triage():
    conn = get_db()
    if not conn:
        return "Database Connection Error"
        
    cursor = conn.cursor(dictionary=True)

    # SELF-HEALING: Update Schema
    try:
        cursor.execute("ALTER TABLE triage ADD COLUMN IF NOT EXISTS oxygen VARCHAR(20)")
        # cursor.execute("ALTER TABLE triage MODIFY COLUMN height VARCHAR(20)")
        # cursor.execute("ALTER TABLE triage MODIFY COLUMN weight VARCHAR(20)")
        # cursor.execute("ALTER TABLE triage MODIFY COLUMN temperature VARCHAR(20)")

        cursor.execute("ALTER TABLE triage ADD COLUMN IF NOT EXISTS nurse_notes TEXT")
        cursor.execute("ALTER TABLE appointments ADD COLUMN IF NOT EXISTS is_urgent INT DEFAULT 0")
        conn.commit()
    except Exception as e:
        pass # Ignore errors if columns already exist or syntax unsupported

    if not session.get('user_id') or not can_access('triage'):
        return redirect(url_for('login.login'))

        
    # Handle save triage
    if request.method == 'POST' and 'save_triage' in request.form:
        if session.get('user_id'):
            cursor.execute("UPDATE users SET current_task = NULL, active_patient_name = NULL WHERE user_id = %s", (session['user_id'],))
            
        appt_id = request.form.get('appt_id')
        if not appt_id:
            return "Error: Appointment ID is missing"

            
        weight = request.form.get('weight', '')
        height = request.form.get('height', '')
        temp = request.form.get('temp', '')
        bp = request.form.get('bp', '')
        pulse = request.form.get('pulse', '')
        oxygen = request.form.get('oxygen', '')
        notes = request.form.get('notes', '')
        is_urgent = 1 if 'is_urgent' in request.form else 0
        
        insert_sql = """
            INSERT INTO triage (appointment_id, weight, height, temperature, blood_pressure, pulse, oxygen, nurse_notes) 
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """
        cursor.execute(insert_sql, (appt_id, weight, height, temp, bp, pulse, oxygen, notes))
        
        update_sql = "UPDATE appointments SET status = 'waiting_doctor', is_urgent = %s WHERE appointment_id = %s"
        cursor.execute(update_sql, (is_urgent, appt_id))
        
        conn.commit()
        
        flash("تم تسجيل البيانات وتحويل المريض للطبيب بنجاح", "success")
        return redirect(url_for('triage.triage'))

        
    # Handle active status update
    if request.method == 'POST' and 'appointment_id' in request.form and not 'save_triage' in request.form:
        aid = int(request.form.get('appointment_id'))
        cursor.execute("SELECT p.full_name_ar FROM patients p JOIN appointments a ON p.patient_id = a.patient_id WHERE a.appointment_id = %s", (aid,))
        p_info = cursor.fetchone()
        p_name = p_info['full_name_ar'] if p_info else 'مريض'
        
        if session.get('user_id'):
            cursor.execute("UPDATE users SET current_task = 'قياس العلامات الحيوية', active_patient_name = %s WHERE user_id = %s", (p_name, session['user_id']))
            conn.commit()

    # List patients
    sql_q = """
        SELECT a.*, p.full_name_ar as p_name, p.gender, p.file_number, p.photo, p.date_of_birth 
        FROM appointments a 
        JOIN patients p ON a.patient_id = p.patient_id 
        WHERE a.status = 'pending_triage' 
        AND DATE(a.appointment_date) = date('now')
        ORDER BY a.created_at ASC

    """
    cursor.execute(sql_q)
    queue = cursor.fetchall()


    
    import datetime
    current_year = datetime.datetime.now().year

    # Custom jinja function to check file existance
    def file_exists(path):
        if not path: return False
        try:
             # the execution happens from app.py root
             return os.path.exists(path)
        except:
             return False
    html = header_html + """
    <style>
        /* Force disable blurs on this page */
        * {
            backdrop-filter: none !important;
            -webkit-backdrop-filter: none !important;
        }
    </style>
    <div class="container py-4 solid-mode">
        <div class="d-flex justify-content-between align-items-center mb-4">
            <h2 class="fw-bold mb-0"><i class="fas fa-user-nurse text-danger me-2"></i>قسم الفحص الأولي (Triage)</h2>
            <span class="badge bg-danger-subtle text-danger rounded-pill px-3 py-2">{{ queue|length }} في الانتظار</span>
        </div>

        <div class="d-flex flex-column gap-3">
            {% for r in queue %}
                <a href="{{ url_for('triage.start_triage', id=r.appointment_id) }}" class="text-decoration-none">
                <div class="patient-list-item d-flex align-items-center justify-content-between p-3 bg-white rounded-4 shadow-sm border border-transparent"
                    style="cursor: pointer; transition: all 0.2s;">

                    <div class="d-flex align-items-center gap-3">
                        <div class="avatar-sm">
                            {% if r.photo and file_exists(r.photo) %}
                                <img src="/{{ r.photo }}" class="rounded-circle shadow-sm border border-2 border-white" style="width: 55px; height: 55px; object-fit: cover;">
                            {% else %}
                                <div class="rounded-circle bg-danger-subtle text-danger d-flex align-items-center justify-content-center border border-danger-subtle" style="width: 55px; height: 55px;">
                                    <i class="fas fa-user-injured fa-lg"></i>
                                </div>
                            {% endif %}
                        </div>
                        <div>
                            <h6 class="fw-bold mb-0 text-dark">{{ r.p_name }}</h6>
                            <div class="text-muted small d-flex align-items-center gap-2">
                                <span class="badge bg-light text-dark border rounded-pill px-2">ID: {{ r.file_number }}</span>
                            </div>
                        </div>
                    </div>

                    <div class="d-none d-md-flex align-items-center gap-4 text-secondary">
                        <div class="d-flex align-items-center gap-1" title="الجنس">
                            <i class="fas fa-venus-mars text-muted"></i>
                            <span>{{ 'ذكر' if r.gender == 'male' else 'أنثى' }}</span>
                        </div>
                        <div class="d-flex align-items-center gap-1" title="العمر">
                            <i class="fas fa-birthday-cake text-muted"></i>
                            <span>
                                {% if r.date_of_birth and r.date_of_birth.__class__.__name__ == 'datetime' %}
                                    {{ current_year - r.date_of_birth.strftime('%Y')|int }} سنة
                                {% elif r.date_of_birth and r.date_of_birth|string|length >= 4 %}
                                    {{ current_year - (r.date_of_birth|string)[:4]|int }} سنة
                                {% else %}
                                    0 سنة
                                {% endif %}
                            </span>
                        </div>
                    </div>

                    <div>
                        <span class="btn btn-danger-subtle btn-sm rounded-pill fw-bold px-4 py-2 border-0">
                            <i class="fas fa-stethoscope me-1"></i> فحص
                        </span>
                    </div>
                </div>
                </a>
            {% else %}
                <div class="text-center py-5 apple-card bg-white mt-4">
                    <i class="fas fa-check-circle text-success fa-4x mb-3 opacity-25"></i>
                    <h5 class="text-muted">لا يوجد مراجعين في قائمة الانتظار حالياً</h5>
                </div>
            {% endfor %}
        </div>
    </div>


    <style>
        .patient-file-card { cursor: pointer; transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1); border: 2px solid transparent; background: #fff; }
        .patient-file-card:hover { transform: translateY(-5px); box-shadow: 0 15px 30px rgba(0, 0, 0, 0.08); border-color: rgba(220, 53, 69, 0.2); }
        .btn-danger-subtle { background: #fdf2f2; color: #dc3545; border: 1px solid #fee2e2; }
        .btn-danger-subtle:hover { background: #dc3545; color: #fff; }
        .form-check-input:checked { background-color: #dc3545; border-color: #dc3545; }
        .input-group-text { font-size: 1.1rem; }
    </style>

    <script>
        function updateActiveStatus(apptId) {
            const formData = new FormData();
            formData.append('appointment_id', apptId);
            
            fetch("{{ url_for('triage.triage') }}", {
                method: 'POST',
                body: formData
            });
        }
    </script>
    """ + footer_html
    
    return render_template_string(html, queue=queue, current_year=current_year, file_exists=file_exists)

@triage_bp.route('/start_triage/<int:id>', methods=['GET'])
def start_triage(id):
    if not session.get('user_id') or not can_access('triage'):
        return redirect(url_for('login.login'))
        
    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    
    # Get Appointment Info
    cursor.execute("""
        SELECT a.*, p.full_name_ar, p.file_number, p.gender, p.date_of_birth, p.photo
        FROM appointments a 
        JOIN patients p ON a.patient_id = p.patient_id 
        WHERE a.appointment_id = %s
    """, (id,))
    appt = cursor.fetchone()
    
    if not appt:
        return redirect(url_for('triage.triage'))


    # Update User Status
    cursor.execute("UPDATE users SET current_task = 'قياس العلامات الحيوية', active_patient_name = %s WHERE user_id = %s", 
                   (appt['full_name_ar'], session['user_id']))
    conn.commit()


    html = header_html + """
    <style>
        * { backdrop-filter: none !important; -webkit-backdrop-filter: none !important; }
        .triage-card { border-radius: 28px; box-shadow: 0 20px 50px rgba(0,0,0,0.1); border: none; background: #fff; position: relative; overflow: hidden; }
        .vital-card { 
            background: #f8fafc; 
            border-radius: 20px; 
            padding: 12px; 
            border: 1px solid #edf2f7;
            transition: all 0.3s ease;
            position: relative;
        }
        .vital-card:focus-within { background: #fff; box-shadow: 0 8px 20px rgba(0,0,0,0.05); border-color: #3182ce; transform: translateY(-2px); }
        .vital-icon { width: 32px; height: 32px; border-radius: 10px; display: flex; align-items: center; justify-content: center; margin-bottom: 8px; font-size: 0.9rem; }
        
        .bg-temp { background: rgba(245, 101, 101, 0.1); color: #e53e3e; }
        .bg-bp { background: rgba(66, 153, 225, 0.1); color: #3182ce; }
        .bg-oxy { background: rgba(72, 187, 120, 0.1); color: #38a169; }
        .bg-pulse { background: rgba(237, 137, 54, 0.1); color: #dd6b20; }
        
        .form-control { border: none !important; background: transparent !important; padding: 0 !important; font-weight: 700; font-size: 1.1rem; text-align: center; color: #2d3748; }
        .form-control:focus { box-shadow: none !important; }
        .form-label-small { font-size: 0.7rem; font-weight: 600; text-transform: uppercase; color: #718096; display: block; margin-bottom: 2px; }
        
        .patient-header { background: #f0f7ff; border-radius: 20px; padding: 12px 15px; margin-bottom: 20px; border: 1px dashed #bee3f8; }
        
        .emergency-banner {
            display: none;
            background: #fff5f5;
            border: 1px solid #feb2b2;
            color: #c53030;
            padding: 10px;
            border-radius: 15px;
            margin-bottom: 15px;
            animation: pulse-red 2s infinite;
        }
        
        @keyframes pulse-red {
            0% { box-shadow: 0 0 0 0 rgba(245, 101, 101, 0.4); }
            70% { box-shadow: 0 0 0 10px rgba(245, 101, 101, 0); }
            100% { box-shadow: 0 0 0 0 rgba(245, 101, 101, 0); }
        }

        .is-critical { border-color: #f56565 !important; background: #fff5f5 !important; }
        .is-critical .form-label-small { color: #c53030; }
        .is-critical .form-control { color: #c53030; }
    </style>

    <div class="container py-4">
        <div class="row justify-content-center">
            <div class="col-md-7 col-lg-5">
                <div class="card triage-card">
                    <div class="card-header border-0 py-3 text-center" style="background: linear-gradient(135deg, #2d3748, #1a202c);">
                        <h6 class="text-white fw-bold mb-0">
                            <i class="fas fa-microchip me-2" style="color: #63b3ed;"></i> 
                            نظام الفحص الذكي (Smart Triage)
                        </h6>
                    </div>
                    
                    <div class="card-body p-4 text-end">
                        <!-- Emergency Alert -->
                        <div id="emergencyAlert" class="emergency-banner text-center fw-bold">
                            <i class="fas fa-exclamation-triangle me-2"></i> تنبيه: حالة حرجة جداً - تفعيل وضع الطوارئ
                        </div>

                        <!-- Patient Info Mini -->
                        <div class="patient-header d-flex align-items-center gap-3">
                            """ + (f'<img src="/{appt["photo"]}" class="rounded-circle shadow-sm" style="width: 45px; height: 45px; object-fit: cover; border: 2px solid #fff;">' if appt["photo"] else '<div class="rounded-circle bg-white text-primary d-flex align-items-center justify-content-center shadow-sm" style="width: 45px; height: 45px;"><i class="fas fa-user-injured"></i></div>') + """
                            <div class="flex-grow-1">
                                <div class="fw-bold mb-0 text-dark" style="font-size: 0.9rem;">""" + appt['full_name_ar'] + """</div>
                                <div class="text-muted d-flex gap-2" style="font-size: 0.7rem;">
                                    <span>#""" + appt['file_number'] + """</span>
                                    <span>•</span>
                                    <span>""" + ('ذكر' if appt['gender'] == 'male' else 'أنثى') + """</span>
                                </div>
                            </div>
                        </div>

                        <form method="POST" action='""" + url_for('triage.triage') + """' id="triageForm">
                            <input type="hidden" name="save_triage" value="1">
                            <input type="hidden" name="appt_id" value='""" + str(id) + """'>

                            <!-- Vitals Grid -->
                            <div class="row g-2 mb-3">
                                <div class="col-6">
                                    <div class="vital-card" id="card-bp">
                                        <div class="vital-icon bg-bp"><i class="fas fa-heartbeat"></i></div>
                                        <span class="form-label-small">ضغط الدم</span>
                                        <input type="text" name="bp" id="in-bp" class="form-control" placeholder="120/80" oninput="analyzeVitals()">
                                    </div>
                                </div>
                                <div class="col-6">
                                    <div class="vital-card" id="card-temp">
                                        <div class="vital-icon bg-temp"><i class="fas fa-thermometer-half"></i></div>
                                        <span class="form-label-small">الحرارة °C</span>
                                        <input type="text" name="temp" id="in-temp" class="form-control" placeholder="37.0" oninput="analyzeVitals()">
                                    </div>
                                </div>
                                <div class="col-6">
                                    <div class="vital-card" id="card-oxy">
                                        <div class="vital-icon bg-oxy"><i class="fas fa-lungs"></i></div>
                                        <span class="form-label-small">الأوكسجين %</span>
                                        <input type="text" name="oxygen" id="in-oxy" class="form-control" placeholder="98" oninput="analyzeVitals()">
                                    </div>
                                </div>
                                <div class="col-6">
                                    <div class="vital-card" id="card-pulse">
                                        <div class="vital-icon bg-pulse"><i class="fas fa-pills"></i></div>
                                        <span class="form-label-small">النبض (BPM)</span>
                                        <input type="text" name="pulse" id="in-pulse" class="form-control" placeholder="75" oninput="analyzeVitals()">
                                    </div>
                                </div>
                            </div>

                            <div class="row g-2 mb-3">
                                <div class="col-6">
                                    <div class="bg-light p-2 rounded-4 text-center border">
                                        <span class="form-label-small">الوزن (kg)</span>
                                        <input type="text" name="weight" class="form-control" placeholder="0">
                                    </div>
                                </div>
                                <div class="col-6">
                                    <div class="bg-light p-2 rounded-4 text-center border">
                                        <span class="form-label-small">الطول (cm)</span>
                                        <input type="text" name="height" class="form-control" placeholder="0">
                                    </div>
                                </div>
                            </div>

                            <div class="mb-3">
                                <textarea name="notes" class="form-control bg-light p-3 text-end" rows="2" placeholder="ملاحظات الممرض الإضافية..." style="border-radius: 15px; font-size: 0.85rem; border: 1px solid #edf2f7 !important; background: #f8fafc !important;"></textarea>
                            </div>

                            <div class="form-check form-switch p-3 border rounded-4 mb-4 d-flex justify-content-between align-items-center" id="urgentToggleArea" style="transition: all 0.3s;">
                                <label class="form-check-label fw-bold text-dark mb-0 ms-0" for="isUrgentSwitch" style="font-size: 0.85rem;">
                                    <i class="fas fa-star text-warning me-2" id="starIcon"></i> وضع حالة طوارئ
                                </label>
                                <input class="form-check-input" type="checkbox" name="is_urgent" id="isUrgentSwitch">
                            </div>

                            <button type="submit" class="btn btn-primary w-100 rounded-pill py-2 fw-bold shadow-sm" style="background: #2d3748; border: none;">
                                <i class="fas fa-check-circle me-1"></i> إرسال البيانات فوراً
                            </button>
                        </form>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <script>
        function analyzeVitals() {
            const temp = parseFloat(document.getElementById('in-temp').value);
            const oxy = parseFloat(document.getElementById('in-oxy').value);
            const pulse = parseFloat(document.getElementById('in-pulse').value);
            const bpStr = document.getElementById('in-bp').value;
            
            let isCritical = false;
            
            // Analyze Temperature
            if (temp > 39.0 || temp < 35.0) {
                document.getElementById('card-temp').classList.add('is-critical');
                isCritical = true;
            } else {
                document.getElementById('card-temp').classList.remove('is-critical');
            }

            // Analyze Oxygen
            if (oxy > 0 && oxy < 91) {
                document.getElementById('card-oxy').classList.add('is-critical');
                isCritical = true;
            } else {
                document.getElementById('card-oxy').classList.remove('is-critical');
            }

            // Analyze Pulse
            if (pulse > 130 || pulse < 45) {
                document.getElementById('card-pulse').classList.add('is-critical');
                isCritical = true;
            } else {
                document.getElementById('card-pulse').classList.remove('is-critical');
            }

            // Analyze BP
            if (bpStr.includes('/')) {
                const parts = bpStr.split('/');
                const sys = parseInt(parts[0]);
                const dia = parseInt(parts[1]);
                if (sys > 180 || sys < 85 || dia > 110 || dia < 45) {
                    document.getElementById('card-bp').classList.add('is-critical');
                    isCritical = true;
                } else {
                    document.getElementById('card-bp').classList.remove('is-critical');
                }
            }

            // UI Feedback
            const banner = document.getElementById('emergencyAlert');
            const toggle = document.getElementById('isUrgentSwitch');
            const toggleArea = document.getElementById('urgentToggleArea');
            const star = document.getElementById('starIcon');

            if (isCritical) {
                banner.style.display = 'block';
                toggle.checked = true;
                toggleArea.style.background = '#fff5f5';
                toggleArea.style.borderColor = '#feb2b2';
                star.className = 'fas fa-exclamation-circle text-danger me-2';
            } else {
                banner.style.display = 'none';
                // Don't auto-uncheck if the nurse manually checked it? 
                // Let's keep it sync for now for "Smart" feel
                // toggle.checked = false; 
                toggleArea.style.background = 'transparent';
                toggleArea.style.borderColor = '#edf2f7';
                star.className = 'fas fa-star text-warning me-2';
            }
        }
    </script>
    """ + footer_html
    return render_template_string(html)

