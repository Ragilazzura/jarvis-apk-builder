// lib/services/jarvis_background_service.dart
import 'dart:ui';
import 'package:flutter/material.dart';
import 'package:flutter_background_service/flutter_background_service.dart';
import 'package:flutter_local_notifications/flutter_local_notifications.dart';
import 'package:flutter_dotenv/flutter_dotenv.dart'; // 👈 Wajib ada untuk isolate background
import 'jarvis_audio_streamer.dart';

Future<void> initializeBackgroundService() async {
  final service = FlutterBackgroundService();

  const AndroidNotificationChannel channel = AndroidNotificationChannel(
    'jarvis_foreground', 
    'J.A.R.V.I.S. Background Sentry', 
    description: 'Jarvis sedang siaga mendengarkan panggilan Bos via Server...',
    importance: Importance.low,
  );

  final FlutterLocalNotificationsPlugin flutterLocalNotificationsPlugin =
      FlutterLocalNotificationsPlugin();

  await flutterLocalNotificationsPlugin
      .resolvePlatformSpecificImplementation<
          AndroidFlutterLocalNotificationsPlugin>()
      ?.createNotificationChannel(channel);

  await service.configure(
    androidConfiguration: AndroidConfiguration(
      onStart: onStart,
      autoStart: true,
      isForegroundMode: true,
      notificationChannelId: 'jarvis_foreground',
      initialNotificationTitle: 'J.A.R.V.I.S. Cloud Online',
      initialNotificationContent: 'Sistem pendengaran awan aktif di latar belakang.',
    ),
    iosConfiguration: IosConfiguration(
      autoStart: true,
      onForeground: onStart,
    ),
  );
}

@pragma('vm:entry-point')
void onStart(ServiceInstance service) async {
  DartPluginRegistrant.ensureInitialized();
  WidgetsFlutterBinding.ensureInitialized();

  // 1. WAJIB: Load .env di isolate background agar URL Railway terbaca sempurna
  try {
    await dotenv.load(fileName: ".env");
  } catch (e) {
    debugPrint("⚠️ [BACKGROUND] Gagal memuat .env di isolate: $e");
  }

  debugPrint("🚀 [BACKGROUND] Service onStart berhasil dijalankan!");

  // 2. Inisialisasi Audio Streamer
  final audioStreamer = JarvisAudioStreamer();

  // 3. Mulai streaming audio mikrofon ke server Python Railway
  try {
    await audioStreamer.startStreaming(() {
      debugPrint("✨ [BACKGROUND] Server mengonfirmasi Wake Word terdeteksi!");
      service.invoke('wake_word_detected');
    });
  } catch (e) {
    debugPrint("🚨 [BACKGROUND] Gagal memulai audio streamer: $e");
  }

  service.on('startStreaming').listen((event) {
    audioStreamer.startStreaming(() {
      debugPrint("✨ [BACKGROUND] Server mengonfirmasi Wake Word terdeteksi!");
      service.invoke('wake_word_detected');
    });
  });

  service.on('stopService').listen((event) {
    audioStreamer.stopStreaming();
    service.stopSelf();
  });
}