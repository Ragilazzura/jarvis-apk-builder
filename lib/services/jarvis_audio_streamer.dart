// lib/services/jarvis_audio_streamer.dart
import 'package:flutter/foundation.dart';
import 'package:web_socket_channel/web_socket_channel.dart';
import 'package:record/record.dart';
import 'package:flutter_dotenv/flutter_dotenv.dart';

class JarvisAudioStreamer {
  WebSocketChannel? _channel;
  final AudioRecorder _audioRecorder = AudioRecorder();
  bool _isStreaming = false;

  /// Memulai streaming audio ke backend Railway untuk deteksi wake word
  Future<void> startStreaming(VoidCallback onWakeWordDetected) async {
    if (_isStreaming) return;

    // Ambil URL Railway dari .env, ubah protokol dari https/http ke wss/ws
    final railwayUrl = dotenv.env['RAILWAY_SERVER_URL'] ?? "https://worker-production-792b.up.railway.app";
    final wsUrl = railwayUrl
        .replaceFirst('https://', 'wss://')
        .replaceFirst('http://', 'ws://');

    try {
      // 1. Hubungkan ke WebSocket endpoint server Python
      _channel = WebSocketChannel.connect(Uri.parse('$wsUrl/ws/audio_stream'));

      // 2. Dengarkan sinyal balasan dari server
      _channel!.stream.listen((message) {
        if (message.contains("wake_word_triggered") || message.contains("wake_word")) {
          debugPrint("🚨 [WEBSOCKET] Sinyal Wake Word Diterima dari Server!");
          onWakeWordDetected();
        }
      }, onError: (error) {
        debugPrint("❌ [WEBSOCKET ERROR]: $error");
      }, onDone: () {
        debugPrint("🔌 [WEBSOCKET] Koneksi audio stream terputus.");
        _isStreaming = false;
      });

      // 3. Mulai rekam stream mikrofon (PCM 16-bit, 16kHz, Mono)
      if (await _audioRecorder.hasPermission()) {
        final stream = await _audioRecorder.startStream(const RecordConfig(
          encoder: AudioEncoder.pcm16bits,
          sampleRate: 16000,
          numChannels: 1,
        ));

        _isStreaming = true;
        debugPrint("🎙️ [AUDIO STREAM] Mulai mengirim data audio ke server...");

        stream.listen((Uint8List rawData) {
          if (_channel != null && _isStreaming) {
            // Kirim potongan data biner mentah langsung ke server via WebSocket
            debugPrint("📤 Mengirim ${rawData.length} bytes audio ke server...");
            _channel!.sink.add(rawData);
          }
        });
      }
    } catch (e) {
      debugPrint("🚨 [STREAMING EXCEPTION]: $e");
    }
  }

  /// Menghentikan streaming audio
  Future<void> stopStreaming() async {
    _isStreaming = false;
    await _audioRecorder.stop();
    await _channel?.sink.close();
    debugPrint("🛑 [AUDIO STREAM] Dihentikan.");
  }
}