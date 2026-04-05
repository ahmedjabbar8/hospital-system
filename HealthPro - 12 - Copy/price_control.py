from flask import Blueprint, session, redirect, url_for, request, flash, render_template_string
from config import get_db
from header import header_html
from footer import footer_html

price_control_bp = Blueprint('price_control', __name__)

@price_control_bp.route('/price_control', methods=['GET', 'POST'])
def price_control():
    if not session.get('user_id') or session.get('role') != 'admin':
        return redirect(url_for('login.login'))
        
    conn = get_db()
    if not conn:
        return "Database Error"
        
    cursor = conn.cursor(dictionary=True)
    
    if request.method == 'POST' and 'update_prices' in request.form:
        for key, value in request.form.items():
            if key.startswith('settings['):
                # Extra settings[key]
                clean_key = key[9:-1] # Remove 'settings[' and ']'
                cursor.execute("UPDATE system_settings SET setting_value = %s WHERE setting_key = %s", (value, clean_key))
                
        conn.commit()
        flash("تم تحديث الأسعار وإعدادات العملة بنجاح", "success")
        conn.close()
        return redirect(url_for('price_control.price_control'))

    cursor.execute("SELECT * FROM system_settings")
    settings_res = cursor.fetchall()
    sys_settings = {row['setting_key']: row['setting_value'] for row in settings_res}
    
    conn.close()

    html = header_html + """
    <div class="container py-4">
        <div class="row justify-content-center">
            <div class="col-md-8">
                <div class="apple-card p-4">
                    <div class="d-flex justify-content-between align-items-center mb-4 border-bottom pb-3">
                        <h4 class="fw-bold mb-0 text-primary"><i class="fas fa-tags me-2"></i> مركز التحكم في الأسعار
                            والعملة</h4>
                        <a href="{{ url_for('settings.view_settings') }}" class="btn btn-light btn-sm rounded-pill px-3">رجوع للإعدادات</a>
                    </div>

                    <form method="POST">
                        <div class="row g-4">
                            <!-- Currency Section -->
                            <div class="col-12">
                                <h6 class="fw-bold text-muted mb-3">إعدادات العملة</h6>
                                <div class="p-3 bg-light rounded-4 border">
                                    <label class="form-label small fw-bold">رمز العملة (مثلاً: د.ع، IQD، $)</label>
                                    <input type="text" name="settings[currency_label]" class="form-control"
                                        value="{{ sys_settings.currency_label if sys_settings.currency_label else 'د.ع' }}"
                                        required>
                                </div>
                            </div>

                            <!-- System Prices -->
                            <div class="col-12">
                                <h6 class="fw-bold text-muted mb-3">الأسعار الافتراضية للخدمات</h6>
                                <div class="row g-3">
                                    <div class="col-md-6">
                                        <div class="p-3 border rounded-4">
                                            <label class="form-label small fw-bold">سعر الكشفية (Consultation)</label>
                                            <div class="input-group">
                                                <input type="number" name="settings[price_consultation]"
                                                    class="form-control"
                                                    value="{{ sys_settings.price_consultation if sys_settings.price_consultation else 25000 }}"
                                                    required>
                                                <span class="input-group-text bg-white">
                                                    {{ sys_settings.currency_label if sys_settings.currency_label else 'د.ع' }}
                                                </span>
                                            </div>
                                        </div>
                                    </div>
                                    <div class="col-md-6">
                                        <div class="p-3 border rounded-4">
                                            <label class="form-label small fw-bold">سعر التحليل الافتراضي (Lab)</label>
                                            <div class="input-group">
                                                <input type="number" name="settings[price_lab_default]" class="form-control"
                                                    value="{{ sys_settings.price_lab_default if sys_settings.price_lab_default else 15000 }}"
                                                    required>
                                                <span class="input-group-text bg-white">
                                                    {{ sys_settings.currency_label if sys_settings.currency_label else 'د.ع' }}
                                                </span>
                                            </div>
                                        </div>
                                    </div>
                                    <div class="col-md-6">
                                        <div class="p-3 border rounded-4">
                                            <label class="form-label small fw-bold">سعر الأشعة الافتراضي (Radiology)</label>
                                            <div class="input-group">
                                                <input type="number" name="settings[price_rad_default]" class="form-control"
                                                    value="{{ sys_settings.price_rad_default if sys_settings.price_rad_default else 30000 }}"
                                                    required>
                                                <span class="input-group-text bg-white">
                                                    {{ sys_settings.currency_label if sys_settings.currency_label else 'د.ع' }}
                                                </span>
                                            </div>
                                        </div>
                                    </div>
                                    <div class="col-md-6">
                                        <div class="p-3 border rounded-4">
                                            <label class="form-label small fw-bold">سعر العلاج/الوصفة (Prescription)</label>
                                            <div class="input-group">
                                                <input type="number" name="settings[price_rx_default]" class="form-control"
                                                    value="{{ sys_settings.price_rx_default if sys_settings.price_rx_default else 5000 }}"
                                                    required>
                                                <span class="input-group-text bg-white">
                                                    {{ sys_settings.currency_label if sys_settings.currency_label else 'د.ع' }}
                                                </span>
                                            </div>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </div>

                        <div class="d-grid mt-5">
                            <button type="submit" name="update_prices" value="1"
                                class="btn btn-primary fw-bold py-3 rounded-pill shadow-sm">
                                <i class="fas fa-check-circle me-2"></i> حفظ كافة الإعدادات المالية
                            </button>
                        </div>
                    </form>
                </div>
            </div>
        </div>
    </div>
    """ + footer_html
    
    return render_template_string(html, sys_settings=sys_settings)
