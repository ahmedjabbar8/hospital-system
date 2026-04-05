from flask import Blueprint, session, redirect, url_for, request, flash, render_template_string
from config import get_db
from header import header_html
from footer import footer_html
import os
import time

edit_patient_bp = Blueprint('edit_patient', __name__)

@edit_patient_bp.route('/edit_patient', methods=['GET', 'POST'])
def edit_patient():
    if not session.get('user_id'):
        return redirect(url_for('login.login'))
        
    id = request.args.get('id', type=int)
    if not id:
        return redirect(url_for('patients.patients'))
        
    conn = get_db()
    if not conn:
        return "Database Error"
        
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM patients WHERE patient_id = %s", (id,))
    p = cursor.fetchone()
    
    if not p:
        conn.close()
        return redirect(url_for('patients.patients'))
        
    if request.method == 'POST' and 'update' in request.form:
        name = request.form.get('full_name_ar', '')
        phone = request.form.get('phone1', '')
        address = request.form.get('address', '')
        nat_id = request.form.get('national_id') or None
        allergies = request.form.get('allergies', '')
        history = request.form.get('medical_history', '')
        
        # Handle Photo Upload
        photo_path = p.get('photo', '')
        upload_dir_name = 'uploads/patients/'
        target_dir = os.path.join(os.path.dirname(__file__), upload_dir_name)
        
        if not os.path.exists(target_dir):
            os.makedirs(target_dir, mode=0o777, exist_ok=True)
            
        if 'photo' in request.files and request.files['photo'].filename != '':
            photo_file = request.files['photo']
            ext = os.path.splitext(photo_file.filename)[1]
            file_name = f"photo_{int(time.time())}{ext}"
            target_file = os.path.join(target_dir, file_name)
            db_path = upload_dir_name + file_name
            
            try:
                photo_file.save(target_file)
                photo_path = db_path
            except Exception:
                pass
                
        # Check for duplicate National ID (excluding current patient)
        if nat_id:
            cursor.execute("SELECT patient_id FROM patients WHERE national_id = %s AND patient_id != %s", (nat_id, id))
            res_id = cursor.fetchone()
            if res_id:
                flash(f"عذراً، رقم الهوية ( {nat_id} ) مسجل مسبقاً لمريض آخر.", "danger")
                return redirect(url_for('edit_patient.edit_patient', id=id))

        # Update data
        cursor.execute("""
            UPDATE patients 
            SET full_name_ar = %s, phone1 = %s, address = %s, national_id = %s, photo = %s, allergies = %s, medical_history = %s 
            WHERE patient_id = %s
        """, (name, phone, address, nat_id, photo_path, allergies, history, id))
        
        conn.commit()
        
        flash("تم تحديث بيانات المريض بنجاح", "success")
        return redirect(url_for('patients.patients'))

    
    photo_url = ''
    if p.get('photo'):
        photo_url = '/' + p['photo'] if not '://' in p['photo'] else p['photo']

    html = header_html + """
    <div class="container py-4">
        <div class="row justify-content-center">
            <div class="col-md-7">
                <div class="apple-card p-4">
                    <div class="d-flex align-items-center mb-4 pb-3 border-bottom">
                        {% if p.photo %}
                            <img src="{{ photo_url }}" onerror="this.onerror=null; this.src='/{{ p.photo }}';" class="rounded-circle shadow-sm border me-3"
                                style="width: 70px; height: 70px; object-fit: cover;">
                        {% else %}
                            <div class="rounded-circle bg-light d-flex align-items-center justify-content-center border me-3"
                                style="width: 70px; height: 70px;">
                                <i class="fas fa-user text-muted fa-2x"></i>
                            </div>
                        {% endif %}
                        <div>
                            <h4 class="fw-bold mb-0">تعديل بيانات المريض</h4>
                            <small class="text-muted">رقم الملف: {{ p.file_number }}</small>
                        </div>
                    </div>

                    <form method="POST" enctype="multipart/form-data">
                        <div class="row g-3">
                            <div class="col-md-12">
                                <label class="form-label fw-bold small">الاسم الكامل (عربي)</label>
                                <input type="text" name="full_name_ar" class="form-control"
                                    value="{{ p.full_name_ar }}" required>
                            </div>

                            <div class="col-md-6">
                                <label class="form-label fw-bold small">رقم الهاتف</label>
                                <input type="text" name="phone1" class="form-control" value="{{ p.phone1 if p.phone1 else '' }}"
                                    required>
                            </div>
                            <div class="col-md-12">
                                <label class="form-label fw-bold small text-danger">الحساسية (Allergies)</label>
                                <textarea name="allergies" class="form-control" rows="2">{{ p.allergies if p.allergies else '' }}</textarea>
                            </div>
                            <div class="col-md-12">
                                <label class="form-label fw-bold small">التاريخ المرضي (Medical History)</label>
                                <textarea name="medical_history" class="form-control" rows="2">{{ p.medical_history if p.medical_history else '' }}</textarea>
                            </div>
                            <div class="col-md-12">
                                <label class="form-label fw-bold small">العنوان</label>
                                <textarea name="address" class="form-control"
                                    rows="1">{{ p.address if p.address else '' }}</textarea>
                            </div>
                            <div class="col-md-12">
                                <label class="form-label fw-bold small">تحديث الصورة الشخصية</label>
                                <input type="file" name="photo" class="form-control" accept="image/*">
                            </div>
                        </div>

                        <div class="d-grid gap-2 mt-4 pt-3">
                            <button type="submit" name="update"
                                class="btn btn-primary fw-bold py-2 rounded-pill shadow-sm">حفظ التعديلات</button>
                            <a href="{{ url_for('patients.patients') }}" class="btn btn-light fw-bold py-2 rounded-pill">إلغاء والعودة</a>
                        </div>
                    </form>
                </div>
            </div>
        </div>
    </div>
    """ + footer_html
    
    return render_template_string(html, p=p, photo_url=photo_url)
