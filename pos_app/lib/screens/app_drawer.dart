import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:pos_app/providers/auth_provider.dart';
import 'package:pos_app/screens/closing_screen.dart';
import 'package:pos_app/screens/error_log_screen.dart';
import 'package:pos_app/screens/reports/reports_screen.dart';
import 'package:pos_app/services/auth_service.dart';
import 'package:pos_app/services/sync_service.dart';

class AppDrawer extends ConsumerWidget {
  final VoidCallback onCloseSession;
  final VoidCallback onLogout;

  const AppDrawer({
    super.key,
    required this.onCloseSession,
    required this.onLogout,
  });

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final auth = ref.watch(authProvider);

    return Drawer(
      child: ListView(
        padding: EdgeInsets.zero,
        children: [
          DrawerHeader(
            decoration: BoxDecoration(
              color: Theme.of(context).colorScheme.primary,
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              mainAxisAlignment: MainAxisAlignment.end,
              children: [
                const Icon(Icons.point_of_sale, size: 48, color: Colors.white),
                const SizedBox(height: 8),
                Text(
                  auth.fullName ?? 'Cashier',
                  style: const TextStyle(color: Colors.white, fontSize: 18),
                ),
                if (auth.roleProfile != null)
                  Text(
                    auth.roleProfile!,
                    style: const TextStyle(color: Colors.white70, fontSize: 12),
                  ),
              ],
            ),
          ),
          ListTile(
            leading: const Icon(Icons.bar_chart),
            title: const Text('Reports'),
            onTap: () {
              Navigator.pop(context);
              Navigator.push(
                context,
                MaterialPageRoute(builder: (_) => const ReportsScreen()),
              );
            },
          ),
          ListTile(
            leading: const Icon(Icons.error_outline),
            title: const Text('Error Log'),
            onTap: () {
              Navigator.pop(context);
              Navigator.push(
                context,
                MaterialPageRoute(builder: (_) => const ErrorLogScreen()),
              );
            },
          ),
          ListTile(
            leading: const Icon(Icons.sync),
            title: const Text('Manual Sync'),
            onTap: () async {
              Navigator.pop(context);
              try {
                final result = await SyncService().triggerSync();
                if (context.mounted) {
                  ScaffoldMessenger.of(context).showSnackBar(
                    SnackBar(
                      content: Text(
                        'Sync completed: ${result['message'] ?? 'OK'}',
                      ),
                    ),
                  );
                }
              } catch (e) {
                if (context.mounted) {
                  ScaffoldMessenger.of(
                    context,
                  ).showSnackBar(const SnackBar(content: Text('Sync failed')));
                }
              }
            },
          ),
          const Divider(),
          ListTile(
            leading: const Icon(Icons.lock, color: Colors.red),
            title: const Text('Close Session'),
            onTap: () {
              Navigator.pop(context);
              Navigator.push(
                context,
                MaterialPageRoute(
                  builder: (_) =>
                      ClosingScreen(onSessionClosed: onCloseSession),
                ),
              );
            },
          ),
          ListTile(
            leading: const Icon(Icons.logout),
            title: const Text('Logout'),
            onTap: () async {
              Navigator.pop(context);
              await AuthService().logout();
              ref.read(authProvider.notifier).setLoggedOut();
              onLogout();
            },
          ),
        ],
      ),
    );
  }
}
