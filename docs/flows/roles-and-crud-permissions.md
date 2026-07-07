# Roles & CRUD Permissions

## Roles Overview

| Role | Location Requirement | Scope |
|------|----------------------|-------|
| **Admin** | None (no branch/warehouse) | Full system access |
| **Purchaser** | Must be assigned to a branch | Procurement & vendor management |
| **Branch Manager** | Must be assigned to a branch | Branch operations & inventory |
| **Warehouse Manager** | Must be assigned to a warehouse | Warehouse operations & stock |

**Legend used in tables below:**
- `A` = Add (Create)
- `C` = Change (Update)
- `D` = Delete
- `V` = View
- `—` = No access
- *(own)* = Scoped to user's own branch/warehouse only
- *(self)* = Only their own record

---

## 1. Users & Auth

### User

| Action | Admin | Purchaser | Branch Manager | Warehouse Manager |
|--------|-------|-----------|----------------|-------------------|
| Add | ✅ | — | — | — |
| Change | ✅ | — | — | — |
| Delete | ✅ | — | — | — |
| View | ✅ all | — | ✅ *(self only)* | — |

**Rules:**
- Non-admin users can only see themselves in the user list; all fields are read-only.
- Creating a user assigns them to a group (role). The group determines `is_staff=True` for admin panel access.
- Validation enforces location requirements: Branch Manager/Purchaser → branch, Warehouse Manager → warehouse, Admin → neither.

### Group

| Action | Admin | Purchaser | Branch Manager | Warehouse Manager |
|--------|-------|-----------|----------------|-------------------|
| Change | ✅ | — | — | — |
| Delete | ✅ | — | — | — |
| View | ✅ | — | — | — |

---

## 2. Locations

### Branch

| Action | Admin | Purchaser | Branch Manager | Warehouse Manager |
|--------|-------|-----------|----------------|-------------------|
| Add | ✅ | — | — | — |
| Change | ✅ | — | ✅ *(own)* | — |
| Delete | ✅ | — | — | — |
| View | ✅ | — | ✅ *(own)* | — |

**Rules:**
- `branch_code` (primary key) is read-only once set.
- Branch Managers can only edit their own branch record.

### Warehouse

| Action | Admin | Purchaser | Branch Manager | Warehouse Manager |
|--------|-------|-----------|----------------|-------------------|
| Add | ✅ | — | — | — |
| Change | ✅ | — | — | ✅ *(own)* |
| Delete | ✅ | — | — | — |
| View | ✅ | — | — | ✅ *(own)* |

**Rules:**
- Warehouse Managers can only view and edit their assigned warehouse.

---

## 3. Inventory

### Inventory Item

| Action | Admin | Purchaser | Branch Manager | Warehouse Manager |
|--------|-------|-----------|----------------|-------------------|
| Add | ✅ | — | — | — |
| Change | ✅ | — | — | — |
| Delete | ✅ | — | — | — |
| View | ✅ | — | ✅ *(items in own branch)* | ✅ *(items in own warehouse)* |

**Rules:**
- Global item catalog; only Admin can create/modify items.
- Location managers can view items that exist in their branch or warehouse inventory.

### Inventory Category

| Action | Admin | Purchaser | Branch Manager | Warehouse Manager |
|--------|-------|-----------|----------------|-------------------|
| Change | ✅ | — | — | — |
| Delete | ✅ | — | — | — |
| View | ✅ | — | — | — |

### Unit of Measure

| Action | Admin | Purchaser | Branch Manager | Warehouse Manager |
|--------|-------|-----------|----------------|-------------------|
| Add | ✅ | — | — | — |
| Change | ✅ | — | — | — |
| Delete | ✅ | — | — | — |

### Branch Inventory

| Action | Admin | Purchaser | Branch Manager | Warehouse Manager |
|--------|-------|-----------|----------------|-------------------|
| Add | ✅ | — | ✅ *(own branch)* | — |
| Change | ✅ | — | ✅ *(own branch)* | — |
| Delete | ✅ | — | — | — |
| View | ✅ | — | ✅ *(own branch)* | — |

**Rules:**
- Branch Managers can update quantity/reorder thresholds for their branch.
- Deletion restricted to Admin (prevents accidental stock record removal).

### Warehouse Inventory

| Action | Admin | Purchaser | Branch Manager | Warehouse Manager |
|--------|-------|-----------|----------------|-------------------|
| Add | ✅ | — | — | ✅ *(own warehouse)* |
| Change | ✅ | — | — | ✅ *(own warehouse)* |
| Delete | ✅ | — | — | — |
| View | ✅ | — | — | ✅ *(own warehouse)* |

**Rules:**
- Barcode scanning supported for quick item lookup.
- Deletion restricted to Admin.

### BOM (Bill of Materials)

| Action | Admin | Purchaser | Branch Manager | Warehouse Manager |
|--------|-------|-----------|----------------|-------------------|
| Add | ✅ | — | ✅ *(branch items)* | ✅ *(warehouse items)* |
| Change | ✅ | — | ✅ *(branch items)* | ✅ *(warehouse items)* |
| Delete | ✅ | — | — | — |
| View | ✅ | — | ✅ *(branch items)* | ✅ *(warehouse items)* |

### Stock Cycle Count

| Action | Admin | Purchaser | Branch Manager | Warehouse Manager |
|--------|-------|-----------|----------------|-------------------|
| Add | ✅ | — | ✅ *(own branch)* | ✅ *(own warehouse)* |
| Change | ✅ | — | ✅ *(own branch)* | ✅ *(own warehouse)* |
| Delete | ✅ | — | — | — |
| View | ✅ | — | ✅ *(own branch)* | ✅ *(own warehouse)* |

**Rules:**
- Custom form: user selects items from their location and enters counted quantities.
- Scheduled automatically daily at 06:00 via Celery Beat.

### Stock Adjustment

| Action | Admin | Purchaser | Branch Manager | Warehouse Manager |
|--------|-------|-----------|----------------|-------------------|
| Add | ✅ | — | ✅ *(own branch)* | ✅ *(own warehouse)* |
| Change | ✅ | — | ✅ *(own branch)* | ✅ *(own warehouse)* |
| Delete | ✅ | — | — | — |
| View | ✅ | — | ✅ *(own branch)* | ✅ *(own warehouse)* |

**Rules:**
- Requires adjustment type: `INCREASE`, `DECREASE`, or `CORRECTION`.
- Reason field is required.

---

## 4. Products

### Product

| Action | Admin | Purchaser | Branch Manager | Warehouse Manager |
|--------|-------|-----------|----------------|-------------------|
| Add | ✅ | — | — | — |
| Change | ✅ | — | — | — |
| Delete | ✅ | — | — | — |
| View | ✅ | — | — | — |

**Rules:**
- Product catalog is Admin-managed only.
- Products are used as the base for BOMs and sales transactions.

---

## 5. Demands

### Demand

| Action | Admin | Purchaser | Branch Manager | Warehouse Manager |
|--------|-------|-----------|----------------|-------------------|
| Add | ✅ | ✅ | ✅ *(own branch)* | — |
| Change | ✅ | ✅ all statuses | ✅ *(own + SUBMITTED only)* | — |
| Delete | ✅ | — | ✅ *(own + PENDING only)* | — |
| View | ✅ | ✅ all | ✅ *(own branch)* | — |

**Demand Status Workflow:**
```
PENDING → SUBMITTED → APPROVED
                    ↘ REJECTED
```

**Rules:**
- **Branch Manager** creates demands and submits them for approval.
- **Purchaser** reviews submitted demands, can adjust per-item quantities, then approves or rejects.
- Branch Managers can only edit PENDING (unsubmitted) demands — once submitted, it goes to the Purchaser.
- Branch Managers can only delete their own PENDING demands.
- Approved demands can be converted into Purchase Orders by the Purchaser.

### Demand Item (inline on Demand)

Managed inline within the Demand form. Permissions follow the parent Demand record.

---

## 6. Purchases

### Vendor

| Action | Admin | Purchaser | Branch Manager | Warehouse Manager |
|--------|-------|-----------|----------------|-------------------|
| Add | ✅ | ✅ | — | — |
| Change | ✅ | ✅ | — | — |
| Delete | ✅ | — | — | — |
| View | ✅ | ✅ | — | — |

### Purchase Order

| Action | Admin | Purchaser | Branch Manager | Warehouse Manager |
|--------|-------|-----------|----------------|-------------------|
| Add | ✅ | ✅ | — | — |
| Change | ✅ | ✅ | — | — |
| Delete | ✅ | — | — | — |
| View | ✅ | ✅ | — | — |

**Rules:**
- Purchase Orders can be auto-generated from an approved Demand.
- Purchasers cannot delete POs (Admin only).

### Goods Receipt

| Action | Admin | Purchaser | Branch Manager | Warehouse Manager |
|--------|-------|-----------|----------------|-------------------|
| Add | ✅ | — | ✅ *(own branch)* | — |
| Change | ✅ | — | ✅ *(own branch)* | — |
| Delete | ✅ | — | — | — |
| View | ✅ | — | ✅ *(own branch)* | — |

**Rules:**
- Branch Managers record stock received against a Purchase Order.
- At least one receipt image (PurchaseReceiptImage or ReceivedItemImage) is required before marking status as `COMPLETED` or `PARTIAL`.
- Barcode scanning available for item receipt.

### Purchase Receipt Image

| Action | Admin | Purchaser | Branch Manager | Warehouse Manager |
|--------|-------|-----------|----------------|-------------------|
| Add | ✅ | ✅ | — | — |
| Change | ✅ | ✅ | — | — |
| Delete | ✅ | — | — | — |
| View | ✅ | ✅ | — | — |

### Received Item Image

| Action | Admin | Purchaser | Branch Manager | Warehouse Manager |
|--------|-------|-----------|----------------|-------------------|
| Add | ✅ | — | ✅ *(own receipt)* | — |
| Change | ✅ | — | ✅ *(own receipt)* | — |
| Delete | ✅ | — | — | — |
| View | ✅ | — | ✅ *(own receipt)* | — |

**Rules:**
- Images are uploaded to Cloudinary via `MediaCloudinaryStorage`.

### Notification

| Action | Admin | Purchaser | Branch Manager | Warehouse Manager |
|--------|-------|-----------|----------------|-------------------|
| Add | ✅ | — | — | — |
| Change | ✅ | — | — | — |
| Delete | ✅ | — | — | — |
| View | ✅ | ✅ *(own)* | ✅ *(own)* | ✅ *(own)* |

**Rules:**
- Notifications are system-generated; only Admin can create them manually.
- All roles can view their own notifications (visible in top menu bar).

---

## 7. Transfers

### Transfer

| Action | Admin | Purchaser | Branch Manager | Warehouse Manager |
|--------|-------|-----------|----------------|-------------------|
| Add | ✅ | — | ✅ *(own branch)* | ✅ *(own warehouse)* |
| Change | ✅ | — | ✅ *(own + PENDING/APPROVED)* | ✅ *(own + PENDING/APPROVED)* |
| Delete | ✅ | — | ✅ *(own + PENDING only)* | ✅ *(own + PENDING only)* |
| View | ✅ | — | ✅ *(involving own branch)* | ✅ *(involving own warehouse)* |

**Transfer Types:**
- Branch → Branch
- Branch → Warehouse
- Warehouse → Branch
- Warehouse → Warehouse

**Transfer Status Workflow:**
```
PENDING → APPROVED → DISPATCHED → RECEIVED
                   ↘ CANCELLED
```

**Rules:**
- Users see transfers where they are the `from_*` OR `to_*` location.
- Edits are only allowed while status is `PENDING` or `APPROVED`.
- Deletion only allowed on `PENDING` transfers.
- **Dispatch**: Stock deducted from source — barcode-assisted quantity confirmation.
- **Receive**: Stock added to destination — variance (received vs dispatched) is tracked.
- Batch admin actions available: Approve, Dispatch, Receive, Cancel.

### Transfer Item (inline on Transfer)

Managed inline within the Transfer form. Permissions follow the parent Transfer record.

---

## 8. Warehouse Requests

### Warehouse Request

| Action | Admin | Purchaser | Branch Manager | Warehouse Manager |
|--------|-------|-----------|----------------|-------------------|
| Add | ✅ | — | ✅ | ✅ |
| Change | ✅ | — | ✅ *(PENDING only)* | ✅ all |
| Delete | ✅ | — | ✅ | ✅ |
| View | ✅ | — | ✅ *(own branch)* | ✅ all |

**Rules:**
- Branch Managers create requests to pull stock from a warehouse.
- Warehouse Managers approve or reject requests.
- Branch Managers can only edit their own PENDING requests (once submitted to Warehouse Manager, read-only).

### Warehouse Transaction

| Action | Admin | Purchaser | Branch Manager | Warehouse Manager |
|--------|-------|-----------|----------------|-------------------|
| Add | ✅ | — | — | ✅ *(own warehouse)* |
| Change | ✅ | — | — | — |
| Delete | ✅ | — | — | — |
| View | ✅ | — | — | ✅ *(own warehouse)* |

**Rules:**
- Transactions are append-only for Warehouse Managers (no editing after creation).
- Represents physical stock movements in/out of the warehouse.

---

## 9. Sales

### Sales Transaction

| Action | Admin | Purchaser | Branch Manager | Warehouse Manager |
|--------|-------|-----------|----------------|-------------------|
| Add | ✅ | — | — | — |
| Change | ✅ | — | — | — |
| Delete | ✅ | — | — | — |
| View | ✅ | — | — | — |

### Inventory Consumption

| Action | Admin | Purchaser | Branch Manager | Warehouse Manager |
|--------|-------|-----------|----------------|-------------------|
| Add | ✅ | — | — | — |
| Change | ✅ | — | — | — |
| Delete | ✅ | — | — | — |
| View | ✅ | — | — | — |

**Rules:**
- Sales data is imported automatically via Gmail/Celery task (every 5 minutes).
- `unit_price` and `total_amount` are read-only (system-computed).
- Admin-only access; no manual entry by other roles.

---

## 10. Payments

### Vendor Invoice

| Action | Admin | Purchaser | Branch Manager | Warehouse Manager |
|--------|-------|-----------|----------------|-------------------|
| Add | ✅ | ✅ | — | — |
| Change | ✅ | ✅ | — | — |
| Delete | ✅ | — | — | — |
| View | ✅ | ✅ | — | — |

**Rules:**
- Invoice status auto-updates: `UNPAID` → `PARTIAL` → `PAID` based on total payments recorded.

### Payment

| Action | Admin | Purchaser | Branch Manager | Warehouse Manager |
|--------|-------|-----------|----------------|-------------------|
| Add | ✅ | ✅ | — | — |
| Change | ✅ | ✅ | — | — |
| Delete | ✅ | — | — | — |
| View | ✅ | ✅ | — | — |

**Rules:**
- `recorded_by` is auto-populated on creation.
- Purchasers cannot delete payments (Admin only).

### Payment Document

| Action | Admin | Purchaser | Branch Manager | Warehouse Manager |
|--------|-------|-----------|----------------|-------------------|
| Add | ✅ | ✅ | — | — |
| Change | ✅ | ✅ | — | — |
| Delete | ✅ | — | — | — |
| View | ✅ | ✅ | — | — |

**Document Types:** Cheque, Receipt, Proof of Payment

**Rules:**
- Files are uploaded to Cloudinary via `MediaCloudinaryStorage`.
- Purchasers cannot delete documents (Admin only).

---

## 11. Reports

### Audit Log

| Action | Admin | Purchaser | Branch Manager | Warehouse Manager |
|--------|-------|-----------|----------------|-------------------|
| Delete | ✅ | — | — | — |
| View | ✅ | — | — | — |

**Rules:**
- System-generated by middleware; no manual add/change.
- Admin can delete stale log entries.

### Custom Reports

| Report | Admin | Purchaser | Branch Manager | Warehouse Manager |
|--------|-------|-----------|----------------|-------------------|
| Sales vs Consumption | ✅ | — | — | — |
| Item Usage | ✅ | — | — | — |
| Demand vs Received | ✅ | ✅ all | ✅ *(own branch)* | — |
| Warehouse Stock | ✅ | — | — | ✅ *(own warehouse)* |
| Branch Inventory | ✅ | — | ✅ *(own branch)* | — |

**Rules:**
- All reports support date-range filtering (default: last 30 days).
- CSV export available for all reports.
- Location manager reports are auto-filtered to their assigned location.

---

## Quick Reference Summary

| Model | Admin | Purchaser | Branch Mgr | Warehouse Mgr |
|-------|:-----:|:---------:|:----------:|:-------------:|
| User | ACDV | — | V(self) | — |
| Group | CDV | — | — | — |
| Branch | ACDV | — | CV(own) | — |
| Warehouse | ACDV | — | — | CV(own) |
| InventoryItem | ACDV | — | V | V |
| InventoryCategory | CDV | — | — | — |
| UnitOfMeasure | ACDV | — | — | — |
| BranchInventory | ACDV | — | ACV(own) | — |
| WarehouseInventory | ACDV | — | — | ACV(own) |
| BOM | ACDV | — | ACV(own) | ACV(own) |
| StockCycleCount | ACDV | — | ACV(own) | ACV(own) |
| StockAdjustment | ACDV | — | ACV(own) | ACV(own) |
| Product | ACDV | — | — | — |
| Demand | ACDV | ACV | ACV(own) | — |
| Vendor | ACDV | ACV | — | — |
| PurchaseOrder | ACDV | ACV | — | — |
| GoodsReceipt | ACDV | — | ACV(own) | — |
| PurchaseReceiptImage | ACDV | ACV | — | — |
| ReceivedItemImage | ACDV | — | ACV(own) | — |
| Notification | ACDV | V(own) | V(own) | V(own) |
| Transfer | ACDV | — | ACV(own) | ACV(own) |
| WarehouseRequest | ACDV | — | ACV(own) | ACDV |
| WarehouseTransaction | ACDV | — | — | AV(own) |
| SalesTransaction | ACDV | — | — | — |
| InventoryConsumption | ACDV | — | — | — |
| VendorInvoice | ACDV | ACV | — | — |
| Payment | ACDV | ACV | — | — |
| PaymentDocument | ACDV | ACV | — | — |
| AuditLog | DV | — | — | — |
