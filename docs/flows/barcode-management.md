# Flow: Barcode-Based Inventory Management (2.3)

## Overview

Every `InventoryItem` has a `barcode` field (unique, optional) and a `sku` field.
Barcodes are used to look up items quickly in both the admin UI (via scanner input)
and via a REST API (for mobile / PWA use).

---

## Barcode Assignment

### Admin

1. Navigate to **Inventory → Inventory Items**.
2. Select an item → **Edit**.
3. Enter the barcode value in the **Barcode** field.
   - The form validates uniqueness (no two items can share a barcode).
4. Save.

Items without barcodes can still be searched by SKU in the barcode scanner input.

---

## Barcode Printing

### Admin

1. Navigate to **Inventory → Inventory Items**.
2. Select one or more items using the checkboxes.
3. From the **Action** dropdown, choose **"Print barcode labels for selected items"**.
4. Click **Go** → a printable label page opens.
5. Click **Print** → labels are printed using the browser's print dialog.

Label format:
- Item name (bold)
- SKU (if set)
- Barcode rendered using the **Libre Barcode 128 Text** font (visual barcode)
- Barcode number in plain text below
- Unit of measure

Items without a barcode fall back to rendering the SKU as the barcode value.
Items without either are shown with a "No barcode assigned" placeholder.

---

## Barcode Scanning in Admin UI

Available on both:
- **Stock Cycle Count** — create-from-inventory view
- **Stock Adjustment** — create-from-inventory view

### How to scan

1. Open the custom inventory form (cycle count or stock adjustment).
2. A **barcode scanner input** appears at the top of the page (blue card, barcode icon).
3. Click into the input field (or focus it automatically).
4. Scan the item's barcode with a physical barcode scanner.
   - The scanner types the value and presses Enter automatically.
5. The system:
   - Expands the item's section/subcategory if collapsed.
   - Scrolls to the item row.
   - Highlights it with a yellow border (3 seconds).
   - Focuses the quantity input for immediate entry.
6. Status indicator:
   - **"Found"** (green border flash) — item was located.
   - **"Not found: {code}"** (red border) — no item matched that barcode or SKU.

Scanning by **SKU** also works as a fallback.

---

## Barcode Lookup REST API

**Endpoint:** `GET /api/v1/items/barcode/<barcode>/`

**Authentication:** Required (Session or Token)

**Response by role:**

### Admin
```json
{
  "id": 42,
  "name": "Chicken Breast",
  "barcode": "5012345678900",
  "sku": "CHK-001",
  "unit": "kg",
  "section": "Proteins",
  "category": "Poultry",
  "stock": [
    { "branch__branch_code": "BR01", "branch__name": "Main Branch", "quantity": "12.50", "minimum_threshold": "5.00" },
    { "branch__branch_code": "BR02", "branch__name": "North Branch", "quantity": "8.00", "minimum_threshold": "3.00" }
  ]
}
```

### Branch Manager (scoped to their branch)
```json
{
  "id": 42,
  "name": "Chicken Breast",
  "barcode": "5012345678900",
  "sku": "CHK-001",
  "unit": "kg",
  "section": "Proteins",
  "category": "Poultry",
  "stock": {
    "branch_code": "BR01",
    "quantity": "12.50",
    "minimum_threshold": "5.00"
  }
}
```

### Warehouse Manager (scoped to their warehouse)
```json
{
  "id": 42,
  "name": "Chicken Breast",
  "barcode": "5012345678900",
  "sku": "CHK-001",
  "unit": "kg",
  "section": "Proteins",
  "category": "Poultry",
  "stock": {
    "warehouse_id": 1,
    "quantity": "50.00",
    "location": "Aisle 3, Shelf B"
  }
}
```

### Purchaser (item details only, no stock)
```json
{
  "id": 42,
  "name": "Chicken Breast",
  "barcode": "5012345678900",
  "sku": "CHK-001",
  "unit": "kg",
  "section": "Proteins",
  "category": "Poultry",
  "stock": null
}
```

**404 response (barcode not found):**
```json
{ "detail": "No item found for barcode '5012345678900'." }
```

---

## Admin Barcode Scan Redirect (Admin-only utility)

**URL:** `/admin/inventory/inventoryitem/barcode-lookup/?barcode=<value>`

Returns JSON:
```json
{ "found": true, "redirect": "/admin/inventory/inventoryitem/42/change/", "name": "Chicken Breast" }
```
or
```json
{ "found": false, "error": "No item found for barcode: 5012345678900" }
```

This can be used by admin-side JavaScript to build a quick-scan → edit workflow.

---

## Snapshot API (Offline Support)

`GET /api/v1/snapshot/` now includes `barcode` in each inventory item object:

```json
{
  "inventory_items": [
    {
      "id": 42,
      "name": "Chicken Breast",
      "barcode": "5012345678900",
      "sku": "CHK-001",
      "category": "Proteins",
      "sub_category": "Poultry",
      "unit": "kg"
    }
  ]
}
```

This allows the PWA/offline client to perform barcode lookups against locally cached data
without a network request.

---

## Workflow: Goods Receipt Receiving (planned)

> Not yet implemented — barcode scan to fill GoodsReceiptItem quantities.

When implemented:
1. Branch Manager opens a `GoodsReceipt` linked to an approved Demand.
2. Scans each received item's barcode.
3. System matches the scanned barcode to a `GoodsReceiptItem` line.
4. Quantity input is focused; manager enters received quantity.
5. On save, `BranchInventory.quantity` is incremented by `received_quantity`.

---

## Workflow: Transfer Dispatch & Receipt (planned)

> Not yet implemented — barcode scan to confirm transfer quantities.

When implemented:
1. Dispatcher opens an approved `Transfer`.
2. Scans each item's barcode to confirm it is in the dispatch.
3. On dispatch: `BranchInventory` or `WarehouseInventory` is decremented.
4. Recipient scans each barcode to confirm receipt.
5. On receipt: destination inventory is incremented; variance is recorded.
