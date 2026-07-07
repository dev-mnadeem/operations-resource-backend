# Flow: Receiving & Verification (2.6)

## Overview

Branch Manager receives goods against an approved demand. Items are scanned via barcode or entered manually. `BranchInventory` is updated on save. Discrepancies trigger notifications to Purchasers and Admins.

---

## Role Flows

### Branch Manager

**Creating a Goods Receipt:**
1. Navigate to **Purchases → Goods receipts → + Add**.
2. Link to an **approved** demand for your branch.
3. Add `GoodsReceiptItem` lines with `expected_quantity` per item.
4. Set receiver (yourself) and `received_at`. Save.

**Barcode-assisted receiving:**
1. On the Goods Receipts list, click the **Receive** button (barcode icon) on a pending/partial receipt.
2. A barcode scanner input is shown at the top.
3. Scan each item's barcode with a physical scanner — the row highlights and the quantity input is focused.
4. Enter the actual received quantity (or accept the pre-filled expected quantity).
5. Click **Save Received Quantities**.

**Status auto-set:**
- All items received at or above expected → `completed`
- Any item below expected → `partial`

**Mandatory images:**
- Before saving as `completed` or `partial`, attach at least one image:
  - `ReceivedItemImage` (per line item, via the **Received item images** section)
  - or `PurchaseReceiptImage` (receipt document, under **Purchases → Purchase receipt images**)
- Without an image, a warning is shown. (Hard-block is a planned enhancement.)

### Purchaser

- View all goods receipts.
- Upload `PurchaseReceiptImage` (receipt documents) via **Purchases → Purchase receipt images**.
- Receive `receipt_discrepancy` notifications when any receipt has non-zero variance.

### Admin

- Full access to all goods receipts.
- Receives discrepancy notifications.

---

## Inventory Update

`BranchInventory.quantity` is updated **on every `GoodsReceiptItem` save** via the `update_inventory_on_receipt_item_save` signal in `purchases/signals.py`.

Delta = `new_received_quantity - old_received_quantity`

This means:
- Initial save: full `received_quantity` is added.
- Edit: only the delta is applied (prevents double-counting).

---

## Discrepancy Notifications

When a `GoodsReceipt` is saved with status `completed` or `partial`, the `notify_on_receipt_discrepancy` signal checks all `GoodsReceiptItem` records for `variance ≠ 0`.

If any exist:
- A `receipt_discrepancy` notification is created for all Purchasers and Admins.
- Message includes per-item surplus/shortage details and condition notes.

---

## Variance Calculation

`GoodsReceiptItem.variance = received_quantity - expected_quantity`

- **Positive** = surplus (more received than expected)
- **Negative** = shortage (less received than expected)
- **Zero** = exact match

Calculated automatically via the `calculate_receipt_variance` pre-save signal.
