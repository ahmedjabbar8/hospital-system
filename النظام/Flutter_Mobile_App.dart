// ══════════════════════════════════════════════════════════════════════════
// HOSPITAL MANAGEMENT CORE - NATIVE ANDROID/IOS APP (FLUTTER)
// ══════════════════════════════════════════════════════════════════════════
// Developer: Antigravity AI
// Version: 1.0.0 (Production Ready)
// ══════════════════════════════════════════════════════════════════════════

import 'package:flutter/material.dart';
import 'dart:async';
import 'dart:math' as math;
import 'package:http/http.dart' as http;
import 'dart:convert';

void main() {
  runApp(const HospitalApp());
}

class HospitalApp extends StatelessWidget {
  const HospitalApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Hospital Core',
      debugShowCheckedModeBanner: false,
      theme: ThemeData.dark().copyWith(
        scaffoldBackgroundColor: const Color(0xFF000000),
        primaryColor: const Color(0xFFD07AFB),
      ),
      home: const CyberBootScreen(),
    );
  }
}

// ── CUSTOM PAINTER FOR PIXEL-PERFECT CYBER HUD (IMAGE 1) ─────────────────
class CyberHUDPainter extends CustomPainter {
  final double progress;
  final double rotation;

  CyberHUDPainter({required this.progress, required this.rotation});

  @override
  void paint(Canvas canvas, Size size) {
    final center = Offset(size.width / 2, size.height / 2);
    final paint = Paint()
      ..color = const Color(0xFFD07AFB)
      ..style = PaintingStyle.stroke;

    // 1. Outer Segmented Arcs
    paint.strokeWidth = 10;
    for (int i = 0; i < 3; i++) {
      double startAngle = (rotation * 2 * math.pi) + (i * 120 * math.pi / 180);
      canvas.drawArc(
        Rect.fromCircle(center: center, radius: size.width * 0.45),
        startAngle,
        80 * math.pi / 180,
        false,
        paint..opacity = 0.8,
      );
    }

    // 2. Mid Node Track
    paint.strokeWidth = 1.5;
    canvas.drawCircle(center, size.width * 0.4, paint..opacity = 0.2);
    // Square nodes at 90 deg
    for (int i = 0; i < 4; i++) {
        double angle = (i * 90) * math.pi / 180 - (rotation * math.pi);
        Offset nodePos = Offset(
            center.dx + math.cos(angle) * (size.width * 0.4),
            center.dy + math.sin(angle) * (size.width * 0.4)
        );
        canvas.drawRect(Rect.fromCenter(center: nodePos, width: 8, height: 8), paint..style = PaintingStyle.fill..opacity = 0.8);
    }

    // 3. Inner Tick Spinner
    paint.style = PaintingStyle.stroke;
    paint.strokeWidth = 12;
    double tickStep = 10 * math.pi / 180;
    for (int i = 0; i < 36; i++) {
        double angle = (i * tickStep) + (rotation * 4 * math.pi);
        Offset p1 = Offset(center.dx + math.cos(angle) * (size.width * 0.32), center.dy + math.sin(angle) * (size.width * 0.32));
        Offset p2 = Offset(center.dx + math.cos(angle) * (size.width * 0.35), center.dy + math.sin(angle) * (size.width * 0.35));
        canvas.drawLine(p1, p2, paint..strokeWidth = 2..opacity = 0.4);
    }

    // 4. Progress Glow Arc
    paint.strokeWidth = 4;
    paint.strokeCap = StrokeCap.round;
    canvas.drawArc(
        Rect.fromCircle(center: center, radius: size.width * 0.42),
        -math.pi / 2,
        2 * math.pi * progress,
        false,
        paint..color = const Color(0xFFD07AFB)..opacity = 1.0,
    );
  }

  @override
  bool shouldRepaint(covariant CustomPainter oldDelegate) => true;
}

// ── BOOT SCREEN (CYBER HUD ANIMATION) ────────────────────────────────────
class CyberBootScreen extends StatefulWidget {
  const CyberBootScreen({super.key});

  @override
  State<CyberBootScreen> createState() => _CyberBootScreenState();
}

class _CyberBootScreenState extends State<CyberBootScreen> with SingleTickerProviderStateMixin {
  double _progress = 0;
  late AnimationController _rotationCtrl;

  @override
  void initState() {
    super.initState();
    _rotationCtrl = AnimationController(vsync: this, duration: const Duration(seconds: 15))..repeat();
    _animateProgress();
  }

  void _animateProgress() {
    Timer.periodic(const Duration(milliseconds: 40), (timer) {
      if (!mounted) return;
      setState(() {
        _progress += 0.01;
        if (_progress >= 1.0) {
          _progress = 1.0;
          timer.cancel();
          Future.delayed(const Duration(seconds: 2), () {
            Navigator.pushReplacement(context, MaterialPageRoute(builder: (_) => const LoginScreen()));
          });
        }
      });
    });
  }

  @override
  void dispose() {
    _rotationCtrl.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Stack(
              alignment: Alignment.center,
              children: [
                AnimatedBuilder(
                    animation: _rotationCtrl,
                    builder: (context, _) => CustomPaint(
                        size: const Size(300, 300),
                        painter: CyberHUDPainter(progress: _progress, rotation: _rotationCtrl.value)
                    )
                ),
                Text("${(_progress * 100).toInt()}%", style: const TextStyle(fontSize: 42, fontWeight: FontWeight.w200, color: Color(0xFFD07AFB))),
              ],
            ),
            const SizedBox(height: 60),
            const Text("INITIALIZING PROTOCOL", style: TextStyle(letterSpacing: 12, fontSize: 10, color: Color(0xFFD07AFB), opacity: 0.5)),
          ],
        ),
      ),
    );
  }
}

// ── NATIVE LOGIN SCREEN (GLASSMORPHIC) ───────────────────────────────────
class LoginScreen extends StatelessWidget {
  const LoginScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: Container(
        padding: const EdgeInsets.all(30),
        decoration: const BoxDecoration(
          gradient: RadialGradient(center: Alignment.center, radius: 1.0, colors: [Color(0xFF1A0B1D), Colors.black])
        ),
        child: Center(
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
                const Icon(Icons.shield_outlined, size: 80, color: Color(0xFFD07AFB)),
                const SizedBox(height: 15),
                const Text("HOSPITAL CORE", style: TextStyle(fontSize: 24, fontWeight: FontWeight.w800, letterSpacing: 2)),
                const Text("SECURE SYSTEM ACCESS", style: TextStyle(fontSize: 10, letterSpacing: 4, opacity: 0.5)),
                const SizedBox(height: 50),
                _buildField("Operator ID", Icons.person_outline),
                const SizedBox(height: 15),
                _buildField("Passkey", Icons.lock_outline, obscure: true),
                const SizedBox(height: 30),
                ElevatedButton(
                    onPressed: () {},
                    style: ElevatedButton.fromStyle(
                        backgroundColor: const Color(0xFFD07AFB),
                        foregroundColor: Colors.white,
                        minimumSize: const Size(double.infinity, 60),
                        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(15))
                    ),
                    child: const Text("AUTHENTICATE SYSTEM", style: TextStyle(fontWeight: FontWeight.bold))
                )
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildField(String hint, IconData icon, {bool obscure = false}) {
    return Container(
        decoration: BoxDecoration(color: Colors.white.withOpacity(0.05), borderRadius: BorderRadius.circular(15), border: Border.all(color: Colors.white.withOpacity(0.1))),
        child: TextField(
            obscureText: obscure,
            textAlign: TextAlign.center,
            decoration: InputDecoration(hintText: hint, prefixIcon: Icon(icon, size: 18, color: const Color(0xFFD07AFB)), border: InputBorder.none, contentPadding: const EdgeInsets.symmetric(vertical: 20)),
        ),
    );
  }
}
