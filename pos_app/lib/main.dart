import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:pos_app/core/theme.dart';
import 'package:pos_app/screens/app_drawer.dart';
import 'package:pos_app/screens/billing/billing_screen.dart';
import 'package:pos_app/screens/license_activation_screen.dart';
import 'package:pos_app/screens/license_error_screen.dart';
import 'package:pos_app/screens/login_screen.dart';
import 'package:pos_app/screens/session_check_screen.dart';
import 'package:pos_app/services/license_service.dart';
import 'package:pos_app/services/auth_service.dart';

void main() {
  runApp(const ProviderScope(child: PosApp()));
}

class PosApp extends StatelessWidget {
  const PosApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'ERP POS',
      theme: AppTheme.lightTheme,
      debugShowCheckedModeBanner: false,
      home: const AppNavigator(),
    );
  }
}

enum AppScreen {
  splash,
  licenseActivation,
  licenseError,
  login,
  sessionCheck,
  billing,
}

class AppNavigator extends StatefulWidget {
  const AppNavigator({super.key});

  @override
  State<AppNavigator> createState() => _AppNavigatorState();
}

class _AppNavigatorState extends State<AppNavigator>
    with WidgetsBindingObserver {
  final _licenseService = LicenseService();
  final _authService = AuthService();
  final _scaffoldKey = GlobalKey<ScaffoldState>();

  AppScreen _currentScreen = AppScreen.splash;
  String? _licenseError;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    _checkInitialState();
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    super.dispose();
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state == AppLifecycleState.resumed &&
        _currentScreen == AppScreen.billing) {
      _validateLicense();
    }
  }

  Future<void> _checkInitialState() async {
    final hasLicense = await _licenseService.hasStoredLicense();
    if (!hasLicense) {
      setState(() => _currentScreen = AppScreen.licenseActivation);
      return;
    }

    final licenseErr = await _licenseService.validateStoredLicense();
    if (licenseErr != null) {
      setState(() {
        _licenseError = licenseErr;
        _currentScreen = AppScreen.licenseError;
      });
      return;
    }

    final hasAuth = await _authService.hasStoredAuth();
    if (!hasAuth) {
      setState(() => _currentScreen = AppScreen.login);
      return;
    }

    setState(() => _currentScreen = AppScreen.sessionCheck);
  }

  Future<void> _validateLicense() async {
    final err = await _licenseService.validateStoredLicense();
    if (err != null && mounted) {
      setState(() {
        _licenseError = err;
        _currentScreen = AppScreen.licenseError;
      });
    }
  }

  Future<void> _resetToLicenseActivation() async {
    await _authService.logout();
    await _licenseService.clearStoredLicense();
    if (!mounted) return;
    setState(() {
      _licenseError = null;
      _currentScreen = AppScreen.licenseActivation;
    });
  }

  void _goTo(AppScreen screen) {
    setState(() => _currentScreen = screen);
  }

  @override
  Widget build(BuildContext context) {
    switch (_currentScreen) {
      case AppScreen.splash:
        return const Scaffold(body: Center(child: CircularProgressIndicator()));

      case AppScreen.licenseActivation:
        return LicenseActivationScreen(
          onActivated: () => _goTo(AppScreen.login),
        );

      case AppScreen.licenseError:
        return LicenseErrorScreen(
          errorType: _licenseError ?? 'LICENSE_INVALID',
          onRetry: _checkInitialState,
          onReactivate: () => _goTo(AppScreen.licenseActivation),
        );

      case AppScreen.login:
        return LoginScreen(onLoginSuccess: () => _goTo(AppScreen.sessionCheck));

      case AppScreen.sessionCheck:
        return SessionCheckScreen(
          onSessionActive: () => _goTo(AppScreen.billing),
          onResetLicense: _resetToLicenseActivation,
        );

      case AppScreen.billing:
        return Scaffold(
          key: _scaffoldKey,
          drawer: AppDrawer(
            onCloseSession: () => _goTo(AppScreen.sessionCheck),
            onLogout: () => _goTo(AppScreen.login),
          ),
          body: BillingScreen(
            onOpenDrawer: () => _scaffoldKey.currentState?.openDrawer(),
          ),
        );
    }
  }
}
