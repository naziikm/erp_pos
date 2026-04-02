import 'package:pos_app/services/api_client.dart';

class ReportsService {
  final ApiClient _api = ApiClient();

  Future<Map<String, dynamic>> getDaySummary() async {
    final response = await _api.dio.get('/reports/day-summary');
    return response.data;
  }

  Future<Map<String, dynamic>> getInvoices({
    int page = 1,
    int pageSize = 20,
  }) async {
    final response = await _api.dio.get(
      '/reports/invoices',
      queryParameters: {'page': page, 'page_size': pageSize},
    );
    return response.data;
  }

  Future<List<dynamic>> getItemSales() async {
    final response = await _api.dio.get('/reports/item-sales');
    return response.data as List<dynamic>;
  }

  Future<Map<String, dynamic>> getErrors({
    int page = 1,
    int pageSize = 20,
  }) async {
    final response = await _api.dio.get(
      '/reports/errors',
      queryParameters: {'page': page, 'page_size': pageSize},
    );
    return response.data;
  }

  Future<void> resolveError(int errorId) async {
    await _api.dio.post('/reports/errors/$errorId/resolve');
  }
}
