from flask import Blueprint, session, redirect, url_for, request, render_template_string
from config import get_db
from datetime import datetime, date

medical_report_bp = Blueprint('medical_report', __name__)

@medical_report_bp.route('/medical_report')
def medical_report():
    if not session.get('user_id'):
        return redirect(url_for('login.login'))

    patient_id = request.args.get('id')
    if not patient_id:
        return "Please select a patient"

    conn = get_db()
    if not conn:
        return "Database Connection Error"

    cursor = conn.cursor(dictionary=True)

    # 1. Fetch Patient Info
    cursor.execute("SELECT * FROM patients WHERE patient_id = %s", (patient_id,))
    patient = cursor.fetchone()
    if not patient:
        conn.close()
        return "Patient not found"

    # 2. Fetch Latest Consultation (Clinical Summary)
    cursor.execute("""
        SELECT c.*, u.full_name_ar as doc_name, a.appointment_date as visit_date
        FROM consultations c 
        JOIN users u ON c.doctor_id = u.user_id 
        JOIN appointments a ON c.appointment_id = a.appointment_id
        WHERE c.patient_id = %s 
        ORDER BY c.created_at DESC LIMIT 1
    """, (patient_id,))
    latest_consult = cursor.fetchone()

    # 3. Find Next Follow-up (Next scheduled appointment)
    cursor.execute("""
        SELECT appointment_date 
        FROM appointments 
        WHERE patient_id = %s AND appointment_date > CURRENT_DATE 
        AND status IN ('scheduled', 'confirmed')
        ORDER BY appointment_date ASC LIMIT 1
    """, (patient_id,))
    next_apt = cursor.fetchone()
    followup_date = next_apt['appointment_date'] if next_apt else "To be determined"

    # 4. Fetch Lab Results with Reference Ranges
    # We join with lab_tests to get the unit and ranges
    cursor.execute("""
        SELECT lr.*, u.full_name_ar as doc_name, lt.unit, lt.min_value, lt.max_value
        FROM lab_requests lr 
        LEFT JOIN users u ON lr.doctor_id = u.user_id 
        LEFT JOIN lab_tests lt ON lr.test_type = lt.test_name
        WHERE lr.patient_id = %s AND lr.result IS NOT NULL AND lr.result != ''
        ORDER BY lr.created_at DESC
    """, (patient_id,))
    labs_raw = cursor.fetchall()

    # Group labs by date
    labs_grouped = {}
    for l in labs_raw:
        dt = l['created_at']
        if isinstance(dt, (datetime, date)):
            d_str = dt.strftime('%Y-%m-%d')
        else:
            d_str = str(dt)[:10]
        
        if d_str not in labs_grouped:
            labs_grouped[d_str] = []
        labs_grouped[d_str].append(l)

    conn.close()

    html = """
    <!DOCTYPE html>
    <html dir="ltr" lang="en">
    <head>
        <meta charset="UTF-8">
        <title>Clinical Report - {{ patient.full_name_ar }}</title>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
        <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
        <style>
            @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;700&display=swap');
            body { 
                background: #f0f2f5; 
                font-family: 'Outfit', sans-serif;
                color: #2D3436;
                -webkit-print-color-adjust: exact;
            }
            .report-paper {
                background: white;
                width: 210mm;
                min-height: 297mm;
                margin: 40px auto;
                padding: 50px;
                box-shadow: 0 20px 50px rgba(0,0,0,0.1);
                position: relative;
                border: 2px solid #e1e4e8;
                border-radius: 4px;
            }
            /* Decorative Frame */
            .report-paper::before {
                content: '';
                position: absolute;
                top: 15px; left: 15px; right: 15px; bottom: 15px;
                border: 1px solid #d1d5db;
                pointer-events: none;
            }
            .report-header {
                border-bottom: 3px solid #2c3e50;
                padding-bottom: 25px;
                margin-bottom: 35px;
            }
            .section-title {
                background: #f8fafc;
                padding: 10px 20px;
                font-weight: 700;
                border-left: 6px solid #2563eb;
                margin-top: 40px;
                margin-bottom: 20px;
                font-size: 1.2rem;
                text-transform: uppercase;
                letter-spacing: 1px;
            }
            .clinical-box {
                background: #ffffff;
                border: 1px solid #e2e8f0;
                border-radius: 12px;
                padding: 25px;
                margin-bottom: 30px;
            }
            .patient-info-grid {
                display: grid;
                grid-template-columns: repeat(4, 1fr);
                gap: 20px;
                background: #f1f5f9;
                padding: 20px;
                border-radius: 12px;
                margin-bottom: 30px;
            }
            .info-item .label {
                font-size: 0.75rem;
                color: #64748b;
                text-transform: uppercase;
                font-weight: 600;
                display: block;
                margin-bottom: 4px;
            }
            .info-item .value {
                font-weight: 700;
                color: #1e293b;
                font-size: 1rem;
            }
            .lab-table {
                width: 100%;
                border-collapse: separate;
                border-spacing: 0;
                margin-top: 10px;
            }
            .lab-table th {
                background: #f8fafc;
                color: #475569;
                font-weight: 600;
                padding: 12px 15px;
                border-bottom: 2px solid #e2e8f0;
                text-align: left;
                font-size: 0.85rem;
                text-transform: uppercase;
            }
            .lab-table td {
                padding: 12px 15px;
                border-bottom: 1px solid #f1f5f9;
                font-size: 0.95rem;
            }
            .abnormal {
                color: #ef4444;
                font-weight: 800;
            }
            .normal {
                color: #10b981;
                font-weight: 600;
            }
            .followup-alert {
                background: #fffbeb;
                border: 1px solid #fde68a;
                padding: 15px 25px;
                border-radius: 10px;
                margin-top: 30px;
                display: flex;
                align-items: center;
                gap: 15px;
            }
            @media print {
                body { background: white; margin: 0; padding: 0; }
                .report-paper { margin: 0; box-shadow: none; border: none; width: 100%; }
                .no-print { display: none; }
                .report-paper::before { border: 2px solid #000; }
            }
        </style>
    </head>
    <body>
    <div class="container no-print mt-4 text-center">
        <div class="bg-white p-3 rounded-4 shadow-sm mb-4 d-inline-flex gap-4 align-items-center">
            <div class="fw-bold text-muted small"><i class="fas fa-print me-2"></i> PRINT OPTIONS:</div>
            <div class="form-check form-switch">
                <input class="form-check-input" type="checkbox" id="showDiagnosis" checked onclick="toggleSection('diag_sec')">
                <label class="form-check-label small fw-bold" for="showDiagnosis">Prescription</label>
            </div>
            <div class="form-check form-switch">
                <input class="form-check-input" type="checkbox" id="showLabs" checked onclick="toggleSection('labs_sec')">
                <label class="form-check-label small fw-bold" for="showLabs">Lab Results</label>
            </div>
            <div class="vr"></div>
            <button onclick="window.print()" class="btn btn-primary px-5 rounded-pill shadow">
                <i class="fas fa-print me-2"></i> PRINT SELECTED
            </button>
            <a href="javascript:history.back()" class="btn btn-outline-secondary px-4 rounded-pill ms-2">RETURN</a>
        </div>
    </div>

    <div class="report-paper">
        <!-- Header -->
        <div class="report-header d-flex justify-content-between align-items-end">
            <div class="text-start">
                <h1 class="fw-bold mb-1" style="color:#1e293b;">
                    {% if system_icon %}<i class="{{ system_icon }} text-primary me-2"></i>{% endif %} 
                    {{ system_name }}
                </h1>
                <p class="text-muted small mb-0">Smart Clinical Management System</p>
            </div>
            <div class="text-end">
                <h3 class="fw-bold text-uppercase mb-1" style="letter-spacing:3px;">Clinical Report</h3>
                <p class="text-primary fw-bold mb-0">Issued Date: {{ datetime.now().strftime('%d %B %Y') }}</p>
            </div>
        </div>

        <!-- Patient Info -->
        <div class="patient-info-grid">
            <div class="info-item">
                <span class="label">Patient Name</span>
                <span class="value">{{ patient.full_name_ar }}</span>
            </div>
            <div class="info-item">
                <span class="label">Patient ID</span>
                <span class="value">#{{ patient.file_number }}</span>
            </div>
            <div class="info-item">
                <span class="label">Age / Sex</span>
                <span class="value">{{ patient.gender|capitalize }}</span>
            </div>
            <div class="info-item">
                <span class="label">Phone Number</span>
                <span class="value">{{ patient.phone1 or 'N/A' }}</span>
            </div>
        </div>

        <!-- 1. PRESCRIPTION SECTION -->
        <div id="diag_sec">
            <h4 class="section-title"><i class="fas fa-prescription me-2"></i> Medical Prescription</h4>
            {% if latest_consult %}
            <div class="clinical-box mb-4">
                <div class="row g-4">
                    <div class="col-8">
                        <span class="label text-muted small text-uppercase mb-2 d-block">Assessment & Diagnosis</span>
                        <div class="fs-5 fw-bold text-danger">{{ latest_consult.assessment }}</div>
                    </div>
                    <div class="col-4 text-end">
                        <span class="label text-muted small text-uppercase mb-2 d-block">Visit Date</span>
                        <div class="fw-bold">{{ latest_consult.visit_date }}</div>
                    </div>
                    <div class="col-12 mt-4">
                        <div class="p-4 bg-light rounded-4" style="border: 1px dashed #cbd5e1; position: relative;">
                            <i class="fas fa-prescription fa-2x position-absolute opacity-10" style="top:20px; right:20px;"></i>
                            <span class="label text-muted small text-uppercase mb-2 d-block">Drug Dose & Administration</span>
                            <div style="white-space: pre-wrap; font-size: 1.15rem; font-weight:600; line-height:1.8;">{{ latest_consult.plan }}</div>
                        </div>
                    </div>
                </div>
                
                <div class="mt-4 pt-3 border-top d-flex justify-content-between align-items-center">
                    <div>
                        <span class="label text-muted small text-uppercase d-block">Prescribing Physician</span>
                        <div class="fw-bold">Dr. {{ latest_consult.doc_name }}</div>
                    </div>
                    <div class="text-end">
                        <div class="followup-badge bg-warning bg-opacity-10 px-3 py-2 rounded-pill d-inline-flex align-items-center gap-2">
                            <i class="fas fa-calendar-check text-warning"></i>
                            <span class="small fw-bold">NEXT FOLLOW-UP: {{ followup_date }}</span>
                        </div>
                    </div>
                </div>
            </div>
            {% else %}
            <div class="alert alert-light border text-center py-4">No recent consultation data found.</div>
            {% endif %}
        </div>

        <!-- 2. LAB RESULTS SECTION -->
        <div id="labs_sec">
            <h4 class="section-title"><i class="fas fa-flask me-2"></i> Laboratory Findings</h4>
            {% for date_str, results in labs_grouped.items() %}
            <div class="mb-4">
                <div class="d-flex align-items-center gap-3 mb-2">
                    <span class="text-primary fw-bold"><i class="far fa-calendar-alt me-1"></i> Result Date: {{ date_str }}</span>
                    <hr class="flex-grow-1 opacity-10">
                </div>
                <div class="table-responsive">
                    <table class="lab-table">
                        <thead>
                            <tr>
                                <th>Test Parameter</th>
                                <th>Result</th>
                                <th>Unit</th>
                                <th>Ref. Range</th>
                                <th class="text-end">Status</th>
                            </tr>
                        </thead>
                        <tbody>
                            {% for lr in results %}
                            {% set is_abnormal = false %}
                            {% if lr.min_value is not none and lr.max_value is not none and lr.result.replace('.','',1).isdigit() %}
                                {% set val = lr.result|float %}
                                {% if val < lr.min_value|float or val > lr.max_value|float %}
                                    {% set is_abnormal = true %}
                                {% endif %}
                            {% endif %}
                            <tr>
                                <td class="fw-bold">{{ lr.test_type }}</td>
                                <td class="{{ 'abnormal' if is_abnormal else 'normal' }} fs-5">{{ lr.result }}</td>
                                <td class="text-muted small">{{ lr.unit or '' }}</td>
                                <td class="text-muted small">
                                    {% if lr.min_value is not none and lr.max_value is not none %}
                                        {{ lr.min_value }} - {{ lr.max_value }}
                                    {% else %}
                                        -- 
                                    {% endif %}
                                </td>
                                <td class="text-end">
                                    {% if is_abnormal %}
                                        <span class="badge bg-danger rounded-pill px-3" style="font-size:0.65rem;">ABNORMAL</span>
                                    {% else %}
                                        <span class="badge bg-success rounded-pill px-3" style="font-size:0.65rem;">NORMAL</span>
                                    {% endif %}
                                </td>
                            </tr>
                            {% endfor %}
                        </tbody>
                    </table>
                </div>
            </div>
            {% else %}
            <div class="alert alert-light border text-center py-4">No laboratory records available.</div>
            {% endfor %}
        </div>

        <!-- Footer / Signatures -->
        <div class="mt-5 pt-5">
            <div class="row text-center mt-5">
                <div class="col-4">
                    <hr style="width: 70%; margin: 0 auto 10px; border-top: 2px solid #2c3e50;">
                    <p class="small text-muted fw-bold">AUTHORIZED SIGNATURE</p>
                </div>
                <div class="col-4">
                    <div class="opacity-25" style="transform: rotate(-15deg);">
                         <div class="border border-3 border-secondary d-inline-block p-2 rounded-circle" style="width:70px; height:70px;">
                             <i class="fas fa-check-circle fa-2x mt-2"></i>
                         </div>
                         <br><small class="fw-bold">VERIFIED DOCUMENT</small>
                    </div>
                </div>
                <div class="col-4">
                    <hr style="width: 70%; margin: 0 auto 10px; border-top: 2px solid #2c3e50;">
                    <p class="small text-muted fw-bold">HOSPITAL STAMP</p>
                </div>
            </div>
        </div>
        
        <p class="text-center mt-5 small text-muted opacity-50 no-print">End of Consolidated Medical Summary</p>
    </div>

    <script>
        function toggleSection(id) {
            const el = document.getElementById(id);
            if (el) {
                el.style.display = el.style.display === 'none' ? 'block' : 'none';
            }
        }
    </script>
</body>
</html>
    """
    return render_template_string(html, patient=patient, latest_consult=latest_consult, labs_grouped=labs_grouped, followup_date=followup_date, datetime=datetime)
