import 'dart:math' as math;
import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'dart:convert';
import 'dart:typed_data';
import 'package:audioplayers/audioplayers.dart';
import 'package:speech_to_text/speech_to_text.dart' as stt;

void main() {
  runApp(const StarkHUDApp());
}

class StarkHUDApp extends StatelessWidget {
  const StarkHUDApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'J.A.R.V.I.S. Stark HUD Mega-Core',
      debugShowCheckedModeBanner: false,
      theme: ThemeData.dark().copyWith(
        scaffoldBackgroundColor: const Color(0xFF05070B),
        primaryColor: const Color(0xFFFFD700), // Emas Mewah Mark LXXXV
        colorScheme: const ColorScheme.dark(
          primary: Color(0xFFFFD700),
          secondary: Color(0xFFFFA500),
          surface: Color(0xFF111318),
        ),
      ),
      home: const HUDHomeScreen(),
    );
  }
}

class HUDHomeScreen extends StatefulWidget {
  const HUDHomeScreen({super.key});

  @override
  State<HUDHomeScreen> createState() => _HUDHomeScreenState();
}

class _HUDHomeScreenState extends State<HUDHomeScreen> with TickerProviderStateMixin {
  final TextEditingController _controller = TextEditingController();
  final List<Map<String, String>> _messages = [];
  bool _isLoading = false;

  final AudioPlayer _audioPlayer = AudioPlayer();
  final String serverUrl = "https://worker-production-792b.up.railway.app";

  // Inisialisasi Speech to Text
  late stt.SpeechToText _speech;
  bool _isListening = false;

  // Controller Animasi Nano-Tech & Arc Reactor Emas
  late AnimationController _reactorController;
  late AnimationController _nanoActivityController;

  @override
  void initState() {
    super.initState();
    _speech = stt.SpeechToText();
    
    _reactorController = AnimationController(
      vsync: this,
      duration: const Duration(seconds: 6),
    )..repeat();

    _nanoActivityController = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 1200),
    );

    _addJarvisMessage("Nano-Tech Arc Reactor & Voice Engine Online. Ready, Boss.");
  }

  void _addJarvisMessage(String text) {
    setState(() {
      _messages.add({"sender": "jarvis", "text": text});
    });
  }

  // 🎙️ FUNGSI MENDENGARKAN SUARA NYATA (SPEECH-TO-TEXT)
  void _listenVoice() async {
    if (!_isListening) {
      bool available = await _speech.initialize(
        onStatus: (status) {
          print('Speech status: $status');
          if (status == 'notListening' || status == 'done') {
            setState(() => _isListening = false);
            _nanoActivityController.reverse();
          }
        },
        onError: (error) => print('Speech error: $error'),
      );

      if (available) {
        setState(() {
          _isListening = true;
          _nanoActivityController.forward(from: 0.0);
        });
        
        _speech.listen(
          onResult: (result) {
            setState(() {
              _controller.text = result.recognizedWords;
            });
            // Jika kata-kata sudah final, otomatis kirim ke Jarvis
            if (result.finalResult && _controller.text.isNotEmpty) {
              _sendMessage(_controller.text);
            }
          },
          localeId: 'id_ID', // Atur ke Bahasa Indonesia (bisa diganti en_US jika ingin Inggris)
        );
      } else {
        print("Speech recognition tidak diizinkan / didukung di perangkat ini.");
      }
    } else {
      setState(() => _isListening = false);
      _speech.stop();
      _nanoActivityController.reverse();
    }
  }

  Future<void> _sendMessage(String text) async {
    if (text.trim().isEmpty) return;

    if (_isListening) {
      _speech.stop();
      setState(() => _isListening = false);
    }

    setState(() {
      _messages.add({"sender": "user", "text": text});
      _isLoading = true;
    });

    _nanoActivityController.forward(from: 0.0);
    _controller.clear();

    try {
      final response = await http.post(
        Uri.parse("$serverUrl/chat"),
        headers: {"Content-Type": "application/json"},
        body: jsonEncode({"message": text, "is_voice_input": false}),
      );

      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        String replyText = data["reply"] ?? "Protocol executed, Boss.";

        _addJarvisMessage(replyText);

        if (data["audio_base64"] != null && data["audio_base64"].isNotEmpty) {
          try {
            Uint8List audioBytes = base64Decode(data["audio_base64"]);
            await _audioPlayer.stop();
            await _audioPlayer.play(BytesSource(audioBytes));
          } catch (audioErr) {
            print("Audio Playback Error: $audioErr");
          }
        }
      } else {
        _addJarvisMessage("🚨 Connection failed to Stark Mainframe.");
      }
    } catch (e) {
      _addJarvisMessage("🚨 Network error: $e");
    } finally {
      setState(() {
        _isLoading = false;
      });
      _nanoActivityController.reverse();
    }
  }

  void _executeQuickCommand(String command) {
    _sendMessage(command);
  }

  @override
  void dispose() {
    _reactorController.dispose();
    _nanoActivityController.dispose();
    _audioPlayer.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: Text(
          _isListening ? "J.A.R.V.I.S. // LISTENING..." : "J.A.R.V.I.S. // NANO-GOLD HUD",
          style: TextStyle(
            letterSpacing: 2, 
            fontSize: 15, 
            color: _isListening ? Colors.redAccent : const Color(0xFFFFD700), 
            fontWeight: FontWeight.bold
          ),
        ),
        backgroundColor: const Color(0xFF111318).withValues(alpha: 0.8),
        elevation: 4,
        shadowColor: const Color(0xFFFFD700).withValues(alpha: 0.3),
        centerTitle: true,
      ),
      body: Stack(
        children: [
          // 🌀 BACKGROUND NANO-TECH GOLD ARC REACTOR
          Center(
            child: AnimatedBuilder(
              animation: Listenable.merge([_reactorController, _nanoActivityController]),
              builder: (context, child) {
                return CustomPaint(
                  size: const Size(360, 360),
                  painter: NanoGoldReactorPainter(
                    rotationValue: _reactorController.value,
                    activityLevel: (_isLoading || _isListening) ? 1.0 : _nanoActivityController.value,
                  ),
                );
              },
            ),
          ),

          // 📱 LAPISAN UTAMA HUD (CHAT & KONTROL)
          Column(
            children: [
              // 🎛️ PANEL KONTROL PINTASAN EMAS
              Container(
                padding: const EdgeInsets.symmetric(vertical: 8, horizontal: 12),
                color: const Color(0xFF111318).withValues(alpha: 0.85),
                child: SingleChildScrollView(
                  scrollDirection: Axis.horizontal,
                  child: Row(
                    children: [
                      _buildQuickButton("📊 Status", "Cek status kesehatan sistem server sekarang"),
                      const SizedBox(width: 8),
                      _buildQuickButton("🧠 Journal", "Tampilkan jurnal aktivitas harian sistem"),
                      const SizedBox(width: 8),
                      _buildQuickButton("🔒 Lockdown", "Aktifkan atau cek status lockdown sistem"),
                      const SizedBox(width: 8),
                      _buildQuickButton("🛰️ Sentinel", "Jalankan pengecekan uptime server"),
                      const SizedBox(width: 8),
                      _buildQuickButton("👁️ Vision", "Periksa kondisi kamera atau visual sekitar"),
                    ],
                  ),
                ),
              ),

              // 💬 AREA CHAT DENGAN BUBBLE SEAMLESS
              Expanded(
                child: ListView.builder(
                  padding: const EdgeInsets.all(16),
                  itemCount: _messages.length,
                  itemBuilder: (context, index) {
                    final msg = _messages[index];
                    final isUser = msg["sender"] == "user";
                    
                    return Align(
                      alignment: isUser ? Alignment.centerRight : Alignment.centerLeft,
                      child: Container(
                        margin: const EdgeInsets.symmetric(vertical: 6),
                        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
                        constraints: BoxConstraints(maxWidth: MediaQuery.of(context).size.width * 0.75),
                        decoration: BoxDecoration(
                          color: isUser 
                              ? const Color(0xFFFFD700).withValues(alpha: 0.15) 
                              : const Color(0xFF111318).withValues(alpha: 0.75),
                          borderRadius: BorderRadius.only(
                            topLeft: const Radius.circular(12),
                            topRight: const Radius.circular(12),
                            bottomLeft: isUser ? const Radius.circular(12) : const Radius.circular(0),
                            bottomRight: isUser ? const Radius.circular(0) : const Radius.circular(12),
                          ),
                          border: Border.all(
                            color: isUser 
                                ? const Color(0xFFFFD700).withValues(alpha: 0.6) 
                                : const Color(0xFFFFD700).withValues(alpha: 0.25),
                            width: 1,
                          ),
                        ),
                        child: Text(
                          msg["text"] ?? "",
                          style: TextStyle(
                            color: isUser ? const Color(0xFFFFF8E7) : const Color(0xFFFFE082),
                            fontFamily: 'monospace',
                            fontSize: 13,
                            height: 1.3,
                          ),
                        ),
                      ),
                    );
                  },
                ),
              ),
              
              if (_isLoading || _isListening)
                Padding(
                  padding: const EdgeInsets.all(8.0),
                  child: LinearProgressIndicator(
                    color: _isListening ? Colors.redAccent : const Color(0xFFFFD700),
                  ),
                ),

              // ⌨️ INPUT COMMAND & REAL MIC BUTTON
              Container(
                padding: const EdgeInsets.all(12),
                color: const Color(0xFF111318).withValues(alpha: 0.9),
                child: Row(
                  children: [
                    // Tombol Mikrofon Nyata (Tekan untuk Bicara)
                    IconButton(
                      onPressed: _listenVoice,
                      icon: Icon(
                        _isListening ? Icons.mic : Icons.mic_none, 
                        color: _isListening ? Colors.redAccent : const Color(0xFFFFD700)
                      ),
                      style: IconButton.styleFrom(
                        backgroundColor: const Color(0xFF05070B),
                        padding: const EdgeInsets.all(12),
                        side: BorderSide(
                          color: _isListening 
                              ? Colors.redAccent 
                              : const Color(0xFFFFD700).withValues(alpha: 0.3)
                        ),
                      ),
                    ),
                    const SizedBox(width: 8),
                    Expanded(
                      child: TextField(
                        controller: _controller,
                        style: const TextStyle(color: Colors.white, fontFamily: 'monospace'),
                        decoration: InputDecoration(
                          hintText: _isListening ? "Listening to Boss..." : "Enter command or ask Jarvis...",
                          hintStyle: TextStyle(color: Colors.grey.shade600),
                          filled: true,
                          fillColor: const Color(0xFF05070B).withValues(alpha: 0.7),
                          contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
                          border: OutlineInputBorder(
                            borderRadius: BorderRadius.circular(8),
                            borderSide: BorderSide.none,
                          ),
                          focusedBorder: OutlineInputBorder(
                            borderRadius: BorderRadius.circular(8),
                            borderSide: const BorderSide(color: Color(0xFFFFD700), width: 1),
                          ),
                        ),
                        onSubmitted: _sendMessage,
                      ),
                    ),
                    const SizedBox(width: 8),
                    IconButton(
                      onPressed: () => _sendMessage(_controller.text),
                      icon: const Icon(Icons.send, color: Color(0xFFFFD700)),
                      style: IconButton.styleFrom(
                        backgroundColor: const Color(0xFF1F232A),
                        padding: const EdgeInsets.all(12),
                      ),
                    ),
                  ],
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildQuickButton(String label, String command) {
    return ElevatedButton(
      onPressed: () => _executeQuickCommand(command),
      style: ElevatedButton.styleFrom(
        backgroundColor: const Color(0xFF1F232A).withValues(alpha: 0.8),
        foregroundColor: const Color(0xFFFFD700),
        side: BorderSide(color: const Color(0xFFFFD700).withValues(alpha: 0.3)),
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
        textStyle: const TextStyle(fontFamily: 'monospace', fontSize: 12, fontWeight: FontWeight.bold),
      ),
      child: Text(label),
    );
  }
}

// 🧬 CUSTOM PAINTER UNTUK NANO-TECH EMAS & ARC REACTOR
class NanoGoldReactorPainter extends CustomPainter {
  final double rotationValue;
  final double activityLevel;

  NanoGoldReactorPainter({required this.rotationValue, required this.activityLevel});

  @override
  void paint(Canvas canvas, Size size) {
    final Offset center = Offset(size.width / 2, size.height / 2);
    final double radius = size.width * 0.42;

    final Paint goldPaint = Paint()
      ..color = Color.lerp(const Color(0xFFFFD700), const Color(0xFFFFEA75), activityLevel)!
          .withValues(alpha: 0.25 + (activityLevel * 0.25))
      ..style = PaintingStyle.stroke
      ..strokeWidth = 1.5 + (activityLevel * 1.5);

    final Paint corePaint = Paint()
      ..color = const Color(0xFFFFD700).withValues(alpha: 0.6 + (activityLevel * 0.4))
      ..style = PaintingStyle.stroke
      ..strokeWidth = 2.5;

    final Paint glowPaint = Paint()
      ..color = const Color(0xFFFFC107).withValues(alpha: 0.15 + (activityLevel * 0.2))
      ..maskFilter = const MaskFilter.blur(BlurStyle.normal, 12);

    canvas.drawCircle(center, radius * (0.8 + (activityLevel * 0.05)), glowPaint);

    canvas.save();
    canvas.translate(center.dx, center.dy);
    canvas.rotate(-rotationValue * 2 * math.pi);
    
    for (int i = 0; i < 12; i++) {
      double angle = i * (2 * math.pi / 12);
      double innerR = radius * 0.7;
      double outerR = radius * 0.85;
      canvas.drawLine(
        Offset(innerR * math.cos(angle), innerR * math.sin(angle)),
        Offset(outerR * math.cos(angle), outerR * math.sin(angle)),
        goldPaint,
      );
    }
    canvas.restore();

    canvas.save();
    canvas.translate(center.dx, center.dy);
    canvas.rotate(rotationValue * 4 * math.pi * (1 + activityLevel));

    goldPaint.strokeWidth = 1.0;
    canvas.drawCircle(Offset.zero, radius * 0.6, goldPaint);

    for (int i = 0; i < 6; i++) {
      double angle = i * (2 * math.pi / 6);
      Path nanoPath = Path();
      double r1 = radius * 0.45;
      double r2 = radius * 0.6;
      nanoPath.moveTo(r1 * math.cos(angle), r1 * math.sin(angle));
      nanoPath.lineTo(r2 * math.cos(angle + 0.2), r2 * math.sin(angle + 0.2));
      canvas.drawPath(nanoPath, goldPaint);
    }
    canvas.restore();

    canvas.drawCircle(center, radius * 0.25, corePaint);
    
    final Paint solidGold = Paint()
      ..color = const Color(0xFFFFF8E7)
      ..style = PaintingStyle.fill;
    canvas.drawCircle(center, radius * 0.08 + (activityLevel * 0.04), solidGold);
  }

  @override
  bool shouldRepaint(covariant NanoGoldReactorPainter oldDelegate) {
    return oldDelegate.rotationValue != rotationValue || oldDelegate.activityLevel != activityLevel;
  }
}