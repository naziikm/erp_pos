import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:pos_app/providers/session_provider.dart';
import 'package:pos_app/services/session_service.dart';

class ClosingScreen extends ConsumerStatefulWidget {
  final VoidCallback onSessionClosed;

  const ClosingScreen({super.key, required this.onSessionClosed});

  @override
  ConsumerState<ClosingScreen> createState() => _ClosingScreenState();
}

class _ClosingScreenState extends ConsumerState<ClosingScreen> {
  final _sessionService = SessionService();
  Map<String, dynamic>? _summary;
  bool _loading = true;
  bool _closing = false;
  String? _error;
  final _cashController = TextEditingController();

  @override
  void initState() {
    super.initState();
    _loadSummary();
  }

  @override
  void dispose() {
    _cashController.dispose();
    super.dispose();
  }

  Map<String, dynamic> _paymentModeTotals() {
    final raw = _summary?['payments_by_mode'];
    if (raw is Map<String, dynamic>) {
      return raw;
    }
    if (raw is List) {
      final normalized = <String, dynamic>{};
      for (final entry in raw) {
        if (entry is Map) {
          final modeName = entry['mode_name']?.toString();
          final amount = entry['expected_amount'];
          if (modeName != null && modeName.isNotEmpty) {
            normalized[modeName] = amount ?? 0;
          }
        }
      }
      return normalized;
    }
    return <String, dynamic>{};
  }

  Future<void> _loadSummary() async {
    setState(() => _loading = true);
    try {
      final data = await _sessionService.getClosingSummary();
      setState(() {
        _summary = data;
        _loading = false;
      });
    } catch (e) {
      setState(() {
        _loading = false;
        _error = 'Could not load closing summary';
      });
    }
  }

  Future<void> _closeSession() async {
    final actualCash = double.tryParse(_cashController.text) ?? 0;

    setState(() {
      _closing = true;
      _error = null;
    });

    try {
      final payload = {
        'actual_closing_balance': {'Cash': actualCash},
        'force_close': true,
      };
      await _sessionService.closeSession(payload);
      ref.read(sessionProvider.notifier).clearSession();
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Session closed successfully')),
        );
        widget.onSessionClosed();
      }
    } on DioException catch (e) {
      final detail = e.response?.data?['detail'];
      final msg = detail is Map
          ? (detail['message'] ?? 'Close failed')
          : 'Close failed';
      setState(() => _error = msg.toString());
    } catch (e) {
      setState(() => _error = 'Unexpected error: $e');
    } finally {
      setState(() => _closing = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final paymentsByMode = _paymentModeTotals();

    return Scaffold(
      appBar: AppBar(title: const Text('Close Session')),
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : _summary == null
          ? Center(
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Text(_error ?? 'Error loading summary'),
                  TextButton(
                    onPressed: _loadSummary,
                    child: const Text('Retry'),
                  ),
                ],
              ),
            )
          : SingleChildScrollView(
              padding: const EdgeInsets.all(16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  // Summary cards
                  Card(
                    child: Padding(
                      padding: const EdgeInsets.all(16),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            'Session Summary',
                            style: Theme.of(context).textTheme.titleLarge,
                          ),
                          const Divider(),
                          _SummaryRow(
                            'Total Invoices',
                            '${_summary!['total_invoices'] ?? 0}',
                          ),
                          _SummaryRow(
                            'Total Sales',
                            '\u20B9 ${_summary!['total_sales'] ?? '0'}',
                          ),
                          const Divider(),
                          Text(
                            'Collections by Payment Mode',
                            style: Theme.of(context).textTheme.titleSmall,
                          ),
                          const SizedBox(height: 8),
                          ...paymentsByMode.entries.map(
                            (e) => _SummaryRow(e.key, '\u20B9 ${e.value}'),
                          ),
                        ],
                      ),
                    ),
                  ),

                  const SizedBox(height: 16),

                  // Unsynced warning
                  if ((_summary!['unsynced_count'] ?? 0) > 0)
                    Card(
                      color: Colors.orange.shade50,
                      child: Padding(
                        padding: const EdgeInsets.all(16),
                        child: Row(
                          children: [
                            const Icon(Icons.warning, color: Colors.orange),
                            const SizedBox(width: 12),
                            Expanded(
                              child: Text(
                                '${_summary!['unsynced_count']} invoices not yet synced to ERP. '
                                'Closing now will include them but they may not appear in ERP immediately.',
                                style: const TextStyle(fontSize: 13),
                              ),
                            ),
                          ],
                        ),
                      ),
                    ),

                  const SizedBox(height: 16),

                  // Cash entry
                  Card(
                    child: Padding(
                      padding: const EdgeInsets.all(16),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            'Actual Cash Collected',
                            style: Theme.of(context).textTheme.titleSmall,
                          ),
                          const SizedBox(height: 8),
                          TextField(
                            controller: _cashController,
                            decoration: const InputDecoration(
                              prefixText: '\u20B9 ',
                              labelText: 'Enter actual cash amount',
                            ),
                            keyboardType: const TextInputType.numberWithOptions(
                              decimal: true,
                            ),
                          ),
                          const SizedBox(height: 8),
                          if (_cashController.text.isNotEmpty) ...[
                            Builder(
                              builder: (_) {
                                final actual =
                                    double.tryParse(_cashController.text) ?? 0;
                                final expected = paymentsByMode['Cash'] ?? 0;
                                final expectedVal = expected is num
                                    ? expected.toDouble()
                                    : double.tryParse(expected.toString()) ?? 0;
                                final diff = actual - expectedVal;
                                return Text(
                                  'Difference: \u20B9 ${diff.toStringAsFixed(2)}',
                                  style: TextStyle(
                                    color: diff.abs() < 1
                                        ? Colors.green
                                        : Colors.red,
                                    fontWeight: FontWeight.bold,
                                  ),
                                );
                              },
                            ),
                          ],
                        ],
                      ),
                    ),
                  ),

                  if (_error != null) ...[
                    const SizedBox(height: 12),
                    Text(
                      _error!,
                      style: TextStyle(
                        color: Theme.of(context).colorScheme.error,
                      ),
                    ),
                  ],

                  const SizedBox(height: 24),
                  ElevatedButton.icon(
                    onPressed: _closing ? null : _closeSession,
                    icon: _closing
                        ? const SizedBox(
                            width: 20,
                            height: 20,
                            child: CircularProgressIndicator(strokeWidth: 2),
                          )
                        : const Icon(Icons.lock),
                    label: Text(_closing ? 'Closing...' : 'Close Session'),
                    style: ElevatedButton.styleFrom(
                      minimumSize: const Size(double.infinity, 56),
                      backgroundColor: Colors.red.shade700,
                      foregroundColor: Colors.white,
                    ),
                  ),
                ],
              ),
            ),
    );
  }
}

class _SummaryRow extends StatelessWidget {
  final String label;
  final String value;

  const _SummaryRow(this.label, this.value);

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 4),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Text(label),
          Text(value, style: const TextStyle(fontWeight: FontWeight.bold)),
        ],
      ),
    );
  }
}
