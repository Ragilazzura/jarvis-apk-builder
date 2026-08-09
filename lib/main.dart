import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'dart:convert';
import 'package:flutter_tts/flutter_tts.dart'; // Mesin Suara Lokal HP

void main() {
  runApp(const StarkHUDApp());
}

class StarkHUDApp extends StatelessWidget {
  const StarkHUDApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'J.A.R.V.I.S. Stark HUD',
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

  // Inisialisasi Flutter TTS (Pita Suara HP)
  final FlutterTts _flutterTts = FlutterTts();

  // URL Railway backend Jarvis
  final String serverUrl = "https://worker-production-792b.up.railway.app/chat";

  @override
  void initState() {
    super.initState();
    _initTts();
  }

  // Pengaturan Suara (Bahasa Indonesia & Kecepatan)
  Future<void> _initTts() async {
    await _flutterTts.setLanguage("id-ID"); // Set bahasa Indonesia
    await _flutterTts.setSpeechRate(0.5);  // Kecepatan normal/stabil
    await _flutterTts.setVolume(1.0);      // Volume maksimal
    await _flutterTts.setPitch(1.0);       // Nada suara standar
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
        Uri.parse(serverUrl),
        headers: {"Content-Type": "application/json"},
        body: jsonEncode({"message": text, "is_voice_input": false}),
      );

      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        String replyText = data["reply"] ?? "Perintah diterima, Bos.";

        setState(() {
          _messages.add({"sender": "jarvis", "text": replyText});
        });

        // 🟢 EKSEKUSI SUARA LOKAL: HP Membacakan Teks dari Server secara Natural
        await _flutterTts.speak(replyText);

      } else {
        setState(() {
          _messages.add({"sender": "jarvis", "text": "🚨 Gagal terhubung ke server utama Stark."});
        });
      }
    } catch (e) {
      setState(() {
        _messages.add({"sender": "jarvis", "text": "🚨 Error koneksi jaringan: $e"});
      });
    } finally {
      setState(() {
        _isLoading = false;
      });
    }
  }

  @override
  void dispose() {
    _flutterTts.stop();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text(
          "J.A.R.V.I.S. // STARK HUD",
          style: TextStyle(letterSpacing: 2, fontSize: 16, color: Color(0xFF00E5FF), fontWeight: FontWeight.bold),
        ),
        backgroundColor: const Color(0xFF111827),
        elevation: 4,
        shadowColor: const Color(0xFF00E5FF).withOpacity(0.3),
        centerTitle: true,
      ),
      body: Column(
        children: [
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
                        color: isUser ? const Color(0xFF3B82F6) : const Color(0xFF00E5FF).withOpacity(0.4),
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

          Container(
            padding: const EdgeInsets.all(12),
            color: const Color(0xFF111827),
            child: Row(
              children: [
                Expanded(
                  child: TextField(
                    controller: _controller,
                    style: const TextStyle(color: Colors.white, fontFamily: 'monospace'),
                    decoration: InputDecoration(
                      hintText: "Masukkan perintah untuk Jarvis...",
                      hintStyle: TextStyle(color: Colors.grey.shade600),
                      filled: true,
                      fillColor: const Color(0xFF0A0F1D),
                      contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
                      border: OutlineInputBorder(
                        borderRadius: BorderRadius.circular(8),
                        borderSide: BorderSide.none,
                      ),
                      focusedBorder: OutlineInputBorder(
                        borderRadius: BorderRadius.circular(8) ?? BorderRadius.circular(8),
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
}