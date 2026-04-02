import 'package:pos_app/services/api_client.dart';

class AuthService {
  final ApiClient _api = ApiClient();

  Future<Map<String, dynamic>> login(String username, String password) async {
    final response = await _api.dio.post(
      '/auth/login',
      data: {'username': username, 'password': password},
    );
    final token = response.data['token'] as String;
    await _api.storeAuthToken(token);
    return response.data;
  }

  Future<void> logout() async {
    try {
      await _api.dio.post('/auth/logout');
    } catch (_) {
      // Best effort — clear local token regardless
    }
    await _api.clearAuthToken();
  }

  Future<bool> hasStoredAuth() async {
    final token = await _api.getAuthToken();
    return token != null && token.isNotEmpty;
  }
}
