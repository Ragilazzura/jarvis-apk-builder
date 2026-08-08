import 'dart:convert';
import 'dart:typed_data';
import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'package:audioplayers/audioplayers.dart'; // 👈 Import audioplayers

void main() {
  runApp(const JarvisHudApp());
}

class JarvisHudApp extends StatelessWidget {
  const JarvisHudApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'J.A.R.V.I.S. Stark HUD',
      debugShowCheckedModeBanner: false,
      theme: ThemeData.dark().copyWith(
        scaffoldBackgroundColor: const Color(0xFF0A0E17),
        colorScheme: const ColorScheme.dark(
          primary: Color(0xFF00F0FF),
          secondary: Color(0xFFFF3366),
          surface: Color(0xFF121929),
        ),
      ),
      home: const StarkHudScreen(),
    );
  }
}

class StarkHudScreen extends StatefulWidget {
  const StarkHudScreen({super.key});

  @override
  State<StarkHudScreen> createState() => _StarkHudScreenState();
}

class _StarkHudScreenState extends State<StarkHudScreen> {
  // ⚠️ GANTI DENGAN URL RAILWAY JARVIS MILIK BOS
  final String _baseUrl = "https://web-production-xxxx.up.railway.app";

  final TextEditingController _messageController = TextEditingController();
  final ScrollController _scrollController = ScrollController();
  final AudioPlayer _audioPlayer = AudioPlayer(); // 👈 Pemutar Audio

  final List<Map<String, dynamic>> _messages = [
    {
      "sender": "jarvis",
      "text": "At your service, Boss. Voice system initialized.",
      "audio_base64": ""
    }
  ];

  bool _isLoading = false;
  double _cpuUsage = 0.0;
  double _ramUsage = 0.0;
  bool _isLockdown = false;
  bool _isOnline = false;

  @override
  void initState() {
    super.initState();
    _fetchStatus();
  }

  @override
  void dispose() {
    _audioPlayer.dispose();
    super.dispose();
  }

  /// Memutar audio dari string Base64
  Future<void> _playAudio(String base64String) async {
    if (base64String.isEmpty) return;
    try {
      final Uint8List bytes = base64Decode(base64String);
      await _audioPlayer.stop();
      await _audioPlayer.play(BytesSource(bytes));
    } catch (e) {
      print("Error playing audio: $e");
    }
  }

  Future<void> _fetchStatus() async {
    try {
      final response = await http
          .get(Uri.parse('$_baseUrl/status'))
          .timeout(const Duration(seconds: 5));

      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        setState(() {
          _isOnline = true;
          _cpuUsage = (data['cpu_usage'] ?? 0.0).toDouble();
          _ramUsage = (data['ram_usage'] ?? 0.0).toDouble();
          _isLockdown = data['lockdown'] ?? false;
        });
      } else {
        setState(() => _isOnline = false);
      }
    } catch (_) {
      setState(() => _isOnline = false);
    }
  }

  Future<void> _sendMessage() async {
    final text = _messageController.text.trim();
    if (text.isEmpty || _isLoading) return;

    _messageController.clear();
    setState(() {
      _messages.add({"sender": "user", "text": text, "audio_base64": ""});
      _isLoading = true;
    });

    _scrollToBottom();

    try {
      final response = await http.post(
        Uri.parse('$_baseUrl/chat'),
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode({'message': text}),
      );

      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        final reply = data['reply'] ?? "Tidak ada respons dari server.";
        final audioB64 = data['audio_base64'] ?? "";

        setState(() {
          _messages.add({
            "sender": "jarvis",
            "text": reply,
            "audio_base64": audioB64,
          });
        });

        // 🔊 OTOMATIS PUTAR BALASAN SUARA JARVIS!
        if (audioB64.isNotEmpty) {
          _playAudio(audioB64);
        }
      } else {
        setState(() {
          _messages.add({
            "sender": "jarvis",
            "text": "🚨 Error Server HTTP ${response.statusCode}",
            "audio_base64": ""
          });
        });
      }
    } catch (e) {
      setState(() {
        _messages.add({
          "sender": "jarvis",
          "text": "🚨 Gagal terhubung ke Jarvis API: $e",
          "audio_base64": ""
        });
      });
    } finally {
      setState(() => _isLoading = false);
      _scrollToBottom();
      _fetchStatus();
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

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        backgroundColor: const Color(0xFF0F172A),
        elevation: 0,
        title: Row(
          children: [
            Container(
              width: 14,
              height: 14,
              decoration: BoxDecoration(
                shape: BoxShape.circle,
                color: _isOnline ? const Color(0xFF00F0FF) : Colors.red,
                boxShadow: [
                  BoxShadow(
                    color: (_isOnline ? const Color(0xFF00F0FF) : Colors.red)
                        .withOpacity(0.8),
                    blurRadius: 10,
                    spreadRadius: 2,
                  ),
                ],
              ),
            ),
            const SizedBox(width: 12),
            const Text(
              "J.A.R.V.I.S. HUD",
              style: TextStyle(
                color: Color(0xFF00F0FF),
                fontWeight: FontWeight.bold,
                letterSpacing: 1.5,
              ),
            ),
          ],
        ),
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh, color: Color(0xFF00F0FF)),
            onPressed: _fetchStatus,
          ),
        ],
      ),
      body: SafeArea(
        child: Column(
          children: [
            _buildStatusHeader(),
            Expanded(
              child: ListView.builder(
                controller: _scrollController,
                padding: const EdgeInsets.all(16),
                itemCount: _messages.length,
                itemBuilder: (context, index) {
                  final msg = _messages[index];
                  final isJarvis = msg['sender'] == 'jarvis';
                  return _buildChatBubble(
                    msg['text'] ?? '',
                    isJarvis,
                    msg['audio_base64'] ?? '',
                  );
                },
              ),
            ),
            if (_isLoading)
              const LinearProgressIndicator(
                backgroundColor: Colors.transparent,
                color: Color(0xFF00F0FF),
              ),
            _buildInputBar(),
          ],
        ),
      ),
    );
  }

  Widget _buildStatusHeader() {
    return Container(
      margin: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: const Color(0xFF121929),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: const Color(0xFF00F0FF).withOpacity(0.3)),
      ),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceAround,
        children: [
          _buildStatusMetric("CPU", "${_cpuUsage.toStringAsFixed(1)}%"),
          Container(width: 1, height: 24, color: Colors.white24),
          _buildStatusMetric("RAM", "${_ramUsage.toStringAsFixed(1)}%"),
          Container(width: 1, height: 24, color: Colors.white24),
          _buildStatusMetric(
            "SECURITY",
            _isLockdown ? "LOCKED" : "ACTIVE",
            isWarning: _isLockdown,
          ),
        ],
      ),
    );
  }

  Widget _buildStatusMetric(String label, String value,
      {bool isWarning = false}) {
    return Column(
      children: [
        Text(
          label,
          style: const TextStyle(fontSize: 10, color: Colors.white54),
        ),
        const SizedBox(height: 4),
        Text(
          value,
          style: TextStyle(
            fontSize: 13,
            fontWeight: FontWeight.bold,
            color: isWarning ? Colors.redAccent : const Color(0xFF00F0FF),
          ),
        ),
      ],
    );
  }

  Widget _buildChatBubble(String text, bool isJarvis, String audioBase64) {
    return Align(
      alignment: isJarvis ? Alignment.centerLeft : Alignment.centerRight,
      child: Container(
        margin: const EdgeInsets.symmetric(vertical: 6),
        padding: const EdgeInsets.all(14),
        constraints: const BoxConstraints(maxWidth: 300),
        decoration: BoxDecoration(
          color: isJarvis ? const Color(0xFF1E293B) : const Color(0xFF0284C7),
          borderRadius: BorderRadius.circular(16),
          border: Border.all(
            color: isJarvis
                ? const Color(0xFF00F0FF).withOpacity(0.4)
                : Colors.transparent,
          ),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              text,
              style: const TextStyle(color: Colors.white, fontSize: 14),
            ),
            // 🔊 Tombol Putar Ulang Suara jika ada audio
            if (isJarvis && audioBase64.isNotEmpty) ...[
              const SizedBox(height: 8),
              InkWell(
                onTap: () => _playAudio(audioBase64),
                child: const Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Icon(Icons.volume_up, size: 16, color: Color(0xFF00F0FF)),
                    SizedBox(width: 4),
                    Text(
                      "Replay Voice",
                      style: TextStyle(fontSize: 11, color: Color(0xFF00F0FF)),
                    ),
                  ],
                ),
              ),
            ]
          ],
        ),
      ),
    );
  }

  Widget _buildInputBar() {
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: const BoxDecoration(
        color: Color(0xFF0F172A),
        border: Border(top: BorderSide(color: Colors.white10)),
      ),
      child: Row(
        children: [
          Expanded(
            child: TextField(
              controller: _messageController,
              style: const TextStyle(color: Colors.white),
              decoration: InputDecoration(
                hintText: "Enter command for Jarvis...",
                hintStyle: const TextStyle(color: Colors.white38),
                filled: true,
                fillColor: const Color(0xFF1E293B),
                border: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(24),
                  borderSide: BorderSide.none,
                ),
              ),
              onSubmitted: (_) => _sendMessage(),
            ),
          ),
          const SizedBox(width: 8),
          IconButton(
            style: IconButton.styleFrom(
              backgroundColor: const Color(0xFF00F0FF),
              foregroundColor: Colors.black,
            ),
            icon: const Icon(Icons.send_rounded),
            onPressed: _sendMessage,
          ),
        ],
      ),
    );
  }
}