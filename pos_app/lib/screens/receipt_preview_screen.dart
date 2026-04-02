import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import 'package:pos_app/models/models.dart';
import 'package:pos_app/services/pdf_receipt_service.dart';

class ReceiptPreviewScreen extends StatelessWidget {
  final ReceiptData receipt;

  const ReceiptPreviewScreen({super.key, required this.receipt});

  @override
  Widget build(BuildContext context) {
    final dateStr = DateFormat('dd-MMM-yyyy hh:mm a').format(receipt.dateTime);

    return Scaffold(
      appBar: AppBar(
        title: const Text('Receipt'),
        actions: [
          IconButton(
            icon: const Icon(Icons.print),
            tooltip: 'Print',
            onPressed: () => PdfReceiptService.printReceipt(receipt),
          ),
          IconButton(
            icon: const Icon(Icons.share),
            tooltip: 'Share',
            onPressed: () => PdfReceiptService.shareReceipt(receipt),
          ),
        ],
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(24),
        child: Center(
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 400),
            child: Card(
              child: Padding(
                padding: const EdgeInsets.all(24),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.center,
                  children: [
                    // Store name
                    if (receipt.storeName != null)
                      Text(
                        receipt.storeName!,
                        style: const TextStyle(
                          fontSize: 20,
                          fontWeight: FontWeight.bold,
                        ),
                      ),
                    const SizedBox(height: 4),
                    Text(
                      receipt.invoiceNumber,
                      style: const TextStyle(fontSize: 14, color: Colors.grey),
                    ),
                    const SizedBox(height: 4),
                    Text(dateStr, style: const TextStyle(fontSize: 12)),
                    Text(
                      'Cashier: ${receipt.cashierName}',
                      style: const TextStyle(fontSize: 12),
                    ),
                    Text(
                      'Customer: ${receipt.customerName}',
                      style: const TextStyle(fontSize: 12),
                    ),
                    const Divider(height: 24),

                    // Item lines
                    ...receipt.items.map(
                      (item) => Padding(
                        padding: const EdgeInsets.symmetric(vertical: 2),
                        child: Row(
                          children: [
                            Expanded(
                              child: Column(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: [
                                  Text(
                                    item.itemName,
                                    style: const TextStyle(fontSize: 13),
                                  ),
                                  Text(
                                    '${item.qty} x \u20B9${item.rate.toStringAsFixed(2)}'
                                    '${item.discountPercent > 0 ? ' (-${item.discountPercent.toStringAsFixed(0)}%)' : ''}',
                                    style: TextStyle(
                                      fontSize: 11,
                                      color: Colors.grey.shade600,
                                    ),
                                  ),
                                ],
                              ),
                            ),
                            Text(
                              '\u20B9${item.amount.toStringAsFixed(2)}',
                              style: const TextStyle(fontSize: 13),
                            ),
                          ],
                        ),
                      ),
                    ),
                    const Divider(height: 24),

                    // Totals
                    _ReceiptRow('Net Total', receipt.netTotal),
                    if (receipt.totalDiscount > 0)
                      _ReceiptRow('Discount', -receipt.totalDiscount),
                    _ReceiptRow('Grand Total', receipt.grandTotal, bold: true),
                    _ReceiptRow(
                      'Rounded Total',
                      receipt.roundedTotal,
                      bold: true,
                    ),
                    const Divider(height: 24),

                    // Payments
                    ...receipt.payments
                        .where((p) => p.amount > 0)
                        .map((p) => _ReceiptRow(p.modeName, p.amount)),
                    if (receipt.changeDue > 0)
                      _ReceiptRow('Change Due', receipt.changeDue, bold: true),
                    const Divider(height: 24),

                    if (receipt.footerText != null)
                      Text(
                        receipt.footerText!,
                        textAlign: TextAlign.center,
                        style: const TextStyle(
                          fontSize: 11,
                          color: Colors.grey,
                        ),
                      ),
                    const Text(
                      'Thank you!',
                      style: TextStyle(
                        fontSize: 12,
                        fontStyle: FontStyle.italic,
                      ),
                    ),
                  ],
                ),
              ),
            ),
          ),
        ),
      ),
      bottomNavigationBar: Padding(
        padding: const EdgeInsets.all(16),
        child: Row(
          children: [
            Expanded(
              child: OutlinedButton.icon(
                onPressed: () => PdfReceiptService.printReceipt(receipt),
                icon: const Icon(Icons.print),
                label: const Text('Reprint'),
              ),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: ElevatedButton.icon(
                onPressed: () => Navigator.of(context).pop(),
                icon: const Icon(Icons.add_shopping_cart),
                label: const Text('New Sale'),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _ReceiptRow extends StatelessWidget {
  final String label;
  final double value;
  final bool bold;

  const _ReceiptRow(this.label, this.value, {this.bold = false});

  @override
  Widget build(BuildContext context) {
    final style = bold
        ? const TextStyle(fontWeight: FontWeight.bold, fontSize: 14)
        : const TextStyle(fontSize: 13);
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 1),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Text(label, style: style),
          Text('\u20B9 ${value.toStringAsFixed(2)}', style: style),
        ],
      ),
    );
  }
}
