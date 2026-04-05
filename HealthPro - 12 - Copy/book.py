from flask import Blueprint, session, redirect, url_for, request, flash, render_template_string
from config import get_db, can_access
from header import header_html
from footer import footer_html
import datetime

book_bp = Blueprint('book', __name__)

@book_bp.route('/book', methods=['GET', 'POST'])
def book():
    if not session.get('user_id'):
        return redirect(url_for('login.login'))
        
    patient_id = request.args.get('id')
    if not patient_id:
        return redirect(url_for('patients.patients'))
        
    conn = get_db()
    if not conn:
        return "Database Connection Error"
        
    cursor = conn.cursor(dictionary=True)
    
    # Fetch Patient Info
    cursor.execute("SELECT * FROM patients WHERE patient_id = %s", (patient_id,))
    patient = cursor.fetchone()
    
    if not patient:
        return redirect(url_for('patients.patients'))

        
    if request.method == 'POST':
        doctor_id = request.form.get('doctor_id')
        dept_id = request.form.get('dept_id')
        date = request.form.get('date')
        
        sql = "INSERT INTO appointments (patient_id, doctor_id, department_id, appointment_date, status) VALUES (%s, %s, %s, %s, 'scheduled')"
        try:
            cursor.execute(sql, (patient_id, doctor_id, dept_id, date))
            conn.commit()
            flash("تم حجز الموعد بنجاح. المريض الآن في قائمة انتظار المحاسبة.", "success")
            # Assuming billing view will be implemented as billing.billing
            return redirect(url_for('billing.billing'))

        except Exception as e:
            conn.rollback()
            flash(f"حدث خطأ أثناء الحجز: {str(e)}", "danger")
            
    # Fetch Doctors and Departments
    cursor.execute("SELECT * FROM users WHERE role = 'doctor'")
    doctors = cursor.fetchall()
    
    cursor.execute("SELECT * FROM departments WHERE department_type = 'medical'")
    depts = cursor.fetchall()
    
    conn.close()
    
    today = datetime.date.today().strftime('%Y-%m-%d')

    html = header_html + """
    <div class="container py-5 solid-mode" style="min-height: 80vh;">
        <div class="row justify-content-center">
            <div class="col-lg-8">
                <!-- Header -->
                <div class="d-flex justify-content-between align-items-center mb-4">
                    <div class="d-flex align-items-center gap-3">
                        <div class="bg-primary text-white d-flex align-items-center justify-content-center rounded-circle shadow-sm" style="width: 50px; height: 50px;">
                            <i class="fas fa-calendar-plus fa-lg"></i>
                        </div>
                        <div>
                            <h3 class="fw-bold mb-0 text-dark">حجز موعد طبي</h3>
                            <p class="text-muted small mb-0">للمريض: <strong>{{ patient.full_name_ar }}</strong></p>
                        </div>
                    </div>
                    <a href="{{ url_for('patients.patients') }}" class="btn btn-light border shadow-sm rounded-pill fw-bold text-muted px-4">إلغاء <i class="fas fa-undo ms-1"></i></a>
                </div>

                <!-- Booking Card -->
                <div class="card border-0 shadow-sm rounded-4 bg-white p-5 animate__animated animate__fadeInUp">
                    {% with messages = get_flashed_messages(with_categories=true) %}
                        {% if messages %}
                            {% for category, message in messages %}
                                <div class="alert alert-{{ 'success' if category == 'success' else 'danger' }} alert-dismissible fade show border-0 shadow-sm rounded-3">
                                    <i class="fas fa-info-circle me-2"></i> {{ message }}
                                    <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
                                </div>
                            {% endfor %}
                        {% endif %}
                    {% endwith %}
                    
                    <form method="POST">
                        <div class="row g-4 mb-5">
                            <div class="col-12">
                                <label class="form-label fw-bold small text-muted"><i class="fas fa-layer-group ms-1"></i> القسم / العيادة</label>
                                <select name="dept_id" id="deptFilter" class="form-select form-control-lg bg-light border-0 rounded-3" required onchange="filterDoctors()">
                                    <option value="" disabled selected>-- اختر القسم الطبي أولاً --</option>
                                    {% for d in depts %}
                                        <option value="{{ d.department_id }}">{{ d.department_name_ar }}</option>
                                    {% endfor %}
                                    {% if not depts %}
                                        <option value="" disabled>لا توجد أقسام طبية مسجلة</option>
                                    {% endif %}
                                </select>
                            </div>
                            
                            <div class="col-12">
                                <label class="form-label fw-bold small text-muted"><i class="fas fa-user-md ms-1"></i> الطبيب المعالج</label>
                                <select name="doctor_id" id="doctorSelect" class="form-select form-control-lg bg-light border-0 rounded-3" required disabled>
                                    <option value="" disabled selected>-- يرجى اختيار القسم --</option>
                                    {% for doc in doctors %}
                                        <option value="{{ doc.user_id }}" data-dept="{{ doc.department_id }}">د. {{ doc.full_name_ar }} ({{ doc.username }})</option>
                                    {% endfor %}
                                </select>
                            </div>

                            <div class="col-12">
                                <label class="form-label fw-bold small text-muted"><i class="far fa-calendar-alt ms-1"></i> تاريخ الموعد</label>
                                <input type="date" name="date" class="form-control form-control-lg bg-light border-0 rounded-3" value="{{ today }}" required>
                            </div>
                        </div>

                        <hr class="mb-4" style="opacity: 0.1;">
                        <button type="submit" id="submitBtn" class="btn btn-primary w-100 py-3 rounded-pill shadow-sm fw-bold fs-5" disabled>
                            <i class="fas fa-check-circle me-2"></i> تأكيد الحجز والتحويل للمحاسبة
                        </button>
                    </form>
                </div>
            </div>
        </div>
    </div>

    <script>
        function filterDoctors() {
            const deptSelect = document.getElementById('deptFilter');
            const docSelect = document.getElementById('doctorSelect');
            const submitBtn = document.getElementById('submitBtn');
            const selectedDept = deptSelect.value;
            
            // Enable the doctor select box
            docSelect.disabled = !selectedDept;
            
            // Get all doctor options except the first placeholder
            const options = Array.from(docSelect.options).slice(1);
            
            // Reset choice
            docSelect.value = "";
            let hasDoctors = false;
            
            options.forEach(opt => {
                if (opt.getAttribute('data-dept') === selectedDept) {
                    opt.style.display = 'block';
                    hasDoctors = true;
                } else {
                    opt.style.display = 'none';
                }
            });
            
            if (!hasDoctors && selectedDept) {
                docSelect.options[0].text = "-- عذراً، لا يوجد أطباء متاحين في هذا القسم --";
                docSelect.disabled = true;
                submitBtn.disabled = true;
            } else if (selectedDept) {
                docSelect.options[0].text = "-- اختر الطبيب المتاح --";
                docSelect.disabled = false;
            }
        }
        
        // Listen to doctor selection to enable submit
        document.getElementById('doctorSelect').addEventListener('change', function() {
            document.getElementById('submitBtn').disabled = !this.value;
        });

        // Initialize display if going back
        document.addEventListener("DOMContentLoaded", function() {
            if(document.getElementById('deptFilter').value) {
                filterDoctors();
            }
        });
    </script>
    """ + footer_html
    
    return render_template_string(html, patient=patient, doctors=doctors, depts=depts, today=today)
