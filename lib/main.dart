import 'dart:math' as math;
import 'dart:io';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:http/http.dart' as http;
import 'dart:convert';
import 'dart:typed_data';
import 'package:audioplayers/audioplayers.dart';
import 'package:speech_to_text/speech_to_text.dart' as stt;
import 'package:web_socket_channel/web_socket_channel.dart';
import 'package:image_picker/image_picker.dart';
import 'package:shared_preferences/shared_preferences.dart'; // 💾 Storage lokal
import 'package:flutter_markdown/flutter_markdown.dart'; // 📝 Render Markdown
import 'hud_notification_service.dart';
import 'services/telemetry_service.dart';

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
                                  "J.A.R.V.I.S OMNI-CORE",
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
                  const Expanded(
                    child: JarvisCoreTab(),
                  ),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }
}

// ==========================================
// TAB 1: JARVIS CORE (OMNI-CONVERSATIONAL UI)
// ==========================================
class JarvisCoreTab extends StatefulWidget {
  const JarvisCoreTab({super.key});

  @override
  State<JarvisCoreTab> createState() => _JarvisCoreTabState();
}

class _JarvisCoreTabState extends State<JarvisCoreTab> with TickerProviderStateMixin {
  final TextEditingController _controller = TextEditingController();
  final ScrollController _scrollController = ScrollController();
  List<Map<String, dynamic>> _messages = [];
  bool _isLoading = false;

  final AudioPlayer _audioPlayer = AudioPlayer();
  final ImagePicker _picker = ImagePicker();
  File? _selectedImage;

  final String serverUrl = "https://worker-production-792b.up.railway.app";

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

    // 📥 1. Muat Riwayat Chat dari Penyimpanan HP
    _loadSavedChatHistory();

    // 🌐 Listening Laporan WebSocket & Push
    JarvisWebSocketService().connect((data) {
      if (data["type"] == "text_chunk" && data["content"] != null) {
        _addMessage("jarvis", data["content"]);
        if (data["audio_base64"] != null) {
          _playTtsAudio(data["audio_base64"]);
        }
      } else if (data["sender"] == "ascar" || data["type"] == "ascar_report") {
        _addMessage("jarvis", data["message"] ?? data["content"] ?? "🛡️ A.S.C.A.R. Report received.");
      }
    });

    // 🌅 Pemicu Otomatis Morning Briefing (Filter Jam 7 & 1x Sehari)
    _checkAndTriggerMorningBriefing();
  }

  // 💾 A. SIMPAN CHAT KE MEMORI LOKAL HP
  Future<void> _saveChatHistory() async {
    final prefs = await SharedPreferences.getInstance();
    List<Map<String, dynamic>> serializableMessages = _messages.map((m) {
      return {
        "sender": m["sender"],
        "text": m["text"],
        "timestamp": m["timestamp"],
      };
    }).toList();
    await prefs.setString('jarvis_chat_history', jsonEncode(serializableMessages));
  }

  // 📥 B. MUAT CHAT SAAT APLIKASI DIBUKA
  Future<void> _loadSavedChatHistory() async {
    final prefs = await SharedPreferences.getInstance();
    String? savedData = prefs.getString('jarvis_chat_history');
    if (savedData != null) {
      setState(() {
        _messages = List<Map<String, dynamic>>.from(jsonDecode(savedData));
      });
      _scrollToBottom();
    } else {
      _addMessage("jarvis", "Omni-Core Online. All systems unified, Boss.");
    }
  }

  // 🌅 C. LOGIKA MORNING BRIEFING PRESISI (JAM 7 PAGI & 1X SEHARI)
  Future<void> _checkAndTriggerMorningBriefing() async {
    final now = DateTime.now();

    // 1. Filter Jam: Hanya di jam 7 pagi (07:00 - 07:59)
    if (now.hour != 7) {
      debugPrint("ℹ️ Morning Briefing dilewati karena bukan jam 7 pagi.");
      return;
    }

    final prefs = await SharedPreferences.getInstance();
    String todayDateStr = "${now.year}-${now.month}-${now.day}";
    String? lastBriefingDate = prefs.getString('last_morning_briefing_date');

    // 2. Filter Tanggal: Hentikan jika hari ini sudah pernah dipicu
    if (lastBriefingDate == todayDateStr) {
      debugPrint("ℹ️ Morning Briefing hari ini sudah pernah dipicu.");
      return;
    }

    try {
      final telemetry = TelemetryService(
        baseUrl: serverUrl,
        secretKey: "stark_hud_secret_2026",
      );

      String? briefingText = await telemetry.fetchMorningBriefing();
      if (briefingText != null && mounted) {
        _addMessage("jarvis", briefingText);

        try {
          await HudNotificationService.showInstantNotification(
            title: "🌅 J.A.R.V.I.S. MORNING BRIEFING",
            body: briefingText,
          );
        } catch (e) {
          debugPrint("🔔 Notification fallback: $briefingText");
        }

        // Tandai bahwa hari ini sudah dikirim
        await prefs.setString('last_morning_briefing_date', todayDateStr);
      }
    } catch (e) {
      debugPrint("⚠️ Gagal memuat Morning Briefing: $e");
    }
  }

  // 📩 D. TAMBAH PESAN BARU
  void _addMessage(String sender, String text, {File? image, Uint8List? imageBytes}) {
    if (!mounted) return;
    setState(() {
      _messages.add({
        "sender": sender,
        "text": text,
        "image": image,
        "imageBytes": imageBytes,
        "timestamp": DateTime.now().toIso8601String(),
      });
    });
    _saveChatHistory();
    _scrollToBottom();
  }

  // 📋 E. SALIN TEKS KE CLIPBOARD HP
  void _copyToClipboard(String text) {
    Clipboard.setData(ClipboardData(text: text));
    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(
        content: Text("📋 Pesan J.A.R.V.I.S. berhasil disalin!"),
        duration: Duration(seconds: 2),
        backgroundColor: Color(0xFFFFD700),
      ),
    );
  }

  // 🕒 F. FORMAT TIMESTAMP HH:MM WIB
  String _formatTimestamp(String? isoString) {
    if (isoString == null) return "";
    try {
      final dt = DateTime.parse(isoString).toLocal();
      final hour = dt.hour.toString().padLeft(2, '0');
      final minute = dt.minute.toString().padLeft(2, '0');
      return "$hour:$minute WIB";
    } catch (e) {
      return "";
    }
  }

  void _scrollToBottom() {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (_scrollController.hasClients) {
        _scrollController.animateTo(
          _scrollController.position.maxScrollExtent,
          duration: const Duration(milliseconds: 300),
          curve: Curves.easeOut,
        );
      }
    });
  }

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
                _sendMessage(_controller.text, isVoiceInput: true);
              }
            }
          },
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

  // 🚀 FUNGSI UTAMA PENGIRIMAN PESAN
  Future<void> _sendMessage(String text, {bool isVoiceInput = false}) async {
    if (text.trim().isEmpty && _selectedImage == null) return;

    if (_isListening) {
      _speech.stop();
      if (mounted) setState(() => _isListening = false);
    }

    String userMsg = text.trim();
    File? imageToSend = _selectedImage;

    _addMessage("user", userMsg.isEmpty ? "[Mengirim Gambar]" : userMsg, image: imageToSend);
    _controller.clear();
    setState(() {
      _selectedImage = null;
      _isLoading = true;
    });
    _nanoActivityController.forward(from: 0.0);

    try {
      List<int>? imageBytes = imageToSend != null ? await imageToSend.readAsBytes() : null;
      String base64Image = imageBytes != null ? base64Encode(imageBytes) : "";

      final response = await http.post(
        Uri.parse("$serverUrl/chat"),
        headers: {"Content-Type": "application/json"},
        body: jsonEncode({
          "message": userMsg.isEmpty ? "Tolong analisis gambar ini, Bos." : userMsg,
          "image_base64": base64Image,
          "is_voice_input": isVoiceInput
        }),
      ).timeout(const Duration(seconds: 120));

      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        
        Uint8List? imgBytes;
        if (data["image_base64"] != null && data["image_base64"].toString().isNotEmpty) {
          imgBytes = base64Decode(data["image_base64"]);
        }

        _addMessage("jarvis", data["reply"] ?? "Protocol executed.", imageBytes: imgBytes);

        if (data["audio_base64"] != null && data["audio_base64"].toString().isNotEmpty) {
          _playTtsAudio(data["audio_base64"]);
        }
      } else {
        _addMessage("jarvis", "🚨 [HTTP ERROR ${response.statusCode}]: ${response.body}");
      }
    } catch (e) {
      _addMessage("jarvis", "🚨 [A.S.C.A.R. NETWORK ERROR]: $e");
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
    _scrollController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Stack(
      children: [
        // ANIMASI HOLOGRAPHIC REACTOR BACKGROUND
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

        // SELECTION AREA (Agar Teks Obrolan BISA DI-BLOCK/COPY MANUAL)
        SelectionArea(
          child: Column(
            children: [
              Expanded(
                child: ListView.builder(
                  controller: _scrollController,
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
                        constraints: BoxConstraints(maxWidth: MediaQuery.of(context).size.width * 0.82),
                        decoration: BoxDecoration(
                          color: isUser
                              ? const Color(0xFFFFD700).withValues(alpha: 0.15)
                              : const Color(0xFF0F131D).withValues(alpha: 0.90),
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
                            if (imageBytes != null) ...[
                              ClipRRect(
                                borderRadius: BorderRadius.circular(8),
                                child: Image.memory(imageBytes, fit: BoxFit.contain),
                              ),
                              const SizedBox(height: 8),
                            ],

                            // RENDER TEKS DENGAN MARKDOWN SUPPORT
                            MarkdownBody(
                              data: msg["text"] ?? "",
                              styleSheet: MarkdownStyleSheet(
                                p: TextStyle(
                                  color: isUser ? const Color(0xFFFFF8E7) : const Color(0xFFFFE082),
                                  fontFamily: 'monospace',
                                  fontSize: 12.5,
                                  height: 1.3,
                                ),
                              ),
                            ),

                            const SizedBox(height: 8),

                            // 📊 FOOTER: ACTION BAR & TIMESTAMP
                            Row(
                              mainAxisAlignment: MainAxisAlignment.spaceBetween,
                              crossAxisAlignment: CrossAxisAlignment.center,
                              children: [
                                if (!isUser)
                                  Row(
                                    children: [
                                      InkWell(
                                        onTap: () => _copyToClipboard(msg["text"] ?? ""),
                                        child: const Row(
                                          children: [
                                            Icon(Icons.copy_rounded, size: 12, color: Color(0xFFFFD700)),
                                            SizedBox(width: 3),
                                            Text("Salin", style: TextStyle(color: Color(0xFFFFD700), fontSize: 11)),
                                          ],
                                        ),
                                      ),
                                      const SizedBox(width: 12),
                                      InkWell(
                                        onTap: () {
                                          setState(() {
                                            _messages.removeAt(index);
                                          });
                                          _saveChatHistory();
                                        },
                                        child: const Row(
                                          children: [
                                            Icon(Icons.delete_outline, size: 12, color: Colors.redAccent),
                                            SizedBox(width: 3),
                                            Text("Hapus", style: TextStyle(color: Colors.redAccent, fontSize: 11)),
                                          ],
                                        ),
                                      ),
                                    ],
                                  )
                                else
                                  const SizedBox(),

                                // 🕒 TIMESTAMP KETERANGAN WAKTU
                                Text(
                                  _formatTimestamp(msg["timestamp"]),
                                  style: TextStyle(
                                    color: isUser ? Colors.white54 : Colors.grey.shade600,
                                    fontSize: 10,
                                    fontFamily: 'monospace',
                                  ),
                                ),
                              ],
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
                              onSubmitted: (val) => _sendMessage(val, isVoiceInput: false),
                            ),
                          ),
                          IconButton(
                            onPressed: () => _sendMessage(_controller.text, isVoiceInput: false),
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
        ),
      ],
    );
  }
}

// ==========================================
// STARK DRAWER (M.I.N.D. PALACE ACCESS)
// ==========================================
class StarkDrawer extends StatelessWidget {
  const StarkDrawer({super.key});

  Future<void> _clearChatHistory(BuildContext context) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.remove('jarvis_chat_history');
    if (context.mounted) {
      Navigator.pop(context);
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text("🗑️ Memori obrolan lokal telah dibersihkan!"),
          backgroundColor: Colors.redAccent,
        ),
      );
    }
  }

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
          const Divider(color: Colors.white10),
          ListTile(
            leading: const Icon(Icons.delete_sweep_rounded, color: Colors.redAccent),
            title: const Text("Bersihkan Memori Chat", style: TextStyle(color: Colors.redAccent, fontSize: 12)),
            onTap: () => _clearChatHistory(context),
          ),
        ],
      ),
    );
  }
}

// ==========================================
// PERSISTENT WEBSOCKET SERVICE
// ==========================================
class JarvisWebSocketService {
  static final JarvisWebSocketService _instance = JarvisWebSocketService._internal();
  factory JarvisWebSocketService() => _instance;
  JarvisWebSocketService._internal();

  WebSocketChannel? channel;
  bool _isConnecting = false;

  void connect(Function(dynamic) onMessageReceived) {
    if (_isConnecting) return;
    _isConnecting = true;

    try {
      channel = WebSocketChannel.connect(
        Uri.parse("wss://worker-production-792b.up.railway.app/ws/stream_chat"),
      );
      
      channel!.stream.listen(
        (event) {
          _isConnecting = false;
          final data = jsonDecode(event);
          onMessageReceived(data);
        },
        onError: (error) {
          _isConnecting = false;
          debugPrint("📡 [WS OFFLINE]: Gagal terhubung ke server Railway. Coba lagi dalam 10s...");
          Future.delayed(const Duration(seconds: 10), () => connect(onMessageReceived));
        },
        onDone: () {
          _isConnecting = false;
          Future.delayed(const Duration(seconds: 10), () => connect(onMessageReceived));
        },
      );
    } catch (e) {
      _isConnecting = false;
      debugPrint("📡 [WS EXCEPTION]: $e");
      Future.delayed(const Duration(seconds: 10), () => connect(onMessageReceived));
    }
  }

  void disconnect() {
    channel?.sink.close();
  }
}

// ==========================================
// HOLOGRAPHIC QUANTUM PARTICLE REACTOR PAINTER
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