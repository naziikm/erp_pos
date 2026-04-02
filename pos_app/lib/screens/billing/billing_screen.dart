import 'dart:async';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:mobile_scanner/mobile_scanner.dart';
import 'package:pos_app/core/constants.dart';
import 'package:pos_app/core/theme.dart';
import 'package:pos_app/models/models.dart';
import 'package:pos_app/providers/auth_provider.dart';
import 'package:pos_app/providers/cart_provider.dart';
import 'package:pos_app/providers/connectivity_provider.dart';
import 'package:pos_app/providers/session_provider.dart';
import 'package:pos_app/screens/billing/customer_selector.dart';
import 'package:pos_app/screens/billing/payment_panel.dart';
import 'package:pos_app/services/billing_service.dart';

class BillingScreen extends ConsumerStatefulWidget {
  final VoidCallback onOpenDrawer;

  const BillingScreen({super.key, required this.onOpenDrawer});

  @override
  ConsumerState<BillingScreen> createState() => _BillingScreenState();
}

class _BillingScreenState extends ConsumerState<BillingScreen> {
  final _billingService = BillingService();
  final _searchController = TextEditingController();

  List<Map<String, dynamic>> _allItems = [];
  List<Map<String, dynamic>> _filteredItems = [];
  List<String> _itemGroups = ['All'];
  String _selectedGroup = 'All';
  Map<String, dynamic>? _selectedCustomer;
  bool _loadingItems = true;
  Timer? _searchDebounce;

  @override
  void initState() {
    super.initState();
    _loadItems();
  }

  @override
  void dispose() {
    _searchController.dispose();
    _searchDebounce?.cancel();
    super.dispose();
  }

  Future<void> _loadItems() async {
    setState(() => _loadingItems = true);
    try {
      final items = await _billingService.getItems();
      final groups = <String>{'All'};
      for (final item in items) {
        final g = item['item_group'];
        if (g != null && g.toString().isNotEmpty) groups.add(g.toString());
      }
      setState(() {
        _allItems = items.cast<Map<String, dynamic>>();
        _filteredItems = _allItems;
        _itemGroups = groups.toList();
        _loadingItems = false;
      });
    } catch (e) {
      setState(() => _loadingItems = false);
    }
  }

  void _filterItems(String query) {
    _searchDebounce?.cancel();
    _searchDebounce = Timer(
      const Duration(milliseconds: AppConstants.searchDebounceMs),
      () {
        setState(() {
          _filteredItems = _allItems.where((item) {
            final matchGroup =
                _selectedGroup == 'All' || item['item_group'] == _selectedGroup;
            final matchSearch =
                query.isEmpty ||
                (item['item_name'] ?? '').toString().toLowerCase().contains(
                  query.toLowerCase(),
                ) ||
                (item['item_code'] ?? '').toString().toLowerCase().contains(
                  query.toLowerCase(),
                );
            return matchGroup && matchSearch;
          }).toList();
        });
      },
    );
  }

  void _onGroupSelected(String group) {
    setState(() => _selectedGroup = group);
    _filterItems(_searchController.text);
  }

  void _addToCart(Map<String, dynamic> item) {
    ref
        .read(cartProvider.notifier)
        .addItem(
          CartItem(
            itemId: item['id'],
            itemCode: item['item_code'] ?? '',
            itemName: item['item_name'] ?? '',
            itemGroup: item['item_group'],
            rate: (item['rate'] ?? 0).toDouble(),
            projectedQty: item['projected_qty']?.toDouble(),
          ),
        );
  }

  void _openBarcodeScanner() {
    showDialog(
      context: context,
      builder: (ctx) => Dialog(
        child: SizedBox(
          height: 400,
          child: MobileScanner(
            onDetect: (capture) {
              final barcode = capture.barcodes.first.rawValue;
              if (barcode != null) {
                Navigator.of(ctx).pop();
                final item = _allItems.firstWhere(
                  (i) => i['barcode'] == barcode || i['item_code'] == barcode,
                  orElse: () => {},
                );
                if (item.isNotEmpty) {
                  _addToCart(item);
                } else {
                  ScaffoldMessenger.of(context).showSnackBar(
                    SnackBar(content: Text('Item not found: $barcode')),
                  );
                }
              }
            },
          ),
        ),
      ),
    );
  }

  Color _stockColor(double? qty) {
    if (qty == null) return Colors.grey;
    if (qty > 10) return AppTheme.successColor;
    if (qty > 0) return AppTheme.warningColor;
    return AppTheme.errorColor;
  }

  @override
  Widget build(BuildContext context) {
    final cart = ref.watch(cartProvider);
    final cartNotifier = ref.read(cartProvider.notifier);
    final isOnline = ref.watch(isOnlineProvider);
    final session = ref.watch(sessionProvider);
    final auth = ref.watch(authProvider);

    return Scaffold(
      appBar: AppBar(
        leading: IconButton(
          icon: const Icon(Icons.menu),
          onPressed: widget.onOpenDrawer,
        ),
        title: Text(session.session?['pos_profile_name'] ?? 'POS Billing'),
        actions: [
          if (!isOnline)
            Container(
              margin: const EdgeInsets.only(right: 8),
              padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
              decoration: BoxDecoration(
                color: AppTheme.warningColor,
                borderRadius: BorderRadius.circular(12),
              ),
              child: const Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Icon(Icons.wifi_off, size: 16, color: Colors.white),
                  SizedBox(width: 4),
                  Text(
                    'Offline',
                    style: TextStyle(color: Colors.white, fontSize: 12),
                  ),
                ],
              ),
            ),
          if (cart.isNotEmpty)
            Badge(
              label: Text('${cart.length}'),
              child: const Icon(Icons.shopping_cart),
            ),
          const SizedBox(width: 12),
        ],
      ),
      body: Row(
        children: [
          // Left: Item grid
          Expanded(
            flex: 3,
            child: Column(
              children: [
                // Offline banner
                if (!isOnline)
                  Container(
                    width: double.infinity,
                    color: AppTheme.offlineBannerColor,
                    padding: const EdgeInsets.all(8),
                    child: const Row(
                      children: [
                        Icon(Icons.wifi_off, size: 16, color: Colors.orange),
                        SizedBox(width: 8),
                        Expanded(
                          child: Text(
                            'Offline — sales are saved locally and will sync when connected',
                            style: TextStyle(
                              fontSize: 12,
                              color: Colors.orange,
                            ),
                          ),
                        ),
                      ],
                    ),
                  ),

                // Search bar
                Padding(
                  padding: const EdgeInsets.all(8),
                  child: Row(
                    children: [
                      Expanded(
                        child: TextField(
                          controller: _searchController,
                          decoration: InputDecoration(
                            hintText: 'Search items...',
                            prefixIcon: const Icon(Icons.search),
                            isDense: true,
                            suffixIcon: _searchController.text.isNotEmpty
                                ? IconButton(
                                    icon: const Icon(Icons.clear),
                                    onPressed: () {
                                      _searchController.clear();
                                      _filterItems('');
                                    },
                                  )
                                : null,
                          ),
                          onChanged: _filterItems,
                        ),
                      ),
                      const SizedBox(width: 8),
                      IconButton(
                        onPressed: _openBarcodeScanner,
                        icon: const Icon(Icons.qr_code_scanner),
                        tooltip: 'Scan Barcode',
                      ),
                    ],
                  ),
                ),

                // Item group tabs
                SizedBox(
                  height: 40,
                  child: ListView(
                    scrollDirection: Axis.horizontal,
                    padding: const EdgeInsets.symmetric(horizontal: 8),
                    children: _itemGroups.map((group) {
                      final selected = _selectedGroup == group;
                      return Padding(
                        padding: const EdgeInsets.only(right: 8),
                        child: FilterChip(
                          label: Text(group),
                          selected: selected,
                          onSelected: (_) => _onGroupSelected(group),
                        ),
                      );
                    }).toList(),
                  ),
                ),
                const SizedBox(height: 8),

                // Item grid
                Expanded(
                  child: _loadingItems
                      ? const Center(child: CircularProgressIndicator())
                      : _filteredItems.isEmpty
                      ? const Center(child: Text('No items found'))
                      : GridView.builder(
                          padding: const EdgeInsets.all(8),
                          gridDelegate:
                              const SliverGridDelegateWithMaxCrossAxisExtent(
                                maxCrossAxisExtent: 200,
                                childAspectRatio: 1.2,
                                crossAxisSpacing: 8,
                                mainAxisSpacing: 8,
                              ),
                          itemCount: _filteredItems.length,
                          itemBuilder: (_, index) {
                            final item = _filteredItems[index];
                            return _ItemCard(
                              item: item,
                              stockColor: _stockColor(
                                item['projected_qty']?.toDouble(),
                              ),
                              onTap: () => _addToCart(item),
                            );
                          },
                        ),
                ),
              ],
            ),
          ),

          // Right: Cart panel
          Container(
            width: 360,
            decoration: BoxDecoration(
              border: Border(left: BorderSide(color: Colors.grey.shade300)),
            ),
            child: Column(
              children: [
                // Customer selector
                Padding(
                  padding: const EdgeInsets.all(8),
                  child: CustomerSelector(
                    selectedCustomer: _selectedCustomer,
                    onCustomerSelected: (c) =>
                        setState(() => _selectedCustomer = c),
                  ),
                ),
                const Divider(height: 1),

                // Cart items
                Expanded(
                  child: cart.isEmpty
                      ? const Center(child: Text('Cart is empty'))
                      : ListView.builder(
                          itemCount: cart.length,
                          itemBuilder: (_, index) {
                            final item = cart[index];
                            return _CartItemTile(
                              item: item,
                              onQtyChanged: (qty) =>
                                  cartNotifier.updateQty(item.itemId, qty),
                              onDiscountChanged: (d) =>
                                  cartNotifier.updateDiscount(item.itemId, d),
                              onRemove: () =>
                                  cartNotifier.removeItem(item.itemId),
                            );
                          },
                        ),
                ),
                const Divider(height: 1),

                // Totals
                Padding(
                  padding: const EdgeInsets.all(12),
                  child: Column(
                    children: [
                      _TotalRow('Net Total', cartNotifier.netTotal),
                      if (cartNotifier.totalDiscount > 0)
                        _TotalRow('Discount', -cartNotifier.totalDiscount),
                      const Divider(),
                      _TotalRow(
                        'Grand Total',
                        cartNotifier.grandTotal,
                        bold: true,
                      ),
                      _TotalRow(
                        'Rounded',
                        cartNotifier.roundedTotal,
                        bold: true,
                      ),
                    ],
                  ),
                ),

                // Pay button
                Padding(
                  padding: const EdgeInsets.all(12),
                  child: ElevatedButton.icon(
                    onPressed: cart.isEmpty
                        ? null
                        : () => _showPaymentPanel(
                            cartNotifier.roundedTotal,
                            session.session,
                            auth,
                          ),
                    icon: const Icon(Icons.payment),
                    label: Text(
                      cart.isEmpty
                          ? 'Add Items'
                          : 'Pay ${cartNotifier.roundedTotal.toStringAsFixed(2)}',
                    ),
                    style: ElevatedButton.styleFrom(
                      minimumSize: const Size(double.infinity, 56),
                      backgroundColor: Theme.of(context).colorScheme.primary,
                      foregroundColor: Colors.white,
                    ),
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  void _showPaymentPanel(
    double total,
    Map<String, dynamic>? session,
    AuthState auth,
  ) {
    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      builder: (_) => PaymentPanel(
        grandTotal: total,
        session: session,
        customer: _selectedCustomer,
        cart: ref.read(cartProvider),
        cashierName: auth.fullName ?? 'Cashier',
        onInvoiceCreated: (receipt) {
          ref.read(cartProvider.notifier).clear();
          setState(() => _selectedCustomer = null);
          Navigator.of(context).pop(); // close payment panel
          _showReceiptDialog(receipt);
        },
      ),
    );
  }

  void _showReceiptDialog(Map<String, dynamic> invoice) {
    showDialog(
      context: context,
      builder: (_) => AlertDialog(
        title: const Text('Invoice Created'),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('Invoice #: ${invoice['invoice_number'] ?? ''}'),
            Text('Total: ${invoice['grand_total'] ?? ''}'),
            const SizedBox(height: 8),
            const Text('Invoice saved successfully!'),
          ],
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(context).pop(),
            child: const Text('New Sale'),
          ),
        ],
      ),
    );
  }
}

class _ItemCard extends StatelessWidget {
  final Map<String, dynamic> item;
  final Color stockColor;
  final VoidCallback onTap;

  const _ItemCard({
    required this.item,
    required this.stockColor,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return Card(
      clipBehavior: Clip.antiAlias,
      child: InkWell(
        onTap: onTap,
        child: Padding(
          padding: const EdgeInsets.all(12),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  Expanded(
                    child: Text(
                      item['item_name'] ?? '',
                      style: const TextStyle(
                        fontWeight: FontWeight.w600,
                        fontSize: 13,
                      ),
                      maxLines: 2,
                      overflow: TextOverflow.ellipsis,
                    ),
                  ),
                  Container(
                    width: 8,
                    height: 8,
                    decoration: BoxDecoration(
                      color: stockColor,
                      shape: BoxShape.circle,
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 4),
              Text(
                item['item_code'] ?? '',
                style: TextStyle(fontSize: 11, color: Colors.grey.shade600),
              ),
              const Spacer(),
              Text(
                '\u20B9 ${(item['rate'] ?? 0).toStringAsFixed(2)}',
                style: TextStyle(
                  fontWeight: FontWeight.bold,
                  fontSize: 16,
                  color: Theme.of(context).colorScheme.primary,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _CartItemTile extends StatelessWidget {
  final CartItem item;
  final ValueChanged<int> onQtyChanged;
  final ValueChanged<double> onDiscountChanged;
  final VoidCallback onRemove;

  const _CartItemTile({
    required this.item,
    required this.onQtyChanged,
    required this.onDiscountChanged,
    required this.onRemove,
  });

  @override
  Widget build(BuildContext context) {
    return Dismissible(
      key: ValueKey(item.itemId),
      direction: DismissDirection.endToStart,
      background: Container(
        color: Colors.red,
        alignment: Alignment.centerRight,
        padding: const EdgeInsets.only(right: 16),
        child: const Icon(Icons.delete, color: Colors.white),
      ),
      onDismissed: (_) => onRemove(),
      child: ListTile(
        dense: true,
        title: Text(item.itemName, style: const TextStyle(fontSize: 13)),
        subtitle: Text(
          '\u20B9${item.rate.toStringAsFixed(2)} x ${item.qty}'
          '${item.discountPercent > 0 ? ' (-${item.discountPercent.toStringAsFixed(0)}%)' : ''}',
          style: const TextStyle(fontSize: 11),
        ),
        trailing: SizedBox(
          width: 120,
          child: Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              IconButton(
                icon: const Icon(Icons.remove_circle_outline, size: 20),
                onPressed: () {
                  if (item.qty > 1) onQtyChanged(item.qty - 1);
                },
                padding: EdgeInsets.zero,
                constraints: const BoxConstraints(),
              ),
              SizedBox(
                width: 30,
                child: Text('${item.qty}', textAlign: TextAlign.center),
              ),
              IconButton(
                icon: const Icon(Icons.add_circle_outline, size: 20),
                onPressed: () => onQtyChanged(item.qty + 1),
                padding: EdgeInsets.zero,
                constraints: const BoxConstraints(),
              ),
              const SizedBox(width: 8),
              Text(
                '\u20B9${item.amount.toStringAsFixed(0)}',
                style: const TextStyle(
                  fontWeight: FontWeight.w600,
                  fontSize: 13,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _TotalRow extends StatelessWidget {
  final String label;
  final double value;
  final bool bold;

  const _TotalRow(this.label, this.value, {this.bold = false});

  @override
  Widget build(BuildContext context) {
    final style = bold
        ? const TextStyle(fontWeight: FontWeight.bold, fontSize: 16)
        : const TextStyle(fontSize: 14);
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 2),
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
