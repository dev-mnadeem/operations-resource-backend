# Flow: Warehouse Inventory Management (2.7)

## Overview

Warehouse Managers control inbound/outbound stock. Branch Managers raise warehouse requests which Warehouse Managers approve. On approval, both `WarehouseInventory` and `BranchInventory` are updated atomically.

---

## Auto-provisioning

### New Warehouse
When a new `Warehouse` is created, a `WarehouseInventory` record (qty=0, threshold=0) is automatically created for every existing `InventoryItem` via the `create_warehouse_inventory_for_new_warehouse` signal.

### New Inventory Item
When a new `InventoryItem` is created, a `WarehouseInventory` record is created for every existing `Warehouse` (mirroring the branch auto-create signal).

---

## Warehouse Inventory

Navigate to **Warehouse → Warehouse inventories**.

| Field | Description |
|-------|-------------|
| `quantity` | Current stock in the warehouse |
| `minimum_threshold` | Triggers low-stock filter when `quantity < minimum_threshold` |
| `location` | Storage location string (e.g., "Aisle 3, Shelf B") |

**Low-stock filter:** Apply **Stock level: Below minimum** to see items that need replenishment.

---

## Warehouse Transactions

Every stock movement creates a `WarehouseTransaction` record:

| Type | When created | Effect |
|------|-------------|--------|
| Inward | Manually by Warehouse Manager | `WarehouseInventory.quantity += quantity` |
| Outward | On WarehouseRequest approval | `WarehouseInventory.quantity -= quantity` |
| Adjustment | Manually by Warehouse Manager | `WarehouseInventory.quantity += quantity` (positive or negative) |

Signal: `update_warehouse_inventory_on_transaction` in `warehouse/signals.py`.

---

## Warehouse Request Workflow

Branch Manager → requests stock from a warehouse.

### Branch Manager
1. Navigate to **Warehouse → Warehouse requests → + Add**.
2. Select the target warehouse. Add items with quantities. Save (status = `pending`).
3. Warehouse Manager at that warehouse receives a `warehouse_request_submitted` notification.

### Warehouse Manager
1. Navigate to **Warehouse → Warehouse requests**.
2. Select one or more pending requests → **Approve selected warehouse requests** → **Go**.
3. On approval:
   - Stock availability is checked per item. If any item is short, an error is shown and that request is skipped.
   - `WarehouseTransaction (OUTWARD)` created per item → `WarehouseInventory.quantity` decremented.
   - `BranchInventory.quantity` incremented for the requesting branch.
   - Requester notified of approval.
4. To reject: select → **Reject selected warehouse requests** → **Go**. Requester notified.

---

## Notifications

| Event | Who is notified |
|-------|----------------|
| Request submitted | Warehouse Managers assigned to that warehouse |
| Request approved | The requesting user |
| Request rejected | The requesting user |

Signal: `notify_on_warehouse_request_status_change` in `warehouse/signals.py`.
