footer_html = """
    </div> <!-- end container -->

    <!-- AUDIO ELEMENTS -->
    <audio id="ringtone" preload="auto" loop>
        <source src="https://www.soundjay.com/phone/phone-calling-1.mp3" type="audio/mpeg">
    </audio>
    <audio id="remoteAudio" autoplay playsinline></audio>

    <!-- INCOMING CALL POPUP -->
    <div id="incomingCallPopup" class="position-fixed top-0 start-50 translate-middle-x mt-3 glass-popup"
        style="z-index:99999;">
        <div class="card shadow-lg border-0 rounded-4 p-4 text-center bg-white" style="width:320px;">
            <div class="bg-success text-white rounded-circle mx-auto mb-3 d-flex align-items-center justify-content-center"
                style="width:70px;height:70px;">
                <i class="fas fa-phone fa-2x"></i>
            </div>
            <h5 class="fw-bold mb-1" id="callerNameDisplay">مكالمة واردة</h5>
            <p class="text-muted small mb-3">اضغط رد للتحدث</p>
            <div class="d-flex justify-content-center gap-3">
                <button class="btn btn-danger px-4 py-2 rounded-pill" onclick="rejectIncomingCall()">رفض</button>
                <button class="btn btn-success px-4 py-2 rounded-pill" onclick="acceptIncomingCall()">رد</button>
            </div>
        </div>
    </div>

    <!-- ACTIVE CALL OVERLAY -->
    <div id="activeCallOverlay" class="position-fixed bottom-0 start-0 m-3 glass-overlay" style="z-index:99999;">
        <div class="card shadow-lg border-0 rounded-4 p-3 bg-dark text-white" style="width:250px;">
            <div class="d-flex align-items-center gap-3">
                <div class="bg-success rounded-circle" style="width:12px;height:12px;animation:pulse 1s infinite;"></div>
                <div class="flex-grow-1">
                    <div class="fw-bold small" id="activeCallName">مكالمة جارية</div>
                    <div id="callTimer" style="font-family:monospace;">00:00</div>
                </div>
                <button class="btn btn-danger btn-sm rounded-circle" style="width:40px;height:40px;"
                    onclick="endCurrentCall()">
                    <i class="fas fa-phone-slash"></i>
                </button>
            </div>
        </div>
    </div>

    <!-- CONNECTION STATUS -->
    <div id="connectionStatus" class="position-fixed bottom-0 end-0 m-2 px-2 py-1 rounded-pill bg-secondary text-white"
        style="font-size:0.65rem; z-index:9999;">
        <i class="fas fa-circle me-1" id="statusDot"></i>
        <span id="statusText">جاري الاتصال...</span>
    </div>

    <style>
        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.5; }
        }
    </style>

    <script src="https://unpkg.com/peerjs@1.5.2/dist/peerjs.min.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>

    <script>
        const userId = "{{ session.get('user_id', '0') }}";
        const userName = "{{ session.get('full_name', 'مستخدم') }}";
        const peerId = "hospital_" + userId;

        let peer = null;
        let currentCall = null;
        let localStream = null;
        let timerInterval = null;
        let callSeconds = 0;

        const ringtoneEl = document.getElementById('ringtone');
        const remoteAudioEl = document.getElementById('remoteAudio');

        if (userId !== '0') {
            ringtoneEl.load();
            initializeCallSystem();
        }

        let isLocalUp = true;
        let isPeerUp = false;

        async function checkSystemHealth() {
            try {
                const controller = new AbortController();
                const id = setTimeout(() => controller.abort(), 2000);
                
                const res = await fetch('/api_ping', { signal: controller.signal });
                clearTimeout(id);
                
                if (res.ok) {
                    isLocalUp = true;
                } else {
                    isLocalUp = false;
                }
            } catch (e) {
                isLocalUp = false;
            }
            updateStatusUI();
        }

        function updateStatusUI() {
            const dot = document.getElementById('statusDot');
            const text = document.getElementById('statusText');

            if (isPeerUp) {
                dot.style.color = '#2ecc71';
                dot.classList.remove('fa-wifi-slash');
                dot.classList.add('fa-circle');
                text.textContent = 'جاهز للاتصال';
            } else if (isLocalUp) {
                dot.style.color = '#2ecc71';
                dot.classList.remove('fa-circle');
                dot.classList.add('fa-network-wired');
                text.textContent = 'النظام متصل';
            } else {
                dot.style.color = '#e74c3c';
                dot.classList.remove('fa-circle');
                dot.classList.add('fa-wifi-slash');
                text.textContent = 'غير متصل';
            }
        }

        function initializeCallSystem() {
            peer = new Peer(peerId, {
                host: '0.peerjs.com',
                port: 443,
                secure: true,
                debug: 0
            });

            peer.on('open', function (id) {
                isPeerUp = true;
                updateStatusUI();
            });

            peer.on('call', function (call) {
                currentCall = call;
                let callerName = 'زميل';
                if (call.metadata && call.metadata.name) {
                    callerName = call.metadata.name;
                }
                document.getElementById('callerNameDisplay').textContent = callerName;
                document.getElementById('incomingCallPopup').classList.add('show');
                playRingtone();
            });

            peer.on('error', function (err) {
                isPeerUp = false;
                updateStatusUI();
            });

            peer.on('disconnected', function () {
                isPeerUp = false;
                updateStatusUI();
                setTimeout(() => { if(!peer.destroyed) peer.reconnect(); }, 2000);
            });
        }

        setInterval(checkSystemHealth, 5000);
        checkSystemHealth();

        function playRingtone() {
            ringtoneEl.currentTime = 0;
            ringtoneEl.volume = 1.0;
            const playPromise = ringtoneEl.play();
            if (playPromise) {
                playPromise.catch(e => {
                    console.log('Ringtone blocked, will play on interaction');
                });
            }
        }

        function stopRingtone() {
            ringtoneEl.pause();
            ringtoneEl.currentTime = 0;
        }

        window.makeCall = async function (targetUserId, targetName) {
            if (!peer || !peer.open) {
                alert('النظام غير جاهز، يرجى الانتظار');
                return false;
            }

            try {
                localStream = await navigator.mediaDevices.getUserMedia({ audio: true });
            } catch (e) {
                const ctx = new (window.AudioContext || window.webkitAudioContext)();
                const oscillator = ctx.createOscillator();
                const dest = ctx.createMediaStreamDestination();
                oscillator.connect(dest);
                oscillator.start();
                localStream = dest.stream;
            }

            const targetPeerId = "hospital_" + targetUserId;
            currentCall = peer.call(targetPeerId, localStream, {
                metadata: { name: userName }
            });

            if (!currentCall) {
                alert('فشل الاتصال');
                return false;
            }

            setupCallEvents(currentCall);
            showActiveCallUI(targetName);
            return true;
        };

        function acceptIncomingCall() {
            document.getElementById('incomingCallPopup').classList.remove('show');
            stopRingtone();

            navigator.mediaDevices.getUserMedia({ audio: true })
                .then(function (stream) {
                    localStream = stream;
                    currentCall.answer(stream);
                    setupCallEvents(currentCall);
                    showActiveCallUI(document.getElementById('callerNameDisplay').textContent);
                })
                .catch(function (e) {
                    const ctx = new (window.AudioContext || window.webkitAudioContext)();
                    const oscillator = ctx.createOscillator();
                    const dest = ctx.createMediaStreamDestination();
                    oscillator.connect(dest);
                    oscillator.start();
                    localStream = dest.stream;
                    currentCall.answer(localStream);
                    setupCallEvents(currentCall);
                    showActiveCallUI(document.getElementById('callerNameDisplay').textContent);
                });
        }

        function rejectIncomingCall() {
            document.getElementById('incomingCallPopup').classList.remove('show');
            stopRingtone();
            if (currentCall) {
                currentCall.close();
                currentCall = null;
            }
        }

        function setupCallEvents(call) {
            call.on('stream', function (remoteStream) {
                remoteAudioEl.srcObject = remoteStream;
                remoteAudioEl.volume = 1.0;

                const playPromise = remoteAudioEl.play();
                if (playPromise) {
                    playPromise.catch(e => {
                        document.body.addEventListener('click', function tryPlay() {
                            remoteAudioEl.play();
                            document.body.removeEventListener('click', tryPlay);
                        }, { once: true });
                    });
                }
            });

            call.on('close', function () {
                endCurrentCall();
            });

            call.on('error', function (err) {
                endCurrentCall();
            });
        }

        function showActiveCallUI(name) {
            document.getElementById('activeCallName').textContent = name;
            document.getElementById('activeCallOverlay').classList.add('show');
            callSeconds = 0;
            document.getElementById('callTimer').textContent = '00:00';

            if (timerInterval) clearInterval(timerInterval);
            timerInterval = setInterval(function () {
                callSeconds++;
                const mins = Math.floor(callSeconds / 60);
                const secs = callSeconds % 60;
                document.getElementById('callTimer').textContent =
                    (mins < 10 ? '0' : '') + mins + ':' + (secs < 10 ? '0' : '') + secs;
            }, 1000);

            window.gCall = currentCall;
        }

        function endCurrentCall() {
            if (currentCall) {
                currentCall.close();
                currentCall = null;
            }

            if (localStream) {
                localStream.getTracks().forEach(t => t.stop());
                localStream = null;
            }

            if (timerInterval) {
                clearInterval(timerInterval);
                timerInterval = null;
            }

            stopRingtone();
            remoteAudioEl.srcObject = null;

            document.getElementById('activeCallOverlay').classList.remove('show');
            document.getElementById('incomingCallPopup').classList.remove('show');

            window.gCall = null;
        }

        window.terminateCallGlobal = endCurrentCall;
        window.startCallSystem = window.makeCall;

        document.body.addEventListener('click', function enableAudio() {
            ringtoneEl.play().then(() => ringtoneEl.pause()).catch(() => { });
            const ctx = new (window.AudioContext || window.webkitAudioContext)();
            ctx.resume();
        }, { once: true });
    </script>
</body>
</html>
"""
