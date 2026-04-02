import 'package:flutter_riverpod/flutter_riverpod.dart';

class SessionState {
  final bool hasSession;
  final Map<String, dynamic>? session;

  SessionState({this.hasSession = false, this.session});
}

class SessionNotifier extends StateNotifier<SessionState> {
  SessionNotifier() : super(SessionState());

  void setSession(Map<String, dynamic>? session) {
    if (session != null) {
      state = SessionState(hasSession: true, session: session);
    } else {
      state = SessionState(hasSession: false, session: null);
    }
  }

  void clearSession() {
    state = SessionState(hasSession: false, session: null);
  }
}

final sessionProvider = StateNotifierProvider<SessionNotifier, SessionState>((
  ref,
) {
  return SessionNotifier();
});
