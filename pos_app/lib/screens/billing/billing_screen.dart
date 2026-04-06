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
  Timer? _refreshTimer;
  int? _selectedCartItemId;
  String _numpadBuffer = '';

  @override
  void initState() {
    super.initState();
    _loadItems();
    // Refresh items from DB every 10 seconds to catch background sync updates
    _refreshTimer = Timer.periodic(const Duration(seconds: 10), (_) => _autoRefreshItems());
  }

  @override
  void dispose() {
    _searchController.dispose();
    _searchDebounce?.cancel();
    _refreshTimer?.cancel();
    super.dispose();
  }

  Future<void> _autoRefreshItems() async {
    // Only refresh if not already loading and not searching
    if (_loadingItems || _searchController.text.isNotEmpty) return;
    await _fetchItems();
  }

  Future<void> _loadItems() async {
    setState(() => _loadingItems = true);
    await _fetchItems();
  }

  Future<void> _fetchItems() async {
    try {
      final items = await _billingService.getItems();
      final groups = <String>{'All'};
      for (final item in items) {
        final g = item['item_group'];
        if (g != null && g.toString().isNotEmpty) groups.add(g.toString());
      }
      if (mounted) {
        setState(() {
          _allItems = items.cast<Map<String, dynamic>>();
          // If we are not searching, update the filtered list too
          if (_searchController.text.isEmpty) {
            _filterItems(''); // This will reset filteredItems to allItems
          }
          _itemGroups = groups.toList();
          _loadingItems = false;
        });
      }
    } catch (e) {
      if (mounted) setState(() => _loadingItems = false);
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

    final contentBg = Colors.grey.shade100;

    final orderPanel = Container(
      color: Colors.white,
      padding: const EdgeInsets.all(10),
      child: Column(
        children: [
          // Customer search / selector on the left panel
          Padding(
            padding: const EdgeInsets.only(bottom: 8),
            child: InkWell(
              onTap: () {
                showDialog(
                  context: context,
                  builder: (_) => AlertDialog(
                    title: const Text('Select Customer'),
                    content: CustomerSelector(
                      selectedCustomer: _selectedCustomer,
                      onCustomerSelected: (c) {
                        setState(() => _selectedCustomer = c);
                        Navigator.of(context).pop();
                      },
                    ),
                  ),
                );
              },
              child: Container(
                width: double.infinity,
                padding: const EdgeInsets.symmetric(
                  horizontal: 12,
                  vertical: 10,
                ),
                decoration: BoxDecoration(
                  color: Colors.grey.shade50,
                  borderRadius: BorderRadius.circular(8),
                  border: Border.all(color: Colors.grey.shade200),
                ),
                child: Row(
                  children: [
                    Icon(Icons.person_search, color: AppTheme.primaryColor),
                    const SizedBox(width: 8),
                    Expanded(
                      child: Text(
                        _selectedCustomer == null
                            ? 'Search customer...'
                            : (_selectedCustomer?['display_name'] ??
                                  _selectedCustomer?['name'] ??
                                  ''),
                        style: TextStyle(
                          color: _selectedCustomer == null
                              ? Colors.grey.shade600
                              : Colors.black87,
                          fontWeight: _selectedCustomer == null
                              ? FontWeight.normal
                              : FontWeight.w600,
                        ),
                        overflow: TextOverflow.ellipsis,
                      ),
                    ),
                    if (_selectedCustomer != null)
                      IconButton(
                        icon: const Icon(Icons.clear, size: 18),
                        onPressed: () =>
                            setState(() => _selectedCustomer = null),
                        padding: EdgeInsets.zero,
                        constraints: const BoxConstraints(),
                      ),
                  ],
                ),
              ),
            ),
          ),
          // Cart list
          Expanded(
            child: Container(
              decoration: BoxDecoration(
                color: Colors.grey.shade50,
                borderRadius: BorderRadius.circular(10),
                border: Border.all(color: Colors.grey.shade200),
              ),
              child: cart.isEmpty
                  ? Center(
                      child: Column(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          Icon(
                            Icons.shopping_cart_outlined,
                            size: 48,
                            color: Colors.grey.shade400,
                          ),
                          const SizedBox(height: 10),
                          Text(
                            'No items selected',
                            style: TextStyle(
                              fontSize: 15,
                              fontWeight: FontWeight.w600,
                              color: Colors.grey.shade700,
                            ),
                          ),
                          const SizedBox(height: 4),
                          Text(
                            'Add items from the menu',
                            style: TextStyle(
                              fontSize: 13,
                              color: Colors.grey.shade500,
                            ),
                          ),
                        ],
                      ),
                    )
                  : ListView.separated(
                      itemCount: cart.length,
                      separatorBuilder: (_, __) =>
                          Divider(height: 1, color: Colors.grey.shade200),
                      itemBuilder: (_, index) {
                        final item = cart[index];
                        final isSelected = _selectedCartItemId == item.itemId;
                        return _CartItemTile(
                          item: item,
                          selected: isSelected,
                          onTap: () =>
                              setState(() => _selectedCartItemId = item.itemId),
                          onQtyChanged: (qty) =>
                              cartNotifier.updateQty(item.itemId, qty),
                          onDiscountChanged: (d) =>
                              cartNotifier.updateDiscount(item.itemId, d),
                          onRemove: () {
                            cartNotifier.removeItem(item.itemId);
                            if (_selectedCartItemId == item.itemId) {
                              setState(() => _selectedCartItemId = null);
                            }
                          },
                        );
                      },
                    ),
            ),
          ),
          const SizedBox(height: 8),
          // Totals
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 8),
            decoration: BoxDecoration(
              border: Border(top: BorderSide(color: Colors.grey.shade300)),
            ),
            child: Column(
              children: [
                _TotalRow('Subtotal', cartNotifier.netTotal),
                if (cartNotifier.totalDiscount > 0)
                  _TotalRow('Discount', -cartNotifier.totalDiscount),
                Divider(height: 10, color: Colors.grey.shade300),
                _TotalRow(
                  'Total',
                  cartNotifier.roundedTotal,
                  bold: true,
                  color: AppTheme.successColor,
                ),
              ],
            ),
          ),
          const SizedBox(height: 6),
          // Numpad + Action buttons
          _NumpadActionGrid(
            onDigit: (d) {
              setState(() => _numpadBuffer += d);
            },
            onClear: () {
              setState(() => _numpadBuffer = '');
            },
            onOk: () {
              final qty = int.tryParse(_numpadBuffer);
              if (qty != null && qty > 0 && _selectedCartItemId != null) {
                cartNotifier.updateQty(_selectedCartItemId!, qty);
              }
              setState(() => _numpadBuffer = '');
            },
            onDiscount: () {
              if (_selectedCartItemId != null) {
                _showDiscountDialog(_selectedCartItemId!, cartNotifier);
              }
            },
            onCustomer: () {
              showDialog(
                context: context,
                builder: (_) => AlertDialog(
                  title: const Text('Select Customer'),
                  content: CustomerSelector(
                    selectedCustomer: _selectedCustomer,
                    onCustomerSelected: (c) {
                      setState(() => _selectedCustomer = c);
                      Navigator.of(context).pop();
                    },
                  ),
                ),
              );
            },
            onClearCart: cart.isEmpty
                ? null
                : () {
                    cartNotifier.clear();
                    setState(() {
                      _selectedCustomer = null;
                      _selectedCartItemId = null;
                      _numpadBuffer = '';
                    });
                  },
            onPay: cart.isEmpty
                ? null
                : () => _showPaymentPanel(
                    cartNotifier.roundedTotal,
                    session.session,
                    auth,
                  ),
            numpadBuffer: _numpadBuffer,
          ),
          const SizedBox(height: 8),
          // Bottom action bar
          SizedBox(
            width: double.infinity,
            height: 44,
            child: ElevatedButton.icon(
              onPressed: cart.isEmpty
                  ? null
                  : () => _showPaymentPanel(
                      cartNotifier.roundedTotal,
                      session.session,
                      auth,
                    ),
              icon: const Icon(Icons.receipt_long, size: 18),
              label: const Text('Submit & Pay'),
              style: ElevatedButton.styleFrom(
                backgroundColor: AppTheme.successColor,
                foregroundColor: Colors.white,
                shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(8),
                ),
              ),
            ),
          ),
        ],
      ),
    );

    final menuPanel = Column(
      children: [
        if (!isOnline)
          Container(
            margin: const EdgeInsets.fromLTRB(12, 12, 12, 0),
            width: double.infinity,
            padding: const EdgeInsets.all(10),
            decoration: BoxDecoration(
              color: AppTheme.offlineBannerColor,
              borderRadius: BorderRadius.circular(10),
            ),
            child: const Row(
              children: [
                Icon(Icons.wifi_off, size: 16, color: Colors.orange),
                SizedBox(width: 8),
                Expanded(
                  child: Text(
                    'Offline mode: sales are saved locally and synced later',
                    style: TextStyle(fontSize: 12, color: Colors.orange),
                  ),
                ),
              ],
            ),
          ),
        Padding(
          padding: const EdgeInsets.all(12),
          child: Row(
            children: [
              Expanded(
                child: TextField(
                  controller: _searchController,
                  decoration: InputDecoration(
                    hintText: 'Search items...',
                    prefixIcon: const Icon(Icons.search),
                    isDense: true,
                    fillColor: Colors.white,
                    filled: true,
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
            ],
          ),
        ),
        SizedBox(
          height: 42,
          child: ListView(
            scrollDirection: Axis.horizontal,
            padding: const EdgeInsets.symmetric(horizontal: 12),
            children: _itemGroups.map((group) {
              final selected = _selectedGroup == group;
              return Padding(
                padding: const EdgeInsets.only(right: 8),
                child: ChoiceChip(
                  label: Text(group),
                  selected: selected,
                  onSelected: (_) => _onGroupSelected(group),
                ),
              );
            }).toList(),
          ),
        ),

        Expanded(
          child: _loadingItems
              ? const Center(child: CircularProgressIndicator())
              : _filteredItems.isEmpty
              ? const Center(child: Text('No items found'))
              : GridView.builder(
                  padding: const EdgeInsets.fromLTRB(12, 0, 12, 12),
                  gridDelegate: const SliverGridDelegateWithMaxCrossAxisExtent(
                    maxCrossAxisExtent: 150,
                    childAspectRatio: 1.10,
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
    );

    return Scaffold(
      appBar: AppBar(
        leading: IconButton(
          icon: const Icon(Icons.menu),
          onPressed: widget.onOpenDrawer,
        ),
        title: Text(session.session?['pos_profile_name'] ?? 'POS Billing'),
        actions: [
          if (cart.isNotEmpty)
            Badge(
              label: Text('${cart.length}'),
              child: const Icon(Icons.shopping_cart),
            ),
          const SizedBox(width: 12),
        ],
      ),
      body: Container(
        color: contentBg,
        child: LayoutBuilder(
          builder: (context, constraints) {
            final compact = constraints.maxWidth < 900;
            if (compact) {
              return Column(
                children: [
                  Expanded(flex: 5, child: menuPanel),
                  Divider(height: 1, color: Colors.grey.shade300),
                  Expanded(flex: 6, child: orderPanel),
                ],
              );
            }

            return Row(
              children: [
                Expanded(child: orderPanel),
                VerticalDivider(width: 1, color: Colors.grey.shade300),
                Expanded(child: menuPanel),
              ],
            );
          },
        ),
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

  void _showDiscountDialog(int itemId, CartNotifier notifier) {
    final controller = TextEditingController();
    showDialog(
      context: context,
      builder: (_) => AlertDialog(
        title: const Text('Set Discount %'),
        content: TextField(
          controller: controller,
          keyboardType: TextInputType.number,
          decoration: const InputDecoration(hintText: 'e.g. 10'),
          autofocus: true,
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(context).pop(),
            child: const Text('Cancel'),
          ),
          ElevatedButton(
            onPressed: () {
              final val = double.tryParse(controller.text);
              if (val != null) notifier.updateDiscount(itemId, val);
              Navigator.of(context).pop();
            },
            child: const Text('Apply'),
          ),
        ],
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
      color: Colors.white,
      elevation: 1,
      margin: EdgeInsets.zero,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
      child: InkWell(
        onTap: onTap,
        child: Padding(
          padding: const EdgeInsets.all(6),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                item['item_name'] ?? '',
                style: const TextStyle(
                  fontWeight: FontWeight.w600,
                  fontSize: 12,
                ),
                maxLines: 3,
                overflow: TextOverflow.ellipsis,
              ),
              const SizedBox(height: 6),
              const Spacer(),
              Row(
                children: [
                  Text(
                    '\u20B9${(item['rate'] ?? 0).toStringAsFixed(0)}',
                    style: TextStyle(
                      fontWeight: FontWeight.bold,
                      fontSize: 14,
                      color: AppTheme.successColor,
                    ),
                  ),
                  const Spacer(),
                  SizedBox(
                    width: 26,
                    height: 26,
                    child: Material(
                      color: AppTheme.successColor,
                      borderRadius: BorderRadius.circular(6),
                      child: InkWell(
                        borderRadius: BorderRadius.circular(6),
                        onTap: onTap,
                        child: const Icon(
                          Icons.add,
                          color: Colors.white,
                          size: 16,
                        ),
                      ),
                    ),
                  ),
                ],
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
  final bool selected;
  final VoidCallback onTap;
  final ValueChanged<int> onQtyChanged;
  final ValueChanged<double> onDiscountChanged;
  final VoidCallback onRemove;

  const _CartItemTile({
    required this.item,
    this.selected = false,
    required this.onTap,
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
      child: Material(
        color: selected
            ? AppTheme.successColor.withValues(alpha: 0.08)
            : Colors.transparent,
        child: InkWell(
          onTap: onTap,
          child: Padding(
            padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 8),
            child: Row(
              children: [
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        item.itemName,
                        style: const TextStyle(
                          fontSize: 13,
                          fontWeight: FontWeight.w500,
                        ),
                      ),
                      const SizedBox(height: 2),
                      Text(
                        '\u20B9${item.rate.toStringAsFixed(2)} x ${item.qty}'
                        '${item.discountPercent > 0 ? '  -${item.discountPercent.toStringAsFixed(0)}%' : ''}',
                        style: TextStyle(
                          fontSize: 11,
                          color: Colors.grey.shade600,
                        ),
                      ),
                    ],
                  ),
                ),
                IconButton(
                  icon: const Icon(Icons.remove_circle_outline, size: 18),
                  onPressed: () {
                    if (item.qty > 1) onQtyChanged(item.qty - 1);
                  },
                  padding: EdgeInsets.zero,
                  constraints: const BoxConstraints.tightFor(
                    width: 28,
                    height: 28,
                  ),
                ),
                SizedBox(
                  width: 24,
                  child: Text(
                    '${item.qty}',
                    textAlign: TextAlign.center,
                    style: const TextStyle(fontWeight: FontWeight.w600),
                  ),
                ),
                IconButton(
                  icon: const Icon(Icons.add_circle_outline, size: 18),
                  onPressed: () => onQtyChanged(item.qty + 1),
                  padding: EdgeInsets.zero,
                  constraints: const BoxConstraints.tightFor(
                    width: 28,
                    height: 28,
                  ),
                ),
                const SizedBox(width: 4),
                SizedBox(
                  width: 52,
                  child: Text(
                    '\u20B9${item.amount.toStringAsFixed(0)}',
                    textAlign: TextAlign.right,
                    style: const TextStyle(
                      fontWeight: FontWeight.w700,
                      fontSize: 13,
                    ),
                  ),
                ),
              ],
            ),
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
  final Color? color;

  const _TotalRow(this.label, this.value, {this.bold = false, this.color});

  @override
  Widget build(BuildContext context) {
    final style = bold
        ? TextStyle(fontWeight: FontWeight.bold, fontSize: 16, color: color)
        : const TextStyle(fontSize: 13);
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

class _NumpadActionGrid extends StatelessWidget {
  final ValueChanged<String> onDigit;
  final VoidCallback onClear;
  final VoidCallback onOk;
  final VoidCallback onDiscount;
  final VoidCallback onCustomer;
  final VoidCallback? onClearCart;
  final VoidCallback? onPay;
  final String numpadBuffer;

  const _NumpadActionGrid({
    required this.onDigit,
    required this.onClear,
    required this.onOk,
    required this.onDiscount,
    required this.onCustomer,
    required this.onClearCart,
    required this.onPay,
    required this.numpadBuffer,
  });

  @override
  Widget build(BuildContext context) {
    Widget actionBtn(String label, VoidCallback? onTap, {Color? bg}) {
      return SizedBox(
        height: 42,
        child: ElevatedButton(
          onPressed: onTap,
          style: ElevatedButton.styleFrom(
            backgroundColor: bg ?? Colors.grey.shade200,
            foregroundColor: bg != null ? Colors.white : Colors.black87,
            elevation: 0,
            padding: EdgeInsets.zero,
            shape: RoundedRectangleBorder(
              borderRadius: BorderRadius.circular(6),
            ),
          ),
          child: Text(
            label,
            style: const TextStyle(fontSize: 12, fontWeight: FontWeight.w600),
            textAlign: TextAlign.center,
          ),
        ),
      );
    }

    Widget numBtn(String label, {Color? bg, Color? fg}) {
      return SizedBox(
        height: 42,
        child: ElevatedButton(
          onPressed: () {
            if (label == 'CLR') {
              onClear();
            } else if (label == 'OK') {
              onOk();
            } else {
              onDigit(label);
            }
          },
          style: ElevatedButton.styleFrom(
            backgroundColor: bg ?? AppTheme.successColor,
            foregroundColor: fg ?? Colors.white,
            elevation: 0,
            padding: EdgeInsets.zero,
            shape: RoundedRectangleBorder(
              borderRadius: BorderRadius.circular(6),
            ),
          ),
          child: Text(
            label,
            style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w700),
          ),
        ),
      );
    }

    return Column(
      children: [
        if (numpadBuffer.isNotEmpty)
          Padding(
            padding: const EdgeInsets.only(bottom: 4),
            child: Text(
              'Qty: $numpadBuffer',
              style: const TextStyle(fontWeight: FontWeight.w600, fontSize: 13),
            ),
          ),
        Row(
          children: [
            // Action buttons column
            Expanded(
              flex: 3,
              child: Column(
                children: [
                  Row(
                    children: [
                      Expanded(child: actionBtn('Discount', onDiscount)),
                      const SizedBox(width: 4),
                      Expanded(child: actionBtn('Customer', onCustomer)),
                    ],
                  ),
                  const SizedBox(height: 4),
                  Row(
                    children: [
                      Expanded(child: actionBtn('Clear', onClearCart)),
                      const SizedBox(width: 4),
                      Expanded(
                        child: actionBtn(
                          'Pay',
                          onPay,
                          bg: AppTheme.primaryColor,
                        ),
                      ),
                    ],
                  ),
                ],
              ),
            ),
            const SizedBox(width: 6),
            // Numpad
            Expanded(
              flex: 3,
              child: Column(
                children: [
                  for (final row in [
                    ['1', '2', '3'],
                    ['4', '5', '6'],
                    ['7', '8', '9'],
                  ]) ...[
                    Row(
                      children: [
                        Expanded(child: numBtn(row[0])),
                        const SizedBox(width: 4),
                        Expanded(child: numBtn(row[1])),
                        const SizedBox(width: 4),
                        Expanded(child: numBtn(row[2])),
                      ],
                    ),
                    const SizedBox(height: 4),
                  ],
                  Row(
                    children: [
                      Expanded(
                        child: numBtn(
                          'CLR',
                          bg: AppTheme.errorColor,
                          fg: Colors.white,
                        ),
                      ),
                      const SizedBox(width: 4),
                      Expanded(child: numBtn('0')),
                      const SizedBox(width: 4),
                      Expanded(
                        child: numBtn('OK', bg: Colors.blue, fg: Colors.white),
                      ),
                    ],
                  ),
                ],
              ),
            ),
          ],
        ),
      ],
    );
  }
}
