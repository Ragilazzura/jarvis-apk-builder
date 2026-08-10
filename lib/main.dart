import 'dart:math' as math;
import 'dart:io';
import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'dart:convert';
import 'dart:typed_data';
import 'package:audioplayers/audioplayers.dart';
import 'package:speech_to_text/speech_to_text.dart' as stt;
import 'package:web_socket_channel/web_socket_channel.dart';
import 'package:image_picker/image_picker.dart';
import 'android_omni_controller.dart';
import 'hud_notification_service.dart';

void main() async {
  WidgetsFlutterBinding.ensureInitialized();
  await HudNotificationService.init();
  runApp(const StarkHUDApp());
}

class StarkHUDApp extends StatelessWidget {
  const StarkHUDApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'J.A.R.V.I.S Mark 1',
      debugShowCheckedModeBanner: false,
      theme: ThemeData.dark().copyWith(
        scaffoldBackgroundColor: const Color(0xFF030508),
        primaryColor: const Color(0xFFFFD700),
        colorScheme: const ColorScheme.dark(
          primary: Color(0xFFFFD700),
          secondary: Color(0xFFFFA500),
          surface: Color(0xFF0A0D14),
        ),
      ),
      home: const HUDMainDashboard(),
    );
  }
}

class HUDMainDashboard extends StatefulWidget {
  const HUDMainDashboard({super.key});

  @override
  State<HUDMainDashboard> createState() => _HUDMainDashboardState();
}

class _HUDMainDashboardState extends State<HUDMainDashboard> {
  int _selectedIndex = 0;

  final List<Widget> _pages = const [
    JarvisCoreTab(),
    FridayWebTab(),
    EdithSentinelTab(),
    LogsJournalTab(),
  ];

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      extendBodyBehindAppBar: true,
      drawer: const StarkDrawer(),
      body: Stack(
        children: [
          Positioned(
            top: -100,
            left: -100,
            child: Container(
              width: 300,
              height: 300,
              decoration: BoxDecoration(
                shape: BoxShape.circle,
                color: const Color(0xFFFFD700).withValues(alpha: 0.05),
              ),
            ),
          ),
          Center(
            child: Container(
              constraints: const BoxConstraints(maxWidth: 600),
              child: Column(
                children: [
                  // 🚀 HEADER MODERN SCI-FI
                  SafeArea(
                    child: Padding(
                      padding: const EdgeInsets.symmetric(horizontal: 16.0, vertical: 8.0),
                      child: Row(
                        mainAxisAlignment: MainAxisAlignment.spaceBetween,
                        children: [
                          Builder(
                            builder: (context) => IconButton(
                              icon: const Icon(Icons.grid_view_rounded, color: Color(0xFFFFD700)),
                              onPressed: () => Scaffold.of(context).openDrawer(),
                            ),
                          ),
                          Container(
                            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 6),
                            decoration: BoxDecoration(
                              color: const Color(0xFF10141E).withValues(alpha: 0.8),
                              borderRadius: BorderRadius.circular(20),
                              border: Border.all(color: const Color(0xFFFFD700).withValues(alpha: 0.3)),
                            ),
                            child: const Row(
                              children: [
                                CircleAvatar(radius: 4, backgroundColor: Color(0xFFFFD700)),
                                SizedBox(width: 8),
                                Text(
                                  "J.A.R.V.I.S Mark 1",
                                  style: TextStyle(
                                    letterSpacing: 2,
                                    fontSize: 12,
                                    color: Color(0xFFFFD700),
                                    fontWeight: FontWeight.bold,
                                  ),
                                ),
                              ],
                            ),
                          ),
                          const Icon(Icons.wifi_tethering, color: Colors.greenAccent, size: 20),
                        ],
                      ),
                    ),
                  ),

                  // 💊 FLOATING SEGMENTED NAVIGATION BAR
                  Padding(
                    padding: const EdgeInsets.symmetric(horizontal: 16.0, vertical: 6.0),
                    child: Container(
                      padding: const EdgeInsets.all(4),
                      decoration: BoxDecoration(
                        color: const Color(0xFF0E121B).withValues(alpha: 0.9),
                        borderRadius: BorderRadius.circular(30),
                        border: Border.all(color: Colors.white.withValues(alpha: 0.08)),
                      ),
                      child: Row(
                        children: [
                          _buildNavPill(0, Icons.bolt_rounded, "CORE"),
                          _buildNavPill(1, Icons.travel_explore_rounded, "FRIDAY"),
                          _buildNavPill(2, Icons.security_rounded, "E.D.I.T.H"),
                          _buildNavPill(3, Icons.menu_book_rounded, "LOGS"),
                        ],
                      ),
                    ),
                  ),

                  // 📄 HALAMAN KONTEN UTAMA
                  Expanded(
                    child: IndexedStack(
                      index: _selectedIndex,
                      children: _pages,
                    ),
                  ),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildNavPill(int index, IconData icon, String label) {
    bool isSelected = _selectedIndex == index;
    return Expanded(
      child: GestureDetector(
        onTap: () => setState(() => _selectedIndex = index),
        child: AnimatedContainer(
          duration: const Duration(milliseconds: 250),
          padding: const EdgeInsets.symmetric(vertical: 8),
          decoration: BoxDecoration(
            color: isSelected ? const Color(0xFFFFD700) : Colors.transparent,
            borderRadius: BorderRadius.circular(25),
            boxShadow: isSelected
                ? [
                    BoxShadow(
                      color: const Color(0xFFFFD700).withValues(alpha: 0.4),
                      blurRadius: 10,
                      spreadRadius: 1,
                    )
                  ]
                : [],
          ),
          child: Row(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Icon(
                icon,
                size: 14,
                color: isSelected ? const Color(0xFF030508) : Colors.grey,
              ),
              const SizedBox(width: 4),
              Text(
                label,
                style: TextStyle(
                  fontSize: 10,
                  fontWeight: FontWeight.bold,
                  color: isSelected ? const Color(0xFF030508) : Colors.grey,
                  letterSpacing: 0.5,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

// ==========================================
// TAB 1: JARVIS CORE (STREAMING + DIAGRAM VIEWER + AUTO-PLAY TTS)
// ==========================================
class JarvisCoreTab extends StatefulWidget {
  const JarvisCoreTab({super.key});

  @override
  State<JarvisCoreTab> createState() => _JarvisCoreTabState();
}

class _JarvisCoreTabState extends State<JarvisCoreTab> with TickerProviderStateMixin {
  final TextEditingController _controller = TextEditingController();
  final List<Map<String, dynamic>> _messages = [];
  bool _isLoading = false;

  final AudioPlayer _audioPlayer = AudioPlayer();
  final ImagePicker _picker = ImagePicker();
  File? _selectedImage;

  final String serverUrl = "https://worker-production-792b.up.railway.app";
  final String wsUrl = "wss://worker-production-792b.up.railway.app/ws/stream_chat";

  late stt.SpeechToText _speech;
  bool _isListening = false;

  late AnimationController _reactorController;
  late AnimationController _nanoActivityController;

  @override
  void initState() {
    super.initState();
    _speech = stt.SpeechToText();

    _reactorController = AnimationController(
      vsync: this,
      duration: const Duration(seconds: 8),
    )..repeat();

    _nanoActivityController = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 800),
    );

    _addMessage("jarvis", "Quantum Core Online. All Systems Nominal, Boss.");
  }

  void _addMessage(String sender, String text, {File? image, Uint8List? imageBytes}) {
    if (!mounted) return;
    setState(() {
      _messages.add({
        "sender": sender,
        "text": text,
        "image": image,
        "imageBytes": imageBytes, // Untuk Diagram Viewer & Visual Response
      });
    });
  }

  // 🎙️ MODUL AUTO-PLAY AUDIO TTS
  Future<void> _playTtsAudio(String base64Audio) async {
    try {
      if (base64Audio.isNotEmpty) {
        Uint8List audioBytes = base64Decode(base64Audio);
        await _audioPlayer.stop();
        await _audioPlayer.play(BytesSource(audioBytes));
      }
    } catch (e) {
      debugPrint("Error playing TTS audio: $e");
    }
  }

  void _pickImage(ImageSource source) async {
    final XFile? photo = await _picker.pickImage(
      source: source,
      imageQuality: 70,
    );

    if (photo != null) {
      setState(() {
        _selectedImage = File(photo.path);
      });
    }
  }

  void _listenVoice() async {
    if (!_isListening) {
      bool available = await _speech.initialize(
        onStatus: (status) {
          if (status == 'notListening' || status == 'done') {
            if (mounted) {
              setState(() => _isListening = false);
              _nanoActivityController.reverse();
            }
          }
        },
      );

      if (available && mounted) {
        setState(() {
          _isListening = true;
          _nanoActivityController.forward(from: 0.0);
        });

        _speech.listen(
          onResult: (result) {
            if (mounted) {
              setState(() {
                _controller.text = result.recognizedWords;
              });
              if (result.finalResult && _controller.text.isNotEmpty) {
                _sendMessage(_controller.text);
              }
            }
          },
          localeId: 'id_ID',
        );
      }
    } else {
      if (mounted) {
        setState(() => _isListening = false);
      }
      _speech.stop();
      _nanoActivityController.reverse();
    }
  }

  Future<void> _sendMessage(String text) async {
    if (text.trim().isEmpty && _selectedImage == null) return;

    if (_isListening) {
      _speech.stop();
      if (mounted) setState(() => _isListening = false);
    }

    String userMsg = text.trim();
    String lowerMsg = userMsg.toLowerCase();
    File? imageToSend = _selectedImage;

    _addMessage("user", userMsg.isEmpty ? "[Mengirim Gambar]" : userMsg, image: imageToSend);
    _controller.clear();
    setState(() {
      _selectedImage = null;
      _isLoading = true;
    });
    _nanoActivityController.forward(from: 0.0);

    // ⏰ 1. PEMICU ALARM LOKAL HUD
    if (lowerMsg.contains("pasang alarm") || lowerMsg.contains("set alarm") || lowerMsg.contains("ingatkan jam")) {
      RegExp regExp = RegExp(r'jam\s+(\d{1,2})(?::|\s+)?(\d{2})?');
      Match? match = regExp.firstMatch(lowerMsg);

      if (match != null) {
        int hour = int.parse(match.group(1)!);
        int minute = match.group(2) != null ? int.parse(match.group(2)!) : 0;

        String res = await HudNotificationService.scheduleAlarm(
          hour: hour,
          minute: minute,
          title: "⏰ J.A.R.V.I.S. PROTOCOL REMINDER",
          body: "Waktunya menjalankan aktivitas, Bos!",
        );

        _addMessage("jarvis", res);
        if (mounted) setState(() => _isLoading = false);
        _nanoActivityController.reverse();
        return;
      }
    }

    // 🧠 2. LOCAL INTENT ROUTER HP NATIVE
    if (lowerMsg.contains("kirim wa") || lowerMsg.contains("whatsapp ke")) {
      RegExp regExp = RegExp(r'(\d+)\s+(?:isi|pesan)\s+(.+)');
      Match? match = regExp.firstMatch(lowerMsg);

      if (match != null) {
        String phone = match.group(1)!;
        String message = match.group(2)!;

        String res = await AndroidOmniController.sendWhatsApp(phone: phone, message: message);
        _addMessage("jarvis", res);
        if (mounted) setState(() => _isLoading = false);
        _nanoActivityController.reverse();
        return;
      }
    } else if (lowerMsg.contains("buka aplikasi") || lowerMsg.contains("buka app")) {
      String appName = lowerMsg.replaceAll("buka aplikasi", "").replaceAll("buka app", "").trim();
      String res = await AndroidOmniController.launchPhoneApp(appName);
      _addMessage("jarvis", res);
      if (mounted) setState(() => _isLoading = false);
      _nanoActivityController.reverse();
      return;
    }

    // 🌐 3. GAMBAR MULTIMODAL VISION VIA HTTP
    if (imageToSend != null) {
      try {
        List<int> imageBytes = await imageToSend.readAsBytes();
        String base64Image = base64Encode(imageBytes);

        final response = await http.post(
          Uri.parse("$serverUrl/chat"),
          headers: {"Content-Type": "application/json"},
          body: jsonEncode({
            "message": userMsg.isEmpty ? "Tolong analisis gambar ini, Bos." : userMsg,
            "image_base64": base64Image,
            "is_voice_input": false
          }),
        );

        if (response.statusCode == 200) {
          final data = jsonDecode(response.body);
          _addMessage("jarvis", data["reply"] ?? "Analisis gambar selesai.");
          if (data["audio_base64"] != null) {
            _playTtsAudio(data["audio_base64"]);
          }
        }
      } catch (e) {
        _addMessage("jarvis", "🚨 Gagal menganalisis gambar: $e");
      } finally {
        if (mounted) setState(() => _isLoading = false);
        _nanoActivityController.reverse();
      }
      return;
    }

    // ⚡ 4. REAL-TIME WEBSOCKET STREAMING (TEXT + DIAGRAM VIEWER SUPPORT)
    try {
      final channel = WebSocketChannel.connect(Uri.parse(wsUrl));
      channel.sink.add(userMsg);

      int streamingIndex = -1;

      channel.stream.listen((event) {
        final data = jsonDecode(event);

        if (data["type"] == "text_chunk") {
          String chunk = data["content"] ?? "";
          if (mounted) {
            setState(() {
              if (streamingIndex == -1) {
                _messages.add({"sender": "jarvis", "text": chunk});
                streamingIndex = _messages.length - 1;
              } else {
                _messages[streamingIndex]["text"] = (_messages[streamingIndex]["text"] ?? "") + chunk;
              }
            });
          }
        } 
        // 📊 DIAGRAM VIEWER DETECTOR IN STREAM
        else if (data["type"] == "diagram_response" || data["image_base64"] != null) {
          Uint8List diagramBytes = base64Decode(data["image_base64"]);
          _addMessage("jarvis", "📊 *MARK-UI Diagram Generated*", imageBytes: diagramBytes);
        }
        else if (data["type"] == "stream_end") {
          if (data["audio_base64"] != null) {
            _playTtsAudio(data["audio_base64"]);
          }
          channel.sink.close();
          if (mounted) setState(() => _isLoading = false);
          _nanoActivityController.reverse();
        }
      }, onError: (error) {
        _sendHttpFallback(userMsg);
      });
    } catch (e) {
      _sendHttpFallback(userMsg);
    }
  }

  void _sendHttpFallback(String userMsg) async {
    try {
      final response = await http.post(
        Uri.parse("$serverUrl/chat"),
        headers: {"Content-Type": "application/json"},
        body: jsonEncode({"message": userMsg, "is_voice_input": false}),
      );

      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        
        // Cek jika balasan memuat diagram/gambar
        Uint8List? imgBytes;
        if (data["image_base64"] != null && data["image_base64"].toString().isNotEmpty) {
          imgBytes = base64Decode(data["image_base64"]);
        }

        _addMessage("jarvis", data["reply"] ?? "Protocol executed.", imageBytes: imgBytes);

        // Auto-play TTS Voice
        if (data["audio_base64"] != null) {
          _playTtsAudio(data["audio_base64"]);
        }
      }
    } catch (e) {
      _addMessage("jarvis", "🚨 Connection Error: $e");
    } finally {
      if (mounted) setState(() => _isLoading = false);
      _nanoActivityController.reverse();
    }
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
    return Stack(
      children: [
        Center(
          child: AnimatedBuilder(
            animation: Listenable.merge([_reactorController, _nanoActivityController]),
            builder: (context, child) {
              return CustomPaint(
                size: const Size(340, 340),
                painter: HolographicQuantumReactorPainter(
                  progress: _reactorController.value,
                  activityLevel: (_isLoading || _isListening) ? 1.0 : _nanoActivityController.value,
                ),
              );
            },
          ),
        ),

        Column(
          children: [
            Expanded(
              child: ListView.builder(
                padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
                itemCount: _messages.length,
                itemBuilder: (context, index) {
                  final msg = _messages[index];
                  final isUser = msg["sender"] == "user";
                  final File? image = msg["image"];
                  final Uint8List? imageBytes = msg["imageBytes"];

                  return Align(
                    alignment: isUser ? Alignment.centerRight : Alignment.centerLeft,
                    child: Container(
                      margin: const EdgeInsets.symmetric(vertical: 6),
                      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
                      constraints: BoxConstraints(maxWidth: MediaQuery.of(context).size.width * 0.8),
                      decoration: BoxDecoration(
                        color: isUser
                            ? const Color(0xFFFFD700).withValues(alpha: 0.15)
                            : const Color(0xFF0F131D).withValues(alpha: 0.85),
                        borderRadius: BorderRadius.only(
                          topLeft: const Radius.circular(16),
                          topRight: const Radius.circular(16),
                          bottomLeft: isUser ? const Radius.circular(16) : Radius.zero,
                          bottomRight: isUser ? Radius.zero : const Radius.circular(16),
                        ),
                        border: Border.all(
                          color: isUser
                              ? const Color(0xFFFFD700).withValues(alpha: 0.5)
                              : Colors.white.withValues(alpha: 0.1),
                        ),
                      ),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          if (image != null) ...[
                            ClipRRect(
                              borderRadius: BorderRadius.circular(8),
                              child: ConstrainedBox(
                                constraints: const BoxConstraints(maxHeight: 180),
                                child: Image.file(image, fit: BoxFit.cover),
                              ),
                            ),
                            const SizedBox(height: 8),
                          ],
                          // 📊 MARK-UI DIAGRAM / VISUAL RESPONSE RENDERER
                          if (imageBytes != null) ...[
                            ClipRRect(
                              borderRadius: BorderRadius.circular(8),
                              child: Image.memory(imageBytes, fit: BoxFit.contain),
                            ),
                            const SizedBox(height: 8),
                          ],
                          Text(
                            msg["text"] ?? "",
                            style: TextStyle(
                              color: isUser ? const Color(0xFFFFF8E7) : const Color(0xFFFFE082),
                              fontFamily: 'monospace',
                              fontSize: 12.5,
                              height: 1.3,
                            ),
                          ),
                        ],
                      ),
                    ),
                  );
                },
              ),
            ),
            if (_isLoading || _isListening)
              Padding(
                padding: const EdgeInsets.symmetric(horizontal: 16.0),
                child: ClipRRect(
                  borderRadius: BorderRadius.circular(4),
                  child: LinearProgressIndicator(
                    color: _isListening ? Colors.redAccent : const Color(0xFFFFD700),
                    backgroundColor: Colors.transparent,
                  ),
                ),
              ),

            // 🌟 FLOATING INPUT BAR
            SafeArea(
              bottom: true,
              child: Column(
                children: [
                  if (_selectedImage != null)
                    Container(
                      margin: const EdgeInsets.symmetric(horizontal: 20, vertical: 4),
                      padding: const EdgeInsets.all(6),
                      decoration: BoxDecoration(
                        color: const Color(0xFF0E121B),
                        borderRadius: BorderRadius.circular(12),
                        border: Border.all(color: const Color(0xFFFFD700).withValues(alpha: 0.5)),
                      ),
                      child: Row(
                        children: [
                          ClipRRect(
                            borderRadius: BorderRadius.circular(8),
                            child: Image.file(_selectedImage!, width: 45, height: 45, fit: BoxFit.cover),
                          ),
                          const SizedBox(width: 10),
                          const Expanded(
                            child: Text(
                              "Gambar siap dikirim ke Gemini Vision...",
                              style: TextStyle(color: Color(0xFFFFE082), fontSize: 11),
                            ),
                          ),
                          IconButton(
                            icon: const Icon(Icons.cancel_rounded, color: Colors.redAccent, size: 20),
                            onPressed: () => setState(() => _selectedImage = null),
                          ),
                        ],
                      ),
                    ),

                  Container(
                    margin: const EdgeInsets.fromLTRB(16, 4, 16, 12),
                    padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 4),
                    decoration: BoxDecoration(
                      color: const Color(0xFF0E121B).withValues(alpha: 0.95),
                      borderRadius: BorderRadius.circular(30),
                      border: Border.all(color: const Color(0xFFFFD700).withValues(alpha: 0.25)),
                    ),
                    child: Row(
                      children: [
                        IconButton(
                          onPressed: _listenVoice,
                          icon: Icon(
                            _isListening ? Icons.mic : Icons.mic_none_rounded,
                            color: _isListening ? Colors.redAccent : const Color(0xFFFFD700),
                            size: 20,
                          ),
                        ),
                        IconButton(
                          onPressed: () => _pickImage(ImageSource.gallery),
                          icon: const Icon(Icons.photo_library_rounded, color: Color(0xFFFFD700), size: 18),
                        ),
                        IconButton(
                          onPressed: () => _pickImage(ImageSource.camera),
                          icon: const Icon(Icons.camera_alt_rounded, color: Color(0xFFFFD700), size: 18),
                        ),
                        Expanded(
                          child: TextField(
                            controller: _controller,
                            style: const TextStyle(color: Colors.white, fontFamily: 'monospace', fontSize: 12.5),
                            decoration: InputDecoration(
                              hintText: "Command Jarvis...",
                              hintStyle: TextStyle(color: Colors.grey.shade600, fontSize: 12),
                              border: InputBorder.none,
                              contentPadding: const EdgeInsets.symmetric(horizontal: 6),
                            ),
                            onSubmitted: _sendMessage,
                          ),
                        ),
                        IconButton(
                          onPressed: () => _sendMessage(_controller.text),
                          icon: const Icon(Icons.arrow_upward_rounded, color: Color(0xFFFFD700), size: 20),
                          style: IconButton.styleFrom(
                            backgroundColor: const Color(0xFFFFD700).withValues(alpha: 0.15),
                          ),
                        ),
                      ],
                    ),
                  ),
                ],
              ),
            ),
          ],
        ),
      ],
    );
  }
}

// ==========================================
// TAB 2: FRIDAY WEB INTELLIGENCE
// ==========================================
class FridayWebTab extends StatefulWidget {
  const FridayWebTab({super.key});

  @override
  State<FridayWebTab> createState() => _FridayWebTabState();
}

class _FridayWebTabState extends State<FridayWebTab> {
  final TextEditingController _urlController = TextEditingController();
  String _webResult = "FRIDAY Web Reader Standby. Masukkan URL untuk meriset halaman web, Bos.";
  bool _isSearching = false;

  void _triggerResearch() async {
    String urlInput = _urlController.text.trim();
    if (urlInput.isEmpty) return;

    setState(() {
      _isSearching = true;
      _webResult = "FRIDAY sedang merayapi dan menganalisis situs target...";
    });

    try {
      final response = await http.post(
        Uri.parse("https://worker-production-792b.up.railway.app/chat"),
        headers: {"Content-Type": "application/json"},
        body: jsonEncode({"message": "Tolong analisis dan berikan ringkasan dari URL ini: $urlInput", "is_voice_input": false}),
      );

      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        if (mounted) {
          setState(() {
            _webResult = data["reply"] ?? "Analisis selesai.";
          });
        }
      } else {
        if (mounted) {
          setState(() {
            _webResult = "🚨 Gagal terhubung ke modul riset FRIDAY.";
          });
        }
      }
    } catch (e) {
      if (mounted) {
        setState(() {
          _webResult = "🚨 Error: $e";
        });
      }
    } finally {
      if (mounted) {
        setState(() {
          _isSearching = false;
        });
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.all(16.0),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Container(
            padding: const EdgeInsets.all(12),
            decoration: BoxDecoration(
              color: const Color(0xFF0E121B),
              borderRadius: BorderRadius.circular(16),
              border: Border.all(color: Colors.white.withValues(alpha: 0.08)),
            ),
            child: Row(
              children: [
                Expanded(
                  child: TextField(
                    controller: _urlController,
                    style: const TextStyle(color: Colors.white, fontFamily: 'monospace', fontSize: 12),
                    decoration: InputDecoration(
                      hintText: "https://example.com",
                      hintStyle: TextStyle(color: Colors.grey.shade600),
                      border: InputBorder.none,
                    ),
                  ),
                ),
                ElevatedButton(
                  onPressed: _isSearching ? null : _triggerResearch,
                  style: ElevatedButton.styleFrom(
                    backgroundColor: const Color(0xFFFFD700),
                    foregroundColor: Colors.black,
                    shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                  ),
                  child: const Text("RISET", style: TextStyle(fontWeight: FontWeight.bold, fontSize: 11)),
                ),
              ],
            ),
          ),
          const SizedBox(height: 16),
          Expanded(
            child: Container(
              padding: const EdgeInsets.all(16),
              width: double.infinity,
              decoration: BoxDecoration(
                color: const Color(0xFF0E121B).withValues(alpha: 0.8),
                borderRadius: BorderRadius.circular(16),
                border: Border.all(color: const Color(0xFFFFD700).withValues(alpha: 0.15)),
              ),
              child: SingleChildScrollView(
                child: Text(_webResult, style: const TextStyle(color: Color(0xFFFFE082), fontFamily: 'monospace', fontSize: 12, height: 1.4)),
              ),
            ),
          ),
        ],
      ),
    );
  }
}

// ==========================================
// TAB 3: EDITH & SENTINEL CONTROL (WITH LIVE PREVIEW CARD)
// ==========================================
class EdithSentinelTab extends StatefulWidget {
  const EdithSentinelTab({super.key});

  @override
  State<EdithSentinelTab> createState() => _EdithSentinelTabState();
}

class _EdithSentinelTabState extends State<EdithSentinelTab> {
  Uint8List? _capturedImageBytes;
  String _previewCaption = "";
  bool _isCapturing = false;

  void _triggerVisionAction(BuildContext context, String command, String captionTitle) async {
    setState(() {
      _isCapturing = true;
      _previewCaption = captionTitle;
    });

    try {
      final response = await http.post(
        Uri.parse("https://worker-production-792b.up.railway.app/chat"),
        headers: {"Content-Type": "application/json"},
        body: jsonEncode({"message": command, "is_voice_input": false}),
      );

      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);

        // Render pratinjau gambar bila dikirimkan oleh server/PC
        if (data["image_base64"] != null && data["image_base64"].toString().isNotEmpty) {
          setState(() {
            _capturedImageBytes = base64Decode(data["image_base64"]);
          });
        }

        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(content: Text(data["reply"] ?? "Perintah dikirim ke E.D.I.T.H.")),
          );
        }
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text("Gagal: $e")));
      }
    } finally {
      if (mounted) {
        setState(() => _isCapturing = false);
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.all(16.0),
      child: ListView(
        children: [
          // 👁️ E.D.I.T.H. LIVE IMAGE PREVIEW CARD (NEW!)
          if (_isCapturing)
            Container(
              margin: const EdgeInsets.only(bottom: 12),
              padding: const EdgeInsets.all(16),
              decoration: BoxDecoration(
                color: const Color(0xFF0E121B),
                borderRadius: BorderRadius.circular(16),
                border: Border.all(color: const Color(0xFFFFD700).withValues(alpha: 0.5)),
              ),
              child: const Row(
                children: [
                  SizedBox(
                    width: 20,
                    height: 20,
                    child: CircularProgressIndicator(strokeWidth: 2, color: Color(0xFFFFD700)),
                  ),
                  SizedBox(width: 12),
                  Text("E.D.I.T.H. sedang mengambil tangkapan layar PC...", style: TextStyle(color: Color(0xFFFFE082), fontSize: 12)),
                ],
              ),
            )
          else if (_capturedImageBytes != null)
            Container(
              margin: const EdgeInsets.only(bottom: 12),
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(
                color: const Color(0xFF0E121B),
                borderRadius: BorderRadius.circular(16),
                border: Border.all(color: const Color(0xFFFFD700).withValues(alpha: 0.4)),
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                    children: [
                      Text(
                        _previewCaption,
                        style: const TextStyle(color: Color(0xFFFFD700), fontWeight: FontWeight.bold, fontSize: 12),
                      ),
                      IconButton(
                        icon: const Icon(Icons.close_rounded, size: 18, color: Colors.grey),
                        onPressed: () => setState(() => _capturedImageBytes = null),
                      ),
                    ],
                  ),
                  const SizedBox(height: 8),
                  ClipRRect(
                    borderRadius: BorderRadius.circular(12),
                    child: Image.memory(_capturedImageBytes!, fit: BoxFit.cover),
                  ),
                ],
              ),
            ),

          _buildControlCard(
            context,
            "E.D.I.T.H. Screen Vision",
            "Ambil screenshot PC lokal & tampilkan pratinjau gambarnya",
            Icons.center_focus_strong_rounded,
            const Color(0xFFFFD700),
            () => _triggerVisionAction(context, "Jarvis, periksa dan analisis apa yang ada di layar laptop saat ini", "👁️ TANGKAPAN LAYAR LAPTOP"),
          ),
          _buildControlCard(
            context,
            "Lock Host PC Screen",
            "Mengunci layar komputer lokal via hybrid bridge",
            Icons.lock_rounded,
            Colors.orangeAccent,
            () => _triggerVisionAction(context, "Matikan suara PC dan kunci layar", "🔒 LOCK SCREEN EXECUTED"),
          ),
          _buildControlCard(
            context,
            "Check Hardware Metrics",
            "Melihat penggunaan CPU, RAM, & Baterai PC",
            Icons.computer_rounded,
            Colors.cyanAccent,
            () => _triggerVisionAction(context, "Cek penggunaan hardware PC sekarang", "💻 HARDWARE METRICS"),
          ),
          _buildControlCard(
            context,
            "Ultron-Sentinel Scan",
            "Memindai kesehatan endpoint peladen secara berkala",
            Icons.satellite_alt_rounded,
            Colors.greenAccent,
            () => _triggerVisionAction(context, "Jalankan pengecekan uptime server sentinel sekarang", "🛰️ SENTINEL SCAN"),
          ),
        ],
      ),
    );
  }

  Widget _buildControlCard(BuildContext context, String title, String subtitle, IconData icon, Color color, VoidCallback onTap) {
    return Container(
      margin: const EdgeInsets.symmetric(vertical: 6),
      decoration: BoxDecoration(
        color: const Color(0xFF0E121B),
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: color.withValues(alpha: 0.2)),
      ),
      child: ListTile(
        leading: Container(
          padding: const EdgeInsets.all(8),
          decoration: BoxDecoration(color: color.withValues(alpha: 0.1), borderRadius: BorderRadius.circular(10)),
          child: Icon(icon, color: color, size: 20),
        ),
        title: Text(title, style: const TextStyle(color: Colors.white, fontSize: 13, fontWeight: FontWeight.bold)),
        subtitle: Text(subtitle, style: const TextStyle(color: Colors.grey, fontSize: 11)),
        trailing: const Icon(Icons.arrow_forward_ios_rounded, size: 12, color: Colors.grey),
        onTap: onTap,
      ),
    );
  }
}

// ==========================================
// TAB 4: LOGS & T.A.C.H.I. JOURNAL CENTER
// ==========================================
class LogsJournalTab extends StatefulWidget {
  const LogsJournalTab({super.key});

  @override
  State<LogsJournalTab> createState() => _LogsJournalTabState();
}

class _LogsJournalTabState extends State<LogsJournalTab> {
  String _memoryLogs = "Memuat arsip T.A.C.H.I. & Mind Palace...";
  bool _isLoading = true;

  @override
  void initState() {
    super.initState();
    _fetchLogs();
  }

  Future<void> _fetchLogs() async {
    try {
      final response = await http.get(
        Uri.parse("https://worker-production-792b.up.railway.app/history"),
      );

      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        if (mounted) {
          setState(() {
            _memoryLogs = data["memories"] ?? "Belum ada catatan memori tersimpan.";
            _isLoading = false;
          });
        }
      } else {
        if (mounted) {
          setState(() {
            _memoryLogs = "🚨 Gagal mengambil data log dari server.";
            _isLoading = false;
          });
        }
      }
    } catch (e) {
      if (mounted) {
        setState(() {
          _memoryLogs = "🚨 Error koneksi: $e";
          _isLoading = false;
        });
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.all(16.0),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              const Text(
                "T.A.C.H.I. JOURNAL & LOGS",
                style: TextStyle(
                  color: Color(0xFFFFD700),
                  fontSize: 14,
                  fontWeight: FontWeight.bold,
                  letterSpacing: 1.5,
                ),
              ),
              IconButton(
                icon: const Icon(Icons.refresh_rounded, color: Color(0xFFFFD700)),
                onPressed: () {
                  setState(() => _isLoading = true);
                  _fetchLogs();
                },
              ),
            ],
          ),
          const SizedBox(height: 8),
          Expanded(
            child: Container(
              padding: const EdgeInsets.all(16),
              width: double.infinity,
              decoration: BoxDecoration(
                color: const Color(0xFF0E121B).withValues(alpha: 0.85),
                borderRadius: BorderRadius.circular(16),
                border: Border.all(color: const Color(0xFFFFD700).withValues(alpha: 0.2)),
              ),
              child: _isLoading
                  ? const Center(child: CircularProgressIndicator(color: Color(0xFFFFD700)))
                  : SingleChildScrollView(
                      child: Text(
                        _memoryLogs,
                        style: const TextStyle(
                          color: Color(0xFFFFE082),
                          fontFamily: 'monospace',
                          fontSize: 12,
                          height: 1.4,
                        ),
                      ),
                    ),
            ),
          ),
        ],
      ),
    );
  }
}

// ==========================================
// STARK DRAWER
// ==========================================
class StarkDrawer extends StatelessWidget {
  const StarkDrawer({super.key});

  @override
  Widget build(BuildContext context) {
    return Drawer(
      backgroundColor: const Color(0xFF080B10),
      child: ListView(
        padding: EdgeInsets.zero,
        children: [
          const DrawerHeader(
            decoration: BoxDecoration(color: Color(0xFF0E121B)),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              mainAxisAlignment: MainAxisAlignment.end,
              children: [
                Icon(Icons.psychology_rounded, color: Color(0xFFFFD700), size: 36),
                SizedBox(height: 8),
                Text("M.I.N.D. PALACE", style: TextStyle(color: Color(0xFFFFD700), fontSize: 16, fontWeight: FontWeight.bold, letterSpacing: 1.5)),
                Text("Arsip Jangka Panjang & Pengetahuan Jarvis", style: TextStyle(color: Colors.grey, fontSize: 11)),
              ],
            ),
          ),
          ListTile(
            leading: const Icon(Icons.menu_book_rounded, color: Color(0xFFFFD700)),
            title: const Text("Tampilkan Jurnal Harian", style: TextStyle(color: Colors.white, fontSize: 12)),
            onTap: () => Navigator.pop(context),
          ),
        ],
      ),
    );
  }
}

// ==========================================
// 🌌 HOLOGRAPHIC QUANTUM PARTICLE REACTOR PAINTER
// ==========================================
class HolographicQuantumReactorPainter extends CustomPainter {
  final double progress;
  final double activityLevel;

  HolographicQuantumReactorPainter({required this.progress, required this.activityLevel});

  @override
  void paint(Canvas canvas, Size size) {
    final Offset center = Offset(size.width / 2, size.height / 2);
    final double maxRadius = size.width * 0.42;

    final double glowAlpha = (0.08 + (activityLevel * 0.12)).clamp(0.0, 1.0);
    final Paint glowBackground = Paint()
      ..color = const Color(0xFFAB47BC).withValues(alpha: glowAlpha)
      ..maskFilter = const MaskFilter.blur(BlurStyle.normal, 25);
    canvas.drawCircle(center, maxRadius * 0.8, glowBackground);

    int ringCount = 20;
    int pointsPerRing = 48;
    double time = progress * 2 * math.pi;

    for (int r = 1; r <= ringCount; r++) {
      double ringRatio = r / ringCount;
      double baseRadius = maxRadius * ringRatio;

      Color particleColor;
      if (ringRatio < 0.35) {
        particleColor = Color.lerp(
          const Color(0xFFD81B60),
          const Color(0xFF8E24AA),
          ringRatio / 0.35,
        )!;
      } else if (ringRatio < 0.75) {
        particleColor = Color.lerp(
          const Color(0xFFFF6D00),
          const Color(0xFFFFAB00),
          (ringRatio - 0.35) / 0.4,
        )!;
      } else {
        particleColor = Color.lerp(
          const Color(0xFFFFD700),
          const Color(0xFFFFF8E7),
          (ringRatio - 0.75) / 0.25,
        )!;
      }

      for (int p = 0; p < pointsPerRing; p++) {
        double angle = (p / pointsPerRing) * 2 * math.pi;

        double wave1 = math.sin(angle * 4 + time * 2 + ringRatio * 5);
        double wave2 = math.cos(angle * 2 - time * 3 + ringRatio * 3);
        double wave3 = math.sin(angle * 6 + time * (1 + activityLevel * 2));

        double totalDisplacement = (wave1 * 0.4 + wave2 * 0.35 + wave3 * 0.25);
        double amplitude = (8.0 + (ringRatio * 14.0)) * (1.0 + (activityLevel * 1.8));

        double distortedRadius = baseRadius + (totalDisplacement * amplitude);

        double particleX = center.dx + distortedRadius * math.cos(angle);
        double particleY = center.dy + distortedRadius * math.sin(angle);

        double particleSize = (1.2 + (ringRatio * 1.8)) * (1.0 + (activityLevel * 0.4));

        double alpha = (0.3 + (ringRatio * 0.6)) * (0.8 + (0.2 * math.sin(time + p)));
        alpha = alpha.clamp(0.05, 1.0);

        final Paint dotPaint = Paint()
          ..color = particleColor.withValues(alpha: alpha)
          ..style = PaintingStyle.fill;

        canvas.drawCircle(Offset(particleX, particleY), particleSize, dotPaint);
      }
    }

    final double coreAlpha = (0.8 + (activityLevel * 0.2)).clamp(0.0, 1.0);
    final Paint corePaint = Paint()
      ..color = const Color(0xFFFFF8E7).withValues(alpha: coreAlpha)
      ..maskFilter = const MaskFilter.blur(BlurStyle.normal, 8);
    canvas.drawCircle(center, 6.0 + (activityLevel * 4.0), corePaint);
  }

  @override
  bool shouldRepaint(covariant HolographicQuantumReactorPainter oldDelegate) {
    return oldDelegate.progress != progress || oldDelegate.activityLevel != activityLevel;
  }
}