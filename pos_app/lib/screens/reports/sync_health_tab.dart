import 'dart:async';
import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import 'package:pos_app/services/sync_service.dart';

class SyncHealthTab extends StatefulWidget {
  const SyncHealthTab({super.key});

  @override
  State<SyncHealthTab> createState() => _SyncHealthTabState();
}

class _SyncHealthTabState extends State<SyncHealthTab> {
  final _syncService = SyncService();
  Map<String, dynamic>? _status;
  Map<String, dynamic>? _queue;
  bool _loading = true;
  bool _isAutoRefreshing = false;
  Timer? _refreshTimer;

  @override
  void initState() {
    super.initState();
    _load();
    // Start auto-refresh timer (every 7 seconds)
    _refreshTimer = Timer.periodic(const Duration(seconds: 7), (_) => _autoRefresh());
  }

  @override
  void dispose() {
    _refreshTimer?.cancel();
    super.dispose();
  }

  Future<void> _load() async {
    setState(() => _loading = true);
    await _fetchData();
  }

  Future<void> _autoRefresh() async {
    if (_loading || _isAutoRefreshing) return;
    setState(() => _isAutoRefreshing = true);
    await _fetchData();
    if (mounted) setState(() => _isAutoRefreshing = false);
  }

  Future<void> _fetchData() async {
    try {
      final results = await Future.wait([
        _syncService.getSyncStatus(),
        _syncService.getInvoiceQueue(),
      ]);
      if (mounted) {
        setState(() {
          _status = results[0];
          _queue = results[1];
          _loading = false;
        });
      }
    } catch (e) {
      if (mounted) setState(() => _loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    if (_loading) return const Center(child: CircularProgressIndicator());

    final tables = (_status?['tables'] as List<dynamic>?) ?? [];

    return RefreshIndicator(
      onRefresh: _load,
      child: ListView(
        padding: const EdgeInsets.all(8),
        children: [
          // Invoice queue
          if (_queue != null)
            Card(
              child: Padding(
                padding: const EdgeInsets.all(16),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      'Invoice Queue',
                      style: Theme.of(context).textTheme.titleMedium,
                    ),
                    const SizedBox(height: 8),
                    Row(
                      mainAxisAlignment: MainAxisAlignment.spaceAround,
                      children: [
                        _QueueBadge(
                          'Pending',
                          _queue!['pending'] ?? 0,
                          Colors.orange,
                        ),
                        _QueueBadge(
                          'Synced',
                          _queue!['synced'] ?? 0,
                          Colors.green,
                        ),
                        _QueueBadge(
                          'Failed',
                          _queue!['failed'] ?? 0,
                          Colors.red,
                        ),
                      ],
                    ),
                  ],
                ),
              ),
            ),

          const SizedBox(height: 8),
          Text(
            'Sync Status per Table',
            style: Theme.of(context).textTheme.titleMedium,
          ),
          const SizedBox(height: 4),

          ...tables.map((t) {
            final table = t as Map<String, dynamic>;
            final lastSynced = table['last_synced_at'];
            final syncTime = lastSynced != null
                ? DateFormat('dd-MMM HH:mm').format(DateTime.parse(lastSynced))
                : 'Never';
            final status = table['status'] ?? 'unknown';

            return Card(
              child: ListTile(
                leading: Icon(
                  status == 'success' ? Icons.check_circle : Icons.warning,
                  color: status == 'success' ? Colors.green : Colors.red,
                ),
                title: Text(table['table_name'] ?? ''),
                subtitle: Text(
                  'Last synced: $syncTime  |  Records: ${table['total_records'] ?? 0}',
                ),
                trailing: table['error_message'] != null
                    ? Tooltip(
                        message: table['error_message'],
                        child: const Icon(
                          Icons.info_outline,
                          color: Colors.red,
                        ),
                      )
                    : null,
              ),
            );
          }),
        ],
      ),
    );
  }
}

class _QueueBadge extends StatelessWidget {
  final String label;
  final int count;
  final Color color;

  const _QueueBadge(this.label, this.count, this.color);

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        Text(
          '$count',
          style: TextStyle(
            fontSize: 24,
            fontWeight: FontWeight.bold,
            color: color,
          ),
        ),
        Text(label, style: Theme.of(context).textTheme.bodySmall),
      ],
    );
  }
}
