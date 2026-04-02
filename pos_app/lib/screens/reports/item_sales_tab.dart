import 'package:flutter/material.dart';
import 'package:pos_app/services/reports_service.dart';

class ItemSalesTab extends StatefulWidget {
  const ItemSalesTab({super.key});

  @override
  State<ItemSalesTab> createState() => _ItemSalesTabState();
}

class _ItemSalesTabState extends State<ItemSalesTab> {
  final _reportsService = ReportsService();
  List<dynamic> _items = [];
  bool _loading = true;
  String _sortBy = 'amount';
  bool _sortAsc = false;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() => _loading = true);
    try {
      final data = await _reportsService.getItemSales();
      setState(() {
        _items = data;
        _loading = false;
      });
      _sort();
    } catch (e) {
      setState(() => _loading = false);
    }
  }

  void _sort() {
    setState(() {
      _items.sort((a, b) {
        final aVal = (a[_sortBy] ?? 0);
        final bVal = (b[_sortBy] ?? 0);
        if (aVal is num && bVal is num) {
          return _sortAsc ? aVal.compareTo(bVal) : bVal.compareTo(aVal);
        }
        return aVal.toString().compareTo(bVal.toString()) * (_sortAsc ? 1 : -1);
      });
    });
  }

  void _toggleSort(String col) {
    if (_sortBy == col) {
      _sortAsc = !_sortAsc;
    } else {
      _sortBy = col;
      _sortAsc = false;
    }
    _sort();
  }

  @override
  Widget build(BuildContext context) {
    if (_loading) return const Center(child: CircularProgressIndicator());
    if (_items.isEmpty) return const Center(child: Text('No item sales data'));

    return RefreshIndicator(
      onRefresh: _load,
      child: SingleChildScrollView(
        scrollDirection: Axis.horizontal,
        child: SingleChildScrollView(
          child: DataTable(
            sortColumnIndex: _sortBy == 'item_name'
                ? 0
                : (_sortBy == 'qty' ? 1 : 2),
            sortAscending: _sortAsc,
            columns: [
              DataColumn(
                label: const Text('Item'),
                onSort: (_, _) => _toggleSort('item_name'),
              ),
              DataColumn(
                label: const Text('Qty'),
                numeric: true,
                onSort: (_, _) => _toggleSort('qty'),
              ),
              DataColumn(
                label: const Text('Amount'),
                numeric: true,
                onSort: (_, _) => _toggleSort('amount'),
              ),
            ],
            rows: _items.map((item) {
              return DataRow(
                cells: [
                  DataCell(Text(item['item_name'] ?? '')),
                  DataCell(Text('${item['qty'] ?? 0}')),
                  DataCell(Text('\u20B9 ${item['amount'] ?? 0}')),
                ],
              );
            }).toList(),
          ),
        ),
      ),
    );
  }
}
