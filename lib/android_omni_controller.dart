// android_omni_controller.dart
import 'package:url_launcher/url_launcher.dart';

// Import A.S.C.A.R Reporter
import 'ascar_reporter_service.dart';

class AndroidOmniController {
  
  // 1. 💬 KIRIM PESAN WHATSAPP
  static Future<String> sendWhatsApp({required String phone, required String message}) async {
    String cleanPhone = phone.replaceAll(RegExp(r'[^\d]'), '');
    if (cleanPhone.startsWith('0')) {
      cleanPhone = '62${cleanPhone.substring(1)}';
    }

    final Uri whatsappUri = Uri.parse("whatsapp://send?phone=$cleanPhone&text=${Uri.encodeComponent(message)}");

    try {
      if (await canLaunchUrl(whatsappUri)) {
        await launchUrl(whatsappUri);
        return "Membuka WhatsApp dan menyiapkan pesan ke $cleanPhone, Bos!";
      } else {
        final Uri webUri = Uri.parse("https://wa.me/$cleanPhone?text=${Uri.encodeComponent(message)}");
        await launchUrl(webUri, mode: LaunchMode.externalApplication);
        return "Membuka WhatsApp Web untuk mengirim pesan, Bos.";
      }
    } catch (e, stackTrace) {
      AscarReporter.reportMobileError(featureName: "Send WhatsApp", errorMessage: e.toString(), stackTrace: stackTrace.toString());
      return "🚨 Gagal mengirim WhatsApp. Laporan dikirim ke A.S.C.A.R.";
    }
  }

  // 2. ✉️ KIRIM SMS
  static Future<String> sendSMS({required String phone, required String message}) async {
    final Uri smsUri = Uri(scheme: 'sms', path: phone, queryParameters: <String, String>{'body': message});

    try {
      if (await canLaunchUrl(smsUri)) {
        await launchUrl(smsUri);
        return "Aplikasi SMS terbuka dengan draft ke $phone, Bos!";
      } else {
        return "🚨 Tidak dapat membuka aplikasi SMS di HP ini.";
      }
    } catch (e, stackTrace) {
      AscarReporter.reportMobileError(featureName: "Send SMS", errorMessage: e.toString(), stackTrace: stackTrace.toString());
      return "🚨 Gagal memicu SMS. Laporan dikirim.";
    }
  }

  // 3. 📞 PANGGIL NOMOR TELEPON
  static Future<String> makePhoneCall(String phone) async {
    final Uri phoneUri = Uri(scheme: 'tel', path: phone);
    try {
      if (await canLaunchUrl(phoneUri)) {
        await launchUrl(phoneUri);
        return "Melakukan panggilan ke $phone...";
      } else {
        return "🚨 Gagal melakukan panggilan telepon.";
      }
    } catch (e, stackTrace) {
      AscarReporter.reportMobileError(featureName: "Make Phone Call", errorMessage: e.toString(), stackTrace: stackTrace.toString());
      return "🚨 Error Telepon. Laporan dikirim.";
    }
  }

  // ⏰ 4. SET ALARM NATIVE HP (DI-PERBAIKI AGAR TIDAK GAGAL PARSING INTENT)
  static Future<String> setAlarm({required int hour, required int minute, required String message}) async {
    // Menggunakan format string intent langsung agar aman ditangkap oleh Android OS
    final String intentString = "intent://#Intent;action=android.intent.action.SET_ALARM;"
        "i.android.intent.extra.HOUR=$hour;"
        "i.android.intent.extra.MINUTES=$minute;"
        "s.android.intent.extra.MESSAGE=${Uri.encodeComponent(message)};"
        "b.android.intent.extra.SKIP_UI=true;end;";

    try {
      final Uri alarmUri = Uri.parse(intentString);
      // Memaksa peluncuran menggunakan externalApplication agar memicu sistem alarm bawaan HP
      if (await canLaunchUrl(alarmUri)) {
        await launchUrl(alarmUri, mode: LaunchMode.externalApplication);
        return "Alarm berhasil dipasang untuk jam ${hour.toString().padLeft(2, '0')}:${minute.toString().padLeft(2, '0')}, Bos!";
      } else {
        return "🚨 Aplikasi Jam/Alarm tidak merespons di perangkat ini.";
      }
    } catch (e, stackTrace) {
      AscarReporter.reportMobileError(featureName: "Set Alarm", errorMessage: e.toString(), stackTrace: stackTrace.toString());
      return "🚨 Gagal memasang alarm. Laporan dikirim.";
    }
  }

  // 🚀 5. BUKA APLIKASI DI HP 
  static Future<String> launchPhoneApp(String appName) async {
    String scheme = "";
    String appLower = appName.toLowerCase();

    if (appLower.contains("whatsapp")) {
      scheme = "whatsapp://";
    } else if (appLower.contains("spotify")) {
      scheme = "spotify://";
    } else if (appLower.contains("youtube")) {
      scheme = "vnd.youtube://";
    } else {
      return "⚠️ Perintah buka aplikasi '$appName' belum terdaftar di sistem Jarvis.";
    }

    try {
      final Uri appUri = Uri.parse(scheme);
      if (await canLaunchUrl(appUri)) {
        await launchUrl(appUri, mode: LaunchMode.externalApplication);
        return "Membuka aplikasi $appName di HP, Bos!";
      } else {
        return "🚨 Aplikasi $appName tidak ditemukan di HP ini.";
      }
    } catch (e, stackTrace) {
      AscarReporter.reportMobileError(featureName: "Launch App ($appName)", errorMessage: e.toString(), stackTrace: stackTrace.toString());
      return "🚨 Gagal membuka aplikasi $appName. Laporan dikirim.";
    }
  }

  // 🎵 6. DEEP LINKING (SEARCH & AUTO PLAY)
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
    } catch (e, stackTrace) {
      AscarReporter.reportMobileError(featureName: "Open Media ($platform)", errorMessage: e.toString(), stackTrace: stackTrace.toString());
      return "🚨 Deep link error. Laporan dikirim.";
    }
  }
}