import 'package:pos_app/services/api_client.dart';

class SessionService {
  final ApiClient _api = ApiClient();

  Future<Map<String, dynamic>> getStatus() async {
    final response = await _api.dio.get('/session/status');
    return response.data;
  }

  Future<Map<String, dynamic>> getClosingSummary() async {
    final response = await _api.dio.get('/session/closing-summary');
    return response.data;
  }

  Future<Map<String, dynamic>> closeSession(
    Map<String, dynamic> payload,
  ) async {
    final response = await _api.dio.post('/session/close', data: payload);
    return response.data;
  }
}
