import 'package:url_launcher/url_launcher.dart';
import 'package:external_app_launcher/external_app_launcher.dart';

class AndroidOmniController {
  
  // 1. 💬 KIRIM PESAN WHATSAPP LANGSUNG DARI HP
  static Future<String> sendWhatsApp({required String phone, required String message}) async {
    // Format nomor harus diawali kode negara tanpa tanda '+' (Contoh: 628123456789)
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
        // Fallback via HTTPS Web API jika aplikasi WhatsApp belum terhubung
        final Uri webUri = Uri.parse("https://wa.me/$cleanPhone?text=${Uri.encodeComponent(message)}");
        await launchUrl(webUri, mode: LaunchMode.externalApplication);
        return "Membuka WhatsApp Web untuk mengirim pesan, Bos.";
      }
    } catch (e) {
      return "🚨 Gagal mengirim WhatsApp: $e";
    }
  }

  // 2. ✉️ KIRIM SMS NATIVE HP
  static Future<String> sendSMS({required String phone, required String message}) async {
    final Uri smsUri = Uri(
      scheme: 'sms',
      path: phone,
      queryParameters: <String, String>{
        'body': message,
      },
    );

    try {
      if (await canLaunchUrl(smsUri)) {
        await launchUrl(smsUri);
        return "Aplikasi SMS terbuka dengan draft ke $phone, Bos!";
      } else {
        return "🚨 Tidak dapat membuka aplikasi SMS di HP ini.";
      }
    } catch (e) {
      return "🚨 Gagal memicu SMS: $e";
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
    } catch (e) {
      return "🚨 Error Telepon: $e";
    }
  }

  // ⏰ SET ALARM NATIVE HP
static Future<String> setAlarm({required int hour, required int minute, required String message}) async {
  final Uri alarmUri = Uri(
    scheme: 'intent',
    path: '#Intent',
    queryParameters: {
      'action': 'android.intent.action.SET_ALARM',
      'extra.android.intent.extra.HOUR': hour.toString(),
      'extra.android.intent.extra.MINUTES': minute.toString(),
      'extra.android.intent.extra.MESSAGE': message,
      'extra.android.intent.extra.SKIP_UI': 'true', // Setel tanpa perlu konfirmasi manual
    },
  );

  try {
    if (await canLaunchUrl(alarmUri)) {
      await launchUrl(alarmUri);
      return "Alarm berhasil dipasang untuk jam ${hour.toString().padLeft(2, '0')}:${minute.toString().padLeft(2, '0')}, Bos!";
    } else {
      // Fallback intent standar
      final Uri fallbackUri = Uri.parse("intent://#Intent;action=android.intent.action.SET_ALARM;i.android.intent.extra.HOUR=$hour;i.android.intent.extra.MINUTES=$minute;s.android.intent.extra.MESSAGE=${Uri.encodeComponent(message)};b.android.intent.extra.SKIP_UI=true;end");
      await launchUrl(fallbackUri);
      return "Protokol pengesetan alarm dikirim ke aplikasi Jam HP, Bos.";
    }
  } catch (e) {
    return "🚨 Gagal memasang alarm: $e";
  }
}

  // 4. 🚀 BUKA APLIKASI DI HP (WhatsApp, Spotify, YouTube, dll)
  static Future<String> launchPhoneApp(String appName) async {
    String packageName = "";
    String appLower = appName.toLowerCase();

    if (appLower.contains("whatsapp")) {
      packageName = "com.whatsapp";
    } else if (appLower.contains("spotify")) {
      packageName = "com.spotify.music";
    } else if (appLower.contains("youtube")) {
      packageName = "com.google.android.youtube";
    } else if (appLower.contains("chrome")) {
      packageName = "com.android.chrome";
    } else {
      return "⚠️ Package Name untuk '$appName' belum terdaftar di sistem Jarvis.";
    }

    try {
      await LaunchApp.openApp(
        androidPackageName: packageName,
        openStore: true,
      );
      return "Membuka aplikasi $appName di HP, Bos!";
    } catch (e) {
      return "🚨 Gagal membuka aplikasi $appName: $e";
    }
  }
}