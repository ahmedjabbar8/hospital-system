from flask import Blueprint, session, redirect, url_for, request, flash, render_template_string
from config import get_db, can_access
from header import header_html
from footer import footer_html
import datetime

billing_bp = Blueprint('billing', __name__)

@billing_bp.route('/billing', methods=['GET', 'POST'])
def billing():
    if not session.get('user_id') or not can_access('invoices'):
        return redirect(url_for('login.login'))
        
    conn = get_db()
    if not conn:
        return "Database Connection Error"
        
    cursor = conn.cursor(dictionary=True)
    
    # Update current task
    cursor.execute("UPDATE users SET current_task = 'إدارة الصندوق المالي' WHERE user_id = %s", (session['user_id'],))
    conn.commit()
    
    # --- Handle Multi-Payment & Discount ---
    if request.method == 'POST' and 'process_payment' in request.form:
        patient_id = int(request.form.get('patient_id', 0))
        appt_id = int(request.form.get('appointment_id', 0))
        discount = float(request.form.get('discount_amount') or 0)
        total_original = float(request.form.get('total_original', 0))
        final_amount = total_original - discount
        
        if request.form.get('pay_appt'):
            cursor.execute("UPDATE appointments SET status = 'pending_triage' WHERE appointment_id = %s", (appt_id,))
            
        pay_labs = request.form.getlist('pay_labs[]')
        for lid in pay_labs:
            cursor.execute("UPDATE lab_requests SET status = 'pending' WHERE request_id = %s", (int(lid),))
            
        pay_rads = request.form.getlist('pay_rads[]')
        for rid in pay_rads:
            cursor.execute("UPDATE radiology_requests SET status = 'pending' WHERE request_id = %s", (int(rid),))
            
        pay_prescs = request.form.getlist('pay_prescs[]')
        for pxid in pay_prescs:
            cursor.execute("UPDATE prescriptions SET status = 'pending' WHERE prescription_id = %s", (int(pxid),))
            
        cursor.execute("INSERT INTO invoices (appointment_id, patient_id, amount, status) VALUES (%s, %s, %s, 'paid')", (appt_id, patient_id, final_amount))
        
        conn.commit()
        flash(f"تم استلام المبلغ بنجاح: {final_amount:,.0f}", "success")
        return redirect(url_for('billing.billing'))



    # Fetch patients with pending payments
    sql_patients = """
        SELECT DISTINCT p.patient_id, p.full_name_ar, p.file_number, p.category, a.appointment_id, a.is_free 
        FROM patients p 
        JOIN appointments a ON p.patient_id = a.patient_id
        LEFT JOIN lab_requests l ON a.appointment_id = l.appointment_id AND l.status = 'pending_payment'
        LEFT JOIN radiology_requests r ON a.appointment_id = r.appointment_id AND r.status = 'pending_payment'
        LEFT JOIN prescriptions pr ON a.appointment_id = pr.appointment_id AND pr.status = 'pending_payment'
        WHERE DATE(a.appointment_date) = date('now')

           AND (
               (a.status = 'scheduled')
               OR (l.status = 'pending_payment')
               OR (r.status = 'pending_payment')
               OR (pr.status = 'pending_payment')
           )
        ORDER BY a.appointment_date DESC
    """
    cursor.execute(sql_patients)
    patients_res = cursor.fetchall()
    
    cursor.execute("SELECT * FROM system_settings")
    prices_res = cursor.fetchall()
    prices = {pr['setting_key']: pr['setting_value'] for pr in prices_res}
    
    price_consult = float(prices.get('price_consultation', 25000))
    currency = prices.get('currency_label', 'د.ع')
    
    discount_rates = {'normal': 0, 'senior': 20, 'martyr': 25, 'special': 30}
    category_names = {'normal': 'عادي', 'senior': 'كبار السن', 'martyr': 'عائلات الشهداء', 'special': 'ذوي الاحتياجات الخاصة'}
    
    patients_data = []
    
    for p in patients_res:
        pid = p['patient_id']
        aid = p['appointment_id']
        is_free = int(p['is_free']) == 1 if p.get('is_free') is not None else False
        items = []
        total = 0
        
        cursor.execute("SELECT * FROM appointments WHERE appointment_id = %s AND status = 'scheduled'", (aid,))
        chk_appt = cursor.fetchone()
        if chk_appt:
            actual_price = 0 if is_free else price_consult
            items.append({'type': 'مراجعة مجانية' if is_free else 'كشف طبي للعيادة', 'id': aid, 'price': actual_price, 'db_type': 'appt'})
            total += actual_price
            
        cursor.execute("SELECT * FROM lab_requests WHERE appointment_id = %s AND status = 'pending_payment'", (aid,))
        for l in cursor.fetchall():
            price = float(l['price']) if l['price'] is not None else 0
            items.append({'type': f"مختبر: {l['test_type']}", 'id': l['request_id'], 'price': price, 'db_type': 'lab'})
            total += price
            
        cursor.execute("SELECT * FROM radiology_requests WHERE appointment_id = %s AND status = 'pending_payment'", (aid,))
        for r in cursor.fetchall():
            price = float(r['price']) if r['price'] is not None else 0
            items.append({'type': f"أشعة: {r['scan_type']}", 'id': r['request_id'], 'price': price, 'db_type': 'rad'})
            total += price
            
        cursor.execute("SELECT * FROM prescriptions WHERE appointment_id = %s AND status = 'pending_payment'", (aid,))
        for px in cursor.fetchall():
            price = float(px['price']) if px['price'] is not None else 0
            items.append({'type': f"صيدلية: {px['medicine_name']}", 'id': px['prescription_id'], 'price': price, 'db_type': 'px'})
            total += price
            
        p_category = p.get('category') or 'normal'
        rate = discount_rates.get(p_category, 0)
        auto_discount = (total * rate) / 100
        
        patients_data.append({
            'patient_id': pid,
            'appointment_id': aid,
            'full_name_ar': p['full_name_ar'],
            'file_number': p['file_number'],
            'total': total,
            'auto_discount': auto_discount,
            'billing_items': items,
            'category_name': category_names.get(p_category, 'عادي')
        })


    html = header_html + """

    <div class="billing-redesign py-4">
        <div class="mb-5 text-center">
            <h1 class="fw-bold display-6 text-success"><i class="fas fa-coins me-2"></i> مركز المحاسبة الذكي</h1>
            <p class="text-muted">إدارة المدفوعات، الخصومات، وإصدار الفواتير الفورية</p>
        </div>
        
        {% with messages = get_flashed_messages(with_categories=true) %}
            {% if messages %}
                {% for category, message in messages %}
                    <div class="alert alert-{{ category }} alert-dismissible fade show text-center w-50 mx-auto">
                        {{ message }}
                        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
                    </div>
                {% endfor %}
            {% endif %}
        {% endwith %}
 
        {% if not patients_data %}
            <div class="text-center py-5 glass-card rounded-5 mb-5 mx-auto" style="max-width: 600px;">
                <i class="fas fa-check-double fa-4x text-success mb-3 opacity-50"></i>
                <h4 class="fw-bold">كافة الحسابات مصفاة بالكامل</h4>
                <p class="text-muted">لا يوجد مرضى بانتظار الدفع في الوقت الحالي.</p>
            </div>
        {% else %}
            <div class="row g-4">
                {% for p in patients_data %}
                    <div class="col-12 col-xl-6">
                        <div class="glass-card shadow-sm border-0 rounded-4 p-4 h-100 position-relative overflow-hidden bg-white">
                            <div class="d-flex justify-content-between align-items-start mb-4">
                                <div>
                                    <h4 class="fw-bold text-dark mb-1">{{ p.full_name_ar }}</h4>
                                    <span class="badge bg-secondary bg-opacity-10 text-dark small rounded-pill px-3">ملف: {{ p.file_number }}</span>
                                </div>
                                <div class="text-end">
                                    <div class="h3 fw-bold text-success mb-0">{{ "{:,.0f}".format(p.total - p.auto_discount) }}
                                        <small style="font-size: 0.6em;">{{ currency }}</small>
                                    </div>
                                    <small class="text-muted text-decoration-line-through">أصلي: {{ "{:,.0f}".format(p.total) }}</small>
                                </div>
                            </div>

                            <form method="POST">
                                <input type="hidden" name="patient_id" value="{{ p.patient_id }}">
                                <input type="hidden" name="appointment_id" value="{{ p.appointment_id }}">
                                <input type="hidden" name="total_original" value="{{ p.total }}">

                                <div class="bg-light bg-opacity-50 rounded-4 p-3 mb-4">
                                    <h6 class="small fw-bold text-muted text-uppercase mb-3"><i class="fas fa-file-invoice me-2"></i> تفاصيل الخدمات</h6>
                                    <div class="d-flex flex-column gap-2">
                                        {% for it in p.billing_items %}
                                            <div class="d-flex justify-content-between align-items-center">
                                                <span class="small text-dark opacity-75">{{ it.type }}</span>
                                                <span class="small fw-bold">{{ "{:,.0f}".format(it.price) }}</span>
                                                {% if it.db_type == 'lab' %}
                                                    <input type="hidden" name="pay_labs[]" value="{{ it.id }}">
                                                {% elif it.db_type == 'rad' %}
                                                    <input type="hidden" name="pay_rads[]" value="{{ it.id }}">
                                                {% elif it.db_type == 'px' %}
                                                    <input type="hidden" name="pay_prescs[]" value="{{ it.id }}">
                                                {% elif it.db_type == 'appt' %}
                                                    <input type="hidden" name="pay_appt" value="1">
                                                {% endif %}
                                            </div>
                                        {% endfor %}
                                    </div>
                                </div>

                                <div class="row g-3 align-items-center mb-4">
                                    <div class="col-md-6">
                                        <div class="p-2 border rounded-4 d-flex align-items-center">
                                            <div class="bg-primary bg-opacity-10 text-primary p-2 rounded-circle me-3">
                                                <i class="fas fa-tag"></i>
                                            </div>
                                            <div>
                                                <div class="small text-muted">فئة المريض</div>
                                                <div class="fw-bold">{{ p.category_name }}</div>
                                            </div>
                                        </div>
                                    </div>
                                    <div class="col-md-6 text-end">
                                        <label class="small text-muted mb-1">تعديل قيمة الخصم</label>
                                        <div class="input-group">
                                            <input type="number" name="discount_amount"
                                                class="form-control apple-form-control text-center fw-bold text-danger border-danger"
                                                value="{{ p.auto_discount }}">
                                            <span class="input-group-text bg-danger text-white border-danger small py-1 px-2">{{ currency }}</span>
                                        </div>
                                    </div>
                                </div>

                                <button type="submit" name="process_payment"
                                    class="btn btn-success w-100 rounded-pill py-3 fw-bold shadow-sm">
                                    <i class="fas fa-receipt me-2"></i> دفع وإصدار فاتورة نهائية
                                </button>
                            </form>
                        </div>
                    </div>
                {% endfor %}
            </div>
        {% endif %}
    </div>

    <style>
        .glass-card {
            background: #ffffff !important;
            border: 1px solid rgba(0, 0, 0, 0.1) !important;
            transition: transform 0.3s ease;
        }

        .glass-card:hover {
            transform: translateY(-5px);
            box-shadow: 0 10px 30px rgba(0, 0, 0, 0.08) !important;
        }

        .apple-form-control:focus {
            box-shadow: 0 0 0 3px rgba(25, 135, 84, 0.1);
            border-color: #198754;
        }
    </style>
    """ + footer_html
    
    return render_template_string(html, patients_data=patients_data, currency=currency)
