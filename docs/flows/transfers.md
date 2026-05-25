# Flow: Inter-Branch & Warehouse Transfers (2.8)

## Overview

Transfers move stock between any two locations: Branch↔Branch, Branch↔Warehouse, Warehouse↔Branch, Warehouse↔Warehouse.

---

## Status Lifecycle

```
pending → approved → dispatched → received
        ↘ cancelled
approved ↘ cancelled
```

---

## Transfer Types

| Type | From | To |
|------|------|----|
| `branch_to_branch` | Branch | Branch |
| `branch_to_warehouse` | Branch | Warehouse |
| `warehouse_to_branch` | Warehouse | Branch |
| `warehouse_to_warehouse` | Warehouse | Warehouse |

---

## Role Flows

### Creating a Transfer (Branch Manager / Warehouse Manager / Admin)

1. Navigate to **Transfers → Transfers → + Add**.
2. Set the **from** location (branch OR warehouse) and **to** location.
3. Set `transfer_type` to match the from/to combination.
4. Enter optional **Notes** for reason/documentation.
5. Add `TransferItem` lines with requested quantities.
6. Save → status = `pending`.

### Approve

1. Select pending transfers → **Approve selected transfers** → **Go**.
2. Status → `approved`. The **Dispatch** button appears in the list.

### Dispatch (with barcode scanning)

1. Click the **Dispatch** button (truck icon) on an approved transfer.
2. **Barcode scanner** input is shown at the top.
   - Scan a barcode → the matching row highlights and the dispatch quantity input is focused.
   - Works with both `barcode` and `sku` values.
3. Adjust dispatch quantities if needed (partial dispatch supported).
4. Click **Confirm Dispatch**.
5. **Effects:**
   - `TransferItem.dispatched_quantity` saved.
   - Transfer status → `dispatched`.
   - Source `BranchInventory` or `WarehouseInventory` decremented by dispatched quantity.
   - Destination Branch Manager or Warehouse Manager notified (`transfer_dispatched`).

### Receive (with barcode scanning)

1. Click the **Receive** button (green check icon) on a dispatched transfer.
2. Scan item barcodes to jump to rows.
3. Enter received quantities (can differ from dispatched — variance is recorded).
4. Click **Confirm Receipt**.
5. **Effects:**
   - `TransferItem.received_quantity` and `variance` saved.
   - Transfer status → `received`.
   - Destination `BranchInventory` or `WarehouseInventory` incremented by received quantity.

### Cancel

- Select pending or approved transfers → **Cancel selected transfers** → **Go**.
- No inventory changes on cancellation.

---

## Inventory Updates

| Event | Inventory change |
|-------|----------------|
| Dispatch | Source location quantity **decremented** |
| Receive | Destination location quantity **incremented** |
| Cancel | No change |

Signal: `update_inventory_on_transfer` in `transfers/signals.py`.

---

## Notifications

| Event | Who is notified |
|-------|----------------|
| Transfer dispatched | Branch Managers at `to_branch`, or Warehouse Managers at `to_warehouse` |

Signal: `_notify_transfer_dispatched` helper in `transfers/signals.py`.

---

## Variance

`TransferItem.variance = received_quantity - dispatched_quantity`

- **Positive** = surplus received
- **Negative** = shortage received
- **Zero** = exact match

Recorded for audit purposes. Future enhancement: trigger notifications on non-zero variance.
