import 'dart:convert';
import 'package:http/http.dart' as http;
import 'package:flutter/foundation.dart'; // 👈 Tambahkan ini untuk debugPrint
import 'package:flutter_dotenv/flutter_dotenv.dart';

class JarvisService {
  // URL Railway diambil aman dari file .env
  static final String baseUrl = dotenv.env['RAILWAY_SERVER_URL'] ?? "https://worker-production-792b.up.railway.app";

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
      debugPrint("Error status: $e"); // 👈 Diubah dari print ke debugPrint
    }
    return {'status': 'offline', 'cpu_usage': 0, 'ram_usage': 0};
  }
}