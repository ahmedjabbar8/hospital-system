from flask import Blueprint, session, redirect, url_for, request, render_template_string
from config import get_db
from header import header_html
from footer import footer_html
import os
import time
import random
import base64

add_patient_bp = Blueprint('add_patient', __name__)

@add_patient_bp.route('/add_patient', methods=['GET', 'POST'])
def add_patient():
    if not session.get('user_id'):
        return redirect(url_for('login.login'))

    conn = get_db()
    if not conn:
        return "Database Connection Error"
    
    cursor = conn.cursor(dictionary=True)
    
    # --- SELF HEALING: Add category column if not exists ---
    try:
        cursor.execute("ALTER TABLE patients ADD COLUMN IF NOT EXISTS category VARCHAR(50) DEFAULT 'normal'")
        cursor.execute("ALTER TABLE patients ADD COLUMN IF NOT EXISTS full_name_en VARCHAR(255) DEFAULT ''")
        cursor.execute("ALTER TABLE patients ADD COLUMN IF NOT EXISTS allergies TEXT DEFAULT ''")
        cursor.execute("ALTER TABLE patients ADD COLUMN IF NOT EXISTS medical_history TEXT DEFAULT ''")
        conn.commit()
    except:
        pass # Ignore if already exists or other minor issue

    error = None

    if request.method == 'POST':
        file_num = "P-" + str(random.randint(10000, 99999))
        name = request.form.get('full_name', '')
        name_en = request.form.get('full_name_en', '')
        nat_id = request.form.get('national_id') or None
        dob = request.form.get('dob', '')
        gender = request.form.get('gender', '')
        phone = request.form.get('phone', '')
        address = request.form.get('address', '')
        category = request.form.get('category', 'normal')
        allergies = request.form.get('allergies', '')
        history = request.form.get('medical_history', '')
        
        # Handle Photo Upload
        photo_path = None
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
            except Exception as e:
                pass # Ignore save error for now
                
        elif request.form.get('photo_base64'):
            data = request.form.get('photo_base64')
            import re
            match = re.search(r'^data:image/(\w+);base64,', data)
            if match:
                type_ext = match.group(1).lower()
                if type_ext not in ['jpg', 'jpeg', 'gif', 'png']:
                    type_ext = 'png'
                data = data[match.end():]
            else:
                type_ext = 'png'
                data = data.replace('data:image/png;base64,', '').replace(' ', '+')
                
            try:
                decoded_data = base64.b64decode(data)
                file_name = f"cam_{int(time.time())}.{type_ext}"
                target_file = os.path.join(target_dir, file_name)
                db_path = upload_dir_name + file_name
                
                with open(target_file, 'wb') as f:
                    f.write(decoded_data)
                
                photo_path = db_path
            except Exception as e:
                pass # Ignore base64 decode error

        # Check for duplicate Name
        cursor.execute("SELECT patient_id FROM patients WHERE full_name_ar = %s", (name,))
        res = cursor.fetchone()
        
        if res:
            error = f"عذراً، الاسم ( {name} ) مسجل مسبقاً في النظام."
        elif nat_id:
            # Check for duplicate National ID
            cursor.execute("SELECT patient_id FROM patients WHERE national_id = %s", (nat_id,))
            res_id = cursor.fetchone()
            if res_id:
                error = f"عذراً، رقم الهوية ( {nat_id} ) مسجل مسبقاً لمريض آخر."
        
        if not error:
            sql = "INSERT INTO patients (file_number, full_name_ar, full_name_en, national_id, date_of_birth, gender, phone1, address, category, photo, allergies, medical_history) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"
            
            if conn.is_pg:
                sql += " RETURNING patient_id"

            try:
                cursor.execute(sql, (file_num, name, name_en, nat_id, dob, gender, phone, address, category, photo_path, allergies, history))
                
                if conn.is_pg:
                    # PostgresCursor with RETURNING already sets lastrowid in execute()
                    new_id = cursor.lastrowid
                else:
                    new_id = cursor.lastrowid
                
                conn.commit()
                return redirect(url_for('add_patient.add_patient', success_id=new_id))
            except Exception as e:
                error = "خطأ في التسجيل: " + str(e)

    success_id = request.args.get('success_id')
    new_patient = None
    if success_id:
        cursor.execute("SELECT * FROM patients WHERE patient_id = %s", (success_id,))
        new_patient = cursor.fetchone()


    html = header_html + """
    <style>
        :root {
            --reg-bg: #f5f6f8;
            --reg-card: #ffffff;
            --reg-text: #2c3e50;
            --reg-border: #e1e4e8;
            --reg-input: #f8f9fa;
            --primary-purple: #bf5af2;
        }

        [data-theme='dark'] {
            --reg-bg: #1a0b1d;
            --reg-card: rgba(26, 11, 29, 0.85);
            --reg-text: #ffffff;
            --reg-border: rgba(191, 90, 242, 0.2);
            --reg-input: rgba(255, 255, 255, 0.05);
        }

        .reg-body { background: transparent; color: var(--reg-text); transition: background 0.3s; }

        
        .glass-card, .success-card-theme {
            background: var(--reg-card) !important;
            backdrop-filter: blur(20px);
            border: 1px solid var(--reg-border) !important;
            border-radius: 20px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.1);
            overflow: hidden;
            transition: all 0.4s cubic-bezier(0.4, 0, 0.2, 1);
        }

        [data-theme='dark'] .glass-card, [data-theme='dark'] .success-card-theme {
            box-shadow: 0 20px 40px rgba(0,0,0,0.4), 0 0 20px rgba(191, 90, 242, 0.1);
            background: linear-gradient(145deg, rgba(40, 20, 50, 0.9), rgba(20, 10, 25, 0.95)) !important;
        }

        .form-control, .form-select { 
            background-color: var(--reg-input) !important; 
            color: var(--reg-text) !important; 
            border: 1px solid var(--reg-border) !important;
            border-radius: 12px !important;
            height: 45px !important;
            font-size: 0.95rem;
            transition: all 0.3s;
        }

        .form-control:focus, .form-select:focus {
            border-color: var(--primary-purple) !important;
            box-shadow: 0 0 0 4px rgba(191, 90, 242, 0.25) !important;
            background-color: rgba(191, 90, 242, 0.05) !important;
        }

        .btn-pill { border-radius: 50px; padding: 10px 24px; font-weight: 600; transition: all 0.4s ease; }
        
        .btn-primary { 
            background: linear-gradient(135deg, #bf5af2 0%, #5e5ce6 100%) !important; 
            border: none !important;
            box-shadow: 0 5px 15px rgba(191, 90, 242, 0.3);
        }
        .btn-primary:hover {
            transform: translateY(-2px);
            box-shadow: 0 8px 20px rgba(191, 90, 242, 0.4);
            filter: brightness(1.1);
        }

        .success-icon-bg { background-color: rgba(191, 90, 242, 0.1); border: 1px solid rgba(191, 90, 242, 0.2); }
        .text-themed-success { color: #bf5af2; }
        
        .dynamic-text-main { color: var(--reg-text); }
        .dynamic-text-muted { color: var(--reg-text); opacity: 0.6; }
        .dashed-divider { border-top: 1px dashed var(--reg-border); opacity: 0.5; }
        
        .id-badge-theme { 
            background: rgba(191, 90, 242, 0.15); 
            color: var(--primary-purple); 
            font-weight: 700;
            border: 1px solid rgba(191, 90, 242, 0.2);
        }

        .barcode-container-pure { 
            background: #ffffff !important; 
            padding: 12px !important; 
            border-radius: 14px;
            box-shadow: 0 4px 10px rgba(0,0,0,0.1);
        }

        .btn-secondary-theme { 
            background: rgba(255, 255, 255, 0.05); 
            color: var(--reg-text); 
            border: 1px solid var(--reg-border);
            backdrop-filter: blur(10px);
        }
        .btn-secondary-theme:hover {
            background: rgba(255, 255, 255, 0.1);
            border-color: var(--primary-purple);
        }
        
        .compact-section { 
            background: rgba(191, 90, 242, 0.03); 
            border-radius: 18px; 
            padding: 20px; 
            border: 1px solid var(--reg-border); 
        }

        /* Actions Card Styling */
        .actions-card {
            background: rgba(191, 90, 242, 0.05);
            border: 1px dashed var(--reg-border);
            border-radius: 18px;
            padding: 15px;
            margin-top: 25px;
            display: flex;
            gap: 12px;
        }

        .camera-capture-btn, .btn-translate-icon {
            color: var(--primary-purple) !important;
            transition: all 0.3s;
        }
        .camera-capture-btn:hover, .btn-translate-icon:hover {
            transform: scale(1.15);
            filter: drop-shadow(0 0 5px var(--primary-purple));
        }

        [data-theme='light'] .btn-primary {
            background: linear-gradient(135deg, #007aff 0%, #0051af 100%) !important;
            box-shadow: 0 5px 15px rgba(0, 122, 255, 0.2);
        }
        [data-theme='light'] .id-badge-theme { background: rgba(0, 122, 255, 0.1); color: #007aff; }
        [data-theme='light'] .text-themed-success { color: #28a745; }
        [data-theme='light'] .success-icon-bg { background-color: #e8f5e9; }

        .form-label { font-weight: 700; font-size: 0.85rem; margin-bottom: 0.5rem; opacity: 0.85; color: var(--reg-text); }
        
        /* Gender Toggle Styling */
        .gender-group {
            display: flex;
            background: var(--reg-input);
            border-radius: 14px;
            padding: 5px;
            border: 1px solid var(--reg-border);
        }
        .gender-item { flex: 1; text-align: center; }
        .gender-item input { display: none; }
        .gender-item label {
            display: block;
            padding: 8px 12px;
            border-radius: 10px;
            cursor: pointer;
            font-size: 0.9rem;
            transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
            color: var(--reg-text);
            opacity: 0.7;
            margin-bottom: 0;
        }
        .gender-item input:checked + label {
            background: var(--primary-purple);
            color: #ffffff !important;
            opacity: 1;
            font-weight: 700;
            box-shadow: 0 4px 12px rgba(191, 90, 242, 0.3);
        }
        [data-theme='light'] .gender-item input:checked + label {
            background: #007aff;
            box-shadow: 0 4px 12px rgba(0, 122, 255, 0.2);
        }
    </style>

    {% if success_id and new_patient %}
        <!-- Ultra Compact Success ID Card View -->

        <div class="container d-flex justify-content-center align-items-center" style="min-height: 60vh;">
            <div class="animate__animated animate__zoomIn" style="width: 100%; max-width: 280px;">
                
                <div class="card border-0 shadow-soft overflow-hidden success-card-theme mb-3" style="border-radius: 16px;">
                    <div class="card-body p-3 text-center">
                        
                        <!-- Success Checkmark -->
                        <div class="success-icon-bg rounded-circle d-flex align-items-center justify-content-center mx-auto mb-3" style="width: 50px; height: 50px;">
                            <i class="fas fa-check text-themed-success fa-lg"></i>
                        </div>
                        <h6 class="fw-bold mb-1 dynamic-text-main">تمت الإضافة بنجاح</h6>
                        <p class="mb-0 dynamic-text-muted" style="font-size: 0.75rem;">تم إنشاء ملف المريض</p>
                        
                        <hr class="my-2 dashed-divider">

                        <!-- Patient Info (Centered, Clean) -->
                        <div class="d-flex flex-column align-items-center mb-2">
                            {% if new_patient.photo %}
                                <img src="/{{ new_patient.photo }}" class="shadow-sm border-theme mb-2"
                                    style="width: 56px; height: 56px; object-fit: cover; border-radius: 50%;" onerror="this.onerror=null; this.src='/{{ new_patient.photo }}';">
                            {% else %}
                                <div class="shadow-sm d-flex align-items-center justify-content-center avatar-placeholder mb-2"
                                    style="width: 56px; height: 56px; border-radius: 50%;">
                                    <i class="fas fa-user fa-lg"></i>
                                </div>
                            {% endif %}
                            
                            <h6 class="fw-bold mb-2 mt-1 dynamic-text-main" style="font-size: 0.95rem; line-height: 1.2;">{{ new_patient.full_name_ar }}</h6>
                            
                            <div class="d-inline-flex align-items-center justify-content-center px-2 py-1 id-badge-theme" style="border-radius: 6px; font-size: 0.75rem;">
                                <i class="fas fa-id-card me-1 opacity-75"></i> {{ new_patient.file_number }}
                            </div>
                        </div>

                        <!-- Barcode Area (Extra Small) -> Forces White Background for Scanner -->
                        <div class="p-1 mx-auto barcode-container-pure" style="width: fit-content; border-radius: 8px;">
                            <canvas id="newBarcode" style="max-height: 28px;"></canvas>
                        </div>
                    </div>
                </div>

                <!-- Compact Action Buttons -->
                <div class="d-flex gap-2">
                    <a href="{{ url_for('book.book') }}?id={{ success_id }}" class="btn btn-primary fw-bold py-1 px-2 flex-grow-1 d-flex align-items-center justify-content-center gap-1" style="border-radius: 12px; font-size: 0.85rem;">
                        <span>حجز موعد</span> <i class="fas fa-arrow-left" style="font-size: 0.75rem;"></i>
                    </a>
                    <a href="{{ url_for('add_patient.add_patient') }}" class="btn btn-secondary-theme fw-bold py-1 px-2 flex-grow-1 d-flex align-items-center justify-content-center gap-1" style="border-radius: 10px; font-size: 0.8rem;">
                        <i class="fas fa-user-plus" style="font-size: 0.7rem;"></i> <span>مريض آخر</span>
                    </a>
                </div>
            </div>
        </div>

        <script src="https://cdn.jsdelivr.net/npm/jsbarcode@3.11.5/dist/JsBarcode.all.min.js"></script>
        <script>
            JsBarcode("#newBarcode", "{{ new_patient.file_number }}", {
                format: "CODE128",
                width: 1.1,
                height: 25,
                displayValue: true,
                fontSize: 9,
                background: "#ffffff",
                lineColor: "#000000",
                margin: 0
            });
        </script>
        
        </div>


    {% else %}
        <!-- Original Registration Form -->
        <div class="row justify-content-center reg-body">
            <div class="col-md-7">
                <div class="glass-card shadow-lg animate__animated animate__fadeInUp">
                    <div class="p-3 text-center border-bottom" style="background: rgba(191, 90, 242, 0.05);">
                        <h4 class="fw-bold mb-0 text-primary"><i class="fas fa-user-plus me-2"></i>تسجيل مريض جديد</h4>
                    </div>
                    <div class="p-3 p-md-4">
                        {% if error %}
                            <div class="alert alert-danger rounded-3 border-0 py-2 small animate__animated animate__shakeX">
                                <i class="fas fa-exclamation-triangle me-2"></i> {{ error }}
                            </div>
                        {% endif %}
                        <form method="POST" enctype="multipart/form-data">
                            <!-- Name Section -->
                            <div class="row g-2 mb-3">
                                <div class="col-md-6">
                                    <label class="form-label">الاسم الكامل (عربي)</label>
                                    <input type="text" name="full_name" id="nameAr" class="form-control" placeholder="الاسم الرباعي" required oninput="transliterateName(); detectGender()">
                                </div>
                                <div class="col-md-6">
                                    <label class="form-label">English Name</label>
                                    <div class="input-group">
                                        <input type="text" name="full_name_en" id="nameEn" class="form-control" placeholder="Full Name">
                                        <button type="button" class="btn-translate-icon" onclick="transliterateName()" title="ترجمة تلقائية">
                                            <i class="fas fa-language"></i>
                                        </button>
                                    </div>
                                </div>
                            </div>

                            <!-- Compact Details Card -->
                            <div class="compact-section mb-3">
                                <div class="row g-2 align-items-end">
                                    <div class="col-md-2">
                                        <label class="form-label">العمر</label>
                                        <input type="number" id="ageInput" class="form-control" placeholder="سنة" oninput="calculateBirthYear(this.value)">
                                    </div>
                                    <div class="col-md-3">
                                        <label class="form-label">رقم الهاتف</label>
                                        <input type="text" name="phone" class="form-control" placeholder="07XXXXXXXXX" required>
                                    </div>
                                    <div class="col-md-4">
                                        <label class="form-label">تاريخ الميلاد</label>
                                        <input type="date" name="dob" id="dobInput" class="form-control" required oninput="calculateAge(this.value)">
                                    </div>
                                    <div class="col-md-3">
                                        <label class="form-label text-center d-block">الجنس</label>
                                        <div class="gender-group">
                                            <div class="gender-item">
                                                <input type="radio" name="gender" value="male" id="g1" checked>
                                                <label for="g1">ذكر</label>
                                            </div>
                                            <div class="gender-item">
                                                <input type="radio" name="gender" value="female" id="g2">
                                                <label for="g2">أنثى</label>
                                            </div>
                                        </div>
                                    </div>
                                </div>
                            </div>
                                <!-- Helper Script for Offline Transliteration & Gender Detection -->
                                <script>
                                    function transliterateName() {
                                        const arName = document.getElementById('nameAr').value;
                                        const map = {
                                            'ا': 'a', 'أ': 'a', 'إ': 'e', 'آ': 'a', 'ب': 'b', 'ت': 't', 'ث': 'th', 'ج': 'j', 'ح': 'h', 'خ': 'kh', 'د': 'd', 'ذ': 'dh', 'ر': 'r', 'ز': 'z', 'س': 's', 'ش': 'sh', 'ص': 's', 'ض': 'd', 'ط': 't', 'ظ': 'z', 'ع': 'a', 'غ': 'gh', 'ف': 'f', 'ق': 'q', 'ك': 'k', 'ل': 'l', 'م': 'm', 'ن': 'n', 'ه': 'h', 'و': 'w', 'ي': 'y', 'ى': 'a', 'ة': 'a', 'ء': '', 'ئ': 'e', 'ؤ': 'o', ' ': ' ',
                                            'َ': 'a', 'ُ': 'u', 'ِ': 'i'
                                        };
                                        let enName = '';
                                        for (let i = 0; i < arName.length; i++) {
                                            const char = arName[i];
                                            enName += map[char] || char;
                                        }
                                        enName = enName.replace(/\\b\\w/g, l => l.toUpperCase());
                                        document.getElementById('nameEn').value = enName;
                                    }

                                    function detectGender() {
                                        const fullName = document.getElementById('nameAr').value.trim();
                                        if (!fullName) return;
                                        const firstName = fullName.split(' ')[0];
                                        
                                        const maleExceptions = ['حمزة', 'طلحة', 'عبيدة', 'عكرمة', 'قتادة', 'أسامة', 'معاوية', 'حذيفة', 'ميسرة', 'عروة'];
                                        const femaleNames = ['زينب', 'مريم', 'هند', 'سعاد', 'نور', 'هدى', 'منى', 'ضحى', 'سجى', 'تقى', 'لمى', 'حوراء', 'زهراء', 'فاطمة', 'خديجة', 'عائشة', 'سارة', 'نورا', 'ليلى', 'سلوى']; 

                                        let isFemale = false;
                                        
                                        // Rule 1: Starts with 'Abd' -> Male
                                        if (firstName.startsWith('عبد') || firstName.startsWith('العبد')) {
                                            isFemale = false;
                                        } 
                                        // Rule 2: Explicit Female Names
                                        else if (femaleNames.includes(firstName)) {
                                            isFemale = true;
                                        } 
                                        // Rule 3: Ends with Taa Marbuta (and not exception)
                                        else if (firstName.endsWith('ة')) {
                                            if (!maleExceptions.includes(firstName)) {
                                                isFemale = true;
                                            }
                                        }

                                        // Apply
                                        if (isFemale) {
                                            document.getElementById('g2').checked = true;
                                        } else {
                                            document.getElementById('g1').checked = true;
                                        }
                                    }

                                    function calculateBirthYear(age) {
                                        if (age && age > 0) {
                                            const year = new Date().getFullYear() - age;
                                            document.getElementById('dobInput').value = `${year}-01-01`;
                                        }
                                    }

                                    function calculateAge(dobStr) {
                                        if (!dobStr) return;
                                        const dob = new Date(dobStr);
                                        const today = new Date();
                                        let age = today.getFullYear() - dob.getFullYear();
                                        const m = today.getMonth() - dob.getMonth();
                                        if (m < 0 || (m === 0 && today.getDate() < dob.getDate())) {
                                            age--;
                                        }
                                        document.getElementById('ageInput').value = Math.max(0, age);
                                    }
                                </script>

                            <div class="row g-2 mb-3">
                                {% if classification_enabled %}
                                <div class="col-md-6">
                                    <label class="form-label">تصنيف المريض</label>
                                    <select name="category" class="form-select" required>
                                        <option value="normal">مريض عادي</option>
                                        <option value="senior">كبار السن</option>
                                        <option value="martyr">عوائل الشهداء</option>
                                        <option value="special">احتياجات خاصة</option>
                                    </select>
                                </div>
                                {% else %}
                                    <input type="hidden" name="category" value="normal">
                                {% endif %}
                                <div class="col-md-6">
                                    <label class="form-label d-block mb-2"><i class="fas fa-image me-1"></i> صورة المريض</label>
                                    <div class="d-flex align-items-center gap-2">
                                        <button type="button" class="camera-capture-btn" data-bs-toggle="modal" data-bs-target="#cameraModal" title="إفتح الكاميرا للتصوير">
                                            <i class="fas fa-camera"></i>
                                        </button>
                                        <div class="flex-grow-1">
                                            <input type="file" name="photo" class="form-control" accept="image/*" style="height: 42px;">
                                        </div>
                                    </div>
                                    <input type="hidden" name="photo_base64" id="photo_base64">
                                    <div id="photo_preview" class="mt-2 d-none text-center">
                                        <img src="" id="captured_image" class="img-fluid rounded-3 shadow-sm"
                                            style="max-height: 150px;">
                                        <br>
                                        <button type="button" class="btn btn-sm btn-outline-danger mt-1" onclick="clearPhoto()">
                                            <i class="fas fa-trash"></i> حذف الصورة
                                        </button>
                                    </div>
                                </div>
                            <div class="row g-2 mb-3">
                                <div class="col-md-6">
                                    <label class="form-label text-danger"><i class="fas fa-exclamation-triangle me-1"></i> الحساسية (Allergies)</label>
                                    <textarea name="allergies" class="form-control" rows="2" placeholder="بنسلين، أطعمة معينة، إلخ..."></textarea>
                                </div>
                                <div class="col-md-6">
                                    <label class="form-label"><i class="fas fa-notes-medical me-1"></i> التاريخ المرضي (Medical History)</label>
                                    <textarea name="medical_history" class="form-control" rows="2" placeholder="أمراض مزمنة، عمليات جراحية سابقة..."></textarea>
                                </div>
                            </div>

                            <div class="row g-2 mb-3">
                                <div class="col-6">
                                    <label class="form-label">المحافظة</label>
                                    <select id="governorateSelect" class="form-select" onchange="updateDistricts()">
                                        <option value="">تحديد المحافظة</option>
                                        <!-- Populated by JS -->
                                    </select>
                                </div>
                                <div class="col-6">
                                    <label class="form-label">المنطقة</label>
                                    <select id="districtSelect" class="form-select" onchange="updateAddress()">
                                        <option value="">تحديد المنطقة</option>
                                        <!-- Populated by JS -->
                                    </select>
                                </div>
                                <input type="hidden" name="address" id="fullAddress">
                            </div>

                                <script>
                                    const iraqLocations = {
                                        "ذي قار": ["الناصرية", "الرفاعي", "الشطرة", "الغراف", "سوق الشيوخ", "الجبايش", "قلعة سكر", "الدواية", "الإصلاح", "سيد دخيل", "البطحاء", "الفضليـة", "العكيكة", "كرمة بني سعيد", "الطار", "المنار", "الفجر", "أور", "النصر", "الفهود", "الحمار", "الخميسية", "حي الحبوبي", "حي السراي", "حي الصالحية", "حي النصر القديم", "حي الثورة", "حي الزهراء", "حي الفداء", "حي الشهداء القديمة", "حي الشرقية", "حي الغربية", "حي الصدور", "حي الشرطة", "حي المتنزه", "حي الحسين (ع)", "حي الرافدين", "حي الغدير", "حي التضامن", "حي أور", "حي سومر", "حي أريدو", "حي الزهور", "حي المهندسين", "حي الشموخ", "حي النصر الجديد", "حي الزهراء الجديدة", "حي الشهداء الجديدة", "حي أور الجديدة", "حي سومر الجديدة", "حي الغدير الثاني", "حي الجامعة", "حي العلماء", "حي الإسكان الصناعي", "حي الإسكان القديم", "حي المنصورية", "حي العروبة", "حي المطار", "حي السلام", "حي الفرات", "حي الرافدين الجديدة", "حي التضامن الثاني", "حي الصدور الجديدة", "حي الحبوبي الجديد", "حي الزهور الثاني", "حي أريدو الثاني", "حي الشموخ الثانية"],
                                        "بغداد": ["الكرخ", "رصافة", "الكاظمية", "الأعظمية", "المنصور", "الكرادة", "الدورة", "مدينة الصدر", "الغزالية", "العامرية", "الزعفرانية", "ببغداد الجديدة", "الشعلة", "حي العامل"],
                                        "البصرة": ["البصرة (المركز)", "الزبير", "القرنة", "شط العرب", "أبو الخصيب", "الفاو", "المدينة"],
                                        "أربيل": ["أربيل (المركز)", "سوران", "كويسنجق", "شقلاوة", "ميركسور"],
                                        "نينوى": ["الموصل", "تلعفر", "سنجار", "الحمدانية", "الشيخان", "برطلة"],
                                        "النجف": ["النجف (المركز)", "الكوفة", "المناذرة", "المشخاب"],
                                        "كربلاء": ["كربلاء (المركز)", "الهندية (طويريج)", "عين التمر", "الحسينية"],
                                        "كركوك": ["كركوك (المركز)", "الحويجة", "داقوق", "الدبس"],
                                        "ديالى": ["بعقوبة", "المقدادية", "الخالص", "خانقين", "بلد روز"],
                                        "الأنبار": ["الرمادي", "الفلوجة", "هيت", "القائم", "الرطبة", "حديثة"],
                                        "بابل": ["الحلة", "المسيب", "المحاويل", "الهاشمية"],
                                        "واسط": ["الكوت", "الصويرة", "العزيزية", "الحي", "النعمانية"],
                                        "القادسية": ["الديوانية", "الشامية", "عفك", "الحمزة"],
                                        "المثنى": ["السماوة", "الرميثة", "الخضر", "الوركاء"],
                                        "ميسان": ["العمارة", "الميمونة", "المجر الكبير", "علي الغربي", "الكحلاء"],
                                        "صلاح الدين": ["تكريت", "سامراء", "بيجي", "بلد", "الشرقاط", "الدجيل"],
                                        "دهوك": ["دهوك (المركز)", "زاخو", "سميل", "العمادية"],
                                        "السليمانية": ["السليمانية (المركز)", "رانية", "دوكان", "حلبجة", "كلار"]
                                    };

                                    const govSelect = document.getElementById('governorateSelect');
                                    const distSelect = document.getElementById('districtSelect');
                                    const fullAddress = document.getElementById('fullAddress');

                                    // Populate Governorates
                                    for (const gov in iraqLocations) {
                                        let option = document.createElement('option');
                                        option.value = gov;
                                        option.text = gov;
                                        govSelect.add(option);
                                    }

                                    function updateDistricts() {
                                        const selectedGov = govSelect.value;
                                        distSelect.innerHTML = '<option value="">اختر المنطقة...</option>'; // Reset

                                        if (selectedGov && iraqLocations[selectedGov]) {
                                            iraqLocations[selectedGov].forEach(dist => {
                                                let option = document.createElement('option');
                                                option.value = dist;
                                                option.text = dist;
                                                distSelect.add(option);
                                            });
                                        }
                                        updateAddress();
                                    }

                                    function updateAddress() {
                                        const gov = govSelect.value;
                                        const dist = distSelect.value;
                                        if (gov && dist) {
                                            fullAddress.value = gov + " - " + dist;
                                        } else if (gov) {
                                            fullAddress.value = gov;
                                        } else {
                                            fullAddress.value = "";
                                        }
                                    }
                                    
                                    // initialize value if exists
                                    setTimeout(() => updateAddress(), 100);
                                </script>
                            <div class="actions-card animate__animated animate__fadeIn">
                                <button type="submit" id="saveBtn" class="btn btn-primary btn-pill shadow-sm btn-save-sm flex-grow-1">
                                    <i class="fas fa-save me-1"></i> <span>حفظ المريض</span>
                                </button>
                                <a href="{{ url_for('patients.patients') }}" class="btn btn-light btn-pill btn-cancel-sm px-4">
                                    إلغاء
                                </a>
                            </div>

                            <script>
                                document.querySelector('form').addEventListener('submit', function(e) {
                                    // Ensure address is updated
                                    if (typeof updateAddress === 'function') updateAddress();
                                    
                                    const btn = document.getElementById('saveBtn');
                                    if (btn) {
                                        btn.disabled = true;
                                        btn.querySelector('span').innerText = 'جاري الحفظ...';
                                        btn.innerHTML = '<i class="fas fa-spinner fa-spin me-1"></i> <span>جاري الحفظ...</span>';
                                    }
                                });
                            </script>

                        </form>
                    </div>
                </div>
            </div>
        </div>
    {% endif %}

    <!-- Camera Modal -->
    <div class="modal fade" id="cameraModal" tabindex="-1" aria-hidden="true">
        <div class="modal-dialog modal-dialog-centered">
            <div class="modal-content">
                <div class="modal-header">
                    <h5 class="modal-title">التقاط صورة</h5>
                    <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
                </div>
                <div class="modal-body text-center">
                    <video id="video" width="100%" height="auto" autoplay playsinline class="bg-dark rounded-3"></video>
                    <canvas id="canvas" class="d-none"></canvas>
                </div>
                <div class="modal-footer justify-content-center">
                    <button type="button" class="btn btn-primary rounded-pill px-4" onclick="capturePhoto()"><i
                            class="fas fa-camera me-1"></i> التقاط</button>
                </div>
            </div>
        </div>
    </div>

    <script>
        let videoStream = null;
        const video = document.getElementById('video');
        const canvas = document.getElementById('canvas');
        const photoBase64 = document.getElementById('photo_base64');
        const photoPreview = document.getElementById('photo_preview');
        const capturedImage = document.getElementById('captured_image');

        // Start camera when modal is opened using Bootstrap events
        document.getElementById('cameraModal').addEventListener('shown.bs.modal', function () {
            if (navigator.mediaDevices && navigator.mediaDevices.getUserMedia) {
                navigator.mediaDevices.getUserMedia({ video: { facingMode: "user" } })
                    .then(stream => {
                        videoStream = stream;
                        video.srcObject = stream;
                    })
                    .catch(err => {
                        console.error("Error accessing camera: ", err);
                        alert("تعذر الوصول إلى الكاميرا. يرجى التأكد من السماح بالوصول وتوفر كاميرا.");
                    });
            } else {
                alert("المتصفح لا يدعم الوصول إلى الكاميرا.");
            }
        });

        // Stop camera when modal is closed
        document.getElementById('cameraModal').addEventListener('hidden.bs.modal', function () {
            if (videoStream) {
                videoStream.getTracks().forEach(track => track.stop());
                videoStream = null;
            }
        });

        function capturePhoto() {
            const context = canvas.getContext('2d');
            canvas.width = video.videoWidth;
            canvas.height = video.videoHeight;
            context.drawImage(video, 0, 0, canvas.width, canvas.height);

            const dataURL = canvas.toDataURL('image/png');
            photoBase64.value = dataURL;
            capturedImage.src = dataURL;
            photoPreview.classList.remove('d-none');

            // Close modal
            const modalEl = document.getElementById('cameraModal');
            const modal = bootstrap.Modal.getInstance(modalEl);
            modal.hide();
        }

        function clearPhoto() {
            photoBase64.value = '';
            capturedImage.src = '';
            photoPreview.classList.add('d-none');
        }
    </script>


    """ + footer_html
    
    return render_template_string(html, success_id=success_id, new_patient=new_patient, error=error, classification_enabled=session.get('patient_classification_enabled', True))

