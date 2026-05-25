# Feature Progress & TODO

> Updated: 2026-03-25
> Overall completion: **~97%**

---

## Business Rules (Clarified)

- **Receiver** is not a separate role — receiving is done by Branch Manager (for branch deliveries) or Warehouse Manager (for warehouse inbound). Remove the `Receiver` group.
- **Sales/POS** — the app does NOT handle POS transactions. Sales data is imported from `.xls` sheets downloaded from a connected Gmail account via Celery. Reports compare imported sales data vs actual inventory consumption.
- **Demand workflow** — Branch Manager raises demand → Purchaser approves or rejects → Admin has full privileges. No automated demand creation from thresholds.
- **Demand notifications** — on any demand status change (submitted, approved, rejected), notify ALL relevant members: the submitting Branch Manager, all Purchasers, all Warehouse Managers, and all Admins.
- **Sales & usage reports** — visible to Admin only. No other role can see these reports.

---

## Summary Table

| Feature | Completion | Status |
|---------|-----------|--------|
| 2.1 Inventory & Sales Integration (BOM) | ✅ 100% | BOM + unit conversion complete |
| 2.2 Inventory Tracking Cycles | ✅ 100% | Complete |
| 2.3 Barcode-Based Inventory Management | ✅ 100% | Complete |
| 2.4 Demand Management | ✅ 100% | Complete |
| 2.5 Purchase & Notification Workflow | ✅ 95% | Vendor, PO, notifications all done |
| 2.6 Receiving & Verification | ✅ 100% | Complete |
| 2.7 Warehouse Inventory Management | ✅ 100% | Complete |
| 2.8 Inter-Branch & Warehouse Transfers | ✅ 100% | Complete |
| 2.9 Payments & Financial Documentation | ✅ 100% | Complete |
| 2.10 User Roles & Permissions | ✅ 100% | Complete |
| 2.11 Reporting & Audit Logs | ✅ 100% | All 5 reports + CSV export done |
| 2.12 Offline Mode & Data Sync | ✅ 100% | Complete |

---

## Known Bugs (Fixed)

- [x] ~~**`WAREHOUSE_MANAGER_GROUP_ALIASES` NameError**~~ — Fixed in `apps/warehouse/signals.py`
- [x] ~~**GoodsReceipt does not update BranchInventory**~~ — Handled by signal in `apps/purchases/signals.py`
- [x] ~~**No demand notifications**~~ — `notify_on_demand_status_change` signal fires for all status changes
- [x] ~~**Bulk approve/reject bypassing signals**~~ — Fixed to use individual `.save()` calls
- [x] ~~**dispatch_transfers wrong stock check**~~ — Fixed to use `BranchInventory` queryset
- [x] ~~**LowStockFilter wrong field**~~ — Fixed to use `WarehouseInventory.minimum_threshold` directly
- [x] ~~**WarehouseRequest approval not updating BranchInventory**~~ — Fixed in `approve_requests` action
- [x] ~~**StockAdjustment Warehouse Manager sees nothing**~~ — Fixed `create_from_inventory` to load warehouse items

---

## 2.1 Inventory & Sales Integration (BOM-Based) ✅

**Done:**
- [x] `BOM` and `BOMItem` models linked to `Product`
- [x] Auto-create `BOM` on `Product` save (signal)
- [x] `SalesTransaction` and `InventoryConsumption` models
- [x] `UnitOfMeasure` model with name + abbreviation
- [x] `unit` FK and `conversion_factor` DecimalField on `BOMItem` (migration `inventory/0010`)
- [x] Signal `reduce_inventory_on_sale` applies `conversion_factor`: `base_qty = bom_item.quantity × bom_item.conversion_factor × quantity_sold`
- [x] Celery task to fetch sales `.xls` sheets from Gmail (IMAP) and create `SalesTransaction` records

**No remaining TODOs.**

---

## 2.2 Inventory Tracking Cycles ✅

**Done:**
- [x] `tracking_frequency` field on `BranchInventory` (daily/weekly/monthly)
- [x] `StockCycleCount` and `StockAdjustment` models with full admin flows
- [x] Variance notification signal on cycle count completion
- [x] Celery Beat task `schedule_cycle_counts` — runs at 06:00 daily
- [x] Barcode scanner support in admin create views
- [x] Flow documented in `docs/flows/inventory-tracking-cycles.md`

---

## 2.3 Barcode-Based Inventory Management ✅

**Done:**
- [x] `barcode` (unique) and `sku` fields on `InventoryItem`
- [x] REST API `GET /api/v1/items/barcode/<barcode>/` — role-scoped
- [x] Admin barcode scan utility at `/admin/inventory/inventoryitem/barcode-lookup/`
- [x] Barcode scanner input in Stock Cycle Count and Stock Adjustment create views
- [x] Barcode scanner at Goods Receipt receive view (2.6)
- [x] Barcode scanner at Transfer dispatch and receive views (2.8)
- [x] Barcode printing admin action
- [x] Flow documented in `docs/flows/barcode-management.md`

---

## 2.4 Demand Management ✅

> **Scope:** Manual only. Branch Manager raises demand. Purchaser approves or rejects. Admin has full access.

**Done:**
- [x] `Demand` and `DemandItem` models with full status lifecycle
- [x] Custom admin add-flow showing current stock vs minimum threshold
- [x] `approved_quantity` field on `DemandItem` for partial approval (migration `demands/0008`)
- [x] Per-item approved qty inputs in demand items view
- [x] Bulk `approve_demands`/`reject_demands` use individual `.save()` (signals fire)
- [x] `convert_to_purchase_order` action — creates draft PO from approved demand
- [x] Demand notifications for all status changes
- [x] Demand status dashboard at `/admin/demands/demand/dashboard/` — counts per branch by status with summary cards
- [x] "Status Dashboard" button in demand changelist object tools
- [x] Flow documented in `docs/flows/demand-management.md`

**No remaining TODOs.**

---

## 2.5 Purchase & Notification Workflow ✅

**Done:**
- [x] `Notification` model + admin (each user sees only their own)
- [x] `Vendor` model — name, contact_person, email, phone, address, payment_terms, is_active
- [x] `PurchaseOrder` model — FK→Demand (nullable), FK→Vendor (nullable for drafts), status lifecycle, created_by
- [x] `PurchaseOrderItem` model — FK→PurchaseOrder, FK→InventoryItem, quantity, unit_price
- [x] `VendorAdmin`, `PurchaseOrderAdmin` with full CRUD (Admin + Purchaser)
- [x] `GoodsReceipt` linked to `PurchaseOrder` (optional FK)
- [x] Demand notifications — `notify_on_demand_status_change` signal fires on all status transitions
- [x] Discrepancy notification on receipt — `notify_on_receipt_discrepancy` signal
- [x] Migrations: `purchases/0006`

**TODO:**
- [ ] (Optional) Actual email delivery for notifications via Django email backend

---

## 2.6 Receiving & Verification ✅

> **Receiver role removed.** Branch Manager receives at branch; Warehouse Manager receives at warehouse.

**Done:**
- [x] `GoodsReceipt` → `GoodsReceiptItem` lifecycle (pending/partial/completed)
- [x] `ReceivedItemImage` and `PurchaseReceiptImage` for photo evidence
- [x] `update_inventory_on_receipt_item_save` signal updates `BranchInventory`
- [x] Barcode-based receiving — custom view `/admin/purchases/goodsreceipt/<pk>/receive/`
- [x] Hard-block on completing without images — status reverted to `pending` if no images
- [x] Discrepancy notification — notifies Purchasers + Admins on non-zero variance
- [x] Flow documented in `docs/flows/receiving-verification.md`

**No remaining TODOs.**

---

## 2.7 Warehouse Inventory Management ✅

**Done:**
- [x] `WarehouseInventory` with item, warehouse, quantity, location, `minimum_threshold`
- [x] `WarehouseTransaction` ledger with signal updating `WarehouseInventory.quantity`
- [x] `WarehouseRequest` + `WarehouseRequestItem` approval workflow
- [x] `approve_requests` action updates both `WarehouseInventory` (OUTWARD) and `BranchInventory`
- [x] `LowStockFilter` using `minimum_threshold` on `WarehouseInventory`
- [x] Auto-create `WarehouseInventory` for all items on new Warehouse creation
- [x] Flow documented in `docs/flows/warehouse-management.md`

**No remaining TODOs.**

---

## 2.8 Inter-Branch & Warehouse Transfers ✅

**Done:**
- [x] `Transfer` model with all 4 direction types and full lifecycle
- [x] `TransferItem` with requested/dispatched/received quantities + variance
- [x] Signal deducts from source on dispatch; adds to destination on receipt
- [x] Barcode scanning at dispatch — `/admin/transfers/transfer/<pk>/dispatch/`
- [x] Barcode scanning at receipt — `/admin/transfers/transfer/<pk>/receive/`
- [x] Partial dispatch support
- [x] `notes` field on `Transfer` (migration `transfers/0003`)
- [x] Dispatch notification to destination Branch/Warehouse Manager
- [x] Stock availability check before dispatch
- [x] Flow documented in `docs/flows/transfers.md`

**No remaining TODOs.**

---

## 2.9 Payments & Financial Documentation ✅

**Done:**
- [x] `PaymentDocument` model — document_type (cheque/receipt/proof_of_payment), FileField, uploaded_by
- [x] `VendorInvoice` model — FK→Vendor, invoice_number, amount, due_date, status (unpaid/partial/paid)
- [x] `Payment` model — FK→VendorInvoice, FK→PurchaseOrder, amount, payment_date, FK→PaymentDocument, recorded_by
- [x] `PaymentDocumentAdmin`, `VendorInvoiceAdmin` (shows amount paid + outstanding inline)
- [x] `PaymentAdmin` with `save_model` auto-updating `VendorInvoice.status` on payment save
- [x] Reconciliation view — outstanding invoices vs payments at `/admin/payments/payment/reconciliation/`
- [x] Reconciliation template with overdue row highlights and totals
- [x] Migrations: `payments/0003`, `payments/0004`

**No remaining TODOs.**

---

## 2.10 User Roles & Permissions ✅

**Done:**
- [x] Four roles: Admin, Branch Manager, Purchaser, Warehouse Manager
- [x] `apps/permissions.py` role-check utility functions
- [x] `create_default_groups` management command with full per-model permissions
- [x] Auto-create groups on `post_migrate` signal
- [x] All admin modules scope querysets and CRUD by role

**No remaining TODOs.**

---

## 2.11 Reporting & Audit Logs ✅

> **Sales and usage reports are Admin-only.**

**Done:**
- [x] `AuditLog` model with action type, model, object repr, JSON changes, IP, user agent, timestamp
- [x] Signal on Django `LogEntry` auto-captures every admin create/update/delete action
- [x] Read-only `AuditLogAdmin` (Admin-only) with indexed search/filter
- [x] **Sales vs Inventory Consumption report** (Admin-only) — date range filter, CSV export
- [x] **Item Usage report** (Admin-only) — aggregate consumption by item/branch, CSV export
- [x] **Demand vs Received report** — Admin/Branch Manager/Purchaser, date range, CSV export
- [x] **Warehouse Stock Levels report** — Admin/Warehouse Manager, warehouse filter, CSV export
- [x] **Branch Inventory Status report** — Admin/Branch Manager, branch filter, CSV export
- [x] All report URLs attached to `AuditLogAdmin.get_urls()` at `/admin/reports/auditlog/reports/*/`
- [x] HTML templates for all 5 reports in `templates/admin/reports/`

**No remaining TODOs.**

---

## 2.12 Offline Mode & Data Sync ✅

**Done:**
- [x] `GET /api/v1/snapshot/` returns permission-gated reference data (items, branches, warehouses, stock levels, user context)
- [x] Delta sync — `GET /api/v1/snapshot/?since=<iso_timestamp>` returns only records changed after that time (`updated_at` on `InventoryItem` + `BranchInventory`)
- [x] `server_time` field in snapshot response — clients store this as their next `since` timestamp
- [x] Service worker (Workbox) — caches all admin pages (`NetworkFirst`, 24h, 200 entries), static assets (`StaleWhileRevalidate`); offline fallback to cache
- [x] IndexedDB offline action queue (Dexie) — intercepts all admin form POSTs when offline, stores full form data with idempotency key
- [x] Background sync — replays queued actions to their original admin URLs on reconnect; handles auth errors, server errors, permanent failures
- [x] `IdempotencyMiddleware` prevents duplicate POST submissions on replay (`X-Client-Request-ID` header)
- [x] Online/offline status indicator in navbar with animated pulse dot (`is-offline` CSS class on body)
- [x] Pending sync badge in navbar — shows pending/failed count; click-to-retry on failed actions
- [x] Sync progress modal shown during replay
- [x] Heartbeat check every 3s + network probe to handle `navigator.onLine` inaccuracies
- [x] PWA manifest at `/admin/manifest.json` — name, short name, theme color, display standalone, start URL
- [x] `<link rel="manifest">` + Apple PWA meta tags in admin base template
- [x] Conflict resolution — sequential replay with idempotency keys; permanent 4xx failures marked `failed` in IndexedDB

**No remaining TODOs.**
