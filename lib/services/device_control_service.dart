import 'package:volume_controller/volume_controller.dart';
import 'package:screen_brightness/screen_brightness.dart';
import 'package:torch_light/torch_light.dart';
import 'package:url_launcher/url_launcher.dart';
import 'package:disk_space_plus/disk_space_plus.dart';
import 'package:battery_plus/battery_plus.dart';
import 'package:flutter/foundation.dart';

class DeviceControlService {
  // 🔦 1. KONTROL SENTER (TORCH)
  static Future<String> toggleTorch(bool enable) async {
    try {
      if (enable) {
        await TorchLight.enableTorch();
        return "🔦 Senter dinyalakan, Sir.";
      } else {
        await TorchLight.disableTorch();
        return "🔦 Senter dimatikan, Sir.";
      }
    } catch (e) {
      return "🚨 Gagal mengontrol senter: Perangkat tidak mendukung atau izin ditolak.";
    }
  }

  // 🔆 2. KONTROL KECERAHAN LAYAR (0.0 - 1.0)
  static Future<String> setBrightness(double level) async {
    try {
      double clamped = level.clamp(0.0, 1.0);
      await ScreenBrightness().setApplicationScreenBrightness(clamped);
      int percentage = (clamped * 100).round();
      return "🔆 Kecerahan layar disesuaikan ke $percentage%, Sir.";
    } catch (e) {
      return "🚨 Gagal menyesuaikan kecerahan layar: $e";
    }
  }

  // 🔊 3. KONTROL VOLUME MEDIA (0.0 - 1.0)
  static Future<String> setVolume(double level) async {
    try {
      double clamped = level.clamp(0.0, 1.0);
      // Menggunakan instance sesuai struktur plugin volume_controller Anda
      await VolumeController.instance.setVolume(clamped);
      int percentage = (clamped * 100).round();
      if (percentage == 0) {
        return "🔊 Audio berhasil di-mute (heningkan), Bos.";
      }
      return "🔊 Volume disesuaikan ke level $percentage%, Bos!";
    } catch (e) {
      return "🚨 Gagal mengubah volume: $e";
    }
  }

  // 🔋 4. CEK STATUS BATERAI (BARU)
  static final Battery _battery = Battery();

  static Future<String> checkBatteryStatus() async {
    try {
      final int batteryLevel = await _battery.batteryLevel;
      final BatteryState batteryState = await _battery.batteryState;

      String statusString = "Normal";
      if (batteryState == BatteryState.charging) {
        statusString = "Sedang di-charge (mengisi daya)";
      } else if (batteryState == BatteryState.full) {
        statusString = "Penuh";
      }

      return "🔋 **[STATUS BATERAI PERANGKAT]**\n"
          "• Sisa Daya: $batteryLevel%\n"
          "• Kondisi: $statusString, Bos!";
    } catch (e) {
      debugPrint("🚨 Error Baterai: $e");
      return "🚨 Gagal membaca status baterai perangkat: $e";
    }
  }

  // 🧹 5. DIAGNOSA STORAGE / PENYIMPANAN HP
  static Future<String> checkStorageDiagnostics() async {
    try {
      double? freeSpaceMB = await DiskSpacePlus().getFreeDiskSpace;
      double? totalSpaceMB = await DiskSpacePlus().getTotalDiskSpace;

      if (freeSpaceMB == null || totalSpaceMB == null) {
        return "🚨 Gagal membaca data penyimpanan HP.";
      }

      double freeGB = freeSpaceMB / 1024;
      double totalGB = totalSpaceMB / 1024;
      double usedGB = totalGB - freeGB;
      double usedPercentage = (usedGB / totalGB) * 100;

      return "📊 **[DIAGNOSA PENYIMPANAN HP]**\n"
          "• Total Kapasitas: ${totalGB.toStringAsFixed(1)} GB\n"
          "• Terpakai: ${usedGB.toStringAsFixed(1)} GB (${usedPercentage.toStringAsFixed(1)}%)\n"
          "• Ruang Kosong: ${freeGB.toStringAsFixed(1)} GB\n"
          "${freeGB < 5.0 ? '⚠️ **Peringatan**: Ruang penyimpanan tersisa sangat tipis, Bos!' : '✅ Penyimpanan dalam kondisi sehat, Bos!'}";
    } catch (e) {
      return "🚨 Error saat membaca memori storage: $e";
    }
  }

  // 🚀 6. LAUNCH APLIKASI UTAMA (VIA NATIVE SCHEME & URL LAUNCHER)
  static Future<String> launchExternalApp({
    required String appScheme,
    required String fallbackUrl,
    required String appName,
  }) async {
    try {
      Uri nativeUri = Uri.parse(appScheme);
      Uri webUri = Uri.parse(fallbackUrl);

      if (await canLaunchUrl(nativeUri)) {
        await launchUrl(nativeUri, mode: LaunchMode.externalApplication);
        return "🚀 Membuka aplikasi $appName, Sir!";
      } else if (await canLaunchUrl(webUri)) {
        await launchUrl(webUri, mode: LaunchMode.externalApplication);
        return "🚀 Membuka $appName, Sir!";
      } else {
        return "⚠️ Tidak dapat meluncurkan $appName di perangkat ini.";
      }
    } catch (e) {
      return "🚨 Error saat membuka $appName: $e";
    }
  }

  // ⏰ 7. ALARM SISTEM ANDROID
  static Future<String> setSystemAlarm(int hour, int minute, String message) async {
    try {
      final Uri alarmUri = Uri.parse(
        'intent#Intent;action=android.intent.action.SET_ALARM;'
        'i.android.intent.extra.alarm.HOUR=$hour;'
        'i.android.intent.extra.alarm.MINUTES=$minute;'
        'S.android.intent.extra.alarm.MESSAGE=$message;'
        'b.android.intent.extra.alarm.SKIP_UI=false;'
        'end;',
      );

      if (await canLaunchUrl(alarmUri)) {
        await launchUrl(alarmUri);
        return "Alarm sistem berhasil di-set untuk jam ${hour.toString().padLeft(2, '0')}:${minute.toString().padLeft(2, '0')} WIB, Bos!";
      } else {
        return "Gagal membuka modul Alarm sistem di perangkat ini.";
      }
    } catch (e) {
      debugPrint("🚨 Error Alarm: $e");
      return "Terjadi kesalahan sistem saat memasang alarm: $e";
    }
  }

  // 🎵 8. DEEP LINKING (SEARCH & AUTO PLAY)
  static Future<String> openMediaWithQuery(String platform, String query) async {
    try {
      Uri uri;
      String encodedQuery = Uri.encodeComponent(query);

      if (platform.toLowerCase() == "youtube") {
        uri = Uri.parse("https://www.youtube.com/results?search_query=$encodedQuery");
      } else if (platform.toLowerCase() == "spotify") {
        uri = Uri.parse("spotify:search:$encodedQuery");
      } else {
        uri = Uri.parse("https://www.google.com/search?q=$encodedQuery");
      }

      if (await canLaunchUrl(uri)) {
        await launchUrl(uri, mode: LaunchMode.externalApplication);
        return "🎶 Mencari '$query' di $platform, Sir!";
      } else {
        return "🚨 Tidak dapat mengarahkan perintah ke $platform.";
      }
    } catch (e) {
      return "🚨 Deep link error: $e";
    }
  }
}