from flask import Blueprint, session, redirect, url_for, request, render_template_string
from config import get_db, can_access
from header import header_html
from footer import footer_html
import datetime

reports_bp = Blueprint('reports', __name__)

@reports_bp.route('/reports')
def reports():
    if not session.get('user_id'):
        return redirect(url_for('login.login'))
        
    # Check permissions (only admins should see reports)
    if session.get('role') != 'admin':
        return redirect(url_for('dashboard.dashboard'))
        
    conn = get_db()
    if not conn:
        return "Database Connection Error"
        
    cursor = conn.cursor(dictionary=True)
    
    # Calculate date 30 days ago
    thirty_days_ago = (datetime.datetime.now() - datetime.timedelta(days=30)).strftime('%Y-%m-%d')
    
    # 1. Monthly Financial Data
    cursor.execute("""
        SELECT 
            DATE(created_at) as day,
            SUM(amount) as amount
        FROM invoices
        WHERE created_at >= %s
        GROUP BY DATE(created_at)
        ORDER BY DATE(created_at) ASC
    """, (thirty_days_ago,))
    finance_rows = cursor.fetchall()
    
    # 2. Patient Volume by Department
    cursor.execute("""
        SELECT 
            d.department_name_ar as dept,
            COUNT(a.appointment_id) as cnt
        FROM appointments a
        JOIN departments d ON a.department_id = d.department_id
        WHERE a.status = 'completed'
          AND a.appointment_date >= %s
        GROUP BY d.department_name_ar
    """, (thirty_days_ago,))
    dept_stats = cursor.fetchall()
    
    # 3. Top Diagnoses (Common cases)
    cursor.execute("""
        SELECT 
            assessment as diag,
            COUNT(*) as cnt
        FROM consultations
        WHERE created_at >= %s
        GROUP BY assessment
        ORDER BY cnt DESC
        LIMIT 5
    """, (thirty_days_ago,))
    top_diagnoses = cursor.fetchall()

    html = header_html + """
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    
    <div class="container-fluid py-4 px-lg-5">
        <div class="row align-items-center mb-4">
            <div class="col">
                <h2 class="fw-bold m-0"><i class="fas fa-chart-pie me-2 text-primary"></i> مركز التقارير والإحصائيات</h2>
                <small class="text-muted">نظرة عامة على الأداء خلال آخر 30 يوم</small>
            </div>
        </div>
        
        <div class="row g-4 mb-4">
            <!-- Daily Revenue -->
            <div class="col-lg-8">
                <div class="card border-0 shadow-sm rounded-4 p-4" style="background: rgba(255,255,255,0.05); backdrop-filter: blur(10px); border: 1px solid rgba(255,255,255,0.1) !important;">
                    <h5 class="fw-bold mb-4">الإيرادات اليومية ($)</h5>
                    <div style="height: 350px;">
                        <canvas id="financeChart"></canvas>
                    </div>
                </div>
            </div>
            
            <!-- Dept Stats -->
            <div class="col-lg-4">
                <div class="card border-0 shadow-sm rounded-4 p-4 h-100" style="background: rgba(255,255,255,0.05); backdrop-filter: blur(10px); border: 1px solid rgba(255,255,255,0.1) !important;">
                    <h5 class="fw-bold mb-4">توزع المراجعين حسب القسم</h5>
                    <canvas id="deptChart"></canvas>
                </div>
            </div>
        </div>
        
        <div class="row g-4">
             <!-- Top Diagnoses -->
             <div class="col-md-6">
                <div class="card border-0 shadow-sm rounded-4 p-4" style="background: rgba(255,255,255,0.05); backdrop-filter: blur(10px); border: 1px solid rgba(255,255,255,0.1) !important;">
                    <h5 class="fw-bold mb-4">التشخيصات الأكثر شيوعاً</h5>
                    <div class="list-group list-group-flush bg-transparent">
                        {% for d in top_diagnoses %}
                        <div class="list-group-item bg-transparent border-0 d-flex justify-content-between align-items-center px-0 py-3">
                            <div>
                                <i class="fas fa-virus-slash text-danger me-2"></i>
                                <span class="fw-bold">{{ d.diag or 'غير مصنف' }}</span>
                            </div>
                            <span class="badge bg-danger rounded-pill">{{ d.cnt }} حالة</span>
                        </div>
                        {% else %}
                        <div class="text-center py-4 opacity-50">لا توجد بيانات متاحة</div>
                        {% endfor %}
                    </div>
                </div>
             </div>
             
             <!-- Quick Stats -->
             <div class="col-md-6">
                 <div class="row g-3">
                     <div class="col-6">
                         <div class="card border-0 shadow-sm rounded-4 p-4 text-center h-100" style="background: linear-gradient(135deg, #6366f1 0%, #a855f7 100%); color: white;">
                             <div class="h1 fw-bold mb-1">{{ finance_rows | count }}</div>
                             <small>يوم نشط</small>
                         </div>
                     </div>
                     <div class="col-6">
                         <div class="card border-0 shadow-sm rounded-4 p-4 text-center h-100" style="background: linear-gradient(135deg, #10b981 0%, #3b82f6 100%); color: white;">
                             <div class="h1 fw-bold mb-1">{{ dept_stats | sum(attribute='cnt') }}</div>
                             <small>إجمالي المراجعين</small>
                         </div>
                     </div>
                 </div>
             </div>
        </div>
    </div>
    
    <script>
        const financeLabels = [{% for r in finance_rows %}"{{ r.day }}",{% endfor %}];
        const financeData = [{% for r in finance_rows %}{{ r.amount }},{% endfor %}];
        
        const deptLabels = [{% for d in dept_stats %}"{{ d.dept }}",{% endfor %}];
        const deptData = [{% for d in dept_stats %}{{ d.cnt }},{% endfor %}];

        // Revenue Chart
        new Chart(document.getElementById('financeChart'), {
            type: 'bar',
            data: {
                labels: financeLabels,
                datasets: [{
                    label: 'الإيرادات اليومية',
                    data: financeData,
                    backgroundColor: 'rgba(99, 102, 241, 0.4)',
                    borderColor: '#6366f1',
                    borderWidth: 2,
                    borderRadius: 10
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: { 
                    y: { beginAtZero: true, grid: { color: 'rgba(255,255,255,0.05)' } },
                    x: { grid: { display: false } }
                }
            }
        });

        // Dept Chart
        new Chart(document.getElementById('deptChart'), {
            type: 'doughnut',
            data: {
                labels: deptLabels,
                datasets: [{
                    data: deptData,
                    backgroundColor: ['#6366f1', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6'],
                    borderWidth: 0
                }]
            },
            options: {
                responsive: true,
                plugins: { legend: { position: 'bottom', labels: { color: '#8e8e93' } } }
            }
        });
    </script>
    """ + footer_html
    
    return render_template_string(html, finance_rows=finance_rows, dept_stats=dept_stats, top_diagnoses=top_diagnoses)
