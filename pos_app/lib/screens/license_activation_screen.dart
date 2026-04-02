import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:pos_app/services/license_service.dart';
import 'package:pos_app/services/machine_id_service.dart';

class LicenseActivationScreen extends StatefulWidget {
  final VoidCallback onActivated;

  const LicenseActivationScreen({super.key, required this.onActivated});

  @override
  State<LicenseActivationScreen> createState() =>
      _LicenseActivationScreenState();
}

class _LicenseActivationScreenState extends State<LicenseActivationScreen> {
  final _keyController = TextEditingController();
  final _licenseService = LicenseService();
  String _machineId = '';
  bool _loading = false;
  String? _error;

  String _normalizeActivationKey(String rawValue) {
    final compact = rawValue.replaceAll(RegExp(r'\s+'), '');
    if (compact.isEmpty) return compact;
    if (compact.toUpperCase().startsWith('POS-LICENSE-')) {
      return 'POS-LICENSE-${compact.substring('POS-LICENSE-'.length)}';
    }
    return 'POS-LICENSE-$compact';
  }

  @override
  void initState() {
    super.initState();
    _loadMachineId();
  }

  Future<void> _loadMachineId() async {
    final id = await MachineIdService.getMachineId();
    setState(() => _machineId = id);
  }

  Future<void> _activate() async {
    final activationKey = _normalizeActivationKey(_keyController.text);
    if (activationKey.isEmpty) {
      setState(() => _error = 'Please enter a license key');
      return;
    }

    setState(() {
      _loading = true;
      _error = null;
    });

    try {
      _keyController.text = activationKey;
      await _licenseService.activate(_machineId, activationKey);
      widget.onActivated();
    } on DioException catch (e) {
      final detail = e.response?.data?['detail'];
      String msg;
      if (detail is Map) {
        final code = detail['error_code'] ?? '';
        switch (code) {
          case 'LICENSE_INVALID_KEY':
            msg = 'Invalid activation key';
            break;
          case 'LICENSE_MACHINE_MISMATCH':
            msg = 'This key was generated for a different machine';
            break;
          case 'LICENSE_EXPIRED':
            msg = 'This license has expired';
            break;
          default:
            msg = detail['message'] ?? 'Activation failed';
        }
      } else {
        msg = 'Network error. Check your connection and try again.';
      }
      setState(() => _error = msg);
    } catch (e) {
      setState(() => _error = 'Unexpected error: $e');
    } finally {
      setState(() => _loading = false);
    }
  }

  @override
  void dispose() {
    _keyController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: Center(
        child: SingleChildScrollView(
          padding: const EdgeInsets.all(32),
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 400),
            child: Column(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                Icon(
                  Icons.verified_user_outlined,
                  size: 80,
                  color: Theme.of(context).colorScheme.primary,
                ),
                const SizedBox(height: 24),
                Text(
                  'Activate License',
                  style: Theme.of(context).textTheme.headlineMedium,
                ),
                const SizedBox(height: 8),
                Text(
                  'Enter your license key to activate this device',
                  style: Theme.of(context).textTheme.bodyMedium,
                  textAlign: TextAlign.center,
                ),
                const SizedBox(height: 32),

                // Machine ID (read-only)
                TextField(
                  readOnly: true,
                  controller: TextEditingController(text: _machineId),
                  decoration: const InputDecoration(
                    labelText: 'Machine ID',
                    prefixIcon: Icon(Icons.devices),
                  ),
                ),
                const SizedBox(height: 16),

                // License key
                TextField(
                  controller: _keyController,
                  decoration: const InputDecoration(
                    labelText: 'Activation Key',
                    prefixIcon: Icon(Icons.vpn_key),
                    hintText: 'Paste POS-LICENSE-... key here',
                  ),
                  maxLines: 3,
                  minLines: 1,
                  textInputAction: TextInputAction.done,
                  onSubmitted: (_) => _activate(),
                ),
                const SizedBox(height: 8),

                if (_error != null) ...[
                  const SizedBox(height: 8),
                  Text(
                    _error!,
                    style: TextStyle(
                      color: Theme.of(context).colorScheme.error,
                    ),
                  ),
                ],

                const SizedBox(height: 24),
                ElevatedButton(
                  onPressed: _loading ? null : _activate,
                  child: _loading
                      ? const SizedBox(
                          height: 20,
                          width: 20,
                          child: CircularProgressIndicator(strokeWidth: 2),
                        )
                      : const Text('Activate'),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
