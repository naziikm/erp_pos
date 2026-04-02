import 'package:dio/dio.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:pos_app/core/constants.dart';

class ApiClient {
  late final Dio _dio;
  final FlutterSecureStorage _storage = const FlutterSecureStorage();

  static final ApiClient _instance = ApiClient._internal();
  factory ApiClient() => _instance;

  ApiClient._internal() {
    _dio = Dio(
      BaseOptions(
        baseUrl: AppConstants.baseUrl,
        connectTimeout: const Duration(seconds: 10),
        receiveTimeout: const Duration(seconds: 30),
        headers: {'Content-Type': 'application/json'},
      ),
    );

    _dio.interceptors.add(
      InterceptorsWrapper(
        onRequest: (options, handler) async {
          final licenseToken = await _storage.read(
            key: AppConstants.licenseTokenKey,
          );
          if (licenseToken != null) {
            options.headers['Authorization'] = 'Bearer $licenseToken';
          }
          final authToken = await _storage.read(key: AppConstants.authTokenKey);
          if (authToken != null) {
            options.headers['X-Auth-Token'] = authToken;
          }
          handler.next(options);
        },
        onError: (error, handler) {
          handler.next(error);
        },
      ),
    );
  }

  Dio get dio => _dio;

  void updateBaseUrl(String url) {
    _dio.options.baseUrl = url;
  }

  Future<void> storeLicenseToken(String token) async {
    await _storage.write(key: AppConstants.licenseTokenKey, value: token);
  }

  Future<void> storeAuthToken(String token) async {
    await _storage.write(key: AppConstants.authTokenKey, value: token);
  }

  Future<String?> getLicenseToken() async {
    return _storage.read(key: AppConstants.licenseTokenKey);
  }

  Future<String?> getAuthToken() async {
    return _storage.read(key: AppConstants.authTokenKey);
  }

  Future<void> clearAuthToken() async {
    await _storage.delete(key: AppConstants.authTokenKey);
  }

  Future<void> clearAll() async {
    await _storage.deleteAll();
  }
}
