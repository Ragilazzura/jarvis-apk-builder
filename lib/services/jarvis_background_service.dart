// lib/services/jarvis_background_service.dart
import 'dart:ui';
import 'package:flutter/material.dart';
import 'package:flutter_background_service/flutter_background_service.dart';
import 'package:flutter_local_notifications/flutter_local_notifications.dart';
import 'jarvis_audio_streamer.dart'; // 👈 Import streamer baru kita

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

// WAJIB: Fungsi ini berjalan di latar belakang (Isolate terpisah)
@pragma('vm:entry-point')
void onStart(ServiceInstance service) async {
  DartPluginRegistrant.ensureInitialized();
  WidgetsFlutterBinding.ensureInitialized();

  // 1. Inisialisasi Audio Streamer
  final audioStreamer = JarvisAudioStreamer();

  // 2. Mulai streaming audio mikrofon ke server Python Railway
  await audioStreamer.startStreaming(() {
    // 3. Callback ini akan dieksekusi KETIKA Server Python membalas: 
    // "Hey Jarvis terdeteksi!"
    debugPrint("✨ [BACKGROUND] Server mengonfirmasi Wake Word terdeteksi!");
    
    // Tembakkan sinyal ke UI utama Flutter (jika aplikasi sedang terbuka/aktif)
    service.invoke('wake_word_detected');
  });

  // Listener jika service dihentikan paksa
  service.on('stopService').listen((event) {
    audioStreamer.stopStreaming();
    service.stopSelf();
  });
}