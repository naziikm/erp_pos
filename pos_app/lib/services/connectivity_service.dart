import 'dart:async';
import 'package:connectivity_plus/connectivity_plus.dart';
import 'package:dio/dio.dart';
import 'package:pos_app/services/api_client.dart';
import 'package:pos_app/core/constants.dart';

class ConnectivityService {
  final Connectivity _connectivity = Connectivity();
  final ApiClient _api = ApiClient();

  final _controller = StreamController<bool>.broadcast();
  Stream<bool> get onlineStream => _controller.stream;

  Timer? _pingTimer;
  bool _isOnline = true;
  bool get isOnline => _isOnline;

  void startMonitoring() {
    // Listen to native connectivity changes
    _connectivity.onConnectivityChanged.listen((results) {
      final hasNetwork = results.any((r) => r != ConnectivityResult.none);
      if (!hasNetwork) {
        _isOnline = false;
        _controller.add(false);
      } else {
        _pingBackend();
      }
    });

    // Periodic health check
    _pingTimer = Timer.periodic(
      const Duration(seconds: AppConstants.healthPollSeconds),
      (_) => _pingBackend(),
    );

    // Initial check
    _pingBackend();
  }

  Future<void> _pingBackend() async {
    try {
      final response = await _api.dio.get(
        '/health',
        options: Options(receiveTimeout: const Duration(seconds: 5)),
      );
      final erp = response.data['erp'];
      _isOnline = erp == 'reachable';
    } catch (_) {
      _isOnline = false;
    }
    _controller.add(_isOnline);
  }

  void dispose() {
    _pingTimer?.cancel();
    _controller.close();
  }
}
