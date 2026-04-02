import 'package:pos_app/services/api_client.dart';

class BillingService {
  final ApiClient _api = ApiClient();

  Future<List<dynamic>> getItems({int? posProfileId}) async {
    final params = <String, dynamic>{};
    if (posProfileId != null) params['pos_profile_id'] = posProfileId;
    final response = await _api.dio.get(
      '/billing/items',
      queryParameters: params,
    );
    return response.data as List<dynamic>;
  }

  Future<List<dynamic>> getCustomers({String? search}) async {
    final params = <String, dynamic>{};
    if (search != null && search.isNotEmpty) params['search'] = search;
    final response = await _api.dio.get(
      '/billing/customers',
      queryParameters: params,
    );
    return response.data as List<dynamic>;
  }

  Future<Map<String, dynamic>> createInvoice(
    Map<String, dynamic> payload,
  ) async {
    final response = await _api.dio.post('/billing/invoice', data: payload);
    return response.data;
  }

  Future<Map<String, dynamic>?> checkInvoice(String transactionId) async {
    try {
      final response = await _api.dio.get(
        '/billing/invoice/check/$transactionId',
      );
      return response.data;
    } catch (e) {
      return null;
    }
  }
}
