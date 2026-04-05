from flask import Blueprint, session, redirect, url_for, request, flash, render_template_string # type: ignore
from config import get_db, can_access # type: ignore
from header import header_html # type: ignore
from footer import footer_html # type: ignore
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
            cursor.execute("SELECT department_id FROM appointments WHERE appointment_id = %s", (appt_id,))
            appt_info = cursor.fetchone()
            if appt_info and appt_info['department_id'] in [3, 4]:
                # For direct Lab/Rad, stay in scheduled or set to something else that's not triage
                cursor.execute("UPDATE appointments SET status = 'scheduled' WHERE appointment_id = %s", (appt_id,))
            else:
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



    # Fix: Use local date from Python instead of UTC date('now')
    today_str = datetime.datetime.now().strftime('%Y-%m-%d')

    # Fetch total paid today
    cursor.execute("SELECT SUM(amount) as total FROM invoices WHERE DATE(created_at) = %s AND status = 'paid'", (today_str,))
    res_tot = cursor.fetchone()
    total_paid_today = float(res_tot['total']) if res_tot and res_tot['total'] else 0.0

    # Fetch patients with pending payments
    sql_patients = """
        SELECT DISTINCT p.patient_id, p.full_name_ar, p.file_number, p.category, a.appointment_id, a.is_free, a.appointment_date 
        FROM patients p 
        JOIN appointments a ON p.patient_id = a.patient_id
        LEFT JOIN lab_requests l ON a.appointment_id = l.appointment_id AND l.status = 'pending_payment'
        LEFT JOIN radiology_requests r ON a.appointment_id = r.appointment_id AND r.status = 'pending_payment'
        LEFT JOIN prescriptions pr ON a.appointment_id = pr.appointment_id AND pr.status = 'pending_payment'
        WHERE DATE(a.appointment_date) = %s

           AND (
               (a.status = 'scheduled')
               OR (l.status = 'pending_payment')
               OR (r.status = 'pending_payment')
               OR (pr.status = 'pending_payment')
           )
        ORDER BY a.appointment_date DESC
    """
    cursor.execute(sql_patients, (today_str,))
    patients_res = cursor.fetchall()
    
    cursor.execute("SELECT * FROM system_settings")
    prices_res = cursor.fetchall()
    prices = {pr['setting_key']: pr['setting_value'] for pr in prices_res}
    
    price_consult = float(prices.get('price_consultation', 25000))
    currency = prices.get('currency_label', 'د.ع')
    
    discount_rates = {
        'normal': float(prices.get('discount_normal', 0)),
        'senior': float(prices.get('discount_senior', 20)),
        'martyr': float(prices.get('discount_martyr', 25)),
        'special': float(prices.get('discount_special', 30))
    }
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
        
        is_delayed = False
        delay_msg = ""
        appt_date_str = ""
        appt_val = p.get('appointment_date')
        if appt_val:
            if isinstance(appt_val, str):
                try:
                    # Parse by splitting by dot for potential microseconds
                    dt_part = appt_val.split('.')[0]
                    # Further ensure precisely 19 chars for standard YYYY-MM-DD HH:MM:SS
                    appt_date_str = str(dt_part)[0:19] # type: ignore
                    appt_dt_obj = datetime.datetime.strptime(appt_date_str, '%Y-%m-%d %H:%M:%S')
                except:
                    appt_dt_obj = None
            else:
                appt_dt_obj = appt_val
                appt_date_str = appt_val.strftime('%Y-%m-%d %H:%M:%S')

            if appt_dt_obj:
                diff_minutes = (datetime.datetime.now() - appt_dt_obj).total_seconds() / 60
                if diff_minutes >= 7:
                    is_delayed = True
                    delay_msg = f"تأخر ({int(diff_minutes)} دقيقة)"

        # Generate dynamic summary label
        parts = []
        types_count = {}
        for it in items:
            t = it['db_type']
            types_count[t] = types_count.get(t, 0) + 1
            
        if types_count.get('appt'): 
            parts.append("كشفية" if types_count['appt'] == 1 else f"{types_count['appt']} كشفيات")
        if types_count.get('lab'):  
            parts.append("تحاليل" if types_count['lab'] > 1 else "تحليل مختبر")
        if types_count.get('rad'):  
            parts.append("أشعة" if types_count['rad'] > 1 else "أشعة")
        if types_count.get('px'):   
            parts.append("صيدلية" if types_count['px'] == 1 else f"{types_count['px']} علاجات")
            
        summary_label = " + ".join(parts) if parts else "بدون تفاصيل"

        patients_data.append({
            'patient_id': pid,
            'appointment_id': aid,
            'full_name_ar': p['full_name_ar'],
            'file_number': p['file_number'],
            'total': total,
            'auto_discount': auto_discount,
            'billing_items': items,
            'summary_label': summary_label,
            'category_name': category_names.get(p_category, 'عادي'),
            'is_delayed': is_delayed,
            'delay_msg': delay_msg,
            'appt_date_str': appt_date_str
        })


    html = header_html + """

    <div class="billing-redesign py-4">
        <div class="mb-5 d-flex flex-column flex-md-row justify-content-center align-items-center gap-4">
            <h1 class="fw-bold display-6 text-success m-0"><i class="fas fa-coins me-2"></i> مركز المحاسبة الذكي</h1>
            <div class="d-flex justify-content-center gap-3" id="buttons_container">
                <a href="{{ url_for('billing.billing_history') }}" class="btn btn-primary bg-gradient rounded-3 shadow-sm d-flex align-items-center justify-content-center px-4 border-0" style="height: 48px; min-width: 160px; font-weight: bold;">
                    <i class="fa-solid fa-print me-2"></i> طباعة وصل قديم
                </a>
                <a href="{{ url_for('billing.patient_statement') }}" class="btn btn-outline-info rounded-3 shadow-sm d-flex align-items-center justify-content-center px-4" style="height: 48px; min-width: 160px; font-weight: bold;">
                    <i class="fa-solid fa-file-invoice-dollar me-2" style="font-size: 1.1rem;"></i> كشف حساب
                </a>
            </div>
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
            <div class="text-center py-5 glass-card rounded-3 mb-5 mx-auto" style="max-width: 600px;">
                <i class="fas fa-check-double fa-4x text-success mb-3 opacity-50"></i>
                <h4 class="fw-bold">كافة الحسابات مصفاة بالكامل</h4>
                <p class="text-muted">لا يوجد مرضى بانتظار الدفع في الوقت الحالي.</p>
            </div>
        {% else %}
            <div class="accordion custom-billing-accordion container" id="billingAccordion" style="max-width: 1000px;">
                {% for p in patients_data %}
                    <div class="accordion-item shadow-sm border rounded-3 mb-3 overflow-hidden bg-white patient-billing-card {% if p.is_delayed %}delayed-card{% endif %}" id="card-{{ p.patient_id }}" data-patient-id="{{ p.patient_id }}" data-arrival-time="{{ p.appt_date_str }}" data-patient-name="{{ p.full_name_ar }}" style="border-color: #eee !important;">
                        
                        <div class="accordion-header" id="heading{{ p.patient_id }}">
                            <div class="d-flex w-100 align-items-center justify-content-between px-4 py-2">
                                <!-- Right Side: Icon and Name -->
                                <div class="d-flex align-items-center gap-3">
                                    <div class="rounded-circle bg-light text-primary d-flex align-items-center justify-content-center" style="width: 42px; height: 42px; background-color: #f1f5f9 !important;">
                                        <i class="fas fa-user-injured fs-6 shadow-sm"></i>
                                    </div>
                                    <div class="d-flex align-items-center gap-3">
                                        <h6 class="fw-bold text-dark mb-0 fs-5">
                                            {{ p.full_name_ar }} 
                                            <i class="fas fa-exclamation-triangle text-danger delay-warning-icon {% if not p.is_delayed %}d-none{% endif %}" title="{{ p.delay_msg }}" style="cursor:help;"></i>
                                        </h6>
                                        <div class="d-flex align-items-center gap-2">
                                            <span class="text-muted small"># {{ p.file_number }}</span>
                                            <span class="text-muted small px-1">|</span>
                                            <span class="text-primary small fw-semibold"><i class="fas fa-user-md me-1"></i> د. مدير النظام</span>
                                            <span class="text-muted small px-1">|</span>
                                            <span class="text-muted small">28 سنة</span>
                                        </div>
                                    </div>
                                </div>

                                <!-- Left Side: Price and Action -->
                                <div class="d-flex align-items-center gap-4">
                                    <div class="text-end me-4">
                                        <span class="badge bg-danger bg-opacity-10 text-danger rounded-3 px-3 py-1 fw-bold"><i class="fas fa-bolt me-1"></i> STAT</span>
                                    </div>
                                    <div class="text-start me-4">
                                        <span class="fs-4 fw-bold text-success">{{ "{:,.0f}".format(p.total - p.auto_discount) }}</span>
                                        <small class="text-muted">{{ currency }}</small>
                                    </div>
                                    <button class="btn btn-primary btn-sm rounded-3 px-4 py-2 collapsed d-flex align-items-center gap-2 shadow-sm" type="button" data-bs-toggle="collapse" data-bs-target="#collapse{{ p.patient_id }}" aria-expanded="false" aria-controls="collapse{{ p.patient_id }}" style="background-color: #eff6ff; border: none; color: #2563eb; font-weight: bold;">
                                        <span>{{ p.summary_label }}</span>
                                        <i class="fas fa-chevron-left small transition-all"></i>
                                    </button>
                                </div>
                            </div>
                        </div>

                        <div id="collapse{{ p.patient_id }}" class="accordion-collapse collapse" aria-labelledby="heading{{ p.patient_id }}" data-bs-parent="#billingAccordion">
                            <div class="accordion-body bg-light bg-opacity-50 p-4 border-top">
                                <form method="POST">
                                    <input type="hidden" name="patient_id" value="{{ p.patient_id }}">
                                    <input type="hidden" name="appointment_id" value="{{ p.appointment_id }}">
                                    <input type="hidden" name="total_original" value="{{ p.total }}">

                                    <div class="row g-4">
                                        <div class="col-lg-7">
                                            <div class="bg-white rounded-3 p-4 shadow-sm border border-light h-100">
                                                <h6 class="fw-bold text-muted text-uppercase mb-4 d-flex align-items-center gap-2"><i class="fas fa-list-ul text-primary"></i> الخدمات والتحاليل</h6>
                                                <div class="table-responsive">
                                                    <table class="table table-borderless align-middle mb-0">
                                                        <tbody>
                                                            {% for it in p.billing_items %}
                                                            <tr class="border-bottom">
                                                                <td class="py-3 px-0"><span class="text-dark fw-semibold"><i class="fas fa-check text-success opacity-75 ms-2 small"></i>{{ it.type }}</span></td>
                                                                <td class="text-end py-3 px-0 fw-bold fs-5 text-primary">{{ "{:,.0f}".format(it.price) }} <small class="text-muted fs-6">{{ currency }}</small></td>
                                                            </tr>
                                                            {% if it.db_type == 'lab' %}
                                                                <input type="hidden" name="pay_labs[]" value="{{ it.id }}">
                                                            {% elif it.db_type == 'rad' %}
                                                                <input type="hidden" name="pay_rads[]" value="{{ it.id }}">
                                                            {% elif it.db_type == 'px' %}
                                                                <input type="hidden" name="pay_prescs[]" value="{{ it.id }}">
                                                            {% elif it.db_type == 'appt' %}
                                                                <input type="hidden" name="pay_appt" value="1">
                                                            {% endif %}
                                                            {% endfor %}
                                                        </tbody>
                                                    </table>
                                                </div>
                                            </div>
                                        </div>
                                        
                                        <div class="col-lg-5">
                                            <div class="bg-white rounded-3 p-4 shadow-sm border border-light h-100 d-flex flex-column">
                                                <h6 class="fw-bold text-muted text-uppercase mb-4 d-flex align-items-center gap-2"><i class="fas fa-calculator text-success"></i> ملخص الدفع النهائي</h6>
                                                
                                                <div class="d-flex justify-content-between mb-3 pb-3 border-bottom">
                                                    <span class="text-muted fw-semibold">المجموع الكلي:</span>
                                                    <span class="fw-bold fs-5">{{ "{:,.0f}".format(p.total) }}</span>
                                                </div>
                                                
                                                <div class="mb-4">
                                                    <label class="d-flex justify-content-between align-items-center mb-2">
                                                        <span class="text-muted fw-semibold">قيمة الخصم المستحق:</span>
                                                        <span class="badge bg-danger bg-opacity-10 text-danger rounded-3 px-3 py-1"><i class="fas fa-tag ms-1"></i> خصم الفئة</span>
                                                    </label>
                                                    <div class="input-group input-group-lg" dir="ltr">
                                                        <span class="input-group-text bg-danger text-white border-0 fw-bold">{{ currency }}</span>
                                                        <input type="number" name="discount_amount"
                                                            class="form-control text-center fw-bold text-danger border-0 shadow-none bg-danger bg-opacity-10"
                                                            value="{{ p.auto_discount }}" dir="rtl">
                                                    </div>
                                                </div>
                                                
                                                <div class="mt-auto pt-2">
                                                    <button type="submit" name="process_payment"
                                                        class="btn btn-success w-100 rounded-3 py-3 fw-bold shadow hover-lift d-flex align-items-center justify-content-center gap-2 fs-5 transition-all">
                                                        <i class="fas fa-receipt"></i> تأكيد استلام المبلغ وإصدار الوصل
                                                    </button>
                                                </div>
                                            </div>
                                        </div>
                                    </div>

                                </form>
                            </div>
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
    
    </style>
    

    <style>
    @keyframes pulse-danger {
      0% { box-shadow: 0 0 0 0 rgba(220, 53, 69, 0.7); }
      70% { box-shadow: 0 0 0 15px rgba(220, 53, 69, 0); }
      100% { box-shadow: 0 0 0 0 rgba(220, 53, 69, 0); }
    }
    .delayed-card {
        border: 2px solid #dc3545 !important;
        animation: pulse-danger 2s infinite;
    }
    </style>

    <!-- إشعارات التأخير في الدفع -->
    <div class="toast-container position-fixed bottom-0 start-0 p-3" id="delay-toasts-container" style="z-index: 10000;">
    </div>

    <script>
    document.addEventListener('DOMContentLoaded', () => {
        const container = document.getElementById('delay-toasts-container');
        
        container.addEventListener('click', (e) => {
            if(e.target.classList.contains('btn-close')){
                const toast = e.target.closest('.toast');
                if(toast) { 
                    toast.classList.remove('show');
                    setTimeout(() => toast.remove(), 300);
                }
            }
        });
        
        // نظام مراقبة التوقيت المباشر (تحديث التأخير بدون ريفريش للصفحة)
        setInterval(() => {
            const now = new Date();
            document.querySelectorAll('.patient-billing-card').forEach(card => {
                const arrivalStr = card.getAttribute('data-arrival-time');
                const pid = card.getAttribute('data-patient-id');
                const pname = card.getAttribute('data-patient-name');
                if(!arrivalStr) return;
                
                const dtParts = arrivalStr.split(' ');
                if(dtParts.length !== 2) return;
                const d = dtParts[0].split('-');
                const t = dtParts[1].split(':');
                const arrivalTime = new Date(d[0], d[1]-1, d[2], t[0], t[1], t[2]);
                
                const diffMs = now - arrivalTime;
                const diffMins = Math.floor(diffMs / 60000);
                
                if(diffMins >= 7) {
                    // تحديث مظهر البطاقة للمتأخر
                    if(!card.classList.contains('delayed-card')) {
                        card.classList.add('delayed-card');
                    }
                    
                    const warningIcon = card.querySelector('.delay-warning-icon');
                    if(warningIcon) {
                        warningIcon.classList.remove('d-none');
                        warningIcon.title = `تأخر (${diffMins} دقيقة)`;
                    }
                    
                    // إظهار إشعار جديد لمرة واحدة عند بلوغ 7 دقائق بالظبط
                    if (diffMins === 7 && !card.dataset.toastShown) {
                        card.dataset.toastShown = 'true';
                        
                        const toastId = 'toast-' + pid + '-' + Date.now();
                        const toastHTML = `
                            <div id="${toastId}" class="toast show align-items-center text-white bg-danger border-0 mb-3 shadow-lg delay-toast" data-patient-id="${pid}" role="alert" aria-live="assertive" aria-atomic="true">
                              <div class="d-flex">
                                <div class="toast-body fw-bold fs-6 pt-3 pb-3">
                                  <i class="fas fa-bell fa-shake me-2 fs-5"></i> المريض <span class="text-warning">${pname}</span> لم يسدد الفاتورة! تجاوز 7 دقائق
                                </div>
                                <button type="button" class="btn-close btn-close-white me-3 m-auto" data-bs-dismiss="toast" aria-label="Close"></button>
                              </div>
                            </div>
                        `;
                        container.insertAdjacentHTML('beforeend', toastHTML);
                        
                        // إخفاء الإشعار بعد 7 ثواني تلقائياً
                        setTimeout(() => {
                            const tEl = document.getElementById(toastId);
                            if(tEl) {
                                tEl.classList.remove('show');
                                setTimeout(() => tEl.remove(), 300);
                            }
                        }, 7000);
                    }
                }
            });
        }, 5000); // يفحص كل 5 ثواني
    });
    </script>
    """ + footer_html
    
    return render_template_string(html, patients_data=patients_data, currency=currency, total_paid_today=total_paid_today)

@billing_bp.route('/billing/history', methods=['GET', 'POST'])
def billing_history():
    if not session.get('user_id') or not can_access('invoices'):
        return redirect(url_for('login.login'))
        
    conn = get_db()
    if not conn:
        return "Database Connection Error"
        
    cursor = conn.cursor(dictionary=True)
    
    # Update current task
    cursor.execute("UPDATE users SET current_task = 'أرشيف وحسابات سابقة' WHERE user_id = %s", (session['user_id'],))
    conn.commit()
    
    search_query = request.form.get('search_query', '').strip() if request.method == 'POST' else ''
    
    sql = """
        SELECT i.invoice_id, i.amount, i.created_at, p.full_name_ar, p.file_number, p.patient_id
        FROM invoices i
        JOIN patients p ON i.patient_id = p.patient_id
        WHERE i.status = 'paid'
    """
    params = []
    if search_query:
        sql += " AND (p.full_name_ar LIKE %s OR p.file_number LIKE %s)"
        params.extend([f'%{search_query}%', f'%{search_query}%'])
        
    sql += " ORDER BY i.created_at DESC LIMIT 50"
    
    cursor.execute(sql, tuple(params))
    invoices = cursor.fetchall()
    
    cursor.execute("SELECT * FROM system_settings")
    prices_res = cursor.fetchall()
    prices = {pr['setting_key']: pr['setting_value'] for pr in prices_res}
    currency = prices.get('currency_label', 'د.ع')
    
    html = header_html + """
    <div class="billing-redesign py-4">
        <div class="mb-5 text-center">
            <h1 class="fw-bold display-6 text-primary"><i class="fas fa-file-invoice-dollar me-2"></i> أرشيف المدفوعات</h1>
            <p class="text-muted">سجل الحسابات السابقة وإعادة طباعة الوصولات</p>
            <a href="{{ url_for('billing.billing') }}" class="btn btn-outline-dark rounded-3 px-4 mt-2">
                <i class="fas fa-arrow-right me-2"></i> العودة لصندوق المحاسبة
            </a>
        </div>
        
        <div class="container mb-4" style="max-width: 900px;">
            <form method="POST" class="d-flex gap-2">
                <input type="text" name="search_query" class="form-control form-control-lg rounded-3 px-4 shadow-sm" placeholder="ابحث باسم المريض أو رقم الملف..." value="{{ search_query }}">
                <button type="submit" class="btn btn-primary rounded-3 px-4 shadow-sm"><i class="fas fa-search me-2"></i> بحث</button>
            </form>
        </div>
        
        <div class="container" style="max-width: 1000px;">
            {% if not invoices %}
                <div class="text-center py-5 glass-card rounded-3 mb-5 mx-auto">
                    <i class="fas fa-search-minus fa-3x text-muted mb-3 opacity-50"></i>
                    <h5 class="fw-bold text-muted">لا توجد فواتير مطابقة</h5>
                </div>
            {% else %}
                <div class="glass-card shadow-sm border-0 rounded-3 overflow-hidden bg-white">
                    <div class="table-responsive">
                    <table class="table table-hover mb-0 align-middle text-center">
                        <thead class="bg-light text-secondary">
                            <tr>
                                <th class="py-3">رقم الوصل</th>
                                <th>اسم المريض</th>
                                <th>رقم الملف</th>
                                <th>تاريخ الدفع</th>
                                <th>المبلغ النهائي</th>
                                <th>إجراء</th>
                            </tr>
                        </thead>
                        <tbody>
                            {% for inv in invoices %}
                            <tr>
                                <td class="fw-bold text-primary">INV-{{ inv.invoice_id }}</td>
                                <td class="fw-bold">{{ inv.full_name_ar }}</td>
                                <td><span class="badge bg-secondary bg-opacity-10 text-dark px-3 py-2 rounded-3">{{ inv.file_number }}</span></td>
                                <td dir="ltr" class="text-muted small">{{ inv.created_at.strftime('%Y-%m-%d %H:%M') if inv.created_at else '' }}</td>
                                <td class="text-success fw-bold fs-5">{{ "{:,.0f}".format(inv.amount) }} <small class="text-muted fw-normal fs-6">{{ currency }}</small></td>
                                <td>
                                    <a href="{{ url_for('billing.print_receipt', invoice_id=inv.invoice_id) }}" target="_blank" class="btn btn-sm btn-primary rounded-3 px-3 shadow-sm">
                                        <i class="fas fa-print me-1"></i> طباعة
                                    </a>
                                </td>
                            </tr>
                            {% endfor %}
                        </tbody>
                    </table>
                    </div>
                </div>
            {% endif %}
        </div>
    </div>
    <style>
        .glass-card { background: #ffffff !important; border: 1px solid rgba(0, 0, 0, 0.1) !important; }
    </style>
    """ + footer_html
    
    return render_template_string(html, invoices=invoices, currency=currency, search_query=search_query)

@billing_bp.route('/billing/print/<int:invoice_id>', methods=['GET'])
def print_receipt(invoice_id):
    if not session.get('user_id'):
        return redirect(url_for('login.login'))
        
    conn = get_db()
    if not conn:
        return "Database Connection Error"
        
    cursor = conn.cursor(dictionary=True)
    
    # Get invoice details
    sql = """
        SELECT i.*, p.full_name_ar, p.file_number, u.full_name_ar as cashier_name
        FROM invoices i
        JOIN patients p ON i.patient_id = p.patient_id
        LEFT JOIN users u ON u.user_id = %s
        WHERE i.invoice_id = %s
    """
    cursor.execute(sql, (session['user_id'], invoice_id))
    inv = cursor.fetchone()
    
    if not inv:
        return "Invoice not found"
        
    cursor.execute("SELECT * FROM system_settings")
    prices_res = cursor.fetchall()
    prices = {pr['setting_key']: pr['setting_value'] for pr in prices_res}
    currency = prices.get('currency_label', 'د.ع')
    
    appt_id = inv.get('appointment_id')
    items = []
    
    if appt_id:
        cursor.execute("SELECT * FROM appointments WHERE appointment_id = %s AND status != 'scheduled'", (appt_id,))
        a = cursor.fetchone()
        if a:
            price_consult = float(prices.get('price_consultation', 25000))
            act_price = 0 if a.get('is_free') else price_consult
            items.append({'name': 'كشف طبي للعيادة', 'price': act_price})
            
        cursor.execute("SELECT test_type as name, price FROM lab_requests WHERE appointment_id = %s AND status != 'pending_payment'", (appt_id,))
        for r in cursor.fetchall():
            items.append({'name': f"مختبر: {r['name']}", 'price': float(r['price'] or 0)})
            
        cursor.execute("SELECT scan_type as name, price FROM radiology_requests WHERE appointment_id = %s AND status != 'pending_payment'", (appt_id,))
        for r in cursor.fetchall():
            items.append({'name': f"أشعة: {r['name']}", 'price': float(r['price'] or 0)})
            
        cursor.execute("SELECT medicine_name as name, price FROM prescriptions WHERE appointment_id = %s AND status != 'pending_payment'", (appt_id,))
        for r in cursor.fetchall():
            items.append({'name': f"صيدلية: {r['name']}", 'price': float(r['price'] or 0)})

    html = """
    <!DOCTYPE html>
    <html dir="rtl" lang="ar">
    <head>
        <meta charset="UTF-8">
        <title>وصل قبض رقم INV-{{ inv.invoice_id }}</title>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.rtl.min.css" rel="stylesheet">
        <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css">
        <style>
            @import url('https://fonts.googleapis.com/css2?family=Tajawal:wght@400;700&display=swap');
            body { font-family: 'Tajawal', sans-serif; background: #e9ecef; }
            
            .receipt-card {
                background: white;
                width: 80mm; /* typical thermal receipt width */
                min-height: auto;
                margin: 20px auto;
                padding: 15px;
                box-shadow: 0 5px 20px rgba(0,0,0,0.1);
                border-radius: 8px;
            }

            @media print {
                body { background: white; margin: 0; padding: 0; }
                .receipt-card { margin: 0; padding: 5px; box-shadow: none; border-radius: 0; width: 100%; border: none; }
                .no-print { display: none !important; }
            }
            .dashed-line { border-top: 1px dashed #999; margin: 12px 0; }
            .item-row { display: flex; justify-content: space-between; margin-bottom: 5px; font-size: 13px; }
            .center-col { text-align: center; }
        </style>
    </head>
    <body>
        <div class="container no-print mt-4 text-center mb-4">
            <button onclick="window.print()" class="btn btn-primary rounded-3 px-4 py-2 shadow-sm me-2">
                <i class="fas fa-print me-2"></i> طباعة الوصل (Thermal)
            </button>
            <button onclick="window.close()" class="btn btn-outline-secondary rounded-3 px-4 py-2">
                <i class="fas fa-times me-2"></i> إغلاق
            </button>
        </div>

        <div class="receipt-card text-dark">
            <div class="text-center mb-2">
                <div class="fs-4 fw-bold">HealthPro <i class="fas fa-plus-square text-danger"></i></div>
                <div class="small text-muted">الوصل المالي الموحد</div>
            </div>
            
            <div class="dashed-line"></div>
            
            <div class="mb-2" style="font-size: 13px;">
                <div class="item-row"><span>رقم الوصل:</span> <span class="fw-bold">INV-{{ inv.invoice_id }}</span></div>
                <div class="item-row"><span>التاريخ:</span> <span dir="ltr">{{ inv.created_at.strftime('%Y-%m-%d %H:%M') if inv.created_at else '' }}</span></div>
                <div class="item-row"><span>اسم المراجع:</span> <span class="fw-bold">{{ inv.full_name_ar }}</span></div>
                <div class="item-row"><span>رقم الملف:</span> <span>{{ inv.file_number }}</span></div>
            </div>

            <div class="dashed-line"></div>
            
            <div style="font-size: 13px;" class="mb-2">
                <div class="fw-bold text-center mb-2 bg-light py-1 rounded">التفاصيل</div>
                {% if items %}
                    {% for item in items %}
                    <div class="item-row">
                        <span style="max-width: 70%;">{{ item.name }}</span>
                        <span class="fw-bold">{{ "{:,.0f}".format(item.price) }}</span>
                    </div>
                    {% endfor %}
                {% else %}
                    <div class="text-center text-muted small py-2">دفعة مسددة مسبقاً</div>
                {% endif %}
            </div>

            <div class="dashed-line" style="border-top-width: 2px;"></div>
            
            <div class="d-flex justify-content-between align-items-center mb-2 bg-light p-2 rounded">
                <span class="fw-bold">المبلغ المسدد:</span>
                <span class="fw-bold fs-5">{{ "{:,.0f}".format(inv.amount) }} <small class="fs-6">{{ currency }}</small></span>
            </div>

            <div class="dashed-line"></div>
            
            <div class="text-center mt-2" style="font-size: 11px; color:#555;">
                أمين الصندوق: {{ inv.cashier_name }}<br>
                نتمنى لكم دوام الصحة والعافية
            </div>
            
            <div class="text-center mt-3">
                <canvas id="barcode"></canvas>
            </div>
        </div>

        <script src="https://cdn.jsdelivr.net/npm/jsbarcode@3.11.5/dist/JsBarcode.all.min.js"></script>
        <script>
            JsBarcode("#barcode", "INV-{{ inv.invoice_id }}", {
                format: "CODE128",
                width: 1.2,
                height: 35,
                displayValue: true,
                fontSize: 10,
                margin: 0
            });
            // window.print();
        </script>
    </body>
    </html>
    """
    return render_template_string(html, inv=inv, currency=currency, items=items)

@billing_bp.route('/billing/statement', methods=['GET', 'POST'])
def patient_statement():
    if not session.get('user_id') or not can_access('invoices'):
        return redirect(url_for('login.login'))
        
    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    
    search_query = request.form.get('search_query', '').strip() if request.method == 'POST' else ''
    
    patients = []
    selected_patient = None
    statement_data = []
    totals = {'paid': 0.0, 'unpaid': 0.0, 'total': 0.0}
    
    cursor.execute("SELECT * FROM system_settings")
    prices_res = cursor.fetchall()
    prices = {pr['setting_key']: pr['setting_value'] for pr in prices_res}
    currency = prices.get('currency_label', 'د.ع')
    
    if search_query:
        # Search for patients
        cursor.execute("SELECT patient_id, full_name_ar, file_number FROM patients WHERE full_name_ar LIKE %s OR file_number LIKE %s LIMIT 10", (f'%{search_query}%', f'%{search_query}%'))
        patients = cursor.fetchall()
        
        # If a single match or specific request, show their statement
        patient_id = request.form.get('patient_id')
        if not patient_id and len(patients) == 1:
            patient_id = patients[0]['patient_id']
            
        if patient_id:
            cursor.execute("SELECT * FROM patients WHERE patient_id = %s", (patient_id,))
            selected_patient = cursor.fetchone()
            
            if selected_patient:
                # Get paid invoices
                cursor.execute("SELECT invoice_id, amount, created_at, 'paid' as status FROM invoices WHERE patient_id = %s AND status = 'paid' ORDER BY created_at DESC", (patient_id,))
                statement_data.extend(cursor.fetchall())
                
                # Calculate unpaid services (simple estimation for statement overview)
                cursor.execute("SELECT appointment_id, appointment_date FROM appointments WHERE patient_id = %s AND status = 'scheduled'", (patient_id,))
                for a in cursor.fetchall():
                    statement_data.append({'invoice_id': '-', 'amount': float(prices.get('price_consultation', 25000)), 'created_at': a['appointment_date'], 'status': 'unpaid', 'type': 'كشف طبي'})
                
                # Calculate totals
                for item in statement_data:
                    amt = float(item['amount'] or 0)
                    totals['total'] += amt
                    if item['status'] == 'paid':
                        totals['paid'] += amt
                    else:
                        totals['unpaid'] += amt

    html = header_html + """
    <div class="billing-redesign py-4">
        <div class="mb-5 text-center">
            <h1 class="fw-bold display-6 text-info"><i class="fas fa-file-invoice-dollar me-2"></i> كشف حساب مريض</h1>
            <p class="text-muted">متابعة الحركات المالية، المبالغ المسددة والمتبقية لكل مراجع</p>
            <a href="{{ url_for('billing.billing') }}" class="btn btn-outline-dark rounded-3 px-4 mt-2">
                <i class="fas fa-arrow-right me-2"></i> العودة لصندوق المحاسبة
            </a>
        </div>
        
        <div class="container mb-4" style="max-width: 900px;">
            <div class="glass-card p-4 rounded-3 shadow-sm mb-4 bg-white">
                <form method="POST" class="d-flex gap-2">
                    <input type="text" name="search_query" class="form-control form-control-lg rounded-3 px-4 shadow-sm" placeholder="ابحث باسم المريض أو رقم الملف لاستخراج كشف الحساب..." value="{{ search_query }}">
                    <button type="submit" class="btn btn-info text-white rounded-3 px-4 shadow-sm"><i class="fas fa-search me-2"></i> بحث</button>
                </form>
            </div>
            
            {% if patients and not selected_patient %}
                <div class="glass-card shadow-sm border-0 rounded-3 overflow-hidden bg-white mb-4">
                    <h5 class="bg-light p-3 mb-0 fw-bold border-bottom">اختر المريض المطلوب</h5>
                    <div class="list-group list-group-flush">
                    {% for p in patients %}
                        <form method="POST" class="list-group-item list-group-item-action d-flex justify-content-between align-items-center p-3">
                            <input type="hidden" name="search_query" value="{{ search_query }}">
                            <input type="hidden" name="patient_id" value="{{ p.patient_id }}">
                            <div>
                                <h6 class="fw-bold mb-1">{{ p.full_name_ar }}</h6>
                                <span class="badge bg-secondary bg-opacity-10 text-dark rounded-3">ملف: {{ p.file_number }}</span>
                            </div>
                            <button type="submit" class="btn btn-sm btn-outline-info rounded-3 px-3">عرض الكشف <i class="fas fa-chevron-left ms-1"></i></button>
                        </form>
                    {% endfor %}
                    </div>
                </div>
            {% endif %}

            {% if selected_patient %}
                <div class="row g-4 mb-4">
                    <div class="col-md-4">
                        <div class="glass-card p-4 rounded-3 text-center bg-white h-100 border-start border-warning border-5">
                            <div class="text-muted small mb-2 fw-bold">إجمالي المطالبات</div>
                            <h3 class="fw-bold text-dark">{{ "{:,.0f}".format(totals.total) }} <small class="fs-6 text-muted">{{ currency }}</small></h3>
                        </div>
                    </div>
                    <div class="col-md-4">
                        <div class="glass-card p-4 rounded-3 text-center bg-white h-100 border-start border-success border-5">
                            <div class="text-muted small mb-2 fw-bold">إجمالي المسدد</div>
                            <h3 class="fw-bold text-success">{{ "{:,.0f}".format(totals.paid) }} <small class="fs-6 text-muted">{{ currency }}</small></h3>
                        </div>
                    </div>
                    <div class="col-md-4">
                        <div class="glass-card p-4 rounded-3 text-center bg-white h-100 border-start border-danger border-5">
                            <div class="text-muted small mb-2 fw-bold">المتبقي (غير مسدد)</div>
                            <h3 class="fw-bold text-danger">{{ "{:,.0f}".format(totals.unpaid) }} <small class="fs-6 text-muted">{{ currency }}</small></h3>
                        </div>
                    </div>
                </div>
                
                <div class="glass-card shadow-sm border-0 rounded-3 overflow-hidden bg-white" id="statementPrintArea">
                    <div class="p-4 border-bottom bg-light d-flex justify-content-between align-items-center">
                        <div>
                            <h5 class="fw-bold text-dark mb-1">كشف حساب: {{ selected_patient.full_name_ar }}</h5>
                            <span class="text-muted small">رقم الملف: {{ selected_patient.file_number }}</span>
                        </div>
                        <button onclick="window.print()" class="btn btn-primary rounded-3 px-4 shadow-sm no-print">
                            <i class="fas fa-print me-2"></i> طباعة الكشف
                        </button>
                    </div>
                    
                    <div class="table-responsive">
                    <table class="table table-hover mb-0 align-middle text-center">
                        <thead class="bg-white text-secondary">
                            <tr>
                                <th class="py-3">التاريخ</th>
                                <th>رقم الحركة/الوصل</th>
                                <th>البيان</th>
                                <th>المبلغ</th>
                                <th>الحالة</th>
                            </tr>
                        </thead>
                        <tbody>
                            {% if statement_data %}
                                {% for item in statement_data %}
                                <tr>
                                    <td dir="ltr" class="text-muted small">{{ item.created_at.strftime('%Y-%m-%d %H:%M') if (item.created_at and not item.created_at is string) else item.created_at }}</td>
                                    <td class="fw-bold text-primary">{{ item.invoice_id if item.invoice_id != '-' else '-' }}</td>
                                    <td>{{ item.type if item.get('type') else 'دفعة نقدية مسددة' }}</td>
                                    <td class="fw-bold">{{ "{:,.0f}".format(item.amount) }}</td>
                                    <td>
                                        {% if item.status == 'paid' %}
                                            <span class="badge bg-success bg-opacity-10 text-success px-3 py-2 rounded-3"><i class="fas fa-check-circle me-1"></i> مسدد</span>
                                        {% else %}
                                            <span class="badge bg-danger bg-opacity-10 text-danger px-3 py-2 rounded-3"><i class="fas fa-times-circle me-1"></i> غير مسدد</span>
                                        {% endif %}
                                    </td>
                                </tr>
                                {% endfor %}
                            {% else %}
                                <tr><td colspan="5" class="py-4 text-muted">لا توجد حركات مالية مسجلة لهذا المريض</td></tr>
                            {% endif %}
                        </tbody>
                    </table>
                    </div>
                </div>
            {% endif %}
        </div>
    </div>
    <style>
        .glass-card { background: #ffffff !important; border: 1px solid rgba(0, 0, 0, 0.1) !important; }
        @media print {
            body * { visibility: hidden; }
            #statementPrintArea, #statementPrintArea * { visibility: visible; }
            #statementPrintArea { position: absolute; left: 0; top: 0; width: 100%; box-shadow: none !important; border: none !important; }
            .no-print { display: none !important; }
        }
    </style>
    """ + footer_html
    
    return render_template_string(html, search_query=search_query, patients=patients, selected_patient=selected_patient, statement_data=statement_data, totals=totals, currency=currency)
