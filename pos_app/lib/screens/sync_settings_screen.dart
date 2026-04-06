import 'package:flutter/material.dart';
import 'package:pos_app/services/sync_service.dart';

class SyncSettingsScreen extends StatefulWidget {
  const SyncSettingsScreen({super.key});

  @override
  State<SyncSettingsScreen> createState() => _SyncSettingsScreenState();
}

class _SyncSettingsScreenState extends State<SyncSettingsScreen> {
  final SyncService _syncService = SyncService();
  bool _isLoading = true;
  List<dynamic> _settings = [];
  String? _errorMessage;

  @override
  void initState() {
    super.initState();
    _loadSettings();
  }

  Future<void> _loadSettings() async {
    setState(() {
      _isLoading = true;
      _errorMessage = null;
    });
    try {
      final settings = await _syncService.getSettings();
      setState(() {
        _settings = settings;
        _isLoading = false;
      });
    } catch (e) {
      setState(() {
        _errorMessage = 'Failed to load settings: $e';
        _isLoading = false;
      });
    }
  }

  Future<void> _updateSetting(String key, String value) async {
    try {
      await _syncService.updateSetting(key, value);
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Setting updated successfully')),
        );
      }
      _loadSettings(); // Reload to get updated timestamps etc
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Update failed: $e')),
        );
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Sync Settings'),
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh),
            onPressed: _loadSettings,
          ),
        ],
      ),
      body: _isLoading
          ? const Center(child: CircularProgressIndicator())
          : _errorMessage != null
              ? Center(
                  child: Column(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      Text(_errorMessage!, style: const TextStyle(color: Colors.red)),
                      const SizedBox(height: 16),
                      ElevatedButton(
                        onPressed: _loadSettings,
                        child: const Text('Retry'),
                      ),
                    ],
                  ),
                )
              : ListView(
                  padding: const EdgeInsets.all(16),
                  children: [
                    const Card(
                      child: Padding(
                        padding: EdgeInsets.all(16),
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(
                              'Synchronization Intervals',
                              style: TextStyle(
                                fontSize: 18,
                                fontWeight: FontWeight.bold,
                              ),
                            ),
                            SizedBox(height: 8),
                            Text(
                              'Configure how often the local system synchronizes with ERPNext in the background.',
                              style: TextStyle(color: Colors.grey),
                            ),
                          ],
                        ),
                      ),
                    ),
                    const SizedBox(height: 16),
                    _buildIntervalTile(
                      key: 'erp_sync_interval_mins',
                      title: 'Master Data Sync',
                      subtitle: 'Includes Items, Prices, Customers, etc.',
                      currentValue: _getSettingValue('erp_sync_interval_mins', '5'),
                      options: [
                        {'label': '1 Minute (Testing Only)', 'value': '1'},
                        {'label': '5 Minutes', 'value': '5'},
                        {'label': '15 Minutes', 'value': '15'},
                        {'label': '30 Minutes', 'value': '30'},
                        {'label': '1 Hour', 'value': '60'},
                        {'label': '3 Hours', 'value': '180'},
                        {'label': '12 Hours', 'value': '720'},
                      ],
                    ),
                    _buildIntervalTile(
                      key: 'stock_sync_interval_mins',
                      title: 'Stock Level Sync',
                      subtitle: 'Updates current stock quantities from ERP.',
                      currentValue: _getSettingValue('stock_sync_interval_mins', '15'),
                      options: [
                        {'label': '5 Minutes', 'value': '5'},
                        {'label': '15 Minutes', 'value': '15'},
                        {'label': '1 Hour', 'value': '60'},
                        {'label': 'Daily', 'value': '1440'},
                      ],
                    ),
                    _buildIntervalTile(
                      key: 'invoice_sync_interval_secs',
                      title: 'Invoice Push Frequency',
                      subtitle: 'How fast local invoices are sent to ERP.',
                      currentValue: _getSettingValue('invoice_sync_interval_secs', '30'),
                      options: [
                        {'label': '10 Seconds', 'value': '10'},
                        {'label': '30 Seconds', 'value': '30'},
                        {'label': '1 Minute', 'value': '60'},
                        {'label': '5 Minutes', 'value': '300'},
                      ],
                    ),
                  ],
                ),
    );
  }

  String _getSettingValue(String key, String defaultValue) {
    try {
      final setting = _settings.firstWhere((s) => s['key'] == key);
      return setting['value'] ?? defaultValue;
    } catch (_) {
      return defaultValue;
    }
  }

  Widget _buildIntervalTile({
    required String key,
    required String title,
    required String subtitle,
    required String currentValue,
    required List<Map<String, String>> options,
  }) {
    return ListTile(
      title: Text(title),
      subtitle: Text(subtitle),
      trailing: DropdownButton<String>(
        value: options.any((o) => o['value'] == currentValue) ? currentValue : null,
        hint: Text(currentValue),
        onChanged: (newValue) {
          if (newValue != null && newValue != currentValue) {
            _updateSetting(key, newValue);
          }
        },
        items: options.map<DropdownMenuItem<String>>((opt) {
          return DropdownMenuItem<String>(
            value: opt['value'],
            child: Text(opt['label']!),
          );
        }).toList(),
      ),
    );
  }
}
