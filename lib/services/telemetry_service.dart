import 'dart:convert';
import 'package:battery_plus/battery_plus.dart';
import 'package:geolocator/geolocator.dart';
import 'package:http/http.dart' as http;
import 'package:flutter/foundation.dart'; 

class TelemetryService {
  final String baseUrl;
  final String secretKey;

  TelemetryService({required this.baseUrl, required this.secretKey});

  /// 🛰️ Ambil data sensor HP & kirim ke Server untuk Morning Briefing
  Future<String?> fetchMorningBriefing() async {
    try {
      // 1. Baca Status Baterai
      final Battery battery = Battery();
      final int batteryLevel = await battery.batteryLevel;
      final BatteryState batteryState = await battery.batteryState;
      final bool isCharging = (batteryState == BatteryState.charging || batteryState == BatteryState.full);

      // 2. Baca Lokasi (GPS) Sederhana
      String locationName = "Lokasi Lokal";
      try {
        LocationPermission permission = await Geolocator.checkPermission();
        if (permission == LocationPermission.denied) {
          permission = await Geolocator.requestPermission();
        }
        
        if (permission == LocationPermission.always || permission == LocationPermission.whileInUse) {
          // 👈 Diperbarui menggunakan locationSettings (menggantikan desiredAccuracy yang deprecated)
          Position position = await Geolocator.getCurrentPosition(
            locationSettings: const LocationSettings(
              accuracy: LocationAccuracy.low,
            ),
          );
          locationName = "${position.latitude.toStringAsFixed(2)}, ${position.longitude.toStringAsFixed(2)}";
        }
      } catch (e) {
        debugPrint("⚠️ [GPS]: Gagal mengambil koordinat: $e"); // 👈 Diubah dari print ke debugPrint
      }

      // 3. Susun Payload Telemetri
      final Map<String, dynamic> payload = {
        "location": locationName,
        "temperature": "28", // Opsional: BISA di-enrich via OpenWeather di backend nanti
        "weather": "Cerah Berawan",
        "battery_level": batteryLevel,
        "is_charging": isCharging,
        "events": ["Testing Integrasi Telemetri JARVIS HUD"]
      };

      // 4. Kirim ke Endpoint Backend
      final response = await http.post(
        Uri.parse("$baseUrl/client/telemetry_briefing"),
        headers: {
          "Authorization": secretKey,
          "Content-Type": "application/json",
        },
        body: jsonEncode(payload),
      );

      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        return data["briefing_message"];
      } else {
        debugPrint("🚨 [TELEMETRY ERROR]: HTTP ${response.statusCode}"); // 👈 Diubah ke debugPrint
        return null;
      }
    } catch (e) {
      debugPrint("🚨 [TELEMETRY EXCEPTION]: $e"); // 👈 Diubah ke debugPrint
      return null;
    }
  }
}