import 'dart:io';
import 'package:device_info_plus/device_info_plus.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:pos_app/core/constants.dart';

class MachineIdService {
  static final DeviceInfoPlugin _deviceInfo = DeviceInfoPlugin();
  static const FlutterSecureStorage _storage = FlutterSecureStorage();

  /// Gets or generates a stable machine ID for this device.
  static Future<String> getMachineId() async {
    // Check if we have one cached
    final stored = await _storage.read(key: AppConstants.machineIdKey);
    if (stored != null && stored.isNotEmpty) return stored;

    String id;
    if (Platform.isAndroid) {
      final info = await _deviceInfo.androidInfo;
      id = info.id; // Android ID
    } else if (Platform.isWindows) {
      final info = await _deviceInfo.windowsInfo;
      id = info.deviceId;
    } else {
      id = 'unknown-platform';
    }

    await _storage.write(key: AppConstants.machineIdKey, value: id);
    return id;
  }
}
