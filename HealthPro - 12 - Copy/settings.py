from flask import Blueprint, session, redirect, url_for, request, render_template_string
from config import get_db
from header import header_html
from footer import footer_html
import json

settings_bp = Blueprint('settings', __name__)

@settings_bp.route('/settings', methods=['GET', 'POST'])
def view_settings():
    if not session.get('user_id'):
        return redirect(url_for('login.login'))
        
    perms = session.get('permissions', [])
    if isinstance(perms, str):
        try:
            perms = json.loads(perms)
        except:
            perms = []
            
    if session.get('role') != 'admin' and 'settings' not in perms:
        return redirect(url_for('dashboard.dashboard'))
        
    conn = get_db()
    if not conn:
        return "Database Error"
        
    cursor = conn.cursor(dictionary=True)
    
    # 2. Fetch Currency & System Settings
    cursor.execute("SELECT * FROM system_settings")
    settings_res = cursor.fetchall()
    sys_settings = {row['setting_key']: row['setting_value'] for row in settings_res}
    
    # 3. Total Stats
    cursor.execute("SELECT COUNT(*) as c FROM patients")
    total_patients_row = cursor.fetchone()
    total_patients = total_patients_row['c'] if total_patients_row else 0
    
    cursor.execute("SELECT SUM(amount) as s FROM invoices WHERE status = 'paid'")
    total_revenues_row = cursor.fetchone()
    total_revenue = total_revenues_row['s'] if total_revenues_row and total_revenues_row['s'] else 0
    
    cursor.execute("SELECT SUM(amount) as s FROM invoices WHERE status = 'paid' AND DATE(created_at) = CURDATE()")
    today_revenue_row = cursor.fetchone()
    today_revenue = today_revenue_row['s'] if today_revenue_row and today_revenue_row['s'] else 0
    
    cursor.execute("SELECT COUNT(*) as c FROM lab_requests WHERE status = 'completed'")
    total_labs_row = cursor.fetchone()
    total_labs = total_labs_row['c'] if total_labs_row else 0
    
    cursor.execute("SELECT COUNT(*) as c FROM appointments WHERE status = 'completed'")
    total_visits_row = cursor.fetchone()
    total_visits = total_visits_row['c'] if total_visits_row else 0
    
    conn.close()

    conn.close()
    
    html = header_html + """
    <div class="row pt-2 mb-4 text-center">
        <div class="col-12">
            <h2 class="fw-bold mb-0">إعدادات النظام</h2>
            <p class="text-muted small">تخصيص وإدارة معايير العمل</p>
        </div>
    </div>

    <!-- Stats Overview (Dashboard Tiles Style) -->
    <div class="row row-cols-2 row-cols-md-4 g-3 mb-5">
        <div class="col">
            <div class="neo-tile tile-blue" style="height: 100px;">
                <i class="fas fa-users text-primary"></i>
                <span class="small">المرضى: {{ "{:,}".format(total_patients) }}</span>
            </div>
        </div>
        <div class="col">
            <div class="neo-tile tile-green" style="height: 100px;">
                <i class="fas fa-wallet text-success"></i>
                <span class="small">دخل اليوم: {{ "{:,.0f}".format(today_revenue|float) }}</span>
            </div>
        </div>
        <div class="col">
            <div class="neo-tile tile-cyan" style="height: 100px;">
                <i class="fas fa-vial text-info"></i>
                <span class="small">فحوصات: {{ "{:,}".format(total_labs) }}</span>
            </div>
        </div>
        <div class="col">
            <div class="neo-tile tile-teal" style="height: 100px;">
                <i class="fas fa-calendar-check text-info"></i>
                <span class="small">زيارات: {{ "{:,}".format(total_visits) }}</span>
            </div>
        </div>
    </div>

    <!-- Main Settings Tiles Grid -->
    <div class="row row-cols-2 row-cols-md-3 row-cols-lg-6 g-3 justify-content-center mb-5">

        <!-- 2. Price Control -->
        <div class="col">
            <a href="price_control" class="neo-tile tile-indigo">
                <i class="fas fa-tags text-primary"></i>
                <span>ادارة الأسعار</span>
            </a>
        </div>

        <!-- 3. Staff & Departments -->
        <div class="col">
            <a href="{{ url_for('manage_staff.manage_staff') }}" class="neo-tile tile-blue">
                <i class="fas fa-user-tie text-info"></i>
                <span>إدارة الموظفين</span>
            </a>
        </div>

        <div class="col">
            <a href="{{ url_for('manage_departments.manage_departments') }}" class="neo-tile tile-teal">
                <i class="fas fa-building text-success"></i>
                <span>إدارة الأقسام</span>
            </a>
        </div>

        <!-- 4. Registration Settings -->
        <div class="col">
            <a href="registration_settings" class="neo-tile tile-orange">
                <i class="fas fa-address-card text-warning"></i>
                <span>التسجيل</span>
            </a>
        </div>

        <!-- 5. Database Maintenance -->
        <div class="col">
            <a href="database_maintenance" class="neo-tile tile-dark">
                <i class="fas fa-database text-secondary"></i>
                <span>البيانات</span>
            </a>
        </div>

        <!-- 6. Radiology & Lab Management -->
        <div class="col">
            <a href="lab_maintenance" class="neo-tile tile-indigo">
                <i class="fas fa-microscope text-primary"></i>
                <span>إدارة الأشعة والمختبر</span>
            </a>
        </div>



    </div>
    """ + footer_html
    
    return render_template_string(html, total_patients=total_patients, today_revenue=today_revenue, total_labs=total_labs, total_visits=total_visits)
