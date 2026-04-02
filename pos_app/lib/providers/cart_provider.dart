import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:pos_app/models/models.dart';

class CartNotifier extends StateNotifier<List<CartItem>> {
  CartNotifier() : super([]);

  void addItem(CartItem item) {
    final idx = state.indexWhere((i) => i.itemId == item.itemId);
    if (idx >= 0) {
      state[idx].qty += 1;
      state = [...state];
    } else {
      state = [...state, item];
    }
  }

  void removeItem(int itemId) {
    state = state.where((i) => i.itemId != itemId).toList();
  }

  void updateQty(int itemId, int qty) {
    final idx = state.indexWhere((i) => i.itemId == itemId);
    if (idx >= 0 && qty > 0) {
      state[idx].qty = qty;
      state = [...state];
    }
  }

  void updateDiscount(int itemId, double percent) {
    final idx = state.indexWhere((i) => i.itemId == itemId);
    if (idx >= 0) {
      state[idx].discountPercent = percent.clamp(0, 100);
      state = [...state];
    }
  }

  void clear() {
    state = [];
  }

  double get netTotal => state.fold(0.0, (sum, i) => sum + (i.rate * i.qty));
  double get totalDiscount =>
      state.fold(0.0, (sum, i) => sum + i.discountAmount);
  double get grandTotal => netTotal - totalDiscount;
  double get roundedTotal => grandTotal.roundToDouble();
}

final cartProvider = StateNotifierProvider<CartNotifier, List<CartItem>>((ref) {
  return CartNotifier();
});
