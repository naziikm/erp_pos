import 'dart:async';
import 'package:flutter/material.dart';
import 'package:pos_app/core/constants.dart';
import 'package:pos_app/services/billing_service.dart';

class CustomerSelector extends StatefulWidget {
  final Map<String, dynamic>? selectedCustomer;
  final ValueChanged<Map<String, dynamic>?> onCustomerSelected;

  const CustomerSelector({
    super.key,
    required this.selectedCustomer,
    required this.onCustomerSelected,
  });

  @override
  State<CustomerSelector> createState() => _CustomerSelectorState();
}

class _CustomerSelectorState extends State<CustomerSelector> {
  final _billingService = BillingService();
  final _searchController = TextEditingController();
  List<Map<String, dynamic>> _customers = [];
  bool _loading = false;
  Timer? _debounce;

  void _search(String query) {
    _debounce?.cancel();
    _debounce = Timer(
      const Duration(milliseconds: AppConstants.searchDebounceMs),
      () async {
        if (query.isEmpty) {
          setState(() => _customers = []);
          return;
        }
        setState(() => _loading = true);
        try {
          final results = await _billingService.getCustomers(search: query);
          setState(() => _customers = results.cast<Map<String, dynamic>>());
        } catch (_) {}
        setState(() => _loading = false);
      },
    );
  }

  @override
  void dispose() {
    _searchController.dispose();
    _debounce?.cancel();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    if (widget.selectedCustomer != null) {
      return InputChip(
        avatar: const Icon(Icons.person, size: 18),
        label: Text(widget.selectedCustomer!['customer_name'] ?? 'Customer'),
        onDeleted: () => widget.onCustomerSelected(null),
      );
    }

    return Column(
      mainAxisSize: MainAxisSize.min,
      children: [
        TextField(
          controller: _searchController,
          decoration: InputDecoration(
            hintText: 'Search customer...',
            prefixIcon: const Icon(Icons.person_search, size: 20),
            isDense: true,
            suffixIcon: _loading
                ? const Padding(
                    padding: EdgeInsets.all(12),
                    child: SizedBox(
                      width: 16,
                      height: 16,
                      child: CircularProgressIndicator(strokeWidth: 2),
                    ),
                  )
                : null,
          ),
          onChanged: _search,
        ),
        // Walk-in option
        ListTile(
          dense: true,
          leading: const Icon(Icons.person_outline, size: 20),
          title: const Text('Walk-in Customer', style: TextStyle(fontSize: 13)),
          onTap: () {
            widget.onCustomerSelected({
              'customer_name': 'Walk-in Customer',
              'id': null,
            });
            _searchController.clear();
            setState(() => _customers = []);
          },
        ),
        if (_customers.isNotEmpty)
          ...(_customers
              .take(5)
              .map(
                (c) => ListTile(
                  dense: true,
                  title: Text(
                    c['customer_name'] ?? '',
                    style: const TextStyle(fontSize: 13),
                  ),
                  subtitle: Text(
                    c['customer_group'] ?? '',
                    style: const TextStyle(fontSize: 11),
                  ),
                  onTap: () {
                    widget.onCustomerSelected(c);
                    _searchController.clear();
                    setState(() => _customers = []);
                  },
                ),
              )),
      ],
    );
  }
}
