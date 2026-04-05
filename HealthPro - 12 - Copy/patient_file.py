import os
import time
from werkzeug.utils import secure_filename
from flask import Blueprint, session, redirect, url_for, request, flash, render_template_string
from config import get_db, can_access
from header import header_html
from footer import footer_html

patient_file_bp = Blueprint('patient_file', __name__)

@patient_file_bp.route('/patient_file', methods=['GET', 'POST'])
def patient_file():
    if not session.get('user_id'):
        return redirect(url_for('login.login'))
        
    patient_id = request.args.get('id')
    if not patient_id:
        return redirect(url_for('patients.patients'))
        
    conn = get_db()
    if not conn:
        return "Database Connection Error"
        
    cursor = conn.cursor(dictionary=True)
    
    # --- Handle Archive Upload ---
    if request.method == 'POST' and 'upload_archive' in request.form:
        file_desc = request.form.get('file_name', '')
        
        target_file_path = None
        if 'archive_file' in request.files:
            file = request.files['archive_file']
            if file and file.filename != '':
                upload_dir = 'uploads/archive/'
                if not os.path.exists(upload_dir):
                    os.makedirs(upload_dir, exist_ok=True)
                    
                file_ext = file.filename.rsplit('.', 1)[1].lower()
                new_name = secure_filename(f"arch_{int(time.time())}.{file_ext}") # simple unique name
                target_file_path = os.path.join(upload_dir, new_name)
                file.save(target_file_path)
                target_file_path = target_file_path.replace("\\", "/")
                
        doc_id = session.get('user_id', 1)
        
        if target_file_path:
            cursor.execute("""
                INSERT INTO radiology_requests (patient_id, doctor_id, scan_type, image_path, status, created_at) 
                VALUES (%s, %s, %s, %s, 'completed', CURRENT_TIMESTAMP)
            """, (patient_id, doc_id, file_desc, target_file_path))
            conn.commit()
            
            flash("تم أرشفة الملف بنجاح", "success")
        else:
            flash("حدث خطأ أثناء رفع الملف", "danger")
            
        return redirect(url_for('patient_file.patient_file', id=patient_id))

        
    cursor.execute("SELECT * FROM patients WHERE patient_id = %s", (patient_id,))
    p = cursor.fetchone()
    
    if not p:
        return redirect(url_for('patients.patients'))

        
    cursor.execute("""
        SELECT c.*, u.full_name_ar as doc_name 
        FROM consultations c 
        JOIN users u ON c.doctor_id = u.user_id 
        WHERE c.patient_id = %s 
        ORDER BY c.created_at DESC
    """, (patient_id,))
    history = cursor.fetchall()
    
    cursor.execute("""
        SELECT * FROM prescriptions 
        WHERE patient_id = %s 
        ORDER BY created_at DESC LIMIT 10
    """, (patient_id,))
    prescs = cursor.fetchall()
    
    cursor.execute("""
        SELECT * FROM lab_requests 
        WHERE patient_id = %s 
        ORDER BY created_at DESC LIMIT 10
    """, (patient_id,))
    labs = cursor.fetchall()
    
    cursor.execute("""
        SELECT t.*, a.appointment_date 
        FROM triage t
        JOIN appointments a ON t.appointment_id = a.appointment_id
        WHERE a.patient_id = %s
        ORDER BY a.appointment_date ASC
    """, (patient_id,))
    vitals_history = cursor.fetchall()
    
    def file_exists(path):
        if not path: return False
        try:
             return os.path.exists(path)
        except:
             return False

    html = header_html + """
    <!-- Include Barcode & Chart Library -->
    <script src="https://cdn.jsdelivr.net/npm/jsbarcode@3.11.5/dist/JsBarcode.all.min.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>

    <style>
        :root {
            --pf-bg: #f5f6f8;
            --pf-card: #ffffff;
            --pf-text: #2c3e50;
            --pf-border: #e1e4e8;
            --pf-input-bg: #ffffff;
        }

        [data-theme='dark'] {
            --pf-bg: #1a0b1d;
            --pf-card: #1a0b1d;
            --pf-text: #f0f0f0;
            --pf-border: rgba(255,255,255,0.08);
            --pf-input-bg: rgba(255,255,255,0.05);
        }

        .pf-body { background: transparent; color: var(--pf-text); min-height: 100vh; font-family: 'Outfit', sans-serif; transition: background 0.3s; }

        
        .glass-card {
            background: var(--pf-card) !important;
            border: 1px solid var(--pf-border) !important;
            border-radius: 20px;
            box-shadow: 0 10px 40px rgba(0,0,0,0.05);
            margin-bottom: 2rem;
            overflow: hidden;
            backdrop-filter: blur(15px);
        }

        [data-theme='dark'] .glass-card {
            background: rgba(40, 20, 50, 0.6) !important;
            box-shadow: 0 20px 50px rgba(0,0,0,0.3);
            border-color: rgba(191, 90, 242, 0.2) !important;
        }

        .hover-scale { transition: all 0.4s cubic-bezier(0.16, 1, 0.3, 1); }
        .hover-scale:hover { transform: translateY(-8px); box-shadow: 0 15px 40px rgba(0,0,0,0.15); }

        .barcode-v { 
            background: #ffffff; 
            padding: 8px 12px; 
            border-radius: 12px; 
            display: inline-block; 
            border: 1px solid var(--pf-border);
            box-shadow: 0 4px 12px rgba(0,0,0,0.08);
            transform: scale(0.9);
            transform-origin: left center;
        }
        
        [data-theme='dark'] .barcode-v {
            background: rgba(255, 255, 255, 0.9);
            border-color: transparent;
        }


        
        .section-header-line { border-right: 4px solid var(--bs-primary); padding-right: 15px; margin-bottom: 1.5rem; }
        
        /* Form & Table Adaptation */
        .form-control { 
            background-color: var(--pf-input-bg) !important; 
            color: var(--pf-text) !important; 
            border: 1px solid var(--pf-border) !important;
            border-radius: 12px !important;
            padding: 12px !important;
        }
        .form-control::placeholder { color: var(--pf-text); opacity: 0.5; }
        
        /* File Input Button Styling */
        .form-control::file-selector-button {
            background: rgba(191, 90, 242, 0.1);
            color: var(--pf-text);
            border: none;
            border-left: 1px solid var(--pf-border);
            margin-left: 15px;
            padding: 8px 15px;
            border-radius: 8px;
            cursor: pointer;
            transition: all 0.3s;
            font-weight: 600;
        }
        [data-theme='dark'] .form-control::file-selector-button {
            background: rgba(255, 255, 255, 0.05);
        }
        .form-control::file-selector-button:hover {
            background: rgba(191, 90, 242, 0.2);
        }
        
        .table { color: var(--pf-text) !important; background: transparent !important; }
        [data-theme='dark'] .table tbody tr, [data-theme='dark'] .table td { background-color: transparent !important; }
        
        .table thead th { background: rgba(0,0,0,0.02); border-bottom: 2px solid var(--pf-border); color: var(--pf-text); opacity: 0.7; }
        [data-theme='dark'] .table thead th { background: rgba(255,255,255,0.02); }
        .table td { border-bottom: 1px solid var(--pf-border); vertical-align: middle; }
        
        [data-theme='dark'] .table-hover tbody tr:hover { background-color: rgba(255,255,255,0.02) !important; }

        .btn-primary { 
            background: linear-gradient(135deg, #bf5af2 0%, #5e5ce6 100%) !important; 
            border: none !important;
            box-shadow: 0 4px 15px rgba(191, 90, 242, 0.3);
            transition: all 0.3s;
        }
        .btn-primary:hover { transform: scale(1.02); box-shadow: 0 6px 20px rgba(191, 90, 242, 0.4); }
        
        .btn-round { border-radius: 12px; padding: 10px 20px; font-weight: 600; transition: all 0.3s; }
        .action-icon { font-size: 2rem; margin-bottom: 0.5rem; display: block; }

        @keyframes fadeInUp {
            from { opacity: 0; transform: translateY(20px); }
            to { opacity: 1; transform: translateY(0); }
        }
        .animate-fade { animation: fadeInUp 0.4s ease-out forwards; }
        
        .archive-form-box {
            background: rgba(191, 90, 242, 0.05);
            border: 1px dashed var(--pf-border);
            border-radius: 20px;
            padding: 1.5rem;
            margin-bottom: 2rem;
        }
        .text-themed { color: var(--pf-text); opacity: 0.85; }
    </style>


    <div class="pf-body pt-4">
        <div class="container-fluid px-lg-5">
            <!-- Compact Patient Header -->
            <div class="d-flex justify-content-center mb-4">
                <div class="glass-card p-2 animate-fade shadow-sm" style="max-width: 900px; width: 100%;">
                    <div class="row align-items-center g-2">
                        <div class="col-md-12">
                                <div class="d-flex align-items-center gap-3">
                                    <div class="avatar-box rounded-circle overflow-hidden shadow-sm" style="width: 60px; height: 60px; background: var(--pf-input-bg); border: 2px solid var(--pf-border);">
                                        {% if p.photo and file_exists(p.photo) %}
                                            <img src="/{{ p.photo }}" class="w-100 h-100" style="object-fit: cover;">
                                        {% else %}
                                            <div class="w-100 h-100 d-flex align-items-center justify-content-center text-muted" style="font-size: 1.8rem; background: var(--pf-input-bg);">
                                                <i class="fas fa-user-circle"></i>
                                            </div>
                                        {% endif %}
                                    </div>
                                    <div class="flex-grow-1">
                                        <div class="d-flex justify-content-between align-items-center">
                                            <h4 class="fw-bold mb-0" style="font-size: 1.15rem;">{{ p.full_name_ar }}</h4>
                                            <div class="d-flex gap-2">
                                                {% if p.allergies %}
                                                    <span class="badge bg-danger animate__animated animate__pulse animate__infinite" title="Allergies"><i class="fas fa-exclamation-triangle me-1"></i> حساسبة: {{ p.allergies }}</span>
                                                {% endif %}
                                            </div>
                                        </div>
                                        <div class="d-flex flex-wrap gap-2 align-items-center mt-1">
                                            <span class="badge bg-primary px-2 py-1 rounded-pill" style="font-size: 0.75rem;">{{ p.file_number }}</span>
                                            <span class="text-themed fw-bold" style="font-size: 0.8rem;"><i class="fas fa-venus-mars me-1"></i> {{ 'ذكر' if p.gender == 'male' else 'أنثى' }}</span>
                                            <span class="text-themed small" style="font-size: 0.75rem;"><i class="fas fa-calendar-alt me-1"></i> 
                                                {% if p.date_of_birth and p.date_of_birth.__class__.__name__ == 'datetime' %}
                                                    {{ p.date_of_birth.strftime('%Y-%m-%d') }}
                                                {% elif p.date_of_birth %}
                                                    {{ p.date_of_birth|string|replace('00:00:00', '')|trim }}
                                                {% endif %}
                                            </span>
                                            <span class="text-themed small" style="font-size: 0.75rem;"><i class="fas fa-phone-alt me-1"></i> {{ p.phone1 }}</span>
                                        </div>
                                        {% if p.medical_history %}
                                            <div class="small mt-2 p-2 rounded bg-light border-start border-4 border-info" style="background: var(--pf-input-bg) !important;">
                                                <i class="fas fa-notes-medical me-1 text-info"></i> {{ p.medical_history }}
                                            </div>
                                        {% endif %}
                                    </div>
                                </div>

                        </div>
                    </div>
                </div>
            </div>



            {% with messages = get_flashed_messages(with_categories=true) %}
                {% if messages %}
                    {% for category, message in messages %}
                        <div class="alert alert-{{ 'success' if category == 'success' else 'danger' }} rounded-4 border-0 shadow-sm animate-fade">
                            <i class="fas fa-info-circle me-2"></i> {{ message }}
                        </div>
                    {% endfor %}
                {% endif %}
            {% endwith %}

            <!-- Main Action Tiles (Original Layout) -->
            <div class="row g-4 mb-5 animate-fade" style="animation-delay: 0.1s;">
                <div class="col-md-3">
                    <a href="{{ url_for('edit_patient.edit_patient') }}?id={{ p.patient_id }}" class="text-decoration-none text-reset">
                        <div class="glass-card hover-scale text-center py-4 mb-0">
                            <i class="fas fa-user-edit action-icon text-primary"></i>
                            <h6 class="fw-bold m-0">تعديل المعلومات</h6>
                        </div>
                    </a>
                </div>
                <div class="col-md-3">
                    <div onclick="showSection('reports-section')" class="glass-card hover-scale text-center py-4 mb-0" style="cursor: pointer;">
                        <i class="fas fa-file-medical-alt action-icon text-success"></i>
                        <h6 class="fw-bold m-0">التقارير الطبية</h6>
                    </div>
                </div>
                <div class="col-md-3">
                    <div onclick="showSection('archive-section')" class="glass-card hover-scale text-center py-4 mb-0" style="cursor: pointer;">
                        <i class="fas fa-archive action-icon text-warning"></i>
                        <h6 class="fw-bold m-0">الأرشيف الرقمي</h6>
                    </div>
                </div>
                <div class="col-md-3">
                    <div onclick="showSection('vitals-section')" class="glass-card hover-scale text-center py-4 mb-0" style="cursor: pointer;">
                        <i class="fas fa-chart-line action-icon text-info"></i>
                        <h6 class="fw-bold m-0">مراقبة العلامات الحيوية</h6>
                    </div>
                </div>
                <div class="col-md-3">
                    <a href="{{ url_for('book.book') }}?id={{ p.patient_id }}" class="text-decoration-none">
                        <div class="glass-card bg-danger text-white hover-scale text-center py-4 mb-0" style="border: none;">
                            <i class="fas fa-calendar-check action-icon opacity-75"></i>
                            <h6 class="fw-bold m-0">حجز موعد</h6>
                        </div>
                    </a>
                </div>
            </div>

            <!-- Content Area -->
            <div class="animate-fade" style="animation-delay: 0.2s;">
                <!-- History Section (Visible by default) -->
                <div class="section-content" id="history-section" style="display: block;">
                    <div class="glass-card p-4">
                        <div class="section-header-line">
                            <h3 class="fw-bold m-0"><i class="fas fa-notes-medical me-2"></i> السجل الطبي والتاريخ المرضي</h3>
                        </div>
                        <div class="row g-4 mt-1">
                            {% for h in history %}
                                <div class="col-12 border-bottom pb-4 mb-4" style="border-color: var(--pf-border) !important;">
                                    <div class="d-flex justify-content-between align-items-center mb-3">
                                        <span class="badge bg-light text-dark border px-3" style="background: var(--pf-input-bg) !important; color: var(--pf-text) !important;">
                                            <i class="far fa-clock me-1"></i>
                                            {% if h.created_at and h.created_at.__class__.__name__ == 'datetime' %}
                                                {{ h.created_at.strftime('%Y-%m-%d %H:%M') }}
                                            {% else %}
                                                {{ h.created_at if h.created_at else '' }}
                                            {% endif %}
                                        </span>
                                        <span class="fw-bold text-primary">د. {{ h.doc_name }}</span>
                                    </div>
                                    <h5 class="fw-bold text-danger mb-3">التشخيص: {{ h.assessment }}</h5>
                                    <p class="opacity-75 mb-3">{{ h.subjective }}</p>
                                    <div class="bg-light p-4 rounded-4 small border" style="background: var(--pf-input-bg) !important; border-color: var(--pf-border) !important;">
                                        <strong class="d-block text-dark mb-2" style="color: var(--pf-text) !important;">الخطة والعلاج:</strong>
                                        {{ h.plan }}
                                    </div>
                                </div>
                            {% else %}
                                <div class="text-center py-5 opacity-50">
                                    <i class="fas fa-folder-open fa-3x mb-3"></i>
                                    <h5>لا توجد سجلات طبية مسجلة بعد</h5>
                                </div>
                            {% endfor %}
                        </div>
                    </div>
                </div>

                <!-- Reports Section -->
                <div class="section-content" id="reports-section" style="display: none;">
                    <div class="row g-4">
                        <div class="col-md-6 text-start">
                            <div class="glass-card p-0">
                                <div class="bg-success text-white p-3 fw-bold"><i class="fas fa-pills me-2"></i> سجل الأدوية والوصفات</div>
                                <div class="p-3">
                                    <table class="table table-hover align-middle">
                                        <thead><tr><th>التاريخ</th><th>الدواء</th><th>الحالة</th></tr></thead>
                                        <tbody>
                                            {% for pr in prescs %}
                                                <tr>
                                                    <td><small class="text-muted">{{ pr.created_at.strftime('%Y-%m-%d') if pr.created_at.__class__.__name__ == 'datetime' else pr.created_at }}</small></td>
                                                    <td class="small">{{ pr.medicine_name|replace('\\n', '<br>')|safe }}</td>
                                                    <td><span class="badge rounded-pill {{ 'bg-success' if pr.status == 'dispensed' else 'bg-warning text-dark' }}">{{ 'مكتمل' if pr.status == 'dispensed' else 'انتظار' }}</span></td>
                                                </tr>
                                            {% endfor %}
                                        </tbody>
                                    </table>
                                </div>
                            </div>
                        </div>
                        <div class="col-md-6 text-start">
                            <div class="glass-card p-0">
                                <div class="bg-info text-white p-3 fw-bold"><i class="fas fa-microscope me-2"></i> سجل التحاليل والمختبر</div>
                                <div class="p-3">
                                    <table class="table table-hover align-middle">
                                        <thead><tr><th>التاريخ</th><th>التحليل</th><th>النتيجة</th></tr></thead>
                                        <tbody>
                                            {% for l in labs %}
                                                <tr>
                                                    <td><small class="text-muted">{{ l.created_at.strftime('%Y-%m-%d') if l.created_at.__class__.__name__ == 'datetime' else l.created_at }}</small></td>
                                                    <td class="small fw-bold">{{ l.test_type }}</td>
                                                    <td class="small">{{ l.result if l.result else '--' }}</td>
                                                </tr>
                                            {% endfor %}
                                        </tbody>
                                    </table>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>

                <!-- Archive Section -->
                <div class="section-content" id="archive-section" style="display: none;">
                    <div class="glass-card p-0">
                        <div class="bg-secondary text-white p-3 fw-bold"><i class="fas fa-file-archive me-2"></i> أرشيف الملفات والأشعة</div>
                        <div class="p-4">
                            <form method="POST" enctype="multipart/form-data" class="archive-form-box">
                                <h6 class="fw-bold mb-3"><i class="fas fa-cloud-upload-alt me-2 text-primary"></i> رفع ملف جديد</h6>
                                <div class="row g-3">
                                    <div class="col-md-5"><input type="text" name="file_name" class="form-control" placeholder="وصف الملف (مثال: أشعة صدر)..." required></div>
                                    <div class="col-md-5"><input type="file" name="archive_file" class="form-control" required></div>
                                    <div class="col-md-2"><button type="submit" name="upload_archive" class="btn btn-primary w-100 btn-round shadow-sm"><i class="fas fa-save me-1"></i> حفظ</button></div>
                                </div>
                            </form>
                            <table class="table table-hover align-middle">
                                <thead><tr><th class="text-center">التاريخ</th><th class="text-center">الوصف</th><th class="text-center">عرض</th></tr></thead>
                                <tbody>
                                    {% for r in rads %}
                                        <tr>
                                            <td class="text-center"><small class="text-muted">{{ r.created_at.strftime('%Y-%m-%d') if r.created_at.__class__.__name__ == 'datetime' else r.created_at }}</small></td>
                                            <td class="fw-bold text-center">{{ r.scan_type }}</td>
                                            <td class="text-center"><a href="/{{ r.image_path }}" target="_blank" class="btn btn-sm btn-outline-primary btn-round px-3"><i class="fas fa-external-link-alt me-1"></i> فتح الملف</a></td>
                                        </tr>
                                    {% endfor %}
                                </tbody>
                            </table>
                        </div>
                    </div>
                </div>
                <!-- Vitals Tracking Section -->
                <div class="section-content" id="vitals-section" style="display: none;">
                    <div class="row g-4">
                        <div class="col-md-12">
                            <div class="glass-card p-4">
                                <div class="section-header-line">
                                    <h3 class="fw-bold m-0"><i class="fas fa-chart-area me-2"></i> مراقبة المؤشرات الحيوية</h3>
                                </div>
                                <div class="row">
                                    <div class="col-lg-8">
                                         <div style="height: 350px;">
                                            <canvas id="vitalsChart"></canvas>
                                         </div>
                                    </div>
                                    <div class="col-lg-4">
                                        <div class="table-responsive">
                                            <table class="table table-sm small">
                                                <thead><tr><th>التاريخ</th><th>الوزن</th><th>الضغط</th></tr></thead>
                                                <tbody>
                                                    {% for v in vitals_history | reverse %}
                                                    <tr>
                                                        <td>{{ v.appointment_date }}</td>
                                                        <td class="fw-bold text-primary">{{ v.weight or '--' }} kg</td>
                                                        <td>{{ v.blood_pressure or '--' }}</td>
                                                    </tr>
                                                    {% endfor %}
                                                </tbody>
                                            </table>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <script>
        const chartData = {
            labels: [{% for v in vitals_history %}"{{ v.appointment_date }}",{% endfor %}],
            weight: [{% for v in vitals_history %}{{ v.weight or 'null' }},{% endfor %}],
            oxygen: [{% for v in vitals_history %}{{ v.oxygen or 'null' }},{% endfor %}],
            pulse: [{% for v in vitals_history %}{{ v.pulse or 'null' }},{% endfor %}]
        };

        function initVitalsChart() {
            const ctx = document.getElementById('vitalsChart').getContext('2d');
            new Chart(ctx, {
                type: 'line',
                data: {
                    labels: chartData.labels,
                    datasets: [
                        {
                            label: 'الوزن (kg)',
                            data: chartData.weight,
                            borderColor: '#bf5af2',
                            backgroundColor: 'rgba(191,90,242,0.1)',
                            borderWidth: 3,
                            tension: 0.4,
                            fill: true,
                            yAxisID: 'y'
                        },
                        {
                            label: 'النبض (bpm)',
                            data: chartData.pulse,
                            borderColor: '#ff3b30',
                            borderWidth: 2,
                            tension: 0.4,
                            fill: false,
                            yAxisID: 'y1'
                        }
                    ]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    interaction: { mode: 'index', intersect: false },
                    plugins: { legend: { position: 'top', labels: { color: '#8e8e93' } } },
                    scales: {
                        y: { 
                            type: 'linear', display: true, position: 'left',
                            grid: { color: 'rgba(255,255,255,0.05)' },
                            title: { display: true, text: 'الوزن' }
                        },
                        y1: {
                            type: 'linear', display: true, position: 'right',
                            grid: { drawOnChartArea: false },
                            title: { display: true, text: 'النبض' }
                        },
                        x: { grid: { display: false } }
                    }
                }
            });
        }

        window.addEventListener('load', initVitalsChart);

        function showSection(id) {
            document.querySelectorAll('.section-content').forEach(s => s.style.display = 'none');
            const target = document.getElementById(id);
            if(target) {
                target.style.display = 'block';
                target.classList.add('animate__animated', 'animate__fadeIn');
            }
        }
    </script>


    """ + footer_html
    
    return render_template_string(html, p=p, history=history, prescs=prescs, labs=labs, rads=rads, file_exists=file_exists)
