import 'package:flutter/material.dart';

class LicenseErrorScreen extends StatelessWidget {
  final String errorType;
  final VoidCallback onRetry;
  final VoidCallback onReactivate;

  const LicenseErrorScreen({
    super.key,
    required this.errorType,
    required this.onRetry,
    required this.onReactivate,
  });

  @override
  Widget build(BuildContext context) {
    String title;
    String message;
    IconData icon;
    Color color;

    switch (errorType) {
      case 'LICENSE_EXPIRED':
        title = 'License Expired';
        message = 'Your license has expired. Please contact support to renew.';
        icon = Icons.timer_off;
        color = Colors.orange;
        break;
      case 'LICENSE_MACHINE_MISMATCH':
        title = 'Machine Mismatch';
        message = 'This license is activated on a different device.';
        icon = Icons.devices_other;
        color = Colors.red;
        break;
      case 'NETWORK_ERROR':
        title = 'Connection Error';
        message = 'Cannot reach the server. Check your network connection.';
        icon = Icons.wifi_off;
        color = Colors.grey;
        break;
      default:
        title = 'License Invalid';
        message = 'Your license could not be verified.';
        icon = Icons.error_outline;
        color = Colors.red;
    }

    return Scaffold(
      body: Center(
        child: Padding(
          padding: const EdgeInsets.all(32),
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Icon(icon, size: 80, color: color),
              const SizedBox(height: 24),
              Text(title, style: Theme.of(context).textTheme.headlineMedium),
              const SizedBox(height: 16),
              Text(
                message,
                style: Theme.of(context).textTheme.bodyLarge,
                textAlign: TextAlign.center,
              ),
              const SizedBox(height: 32),
              ElevatedButton.icon(
                onPressed: onRetry,
                icon: const Icon(Icons.refresh),
                label: const Text('Retry'),
              ),
              const SizedBox(height: 12),
              OutlinedButton.icon(
                onPressed: onReactivate,
                icon: const Icon(Icons.vpn_key),
                label: const Text('Re-activate License'),
              ),
              const SizedBox(height: 24),
              TextButton(
                onPressed: () {},
                child: const Text('Contact Support'),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
