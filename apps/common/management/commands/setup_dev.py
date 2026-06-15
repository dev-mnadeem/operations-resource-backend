"""
First-time development environment setup.

Runs in one shot:
  1. Apply all pending migrations
  2. Create default role groups (Admin, Purchaser, Branch Manager, Warehouse Manager)
  3. Create a Django superuser (non-interactive, known dev password)
  4. Seed foundation data via seed_data (branches, users, UOMs, inventory, products)
  5. Generate realistic Faker transaction data:
       - Demands + DemandItems
       - Goods Receipts + GoodsReceiptItems (against approved demands)
       - Sales Transactions + InventoryConsumptions
       - Stock Adjustments
       - Warehouse Requests + WarehouseRequestItems (if warehouses exist)

Usage:
    python manage.py setup_dev
    python manage.py setup_dev --username=admin --password=mysecret
    python manage.py setup_dev --skip-migrate   # migrations already applied
    python manage.py setup_dev --skip-seed      # skip seed_data, only fake transactions
"""

import random
from datetime import UTC
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import BaseCommand
from faker import Faker

User = get_user_model()

fake = Faker()

ADJUSTMENT_REASONS = [
    "Physical count variance",
    "Damaged goods removed",
    "Received unrecorded stock",
    "Spoilage during storage",
    "Cycle count correction",
    "Supplier short delivery",
    "Theft write-off",
    "Promotional sample issued",
]


class Command(BaseCommand):
    help = (
        "First-time dev setup: migrate → groups → superuser → seed data → "
        "fake transactions"
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--username",
            default="admin",
            help="Superuser username (default: admin)",
        )
        parser.add_argument(
            "--password",
            default="admin1234",
            help="Superuser password (default: admin1234)",
        )
        parser.add_argument(
            "--email",
            default="admin@arcadian.local",
            help="Superuser email",
        )
        parser.add_argument(
            "--skip-migrate",
            action="store_true",
            help="Skip running migrations",
        )
        parser.add_argument(
            "--skip-seed",
            action="store_true",
            help="Skip seed_data (foundation data); only generate fake transactions",
        )

    # ── orchestration ─────────────────────────────────────────────────────────

    def handle(self, *_args, **options):
        step = 1

        if not options["skip_migrate"]:
            self._step(step, "Applying migrations")
            call_command("migrate", verbosity=1)
            step += 1

        self._step(step, "Creating default role groups")
        call_command("create_default_groups", verbosity=0)
        step += 1

        self._step(step, "Creating superuser")
        self._create_superuser(
            options["username"], options["password"], options["email"]
        )
        step += 1

        if not options["skip_seed"]:
            self._step(step, "Seeding foundation data (branches, inventory, products)")
            call_command("seed_data", verbosity=0)
            step += 1

        self._step(step, "Generating Faker transaction data")
        self._seed_transactions()

        self._print_summary(options["username"], options["password"])

    # ── superuser ─────────────────────────────────────────────────────────────

    def _create_superuser(self, username, password, email):
        if User.objects.filter(username=username).exists():
            self.stdout.write(f"  Superuser '{username}' already exists, skipping.")
            return
        User.objects.create_superuser(
            username=username,
            password=password,
            email=email,
            phone="+920000000000",
        )
        self.stdout.write(self.style.SUCCESS(f"  Created superuser '{username}'"))

    # ── transaction seeding ───────────────────────────────────────────────────

    def _seed_transactions(self):
        # Lazy imports keep this loadable before migrations have run.
        from apps.branch.models import Branch
        from apps.demands.models import Demand, DemandItem
        from apps.inventory.models import InventoryItem, StockAdjustment, UnitOfMeasure
        from apps.products.models import Product
        from apps.purchases.models import GoodsReceipt, GoodsReceiptItem
        from apps.sales.models import InventoryConsumption, SalesTransaction
        from apps.warehouse.models import (
            Warehouse,
            WarehouseRequest,
            WarehouseRequestItem,
        )

        branches = list(Branch.objects.all())
        warehouses = list(Warehouse.objects.all())
        items = list(InventoryItem.objects.all())
        uoms = list(UnitOfMeasure.objects.all())
        products = list(Product.objects.filter(is_active=True))
        users = list(User.objects.filter(is_staff=True))

        if not branches or not items or not uoms:
            self.stdout.write(
                self.style.WARNING(
                    "  No branches/items found — run without --skip-seed first."
                )
            )
            return

        self._seed_demands(Demand, DemandItem, branches, items, uoms, users)
        self._seed_goods_receipts(GoodsReceipt, GoodsReceiptItem, Demand, users)
        self._seed_sales(
            SalesTransaction, InventoryConsumption, branches, items, products
        )
        self._seed_stock_adjustments(
            StockAdjustment, branches, warehouses, items, users
        )

        if warehouses:
            self._seed_warehouse_requests(
                WarehouseRequest,
                WarehouseRequestItem,
                branches,
                warehouses,
                items,
                users,
            )

    # ── demands ───────────────────────────────────────────────────────────────

    def _seed_demands(self, Demand, DemandItem, branches, items, uoms, users):  # noqa: N803
        priorities = ["low", "medium", "high"]
        statuses = ["pending", "submitted", "approved", "rejected"]
        weights = [20, 30, 40, 10]
        demand_count = item_count = 0

        for _ in range(20):
            branch = random.choice(branches)
            submitter = random.choice(users)
            status = random.choices(statuses, weights=weights)[0]
            approved_by = approved_at = None

            if status in ("approved", "rejected"):
                approved_by = random.choice(users)
                approved_at = fake.date_time_between(
                    start_date="-6M", end_date="now", tzinfo=UTC
                )

            demand = Demand.objects.create(
                branch=branch,
                status=status,
                submitted_by=submitter,
                approved_by=approved_by,
                approved_at=approved_at,
                rejection_reason=fake.sentence() if status == "rejected" else "",
            )
            demand_count += 1

            sample_items = random.sample(items, min(random.randint(2, 6), len(items)))
            for item in sample_items:
                DemandItem.objects.create(
                    demand=demand,
                    inventory_item=item,
                    quantity=Decimal(str(round(random.uniform(1, 50), 2))),
                    unit=random.choice(uoms),
                    priority=random.choice(priorities),
                )
                item_count += 1

        self.stdout.write(
            f"  Demands:              {demand_count:>4}  ({item_count} line items)"
        )

    # ── goods receipts ────────────────────────────────────────────────────────

    def _seed_goods_receipts(self, GoodsReceipt, GoodsReceiptItem, Demand, users):  # noqa: N803
        approved_demands = list(Demand.objects.filter(status="approved"))
        if not approved_demands:
            self.stdout.write("  Goods receipts:          0  (no approved demands yet)")
            return

        sample_demands = random.sample(approved_demands, min(10, len(approved_demands)))
        receipt_count = item_count = 0

        for demand in sample_demands:
            demand_items = list(demand.items.all())
            if not demand_items:
                continue

            gr = GoodsReceipt.objects.create(
                demand=demand,
                receiver=random.choice(users),
                received_at=fake.date_time_between(
                    start_date="-6M", end_date="now", tzinfo=UTC
                ),
                status=random.choice(["completed", "partial"]),
                total_received_quantity=Decimal("0.00"),
            )

            total_received = Decimal("0.00")
            for demand_item in demand_items:
                expected = demand_item.quantity
                received = Decimal(
                    str(round(float(expected) * random.uniform(0.8, 1.0), 2))
                )
                GoodsReceiptItem.objects.create(
                    goods_receipt=gr,
                    inventory_item=demand_item.inventory_item,
                    expected_quantity=expected,
                    received_quantity=received,
                    variance=received - expected,
                    condition=random.choice(["Good", "Damaged", "", ""]),
                )
                total_received += received
                item_count += 1

            gr.total_received_quantity = total_received
            gr.save()
            receipt_count += 1

        self.stdout.write(
            f"  Goods receipts:       {receipt_count:>4}  ({item_count} line items)"
        )

    # ── sales ─────────────────────────────────────────────────────────────────

    def _seed_sales(  # noqa: PLR0913
        self,
        SalesTransaction,
        InventoryConsumption,
        branches,
        items,
        products,  # noqa: N803
    ):
        txn_count = consumption_count = 0

        for _ in range(30):
            branch = random.choice(branches)

            # Prefer products belonging to this branch; fall back to global ones
            branch_products = [
                p for p in products if p.branch_id == branch.pk or p.branch_id is None
            ]
            product = random.choice(branch_products) if branch_products else None

            qty = random.randint(1, 10)
            unit_price = (
                product.price
                if product
                else Decimal(str(round(random.uniform(100, 2000), 2)))
            )

            # SalesTransaction.save() auto-sets total_amount = quantity_sold * unit_price
            txn = SalesTransaction.objects.create(
                branch=branch,
                product=product,
                quantity_sold=qty,
                unit_price=unit_price,
                total_amount=Decimal("0.00"),
                occurred_at=fake.date_time_between(
                    start_date="-6M", end_date="now", tzinfo=UTC
                ),
            )
            txn_count += 1

            for item in random.sample(items, min(random.randint(1, 3), len(items))):
                InventoryConsumption.objects.create(
                    sales_transaction=txn,
                    inventory_item=item,
                    quantity_consumed=Decimal(str(round(random.uniform(0.5, 5), 2))),
                )
                consumption_count += 1

        self.stdout.write(
            f"  Sales transactions:   {txn_count:>4}  ({consumption_count} consumptions)"
        )

    # ── stock adjustments ─────────────────────────────────────────────────────

    def _seed_stock_adjustments(
        self,
        StockAdjustment,
        branches,
        warehouses,
        items,
        users,  # noqa: N803
    ):
        adj_types = ["increase", "decrease", "correction"]
        count = 0

        for _ in range(15):
            use_branch = not warehouses or random.choice([True, False])
            StockAdjustment.objects.create(
                inventory_item=random.choice(items),
                branch=random.choice(branches) if use_branch else None,
                warehouse=(
                    random.choice(warehouses) if not use_branch and warehouses else None
                ),
                user=random.choice(users),
                adjustment_type=random.choice(adj_types),
                quantity=Decimal(str(round(random.uniform(1, 20), 2))),
                reason=random.choice(ADJUSTMENT_REASONS),
            )
            count += 1

        self.stdout.write(f"  Stock adjustments:    {count:>4}")

    # ── warehouse requests ────────────────────────────────────────────────────

    def _seed_warehouse_requests(
        self,
        WarehouseRequest,  # noqa: N803
        WarehouseRequestItem,  # noqa: N803
        branches,
        warehouses,
        items,
        users,
    ):
        statuses = ["pending", "approved", "rejected"]
        weights = [30, 55, 15]
        req_count = item_count = 0

        for _ in range(10):
            branch = random.choice(branches)
            warehouse = random.choice(warehouses)
            status = random.choices(statuses, weights=weights)[0]
            approved_by = approved_at = None

            if status == "approved":
                approved_by = random.choice(users)
                approved_at = fake.date_time_between(
                    start_date="-3M", end_date="now", tzinfo=UTC
                )

            req = WarehouseRequest.objects.create(
                warehouse=warehouse,
                branch=branch,
                requested_by=random.choice(users),
                status=status,
                approved_by=approved_by,
                approved_at=approved_at,
                rejection_reason=fake.sentence() if status == "rejected" else "",
            )
            req_count += 1

            sample_items = random.sample(items, min(random.randint(2, 5), len(items)))
            for item in sample_items:
                WarehouseRequestItem.objects.create(
                    warehouse_request=req,
                    inventory_item=item,
                    quantity=Decimal(str(round(random.uniform(1, 30), 2))),
                )
                item_count += 1

        self.stdout.write(
            f"  Warehouse requests:   {req_count:>4}  ({item_count} line items)"
        )

    # ── helpers ───────────────────────────────────────────────────────────────

    def _step(self, n, label):
        self.stdout.write(self.style.HTTP_INFO(f"\nStep {n}: {label}..."))

    def _print_summary(self, username, password):
        self.stdout.write("\n" + "─" * 48)
        self.stdout.write(self.style.SUCCESS("  Dev environment is ready!"))
        self.stdout.write("─" * 48)
        self.stdout.write("  Admin panel : http://localhost:8000/admin")
        self.stdout.write(f"  Username    : {username}")
        self.stdout.write(f"  Password    : {password}")
        self.stdout.write("─" * 48 + "\n")
