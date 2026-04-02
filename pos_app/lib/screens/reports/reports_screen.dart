import 'package:flutter/material.dart';
import 'package:pos_app/screens/reports/day_summary_tab.dart';
import 'package:pos_app/screens/reports/invoice_history_tab.dart';
import 'package:pos_app/screens/reports/item_sales_tab.dart';
import 'package:pos_app/screens/reports/sync_health_tab.dart';

class ReportsScreen extends StatelessWidget {
  const ReportsScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return DefaultTabController(
      length: 4,
      child: Scaffold(
        appBar: AppBar(
          title: const Text('Reports'),
          bottom: const TabBar(
            isScrollable: true,
            tabs: [
              Tab(text: 'Day Summary'),
              Tab(text: 'Invoice History'),
              Tab(text: 'Item Sales'),
              Tab(text: 'Sync Health'),
            ],
          ),
        ),
        body: const TabBarView(
          children: [
            DaySummaryTab(),
            InvoiceHistoryTab(),
            ItemSalesTab(),
            SyncHealthTab(),
          ],
        ),
      ),
    );
  }
}
