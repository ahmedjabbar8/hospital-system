from flask import Blueprint, session, redirect, url_for, render_template_string
from config import get_db, can_access
from header import header_html
from footer import footer_html

dashboard_bp = Blueprint('dashboard', __name__)

@dashboard_bp.route('/dashboard')
def dashboard():
    if not session.get('user_id'):
        return redirect(url_for('login.login'))
        
    role = session.get('role', '')
    
    conn = get_db()
    if not conn:
        return "Database connection error."

    cursor = conn.cursor()
    user_id = session.get('user_id')
    is_admin = (role == 'admin')

    # ── Single aggregated query with Doctor-Specific filtering ────────────
    # Doctors only see their own waiting count, Admins see total
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
    q_scheduled = int(row[0] or 0)
    q_triage    = int(row[1] or 0)
    q_doctor    = int(row[2] or 0)
    q_done      = int(row[3] or 0)

    cursor.execute("""
        SELECT
            SUM(CASE WHEN status='pending' THEN 1 ELSE 0 END) AS labs
        FROM lab_requests
        WHERE DATE(created_at) = date('now')
    """)
    q_labs_items = int((cursor.fetchone() or [0])[0] or 0)

    cursor.execute("""
        SELECT
            SUM(CASE WHEN status='pending' THEN 1 ELSE 0 END) AS rads
        FROM radiology_requests
        WHERE DATE(created_at) = date('now')
    """)
    q_rads_items = int((cursor.fetchone() or [0])[0] or 0)

    cursor.execute("""
        SELECT COUNT(*) FROM prescriptions
        WHERE status IN ('pending','pending_payment')
          AND DATE(created_at) = date('now')
    """)
    q_pharmacy = int((cursor.fetchone() or [0])[0] or 0)

    # Nursing lab: pending sample collections (lab requests not yet collected)
    try:
        cursor.execute("""
            SELECT COUNT(*) FROM lab_requests l
            LEFT JOIN nursing_lab_collections nc ON nc.request_id = l.request_id
            WHERE l.status IN ('pending','pending_payment')
              AND nc.request_id IS NULL
              AND DATE(l.created_at) = date('now')
        """)
        q_nursing = int((cursor.fetchone() or [0])[0] or 0)
    except Exception:
        q_nursing = 0

    is_admin = (role == 'admin')

    
    html = header_html + """
    <div class="row pt-2 mb-4 text-center">
        <div class="col-12">
            <h2 class="fw-bold mb-0">HealthPro Intelligence</h2>
            <p class="text-muted small">نظام المسار الذكي لتتبع المرضى لحظياً</p>
        </div>
    </div>

    <!-- Tiny Neo-Tiles Grid (Permission Based) -->
    <div class="row row-cols-3 row-cols-md-5 row-cols-lg-6 g-3 justify-content-center mb-5">

        <!-- Registration -->
        {% if can_access('registration') %}
            <div class="col">
                <a href="{{ url_for('patients.patients') }}" class="neo-tile tile-blue">
                    <span class="tile-count bg-danger text-white" data-type="q_scheduled" style="display: {{ 'block' if q_scheduled > 0 else 'none' }}">{{ q_scheduled }}</span>
                    <i class="fas fa-user-plus text-primary"></i>
                    <span>التسجيل</span>
                </a>
            </div>
        {% endif %}

        <!-- Triage -->
        {% if can_access('triage') %}
            <div class="col">
                <a href="{{ url_for('triage.triage') }}" class="neo-tile tile-red">
                    <span class="tile-count bg-warning text-dark" data-type="q_triage" style="display: {{ 'block' if q_triage > 0 else 'none' }}">{{ q_triage }}</span>
                    <i class="fas fa-user-nurse text-danger"></i>
                    <span>الفحص الأولي</span>
                </a>
            </div>
        {% endif %}

        <!-- Doctor -->
        {% if can_access('doctor') %}
            <div class="col">
                <a href="{{ url_for('doctor_clinic.doctor_clinic') }}" class="neo-tile tile-indigo">
                    <span class="tile-count bg-info text-white" data-type="q_doctor" style="display: {{ 'block' if q_doctor > 0 else 'none' }}">{{ q_doctor }}</span>
                    <i class="fas fa-stethoscope text-primary"></i>
                    <span>العيادة</span>
                </a>
            </div>
        {% endif %}

        <!-- Lab -->
        {% if can_access('lab') %}
            <div class="col">
                <a href="{{ url_for('lab.lab') }}" class="neo-tile tile-cyan">
                    <span class="tile-count bg-info text-white" data-type="q_labs_items" style="display: {{ 'block' if q_labs_items > 0 else 'none' }}">{{ q_labs_items }}</span>
                    <i class="fas fa-flask text-info"></i>
                    <span>المختبر</span>
                </a>
            </div>
        {% endif %}

        <!-- Radiology -->
        {% if can_access('radiology') %}
            <div class="col">
                <a href="{{ url_for('radiology.radiology') }}" class="neo-tile tile-gray">
                    <span class="tile-count bg-secondary text-white" data-type="q_rads_items" style="display: {{ 'block' if q_rads_items > 0 else 'none' }}">{{ q_rads_items }}</span>
                    <i class="fas fa-x-ray text-secondary"></i>
                    <span>الأشعة</span>
                </a>
            </div>
        {% endif %}

        <!-- Pharmacy -->
        {% if can_access('pharmacy') %}
            <div class="col">
                <a href="{{ url_for('pharmacy.pharmacy') }}" class="neo-tile tile-green">
                    <span class="tile-count bg-success text-white" data-type="q_pharmacy" style="display: {{ 'block' if q_pharmacy > 0 else 'none' }}">{{ q_pharmacy }}</span>
                    <i class="fas fa-pills text-success"></i>
                    <span>الصيدلية</span>
                </a>
            </div>
        {% endif %}

        <!-- Nursing Lab -->
        {% if can_access('nursing') %}
            <div class="col">
                <a href="{{ url_for('nursing_lab.nursing_lab') }}" class="neo-tile tile-teal">
                    <span class="tile-count bg-info text-white" data-type="q_nursing" style="display: {{ 'block' if q_nursing > 0 else 'none' }}">{{ q_nursing }}</span>
                    <i class="fas fa-syringe text-info"></i>
                    <span>سحب العينات</span>
                </a>
            </div>
        {% endif %}

        <!-- Analytics / Reports (Admin Only) -->
        {% if is_admin %}
            <div class="col">
                <a href="{{ url_for('reports.reports') }}" class="neo-tile tile-indigo" style="background: linear-gradient(135deg, #6366f1 0%, #10b981 100%);">
                    <i class="fas fa-chart-pie text-white"></i>
                    <span class="text-white">التقارير</span>
                </a>
            </div>
        {% endif %}


        <div class="col">
            <a href="{{ url_for('waiting_list.waiting_list') }}" class="neo-tile tile-teal">
                <i class="fas fa-desktop text-info"></i>
                <span>المراقب المباشر</span>
            </a>
        </div>

        {% if is_admin %}
            <div class="col">
                <a href="{{ url_for('system_data.system_data') }}" class="neo-tile tile-orange border border-danger border-opacity-25">
                    <i class="fas fa-database text-danger"></i>
                    <span>أداة البيانات</span>
                </a>
            </div>
        {% endif %}

        <div class="col">
            <a href="{{ url_for('connect.connect') }}" class="neo-tile tile-blue">
                <i class="fas fa-satellite-dish text-primary"></i>
                <span>مركز الاتصال</span>
            </a>
        </div>

        <!-- Settings -->
        {% if can_access('settings') %}
            <div class="col">
                <a href="{{ url_for('settings.view_settings') }}" class="neo-tile tile-slate">
                    <i class="fas fa-cog text-muted"></i>
                    <span>الإعدادات</span>
                </a>
            </div>
        {% endif %}

    </div>

    <!-- Real-time Connected Workflow Dashboard -->
    <div class="row justify-content-center mt-4 mb-5">
        <div class="col-lg-10">
            <div class="card border-0 shadow-sm overflow-hidden timeline-card" style="will-change: transform;">
                <div class="card-body p-3">

                    <div class="d-flex justify-content-between align-items-center mb-4">
                        <div>
                            <h5 class="fw-bold mb-1 text-dark" style="font-family: 'Cairo', sans-serif;">
                                <i class="fas fa-stream text-primary me-2"></i>تدفق المرضى المباشر
                            </h5>
                            <span class="text-muted small">تحديث لحظي لحركة العيادة</span>
                        </div>
                        <span class="badge bg-success-subtle text-success border border-success-subtle px-3 py-2 rounded-pill shadow-sm">
                            Live <i class="fas fa-wifi ms-1 fa-fade"></i>
                        </span>
                    </div>

                    <div class="position-relative px-3 py-2">
                        <div class="position-absolute top-50 start-0 w-100 translate-middle-y d-none d-md-block"
                            style="height: 3px; background: #e2e8f0; z-index: 0; margin-top: -15px;"></div>

                        <div class="d-flex justify-content-between position-relative flex-wrap gap-3" style="z-index: 1;">

                            <!-- Accounting -->
                            {% if can_access('invoices') %}
                                <div class="text-center step-item flex-fill">
                                    <div class="position-relative d-inline-block mb-2">
                                        <div class="bg-white rounded-circle shadow-sm d-flex align-items-center justify-content-center border border-2 border-primary transition-hover step-circle"
                                            style="width: 50px; height: 50px;">
                                            <i class="fas fa-file-invoice-dollar text-primary fs-5"></i>
                                        </div>
                                        <span class="position-absolute top-0 start-100 translate-middle badge rounded-pill bg-danger border border-white" data-type="q_scheduled" style="display: {{ 'block' if q_scheduled > 0 else 'none' }}">{{ q_scheduled }}</span>
                                    </div>
                                    <div class="fw-bold small text-dark d-block">المحاسبة</div>
                                </div>
                            {% endif %}

                            <!-- Triage -->
                            {% if can_access('triage') %}
                                <div class="text-center step-item flex-fill">
                                    <div class="position-relative d-inline-block mb-2">
                                        <div class="bg-white rounded-circle shadow-sm d-flex align-items-center justify-content-center border border-2 border-warning transition-hover step-circle"
                                            style="width: 50px; height: 50px;">
                                            <i class="fas fa-user-nurse text-warning fs-5"></i>
                                        </div>
                                        <span class="position-absolute top-0 start-100 translate-middle badge rounded-pill bg-danger border border-white" data-type="q_triage" style="display: {{ 'block' if q_triage > 0 else 'none' }}">{{ q_triage }}</span>
                                    </div>
                                    <div class="fw-bold small text-dark d-block">الفحص الأولي</div>
                                </div>
                            {% endif %}

                            <!-- Doctor -->
                            {% if can_access('doctor') %}
                                <div class="text-center step-item flex-fill">
                                    <div class="position-relative d-inline-block mb-2">
                                        <div class="bg-white rounded-circle shadow-sm d-flex align-items-center justify-content-center border border-2 border-indigo transition-hover step-circle"
                                            style="width: 50px; height: 50px; border-color: #6366f1 !important;">
                                            <i class="fas fa-user-md fs-5" style="color: #6366f1;"></i>
                                        </div>
                                        <span class="position-absolute top-0 start-100 translate-middle badge rounded-pill bg-danger border border-white" data-type="q_doctor" style="display: {{ 'block' if q_doctor > 0 else 'none' }}">{{ q_doctor }}</span>
                                    </div>
                                    <div class="fw-bold small text-dark d-block">العيادة</div>
                                </div>
                            {% endif %}

                            <!-- Nursing Lab (Sample Collection) -->
                            {% if can_access('nursing') %}
                                <div class="text-center step-item flex-fill">
                                    <div class="position-relative d-inline-block mb-2">
                                        <a href="{{ url_for('nursing_lab.nursing_lab') }}" class="text-decoration-none">
                                            <div class="bg-white rounded-circle shadow-sm d-flex align-items-center justify-content-center border border-2 border-info transition-hover step-circle"
                                                style="width: 50px; height: 50px;">
                                                <i class="fas fa-syringe text-info fs-5"></i>
                                            </div>
                                            <span class="position-absolute top-0 start-100 translate-middle badge rounded-pill bg-danger border border-white" data-type="q_nursing" style="display: {{ 'block' if q_nursing > 0 else 'none' }}">{{ q_nursing }}</span>
                                        </a>
                                    </div>
                                    <div class="fw-bold small text-dark d-block">سحب عينات</div>
                                </div>
                            {% endif %}

                            <!-- Lab/Radiology -->
                            {% if can_access('lab') or can_access('radiology') %}
                                <div class="text-center step-item flex-fill">
                                    <div class="position-relative d-inline-block mb-2">
                                        <a href="{{ url_for('lab.lab') }}" class="text-decoration-none">
                                            <div class="bg-white rounded-circle shadow-sm d-flex align-items-center justify-content-center border border-2 border-info transition-hover step-circle"
                                                style="width: 50px; height: 50px;">
                                                <i class="fas fa-microscope text-info fs-5"></i>
                                            </div>
                                            <span class="position-absolute top-0 start-100 translate-middle badge rounded-pill bg-danger border border-white" data-type="q_exams" style="display: {{ 'block' if (q_labs_items + q_rads_items) > 0 else 'none' }}">{{ q_labs_items + q_rads_items }}</span>
                                        </a>
                                    </div>
                                    <div class="fw-bold small text-dark d-block">الفحوصات</div>
                                </div>
                            {% endif %}

                            <!-- Pharmacy -->
                            {% if can_access('pharmacy') %}
                                <div class="text-center step-item flex-fill">
                                    <div class="position-relative d-inline-block mb-2">
                                        <div class="bg-white rounded-circle shadow-sm d-flex align-items-center justify-content-center border border-2 border-success transition-hover step-circle"
                                            style="width: 50px; height: 50px;">
                                            <i class="fas fa-pills text-success fs-5"></i>
                                        </div>
                                        <span class="position-absolute top-0 start-100 translate-middle badge rounded-pill bg-danger border border-white" data-type="q_pharmacy" style="display: {{ 'block' if q_pharmacy > 0 else 'none' }}">{{ q_pharmacy }}</span>
                                    </div>
                                    <div class="fw-bold small text-dark d-block">الصيدلية</div>
                                </div>
                            {% endif %}

                            <!-- Done -->
                            <div class="text-center step-item flex-fill">
                                <div class="position-relative d-inline-block mb-2">
                                    <div class="bg-white rounded-circle shadow-sm d-flex align-items-center justify-content-center border border-2 border-secondary transition-hover step-circle"
                                        style="width: 50px; height: 50px;">
                                        <i class="fas fa-check-circle text-secondary fs-5"></i>
                                    </div>
                                    <span class="position-absolute top-0 start-100 translate-middle badge rounded-pill bg-success border border-white" data-type="q_done" style="display: {{ 'block' if q_done > 0 else 'none' }}">{{ q_done }}</span>
                                </div>
                                <div class="fw-bold small text-muted d-block">تم الخروج</div>
                            </div>

                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <script>
    function updateDashboardRealtime() {
        fetch('/api_dashboard_counts')
            .then(res => res.json())
            .then(data => {
                if (data.error) return;
                
                // Update Badge Counts
                const counters = {
                    'q_scheduled': data.scheduled,
                    'q_triage':    data.triage,
                    'q_doctor':    data.doctor,
                    'q_labs_items': data.labs,
                    'q_rads_items': data.rads,
                    'q_pharmacy':   data.pharmacy,
                    'q_nursing':    data.nursing,
                    'q_done':       data.done
                };

                // Update Tiles
                document.querySelectorAll('.tile-count').forEach(tag => {
                    const type = tag.getAttribute('data-type');
                    if (counters[type] !== undefined) {
                        const count = counters[type];
                        tag.innerText = count;
                        tag.style.display = (count > 0) ? 'block' : 'none';
                    }
                });

                // Update Timeline Step Items
                document.querySelectorAll('.step-item .badge').forEach(tag => {
                    const type = tag.getAttribute('data-type');
                    if (counters[type] !== undefined) {
                        const count = counters[type];
                        tag.innerText = count;
                        tag.style.display = (count > 0) ? 'block' : 'none';
                    } else if (type === 'q_exams') {
                        const count = data.labs + data.rads;
                        tag.innerText = count;
                        tag.style.display = (count > 0) ? 'block' : 'none';
                    }
                });
            })
            .catch(err => console.error("Poll Error:", err));
    }

    // Poll every 5 seconds
    setInterval(updateDashboardRealtime, 5000);
    // Initial call
    updateDashboardRealtime();
    </script>
    """ + footer_html
    
    return render_template_string(html,
                                  can_access=can_access,
                                  is_admin=is_admin,
                                  q_scheduled=q_scheduled,
                                  q_triage=q_triage,
                                  q_doctor=q_doctor,
                                  q_labs_items=q_labs_items,
                                  q_rads_items=q_rads_items,
                                  q_pharmacy=q_pharmacy,
                                  q_nursing=q_nursing,
                                  q_done=q_done)

