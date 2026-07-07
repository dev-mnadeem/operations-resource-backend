# Flow: Demand Management (2.4)

## Overview

Branch Manager manually raises a demand for inventory items. Purchaser reviews and approves or rejects it. Admin has full access. No automated demand creation from stock thresholds.

---

## Status Lifecycle

```
pending → submitted → approved
                   ↘ rejected
```

- **pending** — draft, not yet submitted (default when Branch Manager creates)
- **submitted** — Branch Manager has confirmed; awaiting Purchaser review
- **approved** — Purchaser (or Admin) approved; ready for goods receipt
- **rejected** — Purchaser (or Admin) rejected with optional reason

---

## Role Flows

### Branch Manager

1. Navigate to **Demands → Demands → + Add demand**.
2. If assigned to a branch: inventory is pre-filtered to that branch.
3. If Admin: select a branch first, then items load.
4. Enter a quantity for each item needed. Items at or below `minimum_threshold` are highlighted.
5. Click **Save Demands** → `Demand` created with status `submitted`.
6. **Notifications fire:** All Purchasers, Warehouse Managers, and Admins receive a `demand_submitted` notification.

### Purchaser

**Per-demand approval (with partial approval):**
1. Navigate to **Demands → Demands**.
2. Click **View list** on any `submitted` demand.
3. The items table shows each line item with a **Requested** quantity and an **Approved Qty** input.
4. Optionally change the `Approved Qty` for individual items (to partially approve a line item).
5. Click **Approve** to approve (with any adjusted quantities saved to `DemandItem.approved_quantity`).
   — or —
6. Enter a rejection reason and click **Reject**.

**Bulk approval:**
1. Select multiple `submitted` demands via checkboxes.
2. Choose **Approve selected demands** or **Reject selected demands** → **Go**.
3. Each demand triggers the notification signal individually.

### Admin

- Full access to all demands across all branches.
- Can approve/reject and edit any demand.
- Receives notifications on all demand status changes.

---

## Partial Approval

`DemandItem.approved_quantity` stores the approved quantity per line item:
- `null` = full quantity approved (approved_quantity = quantity)
- A value less than `quantity` = partial approval

The downstream `GoodsReceipt` uses `expected_quantity` from the demand item; when creating a GoodsReceipt, the Branch Manager should enter `approved_quantity` (if set) as the expected quantity.

---

## Notifications

| Event | Who is notified |
|-------|----------------|
| Demand submitted | All Purchasers, all Warehouse Managers, all Admins (excluding submitter) |
| Demand approved | Submitting Branch Manager, all Admins (excluding approver and submitter) |
| Demand rejected | Submitting Branch Manager, all Admins (excluding approver and submitter) |

Signal: `notify_on_demand_status_change` in `apps/purchases/signals.py`.
