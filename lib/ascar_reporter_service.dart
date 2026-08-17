// ascar_reporter_service.dart
import 'dart:convert';
import 'package:http/http.dart' as http;
import 'package:flutter/foundation.dart';

class AscarReporter {
  // URL Railway Bos
  static const String baseUrl = "https://worker-production-792b.up.railway.app";
  static const String secretKey = "STARK_OVERRIDE_SECRET_2026";

  static Future<void> reportMobileError({
    required String featureName, 
    required String errorMessage, 
    String? stackTrace
  }) async {
    try {
      final Map<String, dynamic> payload = {
        "feature": featureName,
        "error_message": errorMessage,
        "stack_trace": stackTrace ?? "Tidak ada stack trace",
        "platform": "Android HUD (Flutter)"
      };

      await http.post(
        Uri.parse("$baseUrl/client/mobile_error_report"),
        headers: {
          "Authorization": secretKey,
          "Content-Type": "application/json",
        },
        body: jsonEncode(payload),
      );
      debugPrint("🛡️ [A.S.C.A.R Reporter] Laporan error $featureName terkirim ke Cloud.");
    } catch (e) {
      debugPrint("🚨 [A.S.C.A.R Reporter] Gagal mengirim laporan ke Cloud: $e");
    }
  }
}