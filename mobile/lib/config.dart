/// App configuration.
///
/// The backend is the deployed QuoteDrive website. Override the base URL at
/// build time if needed:
///   flutter run --dart-define=API_BASE_URL=http://10.0.2.2:3000
///
/// Notes:
///   - Android emulator reaches the host machine via 10.0.2.2.
///   - iOS simulator / desktop / web can use http://localhost:3000.
///   - A physical device can use the deployed server URL below directly.
class AppConfig {
  static const String apiBaseUrl = String.fromEnvironment(
    'API_BASE_URL',
    defaultValue: 'http://45.137.194.227:31207',
  );
}
