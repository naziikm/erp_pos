class AppConstants {
  AppConstants._();

  // API
  static const String baseUrl = 'http://127.0.0.1:8000/api/v1';

  // Storage keys
  static const String licenseTokenKey = 'license_token';
  static const String authTokenKey = 'auth_token';
  static const String machineIdKey = 'machine_id';
  static const String printerTypeKey = 'printer_type';
  static const String printerAddressKey = 'printer_address';
  static const String autoPrintKey = 'auto_print';

  // Polling intervals
  static const int sessionPollSeconds = 60;
  static const int healthPollSeconds = 30;

  // Debounce
  static const int searchDebounceMs = 300;
}
