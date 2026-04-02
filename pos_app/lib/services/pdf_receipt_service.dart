import 'package:pdf/pdf.dart';
import 'package:pdf/widgets.dart' as pw;
import 'package:printing/printing.dart';
import 'package:intl/intl.dart';
import 'package:pos_app/models/models.dart';

class PdfReceiptService {
  static Future<pw.Document> _buildPdf(ReceiptData receipt) async {
    final pdf = pw.Document();
    final dateStr = DateFormat('dd-MMM-yyyy hh:mm a').format(receipt.dateTime);

    pdf.addPage(
      pw.Page(
        pageFormat: PdfPageFormat(
          80 * PdfPageFormat.mm,
          double.infinity,
          marginAll: 5 * PdfPageFormat.mm,
        ),
        build: (context) => pw.Column(
          crossAxisAlignment: pw.CrossAxisAlignment.center,
          children: [
            // Store name
            if (receipt.storeName != null)
              pw.Text(
                receipt.storeName!,
                style: pw.TextStyle(
                  fontSize: 16,
                  fontWeight: pw.FontWeight.bold,
                ),
              ),
            pw.Text(
              receipt.invoiceNumber,
              style: const pw.TextStyle(fontSize: 10),
            ),
            pw.SizedBox(height: 4),
            pw.Text(dateStr, style: const pw.TextStyle(fontSize: 8)),
            pw.Text(
              'Cashier: ${receipt.cashierName}',
              style: const pw.TextStyle(fontSize: 8),
            ),
            pw.Text(
              'Customer: ${receipt.customerName}',
              style: const pw.TextStyle(fontSize: 8),
            ),
            pw.Divider(),

            // Item header
            pw.Row(
              mainAxisAlignment: pw.MainAxisAlignment.spaceBetween,
              children: [
                pw.Expanded(
                  child: pw.Text(
                    'Item',
                    style: pw.TextStyle(
                      fontSize: 8,
                      fontWeight: pw.FontWeight.bold,
                    ),
                  ),
                ),
                pw.Text(
                  'Qty',
                  style: pw.TextStyle(
                    fontSize: 8,
                    fontWeight: pw.FontWeight.bold,
                  ),
                ),
                pw.SizedBox(width: 20),
                pw.Text(
                  'Amt',
                  style: pw.TextStyle(
                    fontSize: 8,
                    fontWeight: pw.FontWeight.bold,
                  ),
                ),
              ],
            ),
            pw.SizedBox(height: 2),

            // Items
            ...receipt.items.map(
              (item) => pw.Row(
                mainAxisAlignment: pw.MainAxisAlignment.spaceBetween,
                children: [
                  pw.Expanded(
                    child: pw.Column(
                      crossAxisAlignment: pw.CrossAxisAlignment.start,
                      children: [
                        pw.Text(
                          item.itemName,
                          style: const pw.TextStyle(fontSize: 8),
                        ),
                        pw.Text(
                          '@ ${item.rate.toStringAsFixed(2)}'
                          '${item.discountPercent > 0 ? ' (-${item.discountPercent.toStringAsFixed(0)}%)' : ''}',
                          style: const pw.TextStyle(fontSize: 7),
                        ),
                      ],
                    ),
                  ),
                  pw.Text(
                    '${item.qty}',
                    style: const pw.TextStyle(fontSize: 8),
                  ),
                  pw.SizedBox(width: 10),
                  pw.SizedBox(
                    width: 50,
                    child: pw.Text(
                      item.amount.toStringAsFixed(2),
                      style: const pw.TextStyle(fontSize: 8),
                      textAlign: pw.TextAlign.right,
                    ),
                  ),
                ],
              ),
            ),

            pw.Divider(),

            // Totals
            _pdfTotalRow('Net Total', receipt.netTotal),
            if (receipt.totalDiscount > 0)
              _pdfTotalRow('Discount', -receipt.totalDiscount),
            _pdfTotalRow('Grand Total', receipt.grandTotal, bold: true),
            _pdfTotalRow('Rounded', receipt.roundedTotal, bold: true),
            pw.Divider(),

            // Payments
            ...receipt.payments
                .where((p) => p.amount > 0)
                .map((p) => _pdfTotalRow(p.modeName, p.amount)),
            if (receipt.changeDue > 0)
              _pdfTotalRow('Change Due', receipt.changeDue, bold: true),
            pw.Divider(),

            // Footer
            if (receipt.footerText != null)
              pw.Text(
                receipt.footerText!,
                style: const pw.TextStyle(fontSize: 7),
              ),
            pw.Text(
              'Thank you!',
              style: pw.TextStyle(fontSize: 9, fontStyle: pw.FontStyle.italic),
            ),
            pw.SizedBox(height: 10),
          ],
        ),
      ),
    );

    return pdf;
  }

  static pw.Widget _pdfTotalRow(
    String label,
    double value, {
    bool bold = false,
  }) {
    final style = bold
        ? pw.TextStyle(fontSize: 9, fontWeight: pw.FontWeight.bold)
        : const pw.TextStyle(fontSize: 8);
    return pw.Padding(
      padding: const pw.EdgeInsets.symmetric(vertical: 1),
      child: pw.Row(
        mainAxisAlignment: pw.MainAxisAlignment.spaceBetween,
        children: [
          pw.Text(label, style: style),
          pw.Text(value.toStringAsFixed(2), style: style),
        ],
      ),
    );
  }

  static Future<void> printReceipt(ReceiptData receipt) async {
    final pdf = await _buildPdf(receipt);
    await Printing.layoutPdf(onLayout: (_) async => pdf.save());
  }

  static Future<void> shareReceipt(ReceiptData receipt) async {
    final pdf = await _buildPdf(receipt);
    await Printing.sharePdf(
      bytes: await pdf.save(),
      filename: '${receipt.invoiceNumber}.pdf',
    );
  }
}
