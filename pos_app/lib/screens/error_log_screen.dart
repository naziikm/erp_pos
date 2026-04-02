import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import 'package:pos_app/services/reports_service.dart';
import 'package:pos_app/services/sync_service.dart';

class ErrorLogScreen extends StatefulWidget {
  const ErrorLogScreen({super.key});

  @override
  State<ErrorLogScreen> createState() => _ErrorLogScreenState();
}

class _ErrorLogScreenState extends State<ErrorLogScreen>
    with SingleTickerProviderStateMixin {
  late TabController _tabController;
  final _reportsService = ReportsService();
  final _syncService = SyncService();

  // Error log
  List<dynamic> _errors = [];
  int _errorPage = 1;
  int _errorTotal = 0;
  bool _loadingErrors = true;

  // Failed invoices
  List<dynamic> _failedInvoices = [];
  bool _loadingFailed = true;

  @override
  void initState() {
    super.initState();
    _tabController = TabController(length: 2, vsync: this);
    _loadErrors();
    _loadFailed();
  }

  @override
  void dispose() {
    _tabController.dispose();
    super.dispose();
  }

  Future<void> _loadErrors() async {
    setState(() => _loadingErrors = true);
    try {
      final data = await _reportsService.getErrors(page: _errorPage);
      setState(() {
        _errors = data['errors'] as List<dynamic>? ?? [];
        _errorTotal = data['total'] ?? 0;
        _loadingErrors = false;
      });
    } catch (e) {
      setState(() => _loadingErrors = false);
    }
  }

  Future<void> _loadFailed() async {
    setState(() => _loadingFailed = true);
    try {
      final data = await _syncService.getFailedInvoices();
      setState(() {
        _failedInvoices = data;
        _loadingFailed = false;
      });
    } catch (e) {
      setState(() => _loadingFailed = false);
    }
  }

  Future<void> _resolveError(int errorId) async {
    try {
      await _reportsService.resolveError(errorId);
      _loadErrors();
    } catch (_) {}
  }

  Future<void> _retryInvoice(int invoiceId) async {
    try {
      await _syncService.retryInvoice(invoiceId);
      if (!mounted) return;
      ScaffoldMessenger.of(
        context,
      ).showSnackBar(const SnackBar(content: Text('Invoice queued for retry')));
      _loadFailed();
    } catch (_) {
      if (!mounted) return;
      ScaffoldMessenger.of(
        context,
      ).showSnackBar(const SnackBar(content: Text('Retry failed')));
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Error Log'),
        bottom: TabBar(
          controller: _tabController,
          tabs: const [
            Tab(text: 'Errors'),
            Tab(text: 'Failed Invoices'),
          ],
        ),
      ),
      body: TabBarView(
        controller: _tabController,
        children: [_buildErrorsTab(), _buildFailedInvoicesTab()],
      ),
    );
  }

  Widget _buildErrorsTab() {
    if (_loadingErrors) return const Center(child: CircularProgressIndicator());

    return Column(
      children: [
        Padding(
          padding: const EdgeInsets.all(8),
          child: Text(
            '$_errorTotal errors total',
            style: Theme.of(context).textTheme.bodySmall,
          ),
        ),
        Expanded(
          child: _errors.isEmpty
              ? const Center(child: Text('No errors'))
              : ListView.builder(
                  itemCount: _errors.length,
                  itemBuilder: (_, index) {
                    final err = _errors[index] as Map<String, dynamic>;
                    final severity = err['severity'] ?? 'error';
                    final date = err['created_at'] != null
                        ? DateFormat(
                            'dd-MMM HH:mm',
                          ).format(DateTime.parse(err['created_at']))
                        : '';

                    return Card(
                      margin: const EdgeInsets.symmetric(
                        horizontal: 8,
                        vertical: 4,
                      ),
                      child: ExpansionTile(
                        leading: _severityBadge(severity),
                        title: Text(
                          err['error_category'] ?? 'unknown',
                          style: const TextStyle(fontWeight: FontWeight.w600),
                        ),
                        subtitle: Text(
                          date,
                          style: const TextStyle(fontSize: 11),
                        ),
                        children: [
                          Padding(
                            padding: const EdgeInsets.all(12),
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                Text(
                                  err['error_message'] ?? '',
                                  style: const TextStyle(fontSize: 12),
                                ),
                                const SizedBox(height: 8),
                                Align(
                                  alignment: Alignment.centerRight,
                                  child: TextButton.icon(
                                    onPressed: () => _resolveError(err['id']),
                                    icon: const Icon(Icons.check, size: 16),
                                    label: const Text('Mark Resolved'),
                                  ),
                                ),
                              ],
                            ),
                          ),
                        ],
                      ),
                    );
                  },
                ),
        ),
        if (_errorTotal > 20)
          Padding(
            padding: const EdgeInsets.all(8),
            child: Row(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                IconButton(
                  onPressed: _errorPage > 1
                      ? () {
                          _errorPage--;
                          _loadErrors();
                        }
                      : null,
                  icon: const Icon(Icons.chevron_left),
                ),
                Text('Page $_errorPage'),
                IconButton(
                  onPressed: () {
                    _errorPage++;
                    _loadErrors();
                  },
                  icon: const Icon(Icons.chevron_right),
                ),
              ],
            ),
          ),
      ],
    );
  }

  Widget _buildFailedInvoicesTab() {
    if (_loadingFailed) return const Center(child: CircularProgressIndicator());

    return Column(
      children: [
        if (_failedInvoices.isNotEmpty)
          Padding(
            padding: const EdgeInsets.all(8),
            child: ElevatedButton.icon(
              onPressed: () async {
                for (final inv in _failedInvoices) {
                  await _retryInvoice(inv['id']);
                }
              },
              icon: const Icon(Icons.replay),
              label: const Text('Retry All'),
            ),
          ),
        Expanded(
          child: _failedInvoices.isEmpty
              ? const Center(child: Text('No failed invoices'))
              : ListView.builder(
                  itemCount: _failedInvoices.length,
                  itemBuilder: (_, index) {
                    final inv = _failedInvoices[index] as Map<String, dynamic>;
                    return Card(
                      margin: const EdgeInsets.symmetric(
                        horizontal: 8,
                        vertical: 4,
                      ),
                      child: ListTile(
                        leading: const Icon(Icons.error, color: Colors.red),
                        title: Text(inv['invoice_number'] ?? '#${inv['id']}'),
                        subtitle: Text(
                          '\u20B9 ${inv['grand_total'] ?? 0}  |  ${inv['error_message'] ?? ''}',
                          maxLines: 2,
                        ),
                        trailing: IconButton(
                          icon: const Icon(Icons.replay),
                          onPressed: () => _retryInvoice(inv['id']),
                        ),
                      ),
                    );
                  },
                ),
        ),
      ],
    );
  }

  Widget _severityBadge(String severity) {
    Color color;
    switch (severity) {
      case 'critical':
        color = Colors.red;
        break;
      case 'error':
        color = Colors.orange;
        break;
      case 'warning':
        color = Colors.amber;
        break;
      default:
        color = Colors.blue;
    }
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.2),
        borderRadius: BorderRadius.circular(4),
      ),
      child: Text(
        severity.toUpperCase(),
        style: TextStyle(
          fontSize: 10,
          color: color,
          fontWeight: FontWeight.bold,
        ),
      ),
    );
  }
}
