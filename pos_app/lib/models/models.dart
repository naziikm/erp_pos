class CartItem {
  final int itemId;
  final String itemCode;
  final String itemName;
  final String? itemGroup;
  final double rate;
  int qty;
  double discountPercent;
  double? projectedQty;

  CartItem({
    required this.itemId,
    required this.itemCode,
    required this.itemName,
    this.itemGroup,
    required this.rate,
    this.qty = 1,
    this.discountPercent = 0,
    this.projectedQty,
  });

  double get discountAmount => (rate * qty) * (discountPercent / 100);
  double get amount => (rate * qty) - discountAmount;
}

class PaymentEntry {
  final int modeId;
  final String modeName;
  double amount;
  String? reference;

  PaymentEntry({
    required this.modeId,
    required this.modeName,
    this.amount = 0,
    this.reference,
  });
}

class ReceiptData {
  final String? storeName;
  final String invoiceNumber;
  final DateTime dateTime;
  final String cashierName;
  final String customerName;
  final List<CartItem> items;
  final double netTotal;
  final double totalDiscount;
  final double grandTotal;
  final double roundedTotal;
  final List<PaymentEntry> payments;
  final double changeDue;
  final String? footerText;

  ReceiptData({
    this.storeName,
    required this.invoiceNumber,
    required this.dateTime,
    required this.cashierName,
    required this.customerName,
    required this.items,
    required this.netTotal,
    required this.totalDiscount,
    required this.grandTotal,
    required this.roundedTotal,
    required this.payments,
    this.changeDue = 0,
    this.footerText,
  });
}
