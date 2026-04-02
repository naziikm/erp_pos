import 'package:flutter_riverpod/flutter_riverpod.dart';

class AuthState {
  final bool isLoggedIn;
  final int? userId;
  final String? fullName;
  final String? roleProfile;

  AuthState({
    this.isLoggedIn = false,
    this.userId,
    this.fullName,
    this.roleProfile,
  });
}

class AuthNotifier extends StateNotifier<AuthState> {
  AuthNotifier() : super(AuthState());

  void setLoggedIn(Map<String, dynamic> loginData) {
    state = AuthState(
      isLoggedIn: true,
      userId: loginData['user_id'],
      fullName: loginData['full_name'],
      roleProfile: loginData['role_profile'],
    );
  }

  void setLoggedOut() {
    state = AuthState();
  }
}

final authProvider = StateNotifierProvider<AuthNotifier, AuthState>((ref) {
  return AuthNotifier();
});
