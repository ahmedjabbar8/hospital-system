from flask import Blueprint, session, redirect, url_for, request, render_template_string
from config import get_db

print_rx_bp = Blueprint('print_rx', __name__)

@print_rx_bp.route('/print_rx', methods=['GET'])
def print_rx():
    if not session.get('user_id'):
        return redirect(url_for('login.login'))

    appt_id = request.args.get('id')
    if not appt_id:
        return "No ID provided"

    conn = get_db()
    if not conn:
        return "Database Connection Error"

    cursor = conn.cursor(dictionary=True)
    sql = """
        SELECT pr.*, p.full_name_ar, p.file_number, p.gender, p.date_of_birth, u.full_name_ar as doc_name, d.department_name_ar
        FROM prescriptions pr
        JOIN patients p ON pr.patient_id = p.patient_id
        JOIN users u ON pr.doctor_id = u.user_id
        JOIN appointments a ON pr.appointment_id = a.appointment_id
        JOIN departments d ON a.department_id = d.department_id
        WHERE pr.appointment_id = %s OR pr.prescription_id = %s 
        LIMIT 1
    """
    cursor.execute(sql, (appt_id, appt_id))
    data = cursor.fetchone()
    conn.close()

    if not data:
        return "Prescription not found"

    html = """
    <!DOCTYPE html>
    <html dir="rtl" lang="ar">

    <head>
        <meta charset="UTF-8">
        <title>وصفة طبية - {{ data.full_name_ar }}</title>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.rtl.min.css" rel="stylesheet">
        <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css">
        <style>
            @import url('https://fonts.googleapis.com/css2?family=Tajawal:wght@400;700&display=swap');

            body {
                font-family: 'Tajawal', sans-serif;
                background: #f0f0f0;
            }

            .rx-card {
                background: white;
                width: 210mm;
                min-height: 148mm;
                margin: 30px auto;
                padding: 40px;
                box-shadow: 0 0 20px rgba(0, 0, 0, 0.1);
                border-top: 10px solid #2c3e50;
                border-bottom: 10px solid #2c3e50;
                position: relative;
            }

            .header-box {
                border-bottom: 2px solid #2c3e50;
                padding-bottom: 20px;
                margin-bottom: 30px;
            }

            .hospital-name {
                font-size: 28px;
                font-weight: bold;
                color: #2c3e50;
            }

            .rx-symbol {
                font-size: 60px;
                color: #2C3E50;
                opacity: 0.1;
                position: absolute;
                top: 150px;
                left: 100px;
            }

            .info-label {
                color: #7f8c8d;
                font-size: 14px;
            }

            .info-value {
                font-weight: bold;
                color: #2c3e50;
            }

            .medication-area {
                min-height: 250px;
                font-size: 20px;
                line-height: 2;
                padding: 20px;
                border-right: 4px solid #3498db;
                background: #f9f9f9;
            }

            @media print {
                body {
                    background: white;
                    margin: 0;
                }

                .rx-card {
                    margin: 0;
                    box-shadow: none;
                    border: none;
                    width: 100%;
                }

                .no-print {
                    display: none;
                }
            }
        </style>
    </head>

    <body>

        <div class="container no-print mt-3 text-center">
            <button onclick="window.print()" class="btn btn-dark px-5 shadow-lg"><i class="fas fa-print me-2"></i> طـبـاعـة
                الـوصـفـة</button>
            <a href="{{ url_for('archive.archive') }}" class="btn btn-outline-secondary px-4">رجوع</a>
        </div>

        <div class="rx-card text-center">
            <div class="rx-symbol">Rx</div>

            <!-- Centered Header Icons and Content -->
            <div class="header-box">
                <div class="row align-items-center">
                    <div class="col-4 text-start">
                        <p class="mb-0 hospital-name">HealthPro <i class="fas fa-plus-square text-danger"></i></p>
                        <small class="text-muted">نظام إدارة المستشفيات الذكي</small>
                    </div>
                    <div class="col-4">
                        <h2 class="fw-bold text-uppercase border-bottom pb-2">وصفة طبية</h2>
                        <p class="mb-0">PRESCRIPTION</p>
                    </div>
                    <div class="col-4 text-end">
                        <p class="mb-0 fw-bold">د. {{ data.doc_name }}</p>
                        <small>{{ data.department_name_ar }}</small>
                    </div>
                </div>
            </div>

            <!-- Patient Info Centered Layout -->
            <div class="row mb-5 text-center">
                <div class="col-md-3 border-start">
                    <div class="info-label">اسم المريض</div>
                    <div class="info-value fs-5">{{ data.full_name_ar }}</div>
                </div>
                <div class="col-md-3 border-start">
                    <div class="info-label">رقم الملف</div>
                    <div class="info-value fs-5">{{ data.file_number }}</div>
                </div>
                <div class="col-md-3 border-start">
                    <div class="info-label">العمر / الجنس</div>
                    <div class="info-value fs-5">{{ data.date_of_birth }} / {{ 'ذكر' if data.gender == 'male' else 'أنثى' }}</div>
                </div>
                <div class="col-md-3">
                    <div class="info-label">التاريخ</div>
                    <div class="info-value fs-5">{{ data.created_at.strftime('%Y-%m-%d') if data.created_at else '' }}</div>
                </div>
            </div>

            <!-- Medication List -->
            <div class="medication-area text-start">
                <div class="text-secondary mb-3"><i class="fas fa-prescription fa-2x"></i></div>
                <div class="fw-bold px-4">{{ data.medicine_name | replace('\\n', '<br>') | safe }}</div>
            </div>

            <!-- Footer -->
            <div class="mt-5 pt-4 border-top">
                <div class="row align-items-end">
                    <div class="col-4 text-start">
                        <small class="text-muted">الختم والتوقيع:</small>
                        <div style="height: 60px;"></div>
                        <hr style="width: 200px;">
                    </div>
                    <div class="col-4 text-center">
                        <!-- Barcode Section -->
                        <div class="barcode-container mb-2">
                            <canvas id="barcode"></canvas>
                            <div class="small text-muted mt-1" style="font-size: 10px;">امسح الباركود للحجز التلقائي</div>
                        </div>
                    </div>
                    <div class="col-4 text-end">
                        <p class="mb-0 small text-muted">هذه الوصفة صالحة لمدة 7 أيام من تاريخ الصدور</p>
                        <p class="small text-muted mb-0">تم استخراجها عبر نظام HealthPro V5.0</p>
                    </div>
                </div>
            </div>
        </div>

        <!-- Barcode Script -->
        <script src="https://cdn.jsdelivr.net/npm/jsbarcode@3.11.5/dist/JsBarcode.all.min.js"></script>
        <script>
            JsBarcode("#barcode", "{{ data.file_number }}", {
                format: "CODE128",
                width: 1.5,
                height: 40,
                displayValue: true,
                fontSize: 12,
                margin: 0
            });
        </script>
    </body>

    </html>
    """
    
    return render_template_string(html, data=data)
