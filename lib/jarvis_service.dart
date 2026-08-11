import 'dart:convert';
import 'dart:developer';
import 'package:http/http.dart' as http;

class JarvisService {
  // Ganti dengan URL domain Railway milikmu
  static const String baseUrl = "https://web-production-xxxx.up.railway.app";

  /// Mengirim pesan ke Jarvis FastAPI
  static Future<String> sendMessage(String message) async {
    try {
      final response = await http.post(
        Uri.parse('$baseUrl/chat'),
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode({'message': message}),
      );

      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        return data['reply'] ?? "Tidak ada balasan dari Jarvis.";
      } else {
        return "Error Server (${response.statusCode})";
      }
    } catch (e) {
      return "Gagal terhubung ke Jarvis API: $e";
    }
  }

  /// Mengambil status kesehatan server Railway
  static Future<Map<String, dynamic>> fetchServerStatus() async {
    try {
      final response = await http.get(Uri.parse('$baseUrl/status'));
      if (response.statusCode == 200) {
        return jsonDecode(response.body);
      }
    } catch (e) {
      print("Error status: $e");
    }
    return {'status': 'offline', 'cpu_usage': 0, 'ram_usage': 0};
  }
}