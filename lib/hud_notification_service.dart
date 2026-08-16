import 'package:flutter_local_notifications/flutter_local_notifications.dart';
import 'package:timezone/data/latest.dart' as tz;
import 'package:timezone/timezone.dart' as tz;

class HudNotificationService {
  static final FlutterLocalNotificationsPlugin _notificationsPlugin =
      FlutterLocalNotificationsPlugin();

  // 🚀 Inisialisasi Service Notifikasi & Alarm
  static Future<void> init() async {
    tz.initializeTimeZones();
    tz.setLocalLocation(tz.getLocation('Asia/Jakarta'));

    const AndroidInitializationSettings androidSettings =
        AndroidInitializationSettings('@mipmap/ic_launcher');

    const InitializationSettings initSettings = InitializationSettings(
      android: androidSettings,
    );

    await _notificationsPlugin.initialize(
      settings: initSettings,
      onDidReceiveNotificationResponse: (NotificationResponse details) {
        // Logika ketika notifikasi/alarm ditap oleh pengguna
      },
    );

    // Minta Izin Notifikasi khusus Android 13+ (Diperbarui untuk v22+)
    await _notificationsPlugin
        .resolvePlatformSpecificImplementation<
            AndroidFlutterLocalNotificationsPlugin>()
        ?.requestNotificationsPermission();
  }

  // 🔔 1. KIRIM NOTIFIKASI SEMENTARA / INSTAN (Untuk alert dari PC / System)
  static Future<void> showInstantNotification({
    required String title,
    required String body,
  }) async {
    const AndroidNotificationDetails androidDetails =
        AndroidNotificationDetails(
      'stark_hud_channel',
      'J.A.R.V.I.S. System Alerts',
      channelDescription: 'Notifikasi darurat dan laporan sistem Jarvis',
      importance: Importance.max,
      priority: Priority.high,
      showWhen: true,
    );

    const NotificationDetails platformDetails =
        NotificationDetails(android: androidDetails);

    await _notificationsPlugin.show(
      id: DateTime.now().millisecond,
      title: title,
      body: body,
      notificationDetails: platformDetails,
    );
  }

  // ⏰ 2. PASANG ALARM / PENGINGAT PRESISI (Sesuai Jam & Menit)
  static Future<String> scheduleAlarm({
    required int hour,
    required int minute,
    required String title,
    required String body,
  }) async {
    final now = DateTime.now();
    var scheduledDate = DateTime(now.year, now.month, now.day, hour, minute);

    if (scheduledDate.isBefore(now)) {
      scheduledDate = scheduledDate.add(const Duration(days: 1));
    }

    const AndroidNotificationDetails androidDetails =
        AndroidNotificationDetails(
      'stark_alarm_channel',
      'J.A.R.V.I.S. Scheduled Alarms',
      channelDescription: 'Pengingat & Alarm Presisi Jarvis',
      importance: Importance.max,
      priority: Priority.high,
      playSound: true,
      enableVibration: true,
    );

    const NotificationDetails platformDetails =
        NotificationDetails(android: androidDetails);

    int alarmId = hour * 100 + minute;

    await _notificationsPlugin.zonedSchedule(
      id: alarmId,
      title: title,
      body: body,
      scheduledDate: tz.TZDateTime.from(scheduledDate, tz.local),
      notificationDetails: platformDetails,
      androidScheduleMode: AndroidScheduleMode.exactAllowWhileIdle,
    );

    String timeFormatted =
        "${hour.toString().padLeft(2, '0')}:${minute.toString().padLeft(2, '0')}";
    return "Alarm Jarvis berhasil dipasang untuk jam $timeFormatted WIB, Bos!";
  }
}