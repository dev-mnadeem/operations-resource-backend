# Test Guide: Features 2.4, 2.6, 2.7, 2.8

> Admin panel: http://localhost:8000/admin

## Setup (one-time)

```bash
make run          # start dev server
make superuser    # create admin user
make seed-data    # seed branches, items, warehouses
```

Create test users in **Auth → Users**:
- `branch_mgr` → assign to "Branch Manager" group + a Branch
- `purchaser1` → assign to "Purchaser" group
- `wh_mgr` → assign to "Warehouse Manager" group + a Warehouse

---

## 2.4 Demand Management

### Create a demand (Branch Manager)

1. Log in as `branch_mgr`.
2. Navigate to **Demands → Demands → + Add demand**.
3. Select branch (or pre-filled if user has a branch assigned).
4. Enter quantities for ≥1 items. Click **Save Demands**.
5. **Expected:** Demand created with status `submitted`.
6. **Expected:** Notifications created for all Purchasers, Warehouse Managers, and Admins (check **Purchases → Notifications**).

### Partial approval (Purchaser)

1. Log in as `purchaser1`.
2. Navigate to **Demands → Demands**. Click **View list** on a submitted demand.
3. In the approve form, change the **Approved Qty** for one or more items to a lower value.
4. Click **Approve**.
5. **Expected:** Demand status → `approved`. `DemandItem.approved_quantity` set to the entered values.
6. **Expected:** Branch Manager receives a notification. Admin receives a notification.

### Bulk approve/reject (Purchaser)

1. Navigate to **Demands → Demands**.
2. Select multiple submitted demands. Choose **Approve selected demands** → **Go**.
3. **Expected:** All become `approved`. Each fires the notification signal (check Notifications).

### Reject with reason (Purchaser)

1. Click **View list** on a submitted demand.
2. Enter a rejection reason in the text box. Click **Reject**.
3. **Expected:** Status → `rejected`. Rejection reason saved. Branch Manager notified.

---

## 2.6 Receiving & Verification

### Create a GoodsReceipt and use barcode receive view (Branch Manager)

1. Log in as `branch_mgr`.
2. Navigate to **Purchases → Goods receipts → + Add**.
3. Link it to an approved demand for your branch. Add line items with expected quantities. Save.
4. Back on the changelist, click the **Receive** button (barcode icon) for the new receipt.
5. Scan a barcode (or type a barcode/SKU into the scanner input and press Enter).
   - **Expected:** Row highlights; received quantity input is focused.
6. Enter received quantities. Click **Save Received Quantities**.
7. **Expected:** Receipt status → `partial` or `completed`. `BranchInventory.quantity` incremented.

### Discrepancy notification

1. In the receive view, enter a received quantity **less than** the expected quantity for at least one item.
2. Save.
3. Log in as Admin or Purchaser. Check **Purchases → Notifications**.
4. **Expected:** A notification of type `receipt_discrepancy` with the shortage/surplus detail.

### Mandatory image warning

1. Set a GoodsReceipt status to `completed` in the standard change form (no images attached).
2. Click Save.
3. **Expected:** A warning message is shown: *"Cannot mark as completed/partial without attaching at least one receipt image or item image."*
   (Note: this is a warning, not a hard block — the save still proceeds. Hard-block is a pending TODO.)

---

## 2.7 Warehouse Inventory Management

### Auto-create warehouse inventory

1. Log in as Admin.
2. Navigate to **Warehouse → Warehouses → + Add**.
3. Create a new warehouse. Save.
4. Navigate to **Warehouse → Warehouse inventories**.
5. **Expected:** One `WarehouseInventory` record (qty=0) exists for every `InventoryItem`.

### Minimum threshold and low-stock filter

1. Navigate to **Warehouse → Warehouse inventories**.
2. Edit a warehouse inventory record. Set `minimum_threshold` > current `quantity`. Save.
3. Apply the **Stock level: Below minimum** filter.
4. **Expected:** Only records where `quantity < minimum_threshold` are shown.

### WarehouseRequest approval updates BranchInventory

1. Log in as `branch_mgr`. Navigate to **Warehouse → Warehouse requests → + Add**.
2. Select a warehouse and add items with quantities. Save.
3. Log in as `wh_mgr`. Navigate to **Warehouse → Warehouse requests**.
4. Select the pending request → **Approve selected warehouse requests** → **Go**.
5. **Expected:**
   - `WarehouseRequest.status` → `approved`.
   - `WarehouseInventory.quantity` decremented for each item (via OUTWARD transaction signal).
   - `BranchInventory.quantity` incremented for each item at the requesting branch.
6. Verify: **Inventory → Branch inventories** — check quantities increased.
7. Verify: **Warehouse → Warehouse transactions** — OUTWARD entries exist.

### Low-stock notification for WarehouseRequest rejection

1. As `wh_mgr`, reject a pending request via **Reject selected warehouse requests**.
2. Log in as `branch_mgr`. Check **Purchases → Notifications**.
3. **Expected:** A `warehouse_request_rejected` notification.

---

## 2.8 Inter-Branch & Warehouse Transfers

### Create a transfer with notes

1. Log in as Admin or Branch Manager.
2. Navigate to **Transfers → Transfers → + Add**.
3. Set `from_branch`, `to_branch`, `transfer_type = branch_to_branch`.
4. Fill in the **Notes** field.
5. Add transfer items with quantities. Save.
6. **Expected:** Transfer created with status `pending`. Notes field visible on detail page.

### Approve → Dispatch (with barcode scanning)

1. Select the pending transfer → **Approve selected transfers** → **Go**.
2. Status → `approved`. The **Dispatch** button appears in the list.
3. Click **Dispatch** button (truck icon).
4. Scan a barcode / enter a SKU in the scanner input → press Enter.
   - **Expected:** Row highlights; dispatched quantity input is focused.
5. Optionally adjust `dispatch qty` (partial dispatch). Click **Confirm Dispatch**.
6. **Expected:**
   - Transfer status → `dispatched`.
   - Source `BranchInventory` or `WarehouseInventory` decremented.
   - Destination Branch Manager or Warehouse Manager receives a `transfer_dispatched` notification.

### Receive (with barcode scanning)

1. The **Receive** button (green, check icon) now appears on the dispatched transfer row.
2. Click **Receive**.
3. Scan item barcodes to find rows. Enter received quantities (may differ from dispatched).
4. Click **Confirm Receipt**.
5. **Expected:**
   - Transfer status → `received`.
   - Destination `BranchInventory` or `WarehouseInventory` incremented by received quantities.
   - `TransferItem.variance` = received − dispatched (recorded for each item).

### Stock availability check (dispatch blocked on shortage)

1. Create a transfer from a branch for more stock than is available.
2. Approve the transfer, then click **Dispatch**.
3. Click **Confirm Dispatch** without adjusting the quantity.
4. **Expected:** Error message listing the shortage; transfer stays `approved`.

### Cancel a transfer

1. Select a pending or approved transfer → **Cancel selected transfers** → **Go**.
2. **Expected:** Status → `cancelled`. No inventory changes.

---

## Notification inbox

All notifications (demand, receipt discrepancy, transfer dispatched, warehouse request) can be reviewed at:

**Admin → Purchases → Notifications**

- Admin sees all notifications.
- Non-admin users see only their own.
