import json
from werkzeug.security import generate_password_hash
from flask import Blueprint, session, redirect, url_for, request, flash, render_template_string
from config import get_db, can_access
from header import header_html
from footer import footer_html

manage_staff_bp = Blueprint('manage_staff', __name__)

@manage_staff_bp.route('/manage_staff', methods=['GET', 'POST'])
def manage_staff():
    # --- Security Check ---
    if not session.get('user_id') or session.get('role') != 'admin':
        return redirect(url_for('login.login'))
        
    conn = get_db()
    if not conn:
        return "Database Connection Error"
        
    cursor = conn.cursor(dictionary=True)
    
    # Ensure columns
    try:
        cursor.execute("ALTER TABLE users MODIFY COLUMN permissions TEXT")
        cursor.execute("SHOW COLUMNS FROM users LIKE 'department_id'")
        if not cursor.fetchone():
            cursor.execute("ALTER TABLE users ADD department_id INT DEFAULT 0")
        conn.commit()
    except Exception:
        pass # Ignore errors if columns already exist or syntax unsupported

    # --- Submit Logic & Delete Logic ---
    if request.method == 'POST':
        if 'save_employee' in request.form:
            uid = int(request.form.get('user_id') or 0)
            user = request.form.get('username', '')
            name = request.form.get('full_name', '')
            role = request.form.get('role', 'reception')
            dept = int(request.form.get('department_id', 0))
            
            permissions = request.form.getlist('permissions[]')
            perms = json.dumps(permissions) if permissions else '[]'
            
            pwd = request.form.get('password', '')

            if uid > 0:
                sql = "UPDATE users SET username=%s, full_name_ar=%s, role=%s, department_id=%s, permissions=%s WHERE user_id=%s"
                cursor.execute(sql, (user, name, role, dept, perms, uid))
                if pwd:
                    hashed = generate_password_hash(pwd)
                    cursor.execute("UPDATE users SET password_hash=%s WHERE user_id=%s", (hashed, uid))
                flash("تم تحديث بيانات الموظف بنجاح", "success")
            else:
                hashed = generate_password_hash(pwd) if pwd else generate_password_hash('123456') # Default pass
                sql = "INSERT INTO users (username, password_hash, full_name_ar, role, department_id, permissions) VALUES (%s, %s, %s, %s, %s, %s)"
                cursor.execute(sql, (user, hashed, name, role, dept, perms))
                flash("تم إضافة الموظف بنجاح", "success")
                
            conn.commit()
            conn.close()
            return redirect(url_for('manage_staff.manage_staff'))
            
    # Delete User
    del_user_id = request.args.get('del_user')
    if del_user_id:
        if int(del_user_id) != session.get('user_id'):
            cursor.execute("DELETE FROM users WHERE user_id = %s", (del_user_id,))
            conn.commit()
            flash("تم حذف الموظف بنجاح", "success")
        else:
            flash("لا يمكنك حذف حسابك الخاص", "danger")
        conn.close()
        return redirect(url_for('manage_staff.manage_staff'))
            
    # Fetch Data
    cursor.execute("""
        SELECT u.*, d.department_name_ar 
        FROM users u 
        LEFT JOIN departments d ON u.department_id = d.department_id 
        ORDER BY user_id DESC
    """)
    users = cursor.fetchall()
    conn.close()

    html = header_html + """
    <div class="container-fluid py-5 px-lg-5 solid-mode" style="min-height: 80vh;">
        <!-- Header -->
        <div class="d-flex justify-content-between align-items-center mb-5 animate__animated animate__fadeInDown">
            <div class="d-flex align-items-center gap-3">
                <div class="bg-primary text-white d-flex align-items-center justify-content-center rounded-3 shadow-sm" style="width: 50px; height: 50px;">
                    <i class="fas fa-users-cog fa-lg"></i>
                </div>
                <div>
                    <h3 class="fw-bold mb-0 text-dark">إدارة الموظفين (الموارد البشرية)</h3>
                    <p class="text-muted small mb-0">إدارة الحسابات، الصلاحيات، وهيكلية الأقسام</p>
                </div>
            </div>
            <a href="{{ url_for('manage_staff.add_employee') }}" class="btn btn-primary fw-bold px-4 py-2 rounded-pill shadow-sm d-flex align-items-center gap-2">
                <i class="fas fa-user-plus"></i> إضافة موظف جديد
            </a>
        </div>
        
        {% with messages = get_flashed_messages(with_categories=true) %}
            {% if messages %}
                <div class="mb-4">
                {% for category, message in messages %}
                    <div class="alert alert-{{ category }} alert-dismissible fade show border-0 shadow-sm rounded-3">
                        <i class="fas fa-check-circle me-2"></i> {{ message }}
                        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
                    </div>
                {% endfor %}
                </div>
            {% endif %}
        {% endwith %}

        <!-- Staff List (Clean Table) -->
        <div class="card border-0 shadow-sm rounded-4 overflow-hidden animate__animated animate__fadeInUp">
            <div class="table-responsive">
                <table class="table table-hover align-middle mb-0 border-0">
                    <thead class="bg-light">
                        <tr>
                            <th class="ps-4 py-3 text-muted small fw-bold text-uppercase border-0">اسم الموظف / القسم</th>
                            <th class="py-3 text-muted small fw-bold text-uppercase border-0">اسم الدخول (Username)</th>
                            <th class="text-center py-3 text-muted small fw-bold text-uppercase border-0">الدور الوظيفي</th>
                            <th class="pe-4 text-center py-3 text-muted small fw-bold text-uppercase border-0">الإجراءات</th>
                        </tr>
                    </thead>
                    <tbody class="border-top-0">
                        {% for u in users %}
                        <tr>
                            <td class="ps-4 py-3">
                                <div class="d-flex align-items-center gap-3">
                                    <div class="bg-primary bg-opacity-10 text-primary rounded-circle d-flex align-items-center justify-content-center" style="width: 45px; height: 45px;">
                                        <i class="fas fa-user-tie"></i>
                                    </div>
                                    <div>
                                        <h6 class="fw-bold mb-1 text-dark">{{ u.full_name_ar if u.full_name_ar else u.username }}</h6>
                                        <p class="text-muted small mb-0"><i class="fas fa-building ms-1"></i> {{ u.department_name_ar if u.department_name_ar else 'القسم العام' }}</p>
                                    </div>
                                </div>
                            </td>
                            <td class="py-3">
                                <span class="bg-light text-dark px-3 py-1 rounded-pill fw-bold" style="font-family: monospace; letter-spacing: 0.5px;">{{ u.username }}</span>
                            </td>
                            <td class="text-center py-3">
                                {% if u.role == 'admin' %}
                                    <span class="badge bg-danger bg-opacity-10 text-danger rounded-pill px-3 py-2 fw-bold w-75">مدير النظام</span>
                                {% elif u.role == 'doctor' %}
                                    <span class="badge bg-success bg-opacity-10 text-success rounded-pill px-3 py-2 fw-bold w-75">طبيب</span>
                                {% elif u.role == 'reception' %}
                                    <span class="badge bg-primary bg-opacity-10 text-primary rounded-pill px-3 py-2 fw-bold w-75">استقبال</span>
                                {% else %}
                                    <span class="badge bg-secondary bg-opacity-10 text-secondary rounded-pill px-3 py-2 fw-bold w-75">{{ u.role }}</span>
                                {% endif %}
                            </td>
                            <td class="pe-4 text-center py-3">
                                <a href="{{ url_for('manage_staff.edit_employee', uid=u.user_id) }}" class="btn btn-sm btn-light border rounded-circle shadow-sm" style="width: 38px; height: 38px; display: inline-flex; align-items: center; justify-content: center; transition: 0.3s;" title="تعديل">
                                    <i class="fas fa-pen text-primary"></i>
                                </a>
                                {% if u.user_id != session['user_id'] %}
                                <a href="?del_user={{ u.user_id }}" class="btn btn-sm btn-light border rounded-circle shadow-sm ms-2" style="width: 38px; height: 38px; display: inline-flex; align-items: center; justify-content: center; transition: 0.3s;" onclick="return confirm('هل أنت متأكد من حذف هذا الموظف نهائياً؟');" title="حذف">
                                    <i class="fas fa-trash text-danger"></i>
                                </a>
                                {% endif %}
                            </td>
                        </tr>
                        {% else %}
                        <tr>
                            <td colspan="4" class="text-center text-muted py-5">لا يوجد موظفين حالياً.</td>
                        </tr>
                        {% endfor %}
                    </tbody>
                </table>
            </div>
        </div>
    </div>
    """ + footer_html
    return render_template_string(html, users=users)

@manage_staff_bp.route('/add_employee', methods=['GET', 'POST'])
def add_employee():
    if not session.get('user_id') or session.get('role') != 'admin':
        return redirect(url_for('login.login'))

    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    
    mods = {
        'registration': 'الاستقبال (Registration)', 
        'triage': 'الفحص الحيوي (Triage)', 
        'doctor': 'العيادة (Clinic)', 
        'lab': 'المختبر (Lab)', 
        'nursing': 'سحب العينات (Nursing Lab)',
        'radiology': 'الأشعة (Radiology)', 
        'pharmacy': 'الصيدلية (Pharmacy)', 
        'invoices': 'الحسابات (Billing)', 
        'settings': 'إعدادات النظام (Settings)'
    }

    if request.method == 'POST':
        user = request.form.get('username', '')
        name = request.form.get('full_name', '')
        role = request.form.get('role', 'reception')
        dept = int(request.form.get('department_id', 0))
        pwd = request.form.get('password', '')
        
        permissions = request.form.getlist('permissions[]')
        perms = json.dumps(permissions) if permissions else '[]'
        
        cursor.execute("SELECT user_id FROM users WHERE username = %s", (user,))
        if cursor.fetchone():
            flash("خطأ: اسم المستخدم موجود مسبقاً بجهاز آخر، الرجاء اختيار اسم مختلف.", "danger")
        else:
            # Secure Password Hashing
            hashed = generate_password_hash(pwd) if pwd else generate_password_hash('123456')
            # Generate a unique dummy email since it is required by the schema
            email = f"{user}@healthpro.local"
            sql = "INSERT INTO users (username, password_hash, email, full_name_ar, role, department_id, permissions) VALUES (%s, %s, %s, %s, %s, %s, %s)"
            cursor.execute(sql, (user, hashed, email, name, role, dept, perms))
            conn.commit()
            flash("تم إضافة الموظف بنجاح (مخزن بشكل آمن ومشفّر في قاعدة البيانات).", "success")
            conn.close()
            return redirect(url_for('manage_staff.manage_staff'))

    cursor.execute("SELECT * FROM departments")
    departments = cursor.fetchall()
    conn.close()

    html = header_html + """
    <div class="container py-5 solid-mode" style="min-height: 85vh;">
        <div class="row justify-content-center">
            <div class="col-lg-10">
                <div class="d-flex justify-content-between align-items-center mb-4">
                    <h3 class="fw-bold text-dark mb-0"><i class="fas fa-user-shield text-primary me-2"></i> إضافة موظف جديد</h3>
                    <a href="{{ url_for('manage_staff.manage_staff') }}" class="btn btn-light border shadow-sm rounded-pill fw-bold text-muted px-4">عودة للقائمة <i class="fas fa-undo ms-2"></i></a>
                </div>

                <div class="card border-0 shadow-sm rounded-4 bg-white overflow-hidden p-0 animate__animated animate__fadeInUp">
                    <div class="card-header bg-primary bg-opacity-10 border-0 py-3">
                        <strong class="text-primary"><i class="fas fa-lock me-1"></i> يتم تشفير كلمة المرور وتخزين البيانات بمعايير أمنية داخل قاعدة البيانات</strong>
                    </div>
                    <div class="card-body p-5">
                        <form method="POST">
                            <h5 class="fw-bold border-bottom pb-2 mb-4 text-dark">المعلومات الأساسية</h5>
                            <div class="row g-4 mb-5">
                                <div class="col-md-6">
                                    <label class="form-label fw-bold small text-muted">الاسم الكامل (الوظيفي)</label>
                                    <input type="text" name="full_name" class="form-control form-control-lg bg-light border-0 rounded-3" placeholder="مثال: د. أحمد محمد" required>
                                </div>
                                <div class="col-md-6">
                                    <label class="form-label fw-bold small text-muted">اسم الدخول (Username)</label>
                                    <input type="text" name="username" class="form-control form-control-lg bg-light border-0 rounded-3 text-start" dir="ltr" placeholder="example: ahmed123" required>
                                </div>
                                <div class="col-md-6">
                                    <label class="form-label fw-bold small text-muted">كلمة المرور المشفرة</label>
                                    <input type="password" name="password" class="form-control form-control-lg bg-light border-0 rounded-3" placeholder="أدخل كلمة مرور قوية" required>
                                </div>
                                <div class="col-md-6">
                                    <div class="row g-2">
                                        <div class="col-6">
                                            <label class="form-label fw-bold small text-muted">الدور الرئيسي</label>
                                            <select name="role" class="form-select form-control-lg bg-light border-0 rounded-3">
                                                <option value="doctor">طبيب صلوحي</option>
                                                <option value="nurse">ممرض / مساعد طبي</option>
                                                <option value="lab_tech">فني مختبر / ساحب عينات</option>
                                                <option value="reception" selected>موظف استقبال</option>
                                                <option value="admin">مدير نظام</option>
                                            </select>
                                        </div>
                                        <div class="col-6">
                                            <label class="form-label fw-bold small text-muted">ينتمي إلى قسم</label>
                                            <select name="department_id" class="form-select form-control-lg bg-light border-0 rounded-3">
                                                <option value="0">عام / الإدارة</option>
                                                {% for d in departments %}
                                                    <option value="{{ d.department_id }}">{{ d.department_name_ar }}</option>
                                                {% endfor %}
                                            </select>
                                        </div>
                                    </div>
                                </div>
                            </div>

                            <h5 class="fw-bold border-bottom pb-2 mb-4 text-dark">صلاحيات الوصول (Permissions)</h5>
                            <div class="row row-cols-1 row-cols-md-2 row-cols-lg-4 g-3 mb-5 text-center">
                                {% for k, v in mods.items() %}
                                    <div class="col">
                                        <input type="checkbox" name="permissions[]" value="{{ k }}" id="p_{{ k }}" class="btn-check">
                                        <label class="btn btn-outline-primary w-100 py-3 rounded-3 border fw-bold d-flex flex-column align-items-center justify-content-center gap-2" for="p_{{ k }}" style="transition: 0.2s;">
                                            {{ v }}
                                        </label>
                                    </div>
                                {% endfor %}
                            </div>

                            <hr class="mb-4" style="opacity: 0.1;">
                            
                            <div class="d-flex justify-content-end gap-3">
                                <a href="{{ url_for('manage_staff.manage_staff') }}" class="btn btn-light text-muted px-5 py-3 rounded-pill fw-bold">إلغاء</a>
                                <button type="submit" class="btn btn-primary px-5 py-3 rounded-pill shadow-sm fw-bold">
                                    <i class="fas fa-save me-2"></i> حفظ الموظف الجديد بقاعدة البيانات
                                </button>
                            </div>
                        </form>
                    </div>
                </div>
            </div>
        </div>
    </div>
    """ + footer_html
    return render_template_string(html, departments=departments, mods=mods)

@manage_staff_bp.route('/edit_employee/<int:uid>', methods=['GET', 'POST'])
def edit_employee(uid):
    if not session.get('user_id') or session.get('role') != 'admin':
        return redirect(url_for('login.login'))

    conn = get_db()
    cursor = conn.cursor(dictionary=True)
    
    mods = {
        'registration': 'الاستقبال (Registration)', 
        'triage': 'الفحص الحيوي (Triage)', 
        'doctor': 'العيادة (Clinic)', 
        'lab': 'المختبر (Lab)', 
        'nursing': 'سحب العينات (Nursing Lab)',
        'radiology': 'الأشعة (Radiology)', 
        'pharmacy': 'الصيدلية (Pharmacy)', 
        'invoices': 'الحسابات (Billing)', 
        'settings': 'إعدادات النظام (Settings)'
    }

    if request.method == 'POST':
        user = request.form.get('username', '')
        name = request.form.get('full_name', '')
        role = request.form.get('role', 'reception')
        dept = int(request.form.get('department_id', 0))
        pwd = request.form.get('password', '')
        
        permissions = request.form.getlist('permissions[]')
        perms = json.dumps(permissions) if permissions else '[]'
        
        # Ensure username isn't taken by another user
        cursor.execute("SELECT user_id FROM users WHERE username = %s AND user_id != %s", (user, uid))
        if cursor.fetchone():
            flash("خطأ: اسم المستخدم موجود مسبقاً، يرجى تغييره.", "danger")
        else:
            sql = "UPDATE users SET username=%s, full_name_ar=%s, role=%s, department_id=%s, permissions=%s WHERE user_id=%s"
            cursor.execute(sql, (user, name, role, dept, perms, uid))
            if pwd:
                hashed = generate_password_hash(pwd)
                cursor.execute("UPDATE users SET password_hash=%s WHERE user_id=%s", (hashed, uid))
            
            conn.commit()
            flash("تم تحديث وحفظ بيانات الموظف والصلاحيات بنجاح.", "success")
            conn.close()
            return redirect(url_for('manage_staff.manage_staff'))

    cursor.execute("SELECT * FROM users WHERE user_id = %s", (uid,))
    employee = cursor.fetchone()
    if not employee:
        conn.close()
        return redirect(url_for('manage_staff.manage_staff'))

    cursor.execute("SELECT * FROM departments")
    departments = cursor.fetchall()
    conn.close()

    emp_perms = []
    if employee['permissions']:
        try:
            emp_perms = json.loads(employee['permissions'])
        except:
            emp_perms = []

    html = header_html + """
    <div class="container py-5 solid-mode" style="min-height: 85vh;">
        <div class="row justify-content-center">
            <div class="col-lg-10">
                <div class="d-flex justify-content-between align-items-center mb-4">
                    <h3 class="fw-bold text-dark mb-0"><i class="fas fa-user-edit text-primary me-2"></i> تعديل بيانات الموظف</h3>
                    <a href="{{ url_for('manage_staff.manage_staff') }}" class="btn btn-light border shadow-sm rounded-pill fw-bold text-muted px-4">عودة للقائمة <i class="fas fa-undo ms-2"></i></a>
                </div>

                <div class="card border-0 shadow-sm rounded-4 bg-white p-5 animate__animated animate__fadeInUp">
                    <form method="POST">
                        <h5 class="fw-bold border-bottom pb-2 mb-4 text-dark">المعلومات الأساسية</h5>
                        <div class="row g-4 mb-5">
                            <div class="col-md-6">
                                <label class="form-label fw-bold small text-muted">الاسم الكامل</label>
                                <input type="text" name="full_name" class="form-control form-control-lg bg-light border-0 rounded-3" value="{{ emp.full_name_ar }}" required>
                            </div>
                            <div class="col-md-6">
                                <label class="form-label fw-bold small text-muted">اسم الدخول (Username)</label>
                                <input type="text" name="username" class="form-control form-control-lg bg-light border-0 rounded-3 text-start" dir="ltr" value="{{ emp.username }}" required>
                            </div>
                            <div class="col-md-6">
                                <label class="form-label fw-bold small text-muted">كلمة المرور الجديدة</label>
                                <input type="password" name="password" class="form-control form-control-lg bg-light border-0 rounded-3" placeholder="اتركه فارغاً للاحتفاظ بكلمة المرور السابقة">
                            </div>
                            <div class="col-md-6">
                                <div class="row g-2">
                                    <div class="col-6">
                                        <label class="form-label fw-bold small text-muted">الدور الرئيسي</label>
                                        <select name="role" class="form-select form-control-lg bg-light border-0 rounded-3">
                                            <option value="doctor" {% if emp.role == 'doctor' %}selected{% endif %}>طبيب</option>
                                            <option value="nurse" {% if emp.role == 'nurse' %}selected{% endif %}>ممرض / مساعد طبي</option>
                                            <option value="lab_tech" {% if emp.role == 'lab_tech' %}selected{% endif %}>فني مختبر / ساحب عينات</option>
                                            <option value="reception" {% if emp.role == 'reception' %}selected{% endif %}>موظف استقبال</option>
                                            <option value="admin" {% if emp.role == 'admin' %}selected{% endif %}>مدير نظام</option>
                                        </select>
                                    </div>
                                    <div class="col-6">
                                        <label class="form-label fw-bold small text-muted">القسم</label>
                                        <select name="department_id" class="form-select form-control-lg bg-light border-0 rounded-3">
                                            <option value="0">عام / الإدارة</option>
                                            {% for d in departments %}
                                                <option value="{{ d.department_id }}" {% if emp.department_id == d.department_id %}selected{% endif %}>{{ d.department_name_ar }}</option>
                                            {% endfor %}
                                        </select>
                                    </div>
                                </div>
                            </div>
                        </div>

                        <h5 class="fw-bold border-bottom pb-2 mb-4 text-dark">صلاحيات الوصول (Permissions)</h5>
                        <div class="row row-cols-1 row-cols-md-2 row-cols-lg-4 g-3 mb-5 text-center">
                            {% for k, v in mods.items() %}
                                <div class="col">
                                    <input type="checkbox" name="permissions[]" value="{{ k }}" id="p_{{ k }}" class="btn-check" {% if k in emp_perms %}checked{% endif %}>
                                    <label class="btn btn-outline-primary w-100 py-3 rounded-3 border fw-bold d-flex flex-column align-items-center justify-content-center gap-2" for="p_{{ k }}" style="transition: 0.2s;">
                                        {{ v }}
                                    </label>
                                </div>
                            {% endfor %}
                        </div>

                        <hr class="mb-4" style="opacity: 0.1;">
                        
                        <div class="d-flex justify-content-end gap-3">
                            <button type="submit" class="btn btn-primary px-5 py-3 rounded-pill shadow-sm fw-bold">
                                <i class="fas fa-check-circle me-2"></i> تحديث وحفظ البيانات
                            </button>
                        </div>
                    </form>
                </div>
            </div>
        </div>
    </div>
    """ + footer_html
    return render_template_string(html, emp=employee, departments=departments, mods=mods, emp_perms=emp_perms)
