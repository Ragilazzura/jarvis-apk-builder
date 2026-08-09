import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'dart:convert';
import 'dart:typed_data';
import 'package:audioplayers/audioplayers.dart';

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
        scaffoldBackgroundColor: const Color(0xFF0A0F1D),
        primaryColor: const Color(0xFF00E5FF),
        colorScheme: const ColorScheme.dark(
          primary: Color(0xFF00E5FF),
          secondary: Color(0xFF2979FF),
          surface: Color(0xFF111827),
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

class _HUDHomeScreenState extends State<HUDHomeScreen> {
  final TextEditingController _controller = TextEditingController();
  final List<Map<String, String>> _messages = [];
  bool _isLoading = false;

  final AudioPlayer _audioPlayer = AudioPlayer();
  final String serverUrl = "https://worker-production-792b.up.railway.app";

  @override
  void initState() {
    super.initState();
    _addJarvisMessage("Stark HUD Mega-Core Online. At your service, Boss.");
  }

  void _addJarvisMessage(String text) {
    setState(() {
      _messages.add({"sender": "jarvis", "text": text});
    });
  }

  Future<void> _sendMessage(String text) async {
    if (text.trim().isEmpty) return;

    setState(() {
      _messages.add({"sender": "user", "text": text});
      _isLoading = true;
    });

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
    }
  }

  void _executeQuickCommand(String command) {
    _sendMessage(command);
  }

  @override
  void dispose() {
    _audioPlayer.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text(
          "J.A.R.V.I.S. // MEGA-HUD",
          style: TextStyle(letterSpacing: 2, fontSize: 15, color: Color(0xFF00E5FF), fontWeight: FontWeight.bold),
        ),
        backgroundColor: const Color(0xFF111827),
        elevation: 4,
        shadowColor: const Color(0xFF00E5FF).withValues(alpha: 0.3),
        centerTitle: true,
      ),
      body: Column(
        children: [
          // 🎛️ PANEL KONTROL PINTASAN LENGKAP
          Container(
            padding: const EdgeInsets.symmetric(vertical: 8, horizontal: 12),
            color: const Color(0xFF111827).withValues(alpha: 0.9),
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

          // 💬 AREA CHAT UTAMA
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
                    padding: const EdgeInsets.all(12),
                    constraints: BoxConstraints(maxWidth: MediaQuery.of(context).size.width * 0.75),
                    decoration: BoxDecoration(
                      color: isUser ? const Color(0xFF1E3A8A) : const Color(0xFF1F2937),
                      borderRadius: BorderRadius.circular(8),
                      border: Border.all(
                        color: isUser ? const Color(0xFF3B82F6) : const Color(0xFF00E5FF).withValues(alpha: 0.4),
                        width: 1,
                      ),
                    ),
                    child: Text(
                      msg["text"] ?? "",
                      style: TextStyle(
                        color: isUser ? Colors.white : const Color(0xFFE5E7EB),
                        fontFamily: 'monospace',
                        fontSize: 13,
                      ),
                    ),
                  ),
                );
              },
            ),
          ),
          
          if (_isLoading)
            const Padding(
              padding: EdgeInsets.all(8.0),
              child: LinearProgressIndicator(color: Color(0xFF00E5FF)),
            ),

          // ⌨️ INPUT COMMAND & MIC BUTTON
          Container(
            padding: const EdgeInsets.all(12),
            color: const Color(0xFF111827),
            child: Row(
              children: [
                // Tombol Mikrofon Cepat (Simulasi Voice Input)
                IconButton(
                  onPressed: () {
                    _sendMessage("Berikan laporan status sistem singkat, Bos.");
                  },
                  icon: const Icon(Icons.mic, color: Color(0xFF00E5FF)),
                  style: IconButton.styleFrom(
                    backgroundColor: const Color(0xFF0A0F1D),
                    padding: const EdgeInsets.all(12),
                    side: BorderSide(color: const Color(0xFF00E5FF).withValues(alpha: 0.3)),
                  ),
                ),
                const SizedBox(width: 8),
                Expanded(
                  child: TextField(
                    controller: _controller,
                    style: const TextStyle(color: Colors.white, fontFamily: 'monospace'),
                    decoration: InputDecoration(
                      hintText: "Enter command or ask Jarvis...",
                      hintStyle: TextStyle(color: Colors.grey.shade600),
                      filled: true,
                      fillColor: const Color(0xFF0A0F1D),
                      contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
                      border: OutlineInputBorder(
                        borderRadius: BorderRadius.circular(8),
                        borderSide: BorderSide.none,
                      ),
                      focusedBorder: OutlineInputBorder(
                        borderRadius: BorderRadius.circular(8),
                        borderSide: const BorderSide(color: Color(0xFF00E5FF), width: 1),
                      ),
                    ),
                    onSubmitted: _sendMessage,
                  ),
                ),
                const SizedBox(width: 8),
                IconButton(
                  onPressed: () => _sendMessage(_controller.text),
                  icon: const Icon(Icons.send, color: Color(0xFF00E5FF)),
                  style: IconButton.styleFrom(
                    backgroundColor: const Color(0xFF1F2937),
                    padding: const EdgeInsets.all(12),
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildQuickButton(String label, String command) {
    return ElevatedButton(
      onPressed: () => _executeQuickCommand(command),
      style: ElevatedButton.styleFrom(
        backgroundColor: const Color(0xFF1F2937),
        foregroundColor: const Color(0xFF00E5FF),
        side: BorderSide(color: const Color(0xFF00E5FF).withValues(alpha: 0.3)),
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
        textStyle: const TextStyle(fontFamily: 'monospace', fontSize: 12, fontWeight: FontWeight.bold),
      ),
      child: Text(label),
    );
  }
}