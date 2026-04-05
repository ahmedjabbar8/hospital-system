from flask import Blueprint, session, redirect, url_for, request, render_template_string
from config import get_db
from datetime import datetime

print_lab_bp = Blueprint('print_lab', __name__)

@print_lab_bp.route('/print_lab')
def print_lab():
    if not session.get('user_id'):
        return redirect(url_for('login.login'))

    patient_id = request.args.get('patient_id')
    print_date = request.args.get('date') # Format: YYYY-MM-DD or 'CURRENT_DATE'
    
    if not patient_id:
        return "Patient ID is missing"
        
    # Handle magic word CURRENT_DATE
    if not print_date or print_date.upper().startswith('CURRENT_DA'):
        from datetime import date
        print_date = date.today().strftime('%Y-%m-%d')

    conn = get_db()
    cursor = conn.cursor(dictionary=True)

    # Fetch Patient Info
    cursor.execute("SELECT * FROM patients WHERE patient_id = %s", (patient_id,))
    patient = cursor.fetchone()

    # Fetch Labs for this specific date
    # We use DATE() in SQL to match the YYYY-MM-DD
    cursor.execute("""
        SELECT lr.*, lt.unit, lt.min_value, lt.max_value
        FROM lab_requests lr
        LEFT JOIN lab_tests lt ON lr.test_type = lt.test_name
        WHERE lr.patient_id = %s 
          AND (DATE(lr.created_at) = %s OR lr.created_at LIKE CONCAT(%s, '%%'))
          AND lr.result IS NOT NULL
    """, (patient_id, print_date, print_date))
    labs = cursor.fetchall()
    
    conn.close()

    if not labs:
        return "No results found for this date"

    html = """
    <!DOCTYPE html>
    <html dir="ltr" lang="en">
    <head>
        <meta charset="UTF-8">
        <title>Laboratory Report - {{ patient.full_name_ar }}</title>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
        <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
        <style>
            @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@400;600;700&display=swap');
            body { font-family: 'Outfit', sans-serif; background: #fff; padding: 40px; }
            .report-box { border: 2px solid #334155; padding: 40px; position: relative; min-height: 280mm; }
            .header { border-bottom: 3px solid #334155; padding-bottom: 20px; margin-bottom: 30px; }
            .lab-table { width: 100%; margin-top: 20px; }
            .lab-table th { background: #f8fafc; border-bottom: 2px solid #334155; padding: 12px; text-transform: uppercase; font-size: 0.85rem; }
            .lab-table td { padding: 12px; border-bottom: 1px solid #e2e8f0; }
            .abnormal { color: #ef4444; font-weight: bold; }
            @media print {
                .no-print { display: none; }
                body { padding: 0; }
                .report-box { border: 2px solid #000; }
            }
        </style>
    </head>
    <body>
        <div class="no-print text-center mb-4">
             <button onclick="window.print()" class="btn btn-dark px-4 py-2 rounded-pill"><i class="fas fa-print me-2"></i> PRINT REPORT</button>
             <button onclick="shareAsPDF()" class="btn btn-success px-4 py-2 rounded-pill ms-2" id="waBtn">
                 <i class="fab fa-whatsapp me-1"></i> SEND VIA WHATSAPP (PDF)
             </button>
             <button onclick="window.close()" class="btn btn-outline-secondary px-4 py-2 rounded-pill ms-2">CLOSE</button>
        </div>

        <script src="https://cdnjs.cloudflare.com/ajax/libs/html2pdf.js/0.10.1/html2pdf.bundle.min.js"></script>
        <script src="https://cdnjs.cloudflare.com/ajax/libs/html2canvas/1.4.1/html2canvas.min.js"></script>
        <script>
            async function shareAsPDF() {
                const btn = document.getElementById('waBtn');
                const original = btn.innerHTML;
                btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> PREPARING...';
                
                try {
                    const element = document.querySelector('.report-box');
                    const filename = 'Laboratory Report - {{ patient.full_name_ar }}';
                    
                    // 1. Copy image to clipboard
                    const canvas = await html2canvas(element, { scale: 2 });
                    canvas.toBlob(async (blob) => {
                        try {
                            const item = new ClipboardItem({ "image/png": blob });
                            await navigator.clipboard.write([item]);
                        } catch (err) {}
                    });

                    // 2. Download PDF
                    const opt = {
                        margin: 10,
                        filename: filename + '.pdf',
                        html2canvas: { scale: 2 },
                        jsPDF: { unit: 'mm', format: 'a4', orientation: 'portrait' }
                    };
                    await html2pdf().set(opt).from(element).save();

                    // 3. Open WhatsApp
                    const waText = "Hello, here is your Laboratory Report. The image is copied to your clipboard, just press (Ctrl+V) in the chat to send it immediately.";
                    const waUrl = "https://wa.me/{{ patient.phone1|string|replace('+', '')|replace(' ', '') }}?text=" + encodeURIComponent(waText);
                    window.open(waUrl, '_blank');
                    
                    alert("COMPLETED! You can now press (Ctrl+V) in WhatsApp to send the report instantly.");
                    btn.innerHTML = original;
                } catch (err) {
                    btn.innerHTML = original;
                }
            }
        </script>

        <div class="report-box">
             <div class="header d-flex justify-content-between align-items-end">
                <div>
                    <h2 class="fw-bold mb-1">{{ system_name }}</h2>
                    <p class="text-muted small mb-0">Laboratory Investigation Department</p>
                </div>
                <div class="text-end">
                    <h3 class="fw-bold text-uppercase mb-0">Laboratory Report</h3>
                    <p class="fw-bold text-primary mb-0">Date: {{ print_date }}</p>
                </div>
             </div>

             <div class="row g-4 mb-4 bg-light p-3 rounded">
                <div class="col-6">
                    <small class="text-muted d-block">PATIENT NAME</small>
                    <span class="fw-bold fs-5">{{ patient.full_name_ar }}</span>
                </div>
                <div class="col-3">
                    <small class="text-muted d-block">FILE NO.</small>
                    <span class="fw-bold">#{{ patient.file_number }}</span>
                </div>
                <div class="col-3 text-end">
                    <small class="text-muted d-block">SEX</small>
                    <span class="fw-bold">{{ patient.gender|capitalize }}</span>
                </div>
             </div>

             <table class="lab-table">
                <thead>
                    <tr>
                        <th>Test Description</th>
                        <th>Result</th>
                        <th>Reference Range</th>
                        <th class="text-end">Unit</th>
                    </tr>
                </thead>
                <tbody>
                    {% for l in labs %}
                    {% set is_abnormal = false %}
                    {% if l.min_value is not none and l.max_value is not none and l.result.replace('.','',1).isdigit() %}
                        {% set val = l.result|float %}
                        {% if val < l.min_value|float or val > l.max_value|float %}
                            {% set is_abnormal = true %}
                        {% endif %}
                    {% endif %}
                    <tr>
                        <td class="fw-bold">{{ l.test_type }}</td>
                        <td class="{{ 'abnormal' if is_abnormal else '' }} fs-5">{{ l.result }}</td>
                        <td>{{ l.min_value }} - {{ l.max_value }}</td>
                        <td class="text-end text-muted">{{ l.unit or '--' }}</td>
                    </tr>
                    {% endfor %}
                </tbody>
             </table>

             <div class="mt-5 pt-5">
                <div class="row text-center mt-5">
                    <div class="col-6">
                        <hr style="width: 60%; margin: 0 auto 10px;">
                        <small>Laboratory Specialist</small>
                    </div>
                    <div class="col-6">
                        <hr style="width: 60%; margin: 0 auto 10px;">
                        <small>Pathologist / Director</small>
                    </div>
                </div>
             </div>
        </div>
    </body>
    </html>
    """
    return render_template_string(html, patient=patient, labs=labs, print_date=print_date)
