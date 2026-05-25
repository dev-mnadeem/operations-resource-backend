# Setup & Operational Flow

This document describes the exact order in which records should be created and by which role.
Follow Phase 1–3 once during initial system setup. Phase 4 onwards is the day-to-day operational loop.

---

## Phase 1 — System Foundation (Admin)

These must exist before any other role can do anything.

```
Step 1  →  Create Branches
Step 2  →  Create Warehouses
Step 3  →  Create Inventory Categories
Step 4  →  Create Units of Measure
Step 5  →  Create Inventory Items         (assign category + UoM from steps 3–4)
Step 6  →  Create Products                (catalog items used in sales & BOMs)
Step 7  →  Create Users                   (assign role + location from steps 1–2)
```

### Step-by-step

| # | What to Create | Admin Panel Path | Depends On |
|---|----------------|------------------|------------|
| 1 | **Branch** | Branch → Branches | Nothing |
| 2 | **Warehouse** | Warehouse → Warehouses | Nothing |
| 3 | **Inventory Category** | Inventory → Inventory Categories | Nothing |
| 4 | **Unit of Measure** | Inventory → Units of Measure | Nothing |
| 5 | **Inventory Item** | Inventory → Inventory Items | Steps 3, 4 |
| 6 | **Product** | Products → Products | Nothing |
| 7 | **Users** | Users → Users | Steps 1, 2 |

> After step 7, each user can log in and complete their own phase below.

---

## Phase 2 — Location Setup (Branch Manager & Warehouse Manager)

Once users exist and are assigned to locations, each location manager sets up their stock records.

### Branch Manager does:

```
Step 8  →  Add Branch Inventory           (link Inventory Items to own branch, set quantities + thresholds)
Step 9  →  Create BOMs                    (optional — only if products have component items)
```

| # | What to Create | Admin Panel Path | Depends On |
|---|----------------|------------------|------------|
| 8 | **Branch Inventory** | Inventory → Branch Inventories | Steps 1, 5 |
| 9 | **BOM / BOM Items** | Inventory → BOMs | Steps 5, 6 |

### Warehouse Manager does:

```
Step 10 →  Add Warehouse Inventory        (link Inventory Items to own warehouse, set quantities)
Step 11 →  Create BOMs                    (optional — same as above)
```

| # | What to Create | Admin Panel Path | Depends On |
|---|----------------|------------------|------------|
| 10 | **Warehouse Inventory** | Warehouse → Warehouse Inventories | Steps 2, 5 |
| 11 | **BOM / BOM Items** | Inventory → BOMs | Steps 5, 6 |

---

## Phase 3 — Procurement Setup (Purchaser)

Before any purchasing can happen, vendors must be registered.

```
Step 12 →  Create Vendors
```

| # | What to Create | Admin Panel Path | Depends On |
|---|----------------|------------------|------------|
| 12 | **Vendor** | Purchases → Vendors | Nothing |

---

## Phase 4 — Day-to-Day Operations

This is the repeating operational loop once setup is complete.

---

### Flow A — Branch Restocking via Demand → PO → Goods Receipt

This is the primary procurement loop for branch stock.

```
Branch Manager          Purchaser               Branch Manager
─────────────           ─────────               ──────────────
1. Create Demand
   (add demand items)

2. Submit Demand
   (status: PENDING
    → SUBMITTED)
                        3. Review Demand
                           Approve / Reject
                           (adjust quantities
                            per item if needed)
                           (status → APPROVED
                            or REJECTED)

                        4. Create Purchase Order
                           (from approved demand)

                        5. Send PO to Vendor
                           (external, off-system)

                                                6. Receive Goods
                                                   Create Goods Receipt
                                                   (enter received qty
                                                    per item)

                                                7. Attach Receipt Images
                                                   (required before
                                                    completing receipt)

                                                8. Mark Receipt COMPLETED
                                                   or PARTIAL
```

**Admin panel paths:**

| Step | Role | Path |
|------|------|------|
| Create & Submit Demand | Branch Manager | Demands → Demands |
| Approve/Reject Demand | Purchaser | Demands → Demands |
| Create Purchase Order | Purchaser | Purchases → Purchase Orders |
| Create Goods Receipt | Branch Manager | Purchases → Goods Receipts |
| Attach Images | Branch Manager | Purchases → Received Item Images |

---

### Flow B — Vendor Payment

Follows after a Purchase Order is fulfilled.

```
Purchaser
─────────
1. Create Vendor Invoice       (link to PO, enter amount)
2. Record Payment              (enter amount paid, date)
3. Attach Payment Document     (upload cheque / proof of payment)
   → Invoice status auto-updates: UNPAID → PARTIAL → PAID
```

**Admin panel paths:**

| Step | Role | Path |
|------|------|------|
| Create Vendor Invoice | Purchaser | Payments → Vendor Invoices |
| Record Payment | Purchaser | Payments → Payments |
| Upload Document | Purchaser | Payments → Payment Documents |

---

### Flow C — Stock Transfer Between Locations

Used when stock needs to move between branches or between branch and warehouse.

```
Initiating Location Manager     Receiving Location Manager
───────────────────────────     ──────────────────────────
1. Create Transfer
   (set from/to locations,
    add transfer items)
   (status: PENDING)

2. Submit for Approval
   (Admin approves, or
    location manager if
    authorised)
   (status: PENDING → APPROVED)

3. Dispatch Transfer
   (confirm quantities,
    barcode-assisted)
   (status: APPROVED → DISPATCHED)
                                4. Receive Transfer
                                   (confirm received qty,
                                    barcode-assisted)
                                   (status → RECEIVED)
                                   → Stock added to destination
                                   → Variance recorded if qty differs
```

**Admin panel paths:**

| Step | Role | Path |
|------|------|------|
| Create Transfer | Branch Manager / Warehouse Manager | Transfers → Transfers |
| Approve | Admin | Transfers → Transfers (batch action) |
| Dispatch | Sending location manager | Transfers → Transfers (batch action) |
| Receive | Receiving location manager | Transfers → Transfers (batch action) |

---

### Flow D — Branch Requests Stock from Warehouse

Used when a branch pulls stock directly from a warehouse (different from a Transfer).

```
Branch Manager              Warehouse Manager
──────────────              ─────────────────
1. Create Warehouse Request
   (select warehouse,
    add items + quantities)

                            2. Review Request
                               Approve / Reject

                            3. Fulfil Request
                               (adjust warehouse
                                inventory accordingly)
```

**Admin panel paths:**

| Step | Role | Path |
|------|------|------|
| Create Request | Branch Manager | Warehouse → Warehouse Requests |
| Approve/Reject | Warehouse Manager | Warehouse → Warehouse Requests |

---

### Flow E — Stock Cycle Count

Periodic stock verification at a branch or warehouse.

```
Branch Manager / Warehouse Manager
──────────────────────────────────
1. Create Stock Cycle Count
   (select items to count)

2. Enter Physical Counts
   (actual counted quantities
    per item)

3. Save → System computes variance
   (counted qty vs system qty)

4. Create Stock Adjustment       ← if variance found
   (type: CORRECTION,
    reason: "Cycle count YYYY-MM-DD")
```

**Admin panel paths:**

| Step | Role | Path |
|------|------|------|
| Create Cycle Count | Branch Mgr / Warehouse Mgr | Inventory → Stock Cycle Counts |
| Create Adjustment | Branch Mgr / Warehouse Mgr | Inventory → Stock Adjustments |

> Cycle counts are also auto-scheduled daily at 06:00 by Celery Beat.

---

### Flow F — Sales Import (Admin)

Sales data flows in automatically; no manual creation needed in normal operation.

```
Celery Beat (every 5 min)
──────────────────────────
1. Poll Gmail inbox for sales sheets
2. Parse and import SalesTransactions
3. Create linked InventoryConsumptions
   → Stock quantities reduced automatically
```

Admin can view results at: **Sales → Sales Transactions** and **Sales → Inventory Consumptions**.

---

## Full Dependency Chain (Visual)

```
[Branch]  [Warehouse]  [Inv. Category]  [UoM]
    │           │              │           │
    │           │         [Inv. Item] ────┘
    │           │              │
    │    [Wh. Inventory]  [Br. Inventory]
    │           │              │
  [User] ───── │ ─────────────│──────────────────────────────┐
    │           │              │                              │
[Warehouse   [Branch        [Vendor]                     [Product]
 Manager]    Manager /                                       │
             Purchaser]                                    [BOM]
    │           │              │
[Wh. Request] [Demand] → [Purchase Order] → [Goods Receipt]
    │                                              │
[Transfer] ◄──────────────────────────────── [Inv. Images]
    │
[Wh. Transaction]
                              │
                         [Vend. Invoice] → [Payment] → [Pay. Document]
                                                │
                                          [Audit Log] (auto)
                                          [Sales Tx]  (auto via Gmail)
```

---

## Recommended First-Time Setup Checklist

```
[ ] 1.  Create at least one Branch
[ ] 2.  Create at least one Warehouse
[ ] 3.  Create Inventory Categories
[ ] 4.  Create Units of Measure
[ ] 5.  Create Inventory Items
[ ] 6.  Create Products (if using BOMs or sales)
[ ] 7.  Create a Purchaser user       → assign to a branch
[ ] 8.  Create a Branch Manager user  → assign to a branch
[ ] 9.  Create a Warehouse Manager    → assign to a warehouse
[ ] 10. (Branch Manager) Add Branch Inventory records
[ ] 11. (Warehouse Manager) Add Warehouse Inventory records
[ ] 12. (Purchaser) Create Vendors
[ ] 13. Test Flow A: Branch Manager creates a demand → Purchaser approves → PO created
[ ] 14. Test Flow C: Create a transfer between two locations
```
