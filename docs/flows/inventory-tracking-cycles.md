# Flow: Inventory Tracking Cycles (2.2)

## Overview

Each `BranchInventory` record has a `tracking_frequency` (daily / weekly / monthly).
A Celery Beat task runs every day at 06:00 and auto-creates `StockCycleCount` records
with `status=scheduled` for items whose frequency is due that day.
Branch Managers then perform the physical count and record actuals through the admin.

---

## Automated Scheduling (Celery Beat)

| Frequency | Triggered |
|-----------|-----------|
| Daily     | Every day at 06:00 |
| Weekly    | Every Monday at 06:00 |
| Monthly   | 1st of every month at 06:00 |

Task: `apps.inventory.tasks.schedule_cycle_counts`
Creates `StockCycleCount(status=scheduled)` for each due `BranchInventory`.
Skips items already scheduled for today to prevent duplicates.

---

## Role Flows

### Admin

1. Navigate to **Inventory → Stock Cycle Counts**.
2. See all cycle counts across all branches.
3. Use the **"+ Add stock cycle count"** button → redirected to the custom bulk-create view.
4. Select a branch from the dropdown and click **Load inventory**.
5. The table shows every item for that branch with its current system stock.
6. **Scan a barcode** (scanner input at the top) to instantly jump and highlight any item row.
7. Enter the physically counted quantity in the **Actual counted quantity** column.
8. Click **Save Cycle Counts** → system auto-calculates variance (`counted - system`).
9. `counted_by` is set to the logged-in Admin user.
10. For any completed count with non-zero variance, a **Notification** is created for the Branch Manager and all Admins.
11. Use **Stock Adjustments** to correct inventory if variance needs to be resolved.

### Branch Manager

1. Navigate to **Inventory → Stock Cycle Counts**.
2. Sees only cycle counts for **their branch**.
3. Click **"+ Add stock cycle count"** → custom bulk-create view pre-filtered to their branch (no branch selector shown).
4. The table shows their branch's items with current system stock.
5. **Scan a barcode** (scanner input at the top) to instantly jump and highlight that item row.
6. Enter the physically counted quantity for each item counted.
7. Click **Save Cycle Counts** → variance is auto-calculated, `counted_by` = this manager.
8. If variance is non-zero, the Branch Manager and all Admins receive a Notification.

### Warehouse Manager

- Cannot currently create cycle counts (cycle count admin scopes to branch only).
- Can view `WarehouseTransaction(ADJUSTMENT)` records for warehouse stock corrections.
- Warehouse cycle count support is planned (see TODO).

### Purchaser

- No access to cycle counts.

---

## Stock Adjustments

Adjustments apply a delta to `BranchInventory.quantity` immediately via a `post_save` signal on `StockAdjustment`.

| Type | Effect |
|------|--------|
| Increase | `BranchInventory.quantity += adjustment.quantity` |
| Decrease | `BranchInventory.quantity -= adjustment.quantity` |
| Correction | `BranchInventory.quantity += adjustment.quantity` (net positive correction) |

For warehouse stock, a `WarehouseInventory` delta is applied directly.

### Branch Manager — Stock Adjustment Flow

1. Navigate to **Inventory → Stock Adjustments**.
2. Click **"+ Add stock adjustment"** → custom bulk-create view for their branch.
3. Enter the **Common Reason** (required for all items in this batch).
4. **Scan a barcode** to jump to any item row.
5. For each item, select **Type** (Increase / Decrease / Correction) and enter quantity.
6. Click **Save Adjustments** → each adjustment is created individually, triggering the signal that updates `BranchInventory.quantity`.

---

## Barcode Scanner (Admin UI)

Both the Cycle Count and Stock Adjustment custom views include a barcode scanner input
at the top of the page. When a physical barcode scanner scans an item:

1. The barcode value is typed into the input field and Enter is pressed automatically.
2. JavaScript searches all item rows for a matching `data-barcode` or `data-sku` attribute.
3. The parent section and subcategory are expanded if collapsed.
4. The page scrolls to the item row and highlights it with a yellow border.
5. The quantity input for that item is automatically focused.
6. Status indicator shows "Found" (green) or "Not found" (red).

---

## Variance Notifications

When a `StockCycleCount` is saved with `status=COMPLETED` and `variance != 0`:
- A `Notification` is created for each **Branch Manager** assigned to that branch.
- A `Notification` is created for each **Admin** user.
- Message format: `"Stock variance detected for '{item}' at branch {code}: {surplus/shortage} of {amount} {unit}."`
