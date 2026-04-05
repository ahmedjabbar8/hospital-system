from flask import Blueprint, session, redirect, url_for, request, render_template_string
from config import get_db, can_access
from header import header_html
from footer import footer_html

patient_index_bp = Blueprint('patient_index', __name__)

@patient_index_bp.route('/patient_index', methods=['GET'])
def patient_index():
    if not session.get('user_id') or (not can_access('registration') and not can_access('doctor') and not can_access('invoices')):
        return redirect(url_for('login.login'))
        
    search = request.args.get('q', '')
    
    conn = get_db()
    if not conn:
        return "Database Connection Error"
        
    cursor = conn.cursor(dictionary=True)
    
    sql = """
        SELECT p.*, 
        (SELECT COUNT(*) FROM appointments WHERE patient_id = p.patient_id) as visit_count,
        (SELECT MAX(appointment_date) FROM appointments WHERE patient_id = p.patient_id) as last_visit
        FROM patients p 
    """
    
    params = ()
    if search:
        search_term = f"%{search}%"
        sql += " WHERE p.full_name_ar LIKE %s OR p.file_number LIKE %s OR p.national_id LIKE %s "
        params = (search_term, search_term, search_term)
        
    sql += " ORDER BY p.full_name_ar ASC LIMIT 50"
    
    cursor.execute(sql, params)
    patients = cursor.fetchall()
    
    conn.close()

    html = header_html + """
    <style>
        :root {
            --idx-bg: #f5f6f8;
            --idx-card: #ffffff;
            --idx-text: #2c3e50;
            --idx-border: #e1e4e8;
            --idx-input: #ffffff;
        }

        [data-theme='dark'] {
            --idx-bg: #1a0b1d;
            --idx-card: #1a0b1d;
            --idx-text: #f0f0f0;
            --idx-border: rgba(255,255,255,0.1);
            --idx-input: rgba(255,255,255,0.05);
        }

        .idx-body { background: transparent; color: var(--idx-text); min-height: 100vh; transition: background 0.3s; padding-top: 2rem; }

        
        .glass-card {
            background: var(--idx-card);
            border: 1px solid var(--idx-border);
            border-radius: 20px;
            box-shadow: 0 4px 15px rgba(0,0,0,0.03);
            margin-bottom: 2rem;
            overflow: hidden;
        }

        .form-control { 
            background-color: var(--idx-input) !important; 
            color: var(--idx-text) !important; 
            border: 1px solid var(--idx-border) !important;
            border-radius: 12px !important;
            padding: 12px 20px !important;
        }
        .form-control::placeholder { color: var(--idx-text); opacity: 0.5; }
        
        .table { color: var(--idx-text) !important; background: transparent !important; }
        .table thead th { 
            background: rgba(0,0,0,0.02); 
            border-bottom: 2px solid var(--idx-border); 
            color: var(--idx-text); 
            opacity: 0.7; 
            padding: 1.2rem 1rem;
        }
        [data-theme='dark'] .table,
        [data-theme='dark'] .table tr,
        [data-theme='dark'] .table td { 
            background-color: transparent !important; 
            color: var(--idx-text) !important;
            border-bottom: 1px solid var(--idx-border);
        }

        [data-theme='dark'] .table-hover tbody tr:hover { 
            background-color: rgba(255, 255, 255, 0.03) !important; 
        }

        [data-theme='dark'] .badge.bg-light {
            background-color: var(--idx-input) !important;
            color: var(--idx-text) !important;
            border: 1px solid var(--idx-border) !important;
        }

        .btn-pill { border-radius: 50px; padding: 8px 20px; font-weight: 600; transition: all 0.3s; }
        
        .idx-header { margin-bottom: 2rem; }
        .idx-header h2 { font-weight: 800; display: flex; align-items: center; gap: 15px; }

        .patient-avatar {
            width: 45px;
            height: 45px;
            background: linear-gradient(135deg, #bf5af2 0%, #5e5ce6 100%);
            border-radius: 12px;
            display: flex;
            align-items: center;
            justify-content: center;
            color: white;
            font-size: 1.2rem;
        }
    </style>

    <div class="idx-body">
        <div class="container-fluid px-lg-5">
            <div class="idx-header">
                <h2><i class="fas fa-address-book text-primary"></i> فهرس المرضى والمراجعات</h2>
            </div>

            <div class="glass-card p-4">
                <form method="GET" class="row g-3" action="{{ url_for('patient_index.patient_index') }}">
                    <div class="col-md-10">
                        <input type="text" name="q" class="form-control" placeholder="ابحث بالاسم، رقم الملف، أو الهوية..." value="{{ search|e }}">
                    </div>
                    <div class="col-md-2">
                        <button type="submit" class="btn btn-primary w-100 btn-pill shadow-sm"><i class="fas fa-search me-1"></i> بحث في الفهرس</button>
                    </div>
                </form>
            </div>

            <div class="glass-card p-0">
                <div class="table-responsive">
                    <table class="table table-hover align-middle mb-0">
                        <thead>
                            <tr>
                                <th class="ps-4">المريض</th>
                                <th class="text-center">رقم الملف</th>
                                <th class="text-center">عدد المراجعات</th>
                                <th class="text-center">آخر زيارة</th>
                                <th class="pe-4 text-end">إجراءات</th>
                            </tr>
                        </thead>
                        <tbody>
                            {% for row in patients %}
                                <tr>
                                    <td class="ps-4">
                                        <div class="d-flex align-items-center gap-3">
                                            <div class="patient-avatar shadow-sm">
                                                <i class="fas fa-user"></i>
                                            </div>
                                            <div>
                                                <div class="fw-bold fs-5">{{ row.full_name_ar }}</div>
                                                <div class="small opacity-50">هوية: {{ row.national_id or '---' }}</div>
                                            </div>
                                        </div>
                                    </td>
                                    <td class="text-center">
                                        <span class="badge bg-light text-dark border rounded-pill px-3 py-2" style="background: var(--idx-input) !important; color: var(--idx-text) !important;">
                                            {{ row.file_number }}
                                        </span>
                                    </td>
                                    <td class="text-center">
                                        <span class="badge rounded-pill px-3 py-2" style="background: rgba(191, 90, 242, 0.1); color: #bf5af2; border: 1px solid rgba(191, 90, 242, 0.2);">
                                            <i class="fas fa-history me-1"></i> {{ row.visit_count }} زيارة
                                        </span>
                                    </td>
                                    <td class="text-center">
                                        <small class="opacity-75">
                                            <i class="far fa-calendar-alt me-1"></i>
                                            {% if row.last_visit and row.last_visit.__class__.__name__ in ['datetime', 'date'] %}
                                                {{ row.last_visit.strftime('%Y-%m-%d') }}
                                            {% elif row.last_visit %}
                                                {{ row.last_visit }}
                                            {% else %}
                                                لا يوجد
                                            {% endif %}
                                        </small>
                                    </td>
                                    <td class="pe-4 text-end">
                                        <div class="d-flex justify-content-end gap-2">
                                            <a href="{{ url_for('patient_file.patient_file') }}?id={{ row.patient_id }}" class="btn btn-outline-primary btn-pill btn-sm px-4">
                                                <i class="fas fa-file-medical me-1"></i> ملف المراجعات
                                            </a>
                                            <a href="{{ url_for('book.book') }}?id={{ row.patient_id }}" class="btn btn-success btn-pill btn-sm px-4 shadow-sm">
                                                <i class="fas fa-plus-circle me-1"></i> حجز جديد
                                            </a>
                                        </div>
                                    </td>
                                </tr>
                            {% else %}
                                <tr><td colspan="5" class="text-center py-5 opacity-50"><i class="fas fa-search fa-3x mb-3"></i><h5>لم يتم العثور على أي مريض بالفهرس</h5></td></tr>
                            {% endfor %}
                        </tbody>
                    </table>
                </div>
            </div>
        </div>
    </div>
    """ + footer_html
    
    return render_template_string(html, patients=patients, search=search)
