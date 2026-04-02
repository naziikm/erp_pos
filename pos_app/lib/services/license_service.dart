import 'package:dio/dio.dart';
import 'package:pos_app/services/api_client.dart';

class LicenseService {
  final ApiClient _api = ApiClient();

  Future<Map<String, dynamic>> activate(
    String machineId,
    String activationKey,
  ) async {
    final response = await _api.dio.post(
      '/license/activate',
      data: {'machine_id': machineId, 'activation_key': activationKey},
    );
    final token = response.data['token'] as String;
    await _api.storeLicenseToken(token);
    return response.data;
  }

  Future<Map<String, dynamic>> checkStatus() async {
    final response = await _api.dio.get('/license/status');
    return response.data;
  }

  Future<void> deactivate() async {
    await _api.dio.post('/license/deactivate');
    await _api.clearAll();
  }

  Future<void> clearStoredLicense() async {
    await _api.clearAll();
  }

  Future<bool> hasStoredLicense() async {
    final token = await _api.getLicenseToken();
    return token != null && token.isNotEmpty;
  }

  /// Validates stored license by calling the status endpoint.
  /// Returns null if valid, or an error string if not.
  Future<String?> validateStoredLicense() async {
    try {
      final status = await checkStatus();
      if (status['is_valid'] == true) return null;
      return 'LICENSE_EXPIRED';
    } on DioException catch (e) {
      if (e.response?.statusCode == 403) {
        final detail = e.response?.data['detail'];
        if (detail is Map) return detail['error_code'] ?? 'LICENSE_INVALID';
        return 'LICENSE_INVALID';
      }
      return 'NETWORK_ERROR';
    }
  }
}
