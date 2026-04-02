import 'package:pos_app/services/api_client.dart';

class SyncService {
  final ApiClient _api = ApiClient();

  Future<Map<String, dynamic>> triggerSync() async {
    final response = await _api.dio.post('/sync/erp');
    return response.data;
  }

  Future<Map<String, dynamic>> triggerFullSync() async {
    final response = await _api.dio.post('/sync/erp/full');
    return response.data;
  }

  Future<Map<String, dynamic>> getSyncStatus() async {
    final response = await _api.dio.get('/sync/status');
    return response.data;
  }

  Future<Map<String, dynamic>> getInvoiceQueue() async {
    final response = await _api.dio.get('/sync/invoice-queue');
    return response.data;
  }

  Future<List<dynamic>> getFailedInvoices() async {
    final response = await _api.dio.get('/sync/failed-invoices');
    return response.data as List<dynamic>;
  }

  Future<Map<String, dynamic>> retryInvoice(int invoiceId) async {
    final response = await _api.dio.post('/sync/retry-invoice/$invoiceId');
    return response.data;
  }
}
