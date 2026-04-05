import os
from flask import Flask, session, g
import secrets

app = Flask(__name__)
app.secret_key = secrets.token_hex(32)

# ── Performance: pre-warm DB availability check at startup ─────────────────
from config import _check_pg_available
_check_pg_available()

# ── Request lifecycle: close DB after each request ────────────────────────
@app.teardown_request
def teardown_request(exception):
    db = getattr(g, '_db', None)
    if db is not None:
        try:
            db.close()
        except Exception:
            pass
        g._db = None

# ── Blueprints ─────────────────────────────────────────────────────────────
from index              import index_bp
from login              import login_bp
from logout             import logout_bp
from dashboard          import dashboard_bp
from patients           import patients_bp
from doctor_clinic      import doctor_clinic_bp
from consultation       import consultation_bp
from pharmacy           import pharmacy_bp
from lab                import lab_bp
from radiology          import radiology_bp
from triage             import triage_bp
from patient_index      import patient_index_bp
from patient_file       import patient_file_bp
from book               import book_bp
from connect            import connect_bp
from archive            import archive_bp
from system_data        import system_data_bp
from manage_staff       import manage_staff_bp
from waiting_list       import waiting_list_bp
from api                import api_bp
from billing            import billing_bp
from reservations       import reservations_bp
from add_patient        import add_patient_bp
from edit_patient       import edit_patient_bp
from settings           import settings_bp
from price_control      import price_control_bp
from print_rx           import print_rx_bp
from registration_settings import registration_settings_bp
from lab_maintenance    import lab_maintenance_bp
from manage_departments import manage_departments_bp
from nursing_lab        import nursing_lab_bp
from reports            import reports_bp

app.register_blueprint(index_bp)
app.register_blueprint(login_bp)
app.register_blueprint(logout_bp)
app.register_blueprint(dashboard_bp)
app.register_blueprint(patients_bp)
app.register_blueprint(doctor_clinic_bp)
app.register_blueprint(consultation_bp)
app.register_blueprint(pharmacy_bp)
app.register_blueprint(lab_bp)
app.register_blueprint(radiology_bp)
app.register_blueprint(triage_bp)
app.register_blueprint(patient_index_bp)
app.register_blueprint(patient_file_bp)
app.register_blueprint(book_bp)
app.register_blueprint(connect_bp)
app.register_blueprint(archive_bp)
app.register_blueprint(system_data_bp)
app.register_blueprint(manage_staff_bp)
app.register_blueprint(waiting_list_bp)
app.register_blueprint(api_bp)
app.register_blueprint(billing_bp)
app.register_blueprint(reservations_bp)
app.register_blueprint(add_patient_bp)
app.register_blueprint(edit_patient_bp)
app.register_blueprint(settings_bp)
app.register_blueprint(price_control_bp)
app.register_blueprint(print_rx_bp)
app.register_blueprint(registration_settings_bp)
app.register_blueprint(lab_maintenance_bp)
app.register_blueprint(manage_departments_bp)
app.register_blueprint(nursing_lab_bp)
app.register_blueprint(reports_bp)
# ── Static uploads ─────────────────────────────────────────────────────────
@app.route('/uploads/<path:filename>')
def uploaded_file(filename):
    from flask import send_from_directory
    return send_from_directory(os.path.join(app.root_path, 'uploads'), filename)

# ── Error handlers ─────────────────────────────────────────────────────────
@app.errorhandler(404)
def page_not_found(e):
    from flask import redirect, url_for
    return redirect(url_for('index.index'))

# ── Template globals ───────────────────────────────────────────────────────
@app.context_processor
def inject_now():
    from datetime import datetime, timezone
    return {'now': datetime.now(timezone.utc)}

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False, threaded=True)
