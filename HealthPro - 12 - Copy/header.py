header_html = """
<!DOCTYPE html>
<html lang="ar" dir="rtl" data-theme="light">

<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>HealthPro Premier OS</title>
    <!-- Dependencies -->
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.rtl.min.css">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <link rel="stylesheet" href="{{ url_for('static', filename='apple_ui.css') }}">
    <link rel="stylesheet" href="{{ url_for('static', filename='apple_ui_pro.css') }}">
    <script src="{{ url_for('static', filename='speed_core.js') }}" defer></script>
    <style>
        .theme-adaptive-btn { background: var(--card) !important; color: var(--text) !important; border: 1px solid var(--border) !important; transition: all 0.3s; }
        .theme-adaptive-user-bg { background: rgba(var(--primary-rgb), 0.1) !important; }
        [data-theme='dark'] .theme-adaptive-user-bg { background: rgba(255, 255, 255, 0.05) !important; }
        .apple-nav { transition: background 0.4s ease, border-color 0.4s ease, box-shadow 0.4s ease !important; }
    </style>
</head>

<body>
    <!-- Live Animated Background -->
    <div class="mesh-bg">
        <div class="blob1"></div>
        <div class="blob2"></div>
        <div class="blob3"></div>
    </div>

    <!-- Top Minimal Bar -->
    <div class="apple-nav no-print shadow-sm d-flex align-items-center px-3 justify-content-between">
        <div class="d-flex align-items-center">
            <!-- Distinctive Back Button -->
            <a href="javascript:history.back()"
                class="btn rounded-circle shadow-sm p-0 d-flex align-items-center justify-content-center me-3 hover-scale border-0 theme-adaptive-btn"
                style="width: 40px; height: 40px;"
                title="عودة">
                <i class="fas fa-chevron-right text-primary"></i>
            </a>
            <a href="{{ url_for('dashboard.dashboard') }}" class="text-decoration-none d-flex align-items-center">
                <span class="fw-bold" style="color: var(--text) !important;">Premier <span
                        class="text-primary">OS</span></span>
            </a>
        </div>

        <div class="d-none d-lg-flex flex-column text-center px-4">
            <div class="fw-bold small mb-0" id="current-date" style="color: var(--text);"></div>
            <div class="text-muted" style="font-size: 0.65rem;" id="current-time"></div>
        </div>

        <div class="d-flex align-items-center gap-3">
            <!-- Connection Health (The Pulse) -->
            <div class="d-none d-xl-flex align-items-center border-end pe-3 me-2" id="connection-widget-container">
                <div class="connection-widget">
                    <div class="status-pulse" id="connectionPulse"></div>
                    <span class="status-text h-connection-text" id="connectionText" style="color: var(--text);">متصل بالسيرفر</span>
                </div>
            </div>

            <!-- User Info (Smart Gender & Role) -->
            <div class="text-end d-none d-md-flex align-items-center gap-2 border-end pe-3 me-1">
                <div class="d-flex flex-column align-items-end" style="line-height: 1.2;">
                    <div class="fw-bold small mb-0" style="color: var(--text);">{{ session.get('full_name', 'مستخدم') }}</div>
                </div>
                <div class="rounded-circle d-flex align-items-center justify-content-center shadow-sm theme-adaptive-user-bg"
                    style="width: 38px; height: 38px; border: 1px solid rgba(255,255,255,0.1);">
                    <i class="fas fa-user-tie text-primary" style="font-size: 1.1rem;"></i>
                </div>
            </div>

            <!-- Theme Toggle -->
            <div onclick="toggleTheme()" style="cursor:pointer;" class="p-2" id="theme-btn" title="تغيير المظهر">
                <i class="fas fa-moon"></i>
            </div>

            <!-- Settings & Logout -->
            {% if session.get('role') == 'admin' or 'settings' in session.get('permissions', []) %}
                <a href="{{ url_for('settings.view_settings') }}" class="p-2 text-dark" style="color: var(--text-color) !important;" title="الإعدادات">
                    <i class="fas fa-cog"></i>
                </a>
            {% endif %}

            <a href="{{ url_for('logout.logout') }}" class="p-2 text-danger no-pjax" title="خروج">
                <i class="fas fa-sign-out-alt"></i>
            </a>
        </div>
    </div>

    <script>
        // Theme Engine
        function toggleTheme() {
            const html = document.documentElement;
            const current = html.getAttribute('data-theme');
            const next = current === 'light' ? 'dark' : 'light';
            html.setAttribute('data-theme', next);
            localStorage.setItem('theme', next);
            updateThemeIcon(next);
        }

        function updateThemeIcon(theme) {
            const btn = document.getElementById('theme-btn');
            btn.innerHTML = theme === 'dark' ? '<i class="fas fa-sun text-warning"></i>' : '<i class="fas fa-moon"></i>';
        }

        if (localStorage.getItem('theme') === 'dark') {
            document.documentElement.setAttribute('data-theme', 'dark');
            updateThemeIcon('dark');
        }

        // Live Clock
        function toArabicDigits(str) {
            return str.replace(/\d/g, d => '٠١٢٣٤٥٦٧٨٩'[d]);
        }

        const daysAr = { 0: 'الأحد', 1: 'الاثنين', 2: 'الثلاثاء', 3: 'الأربعاء', 4: 'الخميس', 5: 'الجمعة', 6: 'السبت' };
        const monthsAr = { 0: 'يناير', 1: 'فبراير', 2: 'مارس', 3: 'أبريل', 4: 'مايو', 5: 'يونيو', 6: 'يوليو', 7: 'أغسطس', 8: 'سبتمبر', 9: 'أكتوبر', 10: 'نوفمبر', 11: 'ديسمبر' };

        setInterval(() => {
            const now = new Date();
            const dayName = daysAr[now.getDay()];
            const dayNum = toArabicDigits(now.getDate().toString());
            const monthName = monthsAr[now.getMonth()];
            document.getElementById('current-date').innerText = `${dayName}، ${dayNum} ${monthName}`;

            let hours = now.getHours();
            const minutes = now.getMinutes().toString().padStart(2, '0');
            const ampm = hours >= 12 ? 'م' : 'ص';
            hours = hours % 12;
            hours = hours ? hours : 12;
            const timeStr = toArabicDigits(`${hours}:${minutes}`);
            document.getElementById('current-time').innerText = `${timeStr} ${ampm}`;
        }, 1000);

        function updateConnectionStatus() {
            const pulse = document.getElementById('connectionPulse');
            const text = document.getElementById('connectionText');
            
            if (navigator.onLine) {
                pulse.style.background = '#2ecc71';
                pulse.style.boxShadow = '0 0 10px rgba(46, 204, 113, 0.5)';
                text.innerText = 'متصل بالسيرفر';
                text.style.color = '';
            } else {
                pulse.style.background = '#e74c3c';
                pulse.style.boxShadow = '0 0 10px rgba(231, 76, 60, 0.5)';
                text.innerText = 'انقطع الاتصال';
                text.style.color = '#e74c3c';
            }
        }

        window.addEventListener('online', updateConnectionStatus);
        window.addEventListener('offline', updateConnectionStatus);
        updateConnectionStatus();
    </script>

    <div id="pjax-container" class="container mt-4 pb-5">
        {% with messages = get_flashed_messages(with_categories=true) %}
            {% if messages %}
                {% for category, message in messages %}
                    <div class="alert bg-white shadow-sm border-0 rounded-4 text-center mb-4">
                        <span class="text-{{ category }} fw-bold">{{ message }}</span>
                    </div>
                {% endfor %}
            {% endif %}
        {% endwith %}
"""
