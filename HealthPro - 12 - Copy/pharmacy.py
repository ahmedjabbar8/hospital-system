from flask import Blueprint, session, redirect, url_for, request, flash, render_template_string
from config import get_db, can_access
from header import header_html
from footer import footer_html

pharmacy_bp = Blueprint('pharmacy', __name__)

@pharmacy_bp.route('/pharmacy', methods=['GET', 'POST'])
def pharmacy():
    if not session.get('user_id') or not can_access('pharmacy'):
        return redirect(url_for('login.login'))
        
    conn = get_db()
    if not conn:
        return "Database Connection Error"
        
    cursor = conn.cursor(dictionary=True)
    
    # 1. Fetch Dynamic Currency
    cursor.execute("SELECT * FROM system_settings")
    settings_res = cursor.fetchall()
    sys_settings = {row['setting_key']: row['setting_value'] for row in settings_res}
    currency = sys_settings.get('currency_label', 'د.ع')
    
    # 3. Handle Dispense & Payment
    if request.method == 'POST' and 'dispense_now' in request.form:
        id = int(request.form.get('prescription_id', 0))
        amount = float(request.form.get('price', 0))
        pid = int(request.form.get('patient_id', 0))
        aid = int(request.form.get('appointment_id', 0))
        
        cursor.execute("UPDATE prescriptions SET status = 'dispensed' WHERE prescription_id = %s", (id,))
        cursor.execute("""
            INSERT INTO invoices (appointment_id, patient_id, amount, status, created_at) 
            VALUES (%s, %s, %s, 'paid_pharmacy', CURRENT_TIMESTAMP)

        """, (aid, pid, amount))
        conn.commit()
        
        flash("تم استلام المبلغ وصرف العلاج بنجاح", "success")
        return redirect(url_for('pharmacy.pharmacy'))

        
    # 2. Fetch Pending Prescriptions
    sql = """
        SELECT pr.*, p.full_name_ar as p_name, p.file_number, u.full_name_ar as doc_name 
        FROM prescriptions pr 
        JOIN patients p ON pr.patient_id = p.patient_id 
        LEFT JOIN users u ON pr.doctor_id = u.user_id 
        WHERE pr.status IN ('pending', 'pending_payment', 'pending_triage')
        AND DATE(pr.created_at) = date('now')
        ORDER BY pr.created_at ASC

    """
    cursor.execute(sql)
    prescriptions = cursor.fetchall()

    html = header_html + """

    <div class="d-flex justify-content-between align-items-center mb-4">
        <h2 class="fw-bold text-success"><i class="fas fa-pills me-2"></i> قسم الصيدلية (Pharmacy & Cashier)</h2>
        <div class="badge bg-success-subtle text-success border border-success-subtle p-2 px-3 rounded-pill fw-bold">
            صيدلية متكاملة (صرف + بيع)
        </div>
    </div>

    <div class="row">
        <div class="col-12">
            <div class="apple-card p-0 overflow-hidden shadow-sm">
                <div class="card-header bg-white border-0 py-3 h5 fw-bold mb-0">قائمة الوصفات الطبية بانتظار الصرف</div>
                <div class="table-responsive">
                    <table class="table table-hover align-middle mb-0">
                        <thead class="bg-light">
                            <tr>
                                <th class="ps-4">المريض</th>
                                <th>الطبيب</th>
                                <th>العلاج المطلوب</th>
                                <th>السعر</th>
                                <th class="text-center">الإجراء المالي والصرف</th>
                            </tr>
                        </thead>
                        <tbody>
                            {% for r in prescriptions %}
                                <tr>
                                    <td class="ps-4">
                                        <div class="fw-bold">{{ r.p_name }}</div>
                                        <small class="text-muted">{{ r.file_number }}</small>
                                    </td>
                                    <td><small class="text-muted">د. </small>{{ r.doc_name }}</td>
                                    <td>
                                        <div class="p-2 bg-light rounded-3 small fw-bold text-dark border-start border-success border-3">
                                            {{ r.medicine_name | replace('\\n', '<br>') | safe }}
                                        </div>
                                    </td>
                                    <td>
                                        <span class="badge bg-success fs-6">{{ "{:,.0f}".format(r.price) }} {{ currency }}</span>
                                    </td>
                                    <td class="text-center pe-4">
                                        <form method="POST" class="d-inline-block">
                                            <input type="hidden" name="prescription_id" value="{{ r.prescription_id }}">
                                            <input type="hidden" name="patient_id" value="{{ r.patient_id }}">
                                            <input type="hidden" name="appointment_id" value="{{ r.appointment_id }}">
                                            <input type="hidden" name="price" value="{{ r.price }}">
                                            <button type="submit" name="dispense_now" class="btn btn-success rounded-pill px-4 fw-bold">
                                                <i class="fas fa-money-bill-wave me-2"></i> استلام وصرف
                                            </button>
                                        </form>
                                        <a href="print_rx?id={{ r.prescription_id }}" class="btn btn-light rounded-circle shadow-sm ms-1">
                                            <i class="fas fa-print"></i>
                                        </a>
                                    </td>
                                </tr>
                            {% endfor %}
                            {% if not prescriptions %}
                                <tr>
                                    <td colspan="5" class="text-center py-5">
                                        <i class="fas fa-check-circle fa-3x text-muted mb-3"></i>
                                        <p class="text-muted">لا توجد وصفات طبية حالية للصرف</p>
                                    </td>
                                </tr>
                            {% endif %}
                        </tbody>
                    </table>
                </div>
            </div>
        </div>
    </div>
    """ + footer_html
    
    return render_template_string(html, prescriptions=prescriptions, currency=currency)
