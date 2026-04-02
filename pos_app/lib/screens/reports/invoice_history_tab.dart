import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import 'package:pos_app/services/reports_service.dart';

class InvoiceHistoryTab extends StatefulWidget {
  const InvoiceHistoryTab({super.key});

  @override
  State<InvoiceHistoryTab> createState() => _InvoiceHistoryTabState();
}

class _InvoiceHistoryTabState extends State<InvoiceHistoryTab> {
  final _reportsService = ReportsService();
  List<dynamic> _invoices = [];
  int _page = 1;
  int _total = 0;
  bool _loading = true;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() => _loading = true);
    try {
      final data = await _reportsService.getInvoices(page: _page);
      setState(() {
        _invoices = data['invoices'] as List<dynamic>? ?? [];
        _total = data['total'] ?? 0;
        _loading = false;
      });
    } catch (e) {
      setState(() => _loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    if (_loading) return const Center(child: CircularProgressIndicator());

    return Column(
      children: [
        Padding(
          padding: const EdgeInsets.all(8),
          child: Text(
            '$_total invoices total',
            style: Theme.of(context).textTheme.bodySmall,
          ),
        ),
        Expanded(
          child: _invoices.isEmpty
              ? const Center(child: Text('No invoices found'))
              : RefreshIndicator(
                  onRefresh: _load,
                  child: ListView.builder(
                    itemCount: _invoices.length,
                    itemBuilder: (_, index) {
                      final inv = _invoices[index] as Map<String, dynamic>;
                      final date = inv['created_at'] != null
                          ? DateFormat(
                              'dd-MMM HH:mm',
                            ).format(DateTime.parse(inv['created_at']))
                          : '';
                      return Card(
                        margin: const EdgeInsets.symmetric(
                          horizontal: 8,
                          vertical: 4,
                        ),
                        child: ListTile(
                          leading: Icon(
                            inv['status'] == 'submitted'
                                ? Icons.check_circle
                                : inv['status'] == 'failed'
                                ? Icons.error
                                : Icons.hourglass_empty,
                            color: inv['status'] == 'submitted'
                                ? Colors.green
                                : inv['status'] == 'failed'
                                ? Colors.red
                                : Colors.orange,
                          ),
                          title: Text(inv['invoice_number'] ?? '#${inv['id']}'),
                          subtitle: Text(
                            '$date  |  ${inv['customer_name'] ?? 'Walk-in'}',
                          ),
                          trailing: Text(
                            '\u20B9 ${inv['grand_total'] ?? '0'}',
                            style: const TextStyle(fontWeight: FontWeight.bold),
                          ),
                        ),
                      );
                    },
                  ),
                ),
        ),
        if (_total > 20)
          Padding(
            padding: const EdgeInsets.all(8),
            child: Row(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                IconButton(
                  onPressed: _page > 1
                      ? () {
                          _page--;
                          _load();
                        }
                      : null,
                  icon: const Icon(Icons.chevron_left),
                ),
                Text('Page $_page'),
                IconButton(
                  onPressed: () {
                    _page++;
                    _load();
                  },
                  icon: const Icon(Icons.chevron_right),
                ),
              ],
            ),
          ),
      ],
    );
  }
}
