import 'package:flutter/material.dart';
import 'package:pos_app/services/reports_service.dart';

class DaySummaryTab extends StatefulWidget {
  const DaySummaryTab({super.key});

  @override
  State<DaySummaryTab> createState() => _DaySummaryTabState();
}

class _DaySummaryTabState extends State<DaySummaryTab> {
  final _reportsService = ReportsService();
  Map<String, dynamic>? _data;
  bool _loading = true;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() => _loading = true);
    try {
      final data = await _reportsService.getDaySummary();
      setState(() {
        _data = data;
        _loading = false;
      });
    } catch (e) {
      setState(() => _loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    if (_loading) return const Center(child: CircularProgressIndicator());
    if (_data == null) {
      return Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Text('Could not load summary'),
            TextButton(onPressed: _load, child: const Text('Retry')),
          ],
        ),
      );
    }

    final payments =
        (_data!['payments_by_mode'] as Map<String, dynamic>?) ?? {};

    return RefreshIndicator(
      onRefresh: _load,
      child: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          _MetricCard(
            title: 'Total Sales',
            value: '\u20B9 ${_data!['total_sales'] ?? '0'}',
            icon: Icons.attach_money,
            color: Colors.green,
          ),
          _MetricCard(
            title: 'Total Invoices',
            value: '${_data!['total_invoices'] ?? 0}',
            icon: Icons.receipt_long,
            color: Colors.blue,
          ),
          _MetricCard(
            title: 'Total Discount',
            value: '\u20B9 ${_data!['total_discount'] ?? '0'}',
            icon: Icons.discount,
            color: Colors.orange,
          ),
          const SizedBox(height: 16),
          Text(
            'Payments by Mode',
            style: Theme.of(context).textTheme.titleMedium,
          ),
          const SizedBox(height: 8),
          ...payments.entries.map(
            (e) => Card(
              child: ListTile(
                leading: const Icon(Icons.payment),
                title: Text(e.key),
                trailing: Text(
                  '\u20B9 ${e.value}',
                  style: const TextStyle(fontWeight: FontWeight.bold),
                ),
              ),
            ),
          ),
          if (payments.isEmpty)
            const Card(child: ListTile(title: Text('No payments today'))),
          const SizedBox(height: 16),
          Row(
            children: [
              _SmallMetric(
                'Unsynced',
                '${_data!['unsynced_count'] ?? 0}',
                _data!['unsynced_count'] != 0 ? Colors.orange : Colors.green,
              ),
              const SizedBox(width: 8),
              _SmallMetric(
                'Failed',
                '${_data!['failed_count'] ?? 0}',
                _data!['failed_count'] != 0 ? Colors.red : Colors.green,
              ),
            ],
          ),
        ],
      ),
    );
  }
}

class _MetricCard extends StatelessWidget {
  final String title;
  final String value;
  final IconData icon;
  final Color color;

  const _MetricCard({
    required this.title,
    required this.value,
    required this.icon,
    required this.color,
  });

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Row(
          children: [
            Icon(icon, size: 40, color: color),
            const SizedBox(width: 16),
            Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(title, style: Theme.of(context).textTheme.bodySmall),
                Text(value, style: Theme.of(context).textTheme.headlineSmall),
              ],
            ),
          ],
        ),
      ),
    );
  }
}

class _SmallMetric extends StatelessWidget {
  final String label;
  final String value;
  final Color color;

  const _SmallMetric(this.label, this.value, this.color);

  @override
  Widget build(BuildContext context) {
    return Expanded(
      child: Card(
        child: Padding(
          padding: const EdgeInsets.all(12),
          child: Column(
            children: [
              Text(label, style: Theme.of(context).textTheme.bodySmall),
              const SizedBox(height: 4),
              Text(
                value,
                style: TextStyle(
                  fontSize: 24,
                  fontWeight: FontWeight.bold,
                  color: color,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
