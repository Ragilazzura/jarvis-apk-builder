// device_control_service.dart
import 'package:volume_controller/volume_controller.dart';
import 'package:screen_brightness/screen_brightness.dart';
import 'package:torch_light/torch_light.dart';
import 'package:disk_space_plus/disk_space_plus.dart';
import 'package:battery_plus/battery_plus.dart';

// Import A.S.C.A.R Reporter
import '../ascar_reporter_service.dart';

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
    } catch (e, stackTrace) {
      AscarReporter.reportMobileError(featureName: "Toggle Torch", errorMessage: e.toString(), stackTrace: stackTrace.toString());
      return "🚨 Gagal mengontrol senter. Laporan dikirim ke A.S.C.A.R.";
    }
  }

  // 🔆 2. KONTROL KECERAHAN LAYAR
  static Future<String> setBrightness(double level) async {
    try {
      double clamped = level.clamp(0.0, 1.0);
      await ScreenBrightness().setApplicationScreenBrightness(clamped);
      int percentage = (clamped * 100).round();
      return "🔆 Kecerahan layar disesuaikan ke $percentage%, Sir.";
    } catch (e, stackTrace) {
      AscarReporter.reportMobileError(featureName: "Set Brightness", errorMessage: e.toString(), stackTrace: stackTrace.toString());
      return "🚨 Gagal menyesuaikan kecerahan layar. Laporan dikirim.";
    }
  }

  // 🔊 3. KONTROL VOLUME MEDIA
  static Future<String> setVolume(double level) async {
    try {
      double clamped = level.clamp(0.0, 1.0);
      await VolumeController.instance.setVolume(clamped);
      int percentage = (clamped * 100).round();
      if (percentage == 0) {
        return "🔊 Audio berhasil di-mute (heningkan), Bos.";
      }
      return "🔊 Volume disesuaikan ke level $percentage%, Bos!";
    } catch (e, stackTrace) {
      AscarReporter.reportMobileError(featureName: "Set Volume", errorMessage: e.toString(), stackTrace: stackTrace.toString());
      return "🚨 Gagal mengubah volume. Laporan dikirim.";
    }
  }

  // 🔋 4. CEK STATUS BATERAI
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
    } catch (e, stackTrace) {
      AscarReporter.reportMobileError(featureName: "Check Battery", errorMessage: e.toString(), stackTrace: stackTrace.toString());
      return "🚨 Gagal membaca status baterai. Laporan dikirim.";
    }
  }

  // 🧹 5. DIAGNOSA STORAGE
  static Future<String> checkStorageDiagnostics() async {
    try {
      double? freeSpaceMB = await DiskSpacePlus().getFreeDiskSpace;
      double? totalSpaceMB = await DiskSpacePlus().getTotalDiskSpace;

      if (freeSpaceMB == null || totalSpaceMB == null) {
        throw Exception("Nilai storage yang dikembalikan plugin adalah null.");
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
    } catch (e, stackTrace) {
      AscarReporter.reportMobileError(featureName: "Check Storage", errorMessage: e.toString(), stackTrace: stackTrace.toString());
      return "🚨 Error saat membaca memori storage. Laporan dikirim ke A.S.C.A.R.";
    }
  }
}