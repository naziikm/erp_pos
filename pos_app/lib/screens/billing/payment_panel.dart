import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:uuid/uuid.dart';
import 'package:pos_app/models/models.dart';
import 'package:pos_app/services/billing_service.dart';

class PaymentPanel extends StatefulWidget {
  final double grandTotal;
  final Map<String, dynamic>? session;
  final Map<String, dynamic>? customer;
  final List<CartItem> cart;
  final String cashierName;
  final ValueChanged<Map<String, dynamic>> onInvoiceCreated;

  const PaymentPanel({
    super.key,
    required this.grandTotal,
    required this.session,
    required this.customer,
    required this.cart,
    required this.cashierName,
    required this.onInvoiceCreated,
  });

  @override
  State<PaymentPanel> createState() => _PaymentPanelState();
}

class _PaymentPanelState extends State<PaymentPanel> {
  final _billingService = BillingService();
  final _uuid = const Uuid();

  List<PaymentEntry> _payments = [];
  bool _loading = false;
  String? _error;

  @override
  void initState() {
    super.initState();
    _initPaymentModes();
  }

  void _initPaymentModes() {
    final modes =
        widget.session?['allowed_modes_of_payment'] as List<dynamic>? ?? [];
    _payments = modes.map(_toPaymentEntry).whereType<PaymentEntry>().toList();

    // If only one mode (usually Cash), pre-fill the full amount
    if (_payments.length == 1) {
      _payments[0].amount = widget.grandTotal;
    }
  }

  PaymentEntry? _toPaymentEntry(dynamic rawMode) {
    if (rawMode is String) {
      final modeName = rawMode.trim();
      if (modeName.isEmpty) return null;
      return PaymentEntry(modeId: null, modeName: modeName);
    }

    if (rawMode is Map) {
      final modeName = (rawMode['mode_of_payment'] ?? rawMode['name'] ?? '')
          .toString()
          .trim();
      if (modeName.isEmpty) return null;

      final rawId = rawMode['id'];
      final modeId = rawId is int
          ? rawId
          : int.tryParse(rawId?.toString() ?? '');
      return PaymentEntry(modeId: modeId, modeName: modeName);
    }

    return null;
  }

  double get _totalPaid => _payments.fold(0.0, (sum, p) => sum + p.amount);
  double get _remaining => widget.grandTotal - _totalPaid;
  double get _changeDue {
    // Change only applies to cash
    final cashEntry = _payments.where(
      (p) => p.modeName.toLowerCase() == 'cash',
    );
    if (cashEntry.isEmpty) return 0;
    return _totalPaid > widget.grandTotal ? _totalPaid - widget.grandTotal : 0;
  }

  bool get _canSubmit => _totalPaid >= widget.grandTotal && !_loading;

  Future<void> _submitInvoice() async {
    setState(() {
      _loading = true;
      _error = null;
    });

    final transactionId = _uuid.v4();

    final payload = {
      'transaction_id': transactionId,
      'customer_id': widget.customer?['id'],
      'items': widget.cart
          .map(
            (item) => {
              'item_id': item.itemId,
              'item_code': item.itemCode,
              'item_name': item.itemName,
              'qty': item.qty,
              'rate': item.rate,
              'discount_percentage': item.discountPercent,
              'amount': item.amount,
            },
          )
          .toList(),
      'payments': _payments
          .where((p) => p.amount > 0 && p.modeId != null)
          .map(
            (p) => {
              'mode_of_payment_id': p.modeId,
              'amount': p.amount,
              'reference_number': p.reference,
            },
          )
          .toList(),
      'net_total': widget.cart.fold<double>(
        0,
        (sum, item) => sum + (item.rate * item.qty),
      ),
      'total_discount': widget.cart.fold<double>(
        0,
        (sum, item) => sum + item.discountAmount,
      ),
      'grand_total': widget.grandTotal,
    };

    final missingModeIds = _payments.any(
      (p) => p.amount > 0 && p.modeId == null,
    );
    if (missingModeIds) {
      setState(() {
        _loading = false;
        _error =
            'Payment modes are outdated. Refresh the session and try again.';
      });
      return;
    }

    try {
      final result = await _billingService.createInvoice(payload);
      widget.onInvoiceCreated(result);
    } on DioException catch (e) {
      if (e.type == DioExceptionType.connectionTimeout ||
          e.type == DioExceptionType.receiveTimeout) {
        // Timeout — check if invoice was created
        setState(() => _error = 'Checking invoice status...');
        final existing = await _billingService.checkInvoice(transactionId);
        if (existing != null) {
          widget.onInvoiceCreated(existing);
          return;
        }
        setState(() => _error = 'Network timeout. Please retry.');
      } else if (e.response != null) {
        final statusCode = e.response!.statusCode ?? 0;
        final detail = e.response?.data?['detail'];
        if (statusCode >= 400 && statusCode < 500) {
          final msg = detail is Map
              ? (detail['message'] ?? 'Validation error')
              : 'Validation error';
          setState(() => _error = msg.toString());
        } else {
          setState(() => _error = 'Sale could not be saved. Please retry.');
        }
      } else {
        setState(() => _error = 'Cannot reach server. Please retry.');
      }
    } catch (e) {
      setState(() => _error = 'Unexpected error: $e');
    } finally {
      setState(() => _loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return DraggableScrollableSheet(
      initialChildSize: 0.7,
      minChildSize: 0.5,
      maxChildSize: 0.95,
      expand: false,
      builder: (_, scrollController) => Padding(
        padding: const EdgeInsets.all(16),
        child: ListView(
          controller: scrollController,
          children: [
            // Header
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Text('Payment', style: Theme.of(context).textTheme.titleLarge),
                Text(
                  'Total: \u20B9 ${widget.grandTotal.toStringAsFixed(2)}',
                  style: const TextStyle(
                    fontWeight: FontWeight.bold,
                    fontSize: 18,
                  ),
                ),
              ],
            ),
            const SizedBox(height: 16),

            // Payment mode entries
            ..._payments.asMap().entries.map((entry) {
              final idx = entry.key;
              final payment = entry.value;
              final needsRef = !payment.modeName.toLowerCase().contains('cash');
              return Card(
                child: Padding(
                  padding: const EdgeInsets.all(12),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        payment.modeName,
                        style: const TextStyle(fontWeight: FontWeight.w600),
                      ),
                      const SizedBox(height: 8),
                      TextField(
                        decoration: const InputDecoration(
                          labelText: 'Amount',
                          prefixText: '\u20B9 ',
                          isDense: true,
                        ),
                        keyboardType: const TextInputType.numberWithOptions(
                          decimal: true,
                        ),
                        controller: TextEditingController(
                          text: payment.amount > 0
                              ? payment.amount.toStringAsFixed(2)
                              : '',
                        ),
                        onChanged: (val) {
                          setState(() {
                            _payments[idx].amount = double.tryParse(val) ?? 0;
                          });
                        },
                      ),
                      if (needsRef) ...[
                        const SizedBox(height: 8),
                        TextField(
                          decoration: const InputDecoration(
                            labelText: 'Reference Number',
                            isDense: true,
                          ),
                          onChanged: (val) => _payments[idx].reference = val,
                        ),
                      ],
                    ],
                  ),
                ),
              );
            }),

            const SizedBox(height: 16),

            // Running total
            Card(
              color: _remaining <= 0
                  ? Colors.green.shade50
                  : Colors.orange.shade50,
              child: Padding(
                padding: const EdgeInsets.all(12),
                child: Column(
                  children: [
                    Row(
                      mainAxisAlignment: MainAxisAlignment.spaceBetween,
                      children: [
                        const Text('Paid'),
                        Text('\u20B9 ${_totalPaid.toStringAsFixed(2)}'),
                      ],
                    ),
                    if (_remaining > 0) ...[
                      Row(
                        mainAxisAlignment: MainAxisAlignment.spaceBetween,
                        children: [
                          const Text(
                            'Remaining',
                            style: TextStyle(color: Colors.red),
                          ),
                          Text(
                            '\u20B9 ${_remaining.toStringAsFixed(2)}',
                            style: const TextStyle(color: Colors.red),
                          ),
                        ],
                      ),
                    ],
                    if (_changeDue > 0) ...[
                      Row(
                        mainAxisAlignment: MainAxisAlignment.spaceBetween,
                        children: [
                          const Text(
                            'Change Due',
                            style: TextStyle(fontWeight: FontWeight.bold),
                          ),
                          Text(
                            '\u20B9 ${_changeDue.toStringAsFixed(2)}',
                            style: const TextStyle(fontWeight: FontWeight.bold),
                          ),
                        ],
                      ),
                    ],
                  ],
                ),
              ),
            ),

            if (_error != null) ...[
              const SizedBox(height: 12),
              Text(
                _error!,
                style: TextStyle(color: Theme.of(context).colorScheme.error),
                textAlign: TextAlign.center,
              ),
            ],

            const SizedBox(height: 16),
            ElevatedButton.icon(
              onPressed: _canSubmit ? _submitInvoice : null,
              icon: _loading
                  ? const SizedBox(
                      width: 20,
                      height: 20,
                      child: CircularProgressIndicator(
                        strokeWidth: 2,
                        color: Colors.white,
                      ),
                    )
                  : const Icon(Icons.check_circle),
              label: Text(_loading ? 'Processing...' : 'Complete Sale'),
              style: ElevatedButton.styleFrom(
                minimumSize: const Size(double.infinity, 56),
                backgroundColor: Theme.of(context).colorScheme.primary,
                foregroundColor: Colors.white,
              ),
            ),
          ],
        ),
      ),
    );
  }
}
