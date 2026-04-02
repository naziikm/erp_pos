import 'dart:async';
import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:pos_app/core/constants.dart';
import 'package:pos_app/providers/session_provider.dart';
import 'package:pos_app/services/session_service.dart';
import 'package:pos_app/services/sync_service.dart';

class SessionCheckScreen extends ConsumerStatefulWidget {
  final VoidCallback onSessionActive;
  final Future<void> Function()? onResetLicense;

  const SessionCheckScreen({
    super.key,
    required this.onSessionActive,
    this.onResetLicense,
  });

  @override
  ConsumerState<SessionCheckScreen> createState() => _SessionCheckScreenState();
}

class _SessionCheckScreenState extends ConsumerState<SessionCheckScreen>
    with WidgetsBindingObserver {
  final _sessionService = SessionService();
  final _syncService = SyncService();
  bool _loading = true;
  String? _error;
  DateTime? _lastChecked;
  Timer? _pollTimer;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    _checkSession();
    _pollTimer = Timer.periodic(
      const Duration(seconds: AppConstants.sessionPollSeconds),
      (_) => _checkSession(),
    );
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    _pollTimer?.cancel();
    super.dispose();
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state == AppLifecycleState.resumed) {
      _checkSession();
    }
  }

  Future<void> _checkSession() async {
    if (!mounted) return;
    setState(() {
      _loading = true;
      _error = null;
    });

    try {
      // Step 1: Try to trigger an ERP sync first so the local DB is
      // up-to-date with any new POS Opening Entries from ERPNext.
      try {
        debugPrint('[SessionCheck] Triggering ERP sync...');
        await _syncService.triggerSync();
        debugPrint('[SessionCheck] ERP sync completed.');
      } catch (e) {
        debugPrint('[SessionCheck] ERP sync failed (non-fatal): $e');
      }

      // Step 2: Check session status from backend.
      debugPrint('[SessionCheck] Fetching session status...');
      final result = await _sessionService.getStatus();
      debugPrint('[SessionCheck] Response: $result');
      _lastChecked = DateTime.now();

      if (!mounted) return;

      if (result['has_session'] == true && result['session'] != null) {
        debugPrint(
          '[SessionCheck] Active session found — navigating to billing.',
        );
        ref.read(sessionProvider.notifier).setSession(result['session']);
        widget.onSessionActive();
        return;
      }

      debugPrint('[SessionCheck] No active session detected.');
      ref.read(sessionProvider.notifier).clearSession();
      setState(() => _loading = false);
    } catch (e) {
      debugPrint('[SessionCheck] Error: $e');
      if (!mounted) return;
      setState(() {
        _loading = false;
        _error = e.toString();
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Session Check')),
      body: Center(
        child: Padding(
          padding: const EdgeInsets.all(32),
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              if (_loading) ...[
                const CircularProgressIndicator(),
                const SizedBox(height: 24),
                const Text('Checking for active POS session...'),
              ] else ...[
                Icon(
                  Icons.hourglass_empty,
                  size: 80,
                  color: Theme.of(context).colorScheme.secondary,
                ),
                const SizedBox(height: 24),
                Text(
                  'No Active Session',
                  style: Theme.of(context).textTheme.headlineSmall,
                ),
                const SizedBox(height: 12),
                const Text(
                  'No active POS session found.\nPlease open a session in ERPNext, then tap Refresh.',
                  textAlign: TextAlign.center,
                ),
                if (_error != null) ...[
                  const SizedBox(height: 12),
                  Container(
                    padding: const EdgeInsets.all(8),
                    decoration: BoxDecoration(
                      color: Theme.of(context).colorScheme.errorContainer,
                      borderRadius: BorderRadius.circular(8),
                    ),
                    child: Text(
                      _error!,
                      style: TextStyle(
                        color: Theme.of(context).colorScheme.error,
                        fontSize: 12,
                      ),
                      textAlign: TextAlign.center,
                    ),
                  ),
                ],
                if (_lastChecked != null) ...[
                  const SizedBox(height: 16),
                  Text(
                    'Last checked: ${_lastChecked!.hour.toString().padLeft(2, '0')}:${_lastChecked!.minute.toString().padLeft(2, '0')}:${_lastChecked!.second.toString().padLeft(2, '0')}',
                    style: Theme.of(context).textTheme.bodySmall,
                  ),
                ],
                const SizedBox(height: 24),
                ElevatedButton.icon(
                  onPressed: _checkSession,
                  icon: const Icon(Icons.refresh),
                  label: const Text('Refresh'),
                ),
                if (widget.onResetLicense != null) ...[
                  const SizedBox(height: 12),
                  TextButton.icon(
                    onPressed: () async {
                      await widget.onResetLicense!.call();
                    },
                    icon: const Icon(Icons.vpn_key_off),
                    label: const Text('Go To License Screen'),
                  ),
                ],
                const SizedBox(height: 8),
                Text(
                  'Auto-refreshes every ${AppConstants.sessionPollSeconds} seconds',
                  style: Theme.of(context).textTheme.bodySmall,
                ),
              ],
            ],
          ),
        ),
      ),
    );
  }
}
