"""
Management command to create default role groups for Arcadian ERP.

Run after setup or anytime groups are missing:
    python manage.py create_default_groups

Groups created: Admin, Purchaser, Branch Manager, Warehouse Manager

Role responsibilities:
  Admin           — full access to everything
  Branch Manager  — manages their branch: inventory, demands, goods receipt, transfers
  Purchaser       — reviews and approves/rejects demands, manages purchase receipts
  Warehouse Manager — manages warehouse stock, transactions, and requests
"""

from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from django.core.management.base import BaseCommand

DEFAULT_ROLES = [
    "Admin",
    "Purchaser",
    "Branch Manager",
    "Warehouse Manager",
]


# Models that each role should have view permissions for
ROLE_MODELS = {
    "Branch Manager": [
        "users.user",
        "inventory.inventoryitem",
        "inventory.branchinventory",
        "inventory.bom",
        "inventory.bomitem",
        "inventory.stockcyclecount",
        "inventory.stockadjustment",
        "products.product",
        # Sales/consumption data is Admin-only — not included here
        "demands.demand",
        "demands.demanditem",
        "purchases.goodsreceipt",
        "purchases.goodsreceiptitem",
        "purchases.receiveditemimage",
        "purchases.notification",
        "transfers.transfer",
        "transfers.transferitem",
    ],
    "Purchaser": [
        "demands.demand",
        "demands.demanditem",
        "purchases.purchasereceiptimage",
        "purchases.notification",
        "inventory.inventoryitem",
        "branch.branch",
    ],
    "Warehouse Manager": [
        "users.user",
        "inventory.inventoryitem",
        "warehouse.warehouse",
        "warehouse.warehouseinventory",
        "warehouse.warehousetransaction",
        "warehouse.warehouserequest",
        "warehouse.warehouserequestitem",
        "transfers.transfer",
        "transfers.transferitem",
        "purchases.notification",
        "demands.demand",
        "demands.demanditem",
    ],
}

# Additional specific action permissions (add, change, delete) beyond view
EXTRA_ACTION_MODELS = {
    "Purchaser": {
        "add": [
            "purchases.purchasereceiptimage",
        ],
        "change": [
            "demands.demand",
            "purchases.purchasereceiptimage",
        ],
        "delete": [
            "purchases.purchasereceiptimage",
        ],
    },
    "Branch Manager": {
        # Branch Managers receive goods at their branch
        "add": [
            "purchases.goodsreceipt",
            "purchases.goodsreceiptitem",
            "purchases.receiveditemimage",
            "inventory.stockcyclecount",
            "inventory.stockadjustment",
            "demands.demand",
            "demands.demanditem",
        ],
        "change": [
            "purchases.goodsreceipt",
            "purchases.goodsreceiptitem",
            "purchases.receiveditemimage",
            "inventory.stockcyclecount",
            "inventory.stockadjustment",
            "demands.demand",
            "demands.demanditem",
        ],
    },
    "Warehouse Manager": {
        # Warehouse Managers manage inbound/outbound stock and requests
        "add": [
            "warehouse.warehousetransaction",
            "warehouse.warehouseinventory",
            "warehouse.warehouserequest",
            "warehouse.warehouserequestitem",
        ],
        "change": [
            "warehouse.warehousetransaction",
            "warehouse.warehouseinventory",
            "warehouse.warehouserequest",
        ],
    },
}


class Command(BaseCommand):
    help = "Create default role groups and assign view permissions"

    def handle(self, *_args, **_options):
        for role in DEFAULT_ROLES:
            group, created = Group.objects.get_or_create(name=role)
            if created:
                self.stdout.write(self.style.SUCCESS(f"Created group: {role}"))
            else:
                self.stdout.write(f"Group already exists: {role}")

        # Admin gets all permissions
        admin_group = Group.objects.get(name="Admin")
        admin_group.permissions.set(Permission.objects.all())
        admin_group.save()
        self.stdout.write(
            self.style.SUCCESS("Assigned all permissions to Admin group.")
        )

        # Assign view permissions to role groups
        for role_name, model_list in ROLE_MODELS.items():
            group = Group.objects.get(name=role_name)
            view_perms = []
            for model_path in model_list:
                app_label, model_name = model_path.split(".")
                try:
                    ct = ContentType.objects.get(app_label=app_label, model=model_name)
                    perm = Permission.objects.get(
                        content_type=ct, codename=f"view_{model_name}"
                    )
                    view_perms.append(perm)
                except (ContentType.DoesNotExist, Permission.DoesNotExist):
                    # Model might not exist yet, skip
                    pass
            if view_perms:
                group.permissions.set(view_perms)
                group.save()
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Assigned {len(view_perms)} view permissions to {role_name}"
                    )
                )

        # Assign extra action permissions to role groups
        for role_name, actions in EXTRA_ACTION_MODELS.items():
            group = Group.objects.get(name=role_name)
            action_perms = []
            for action, model_list in actions.items():
                for model_path in model_list:
                    app_label, model_name = model_path.split(".")
                    try:
                        ct = ContentType.objects.get(
                            app_label=app_label, model=model_name
                        )
                        perm = Permission.objects.get(
                            content_type=ct, codename=f"{action}_{model_name}"
                        )
                        action_perms.append(perm)
                    except (ContentType.DoesNotExist, Permission.DoesNotExist):
                        pass
            if action_perms:
                # Add action perms to existing view perms
                group.permissions.add(*action_perms)
                group.save()
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Assigned {len(action_perms)} extra permissions to {role_name}"
                    )
                )

        self.stdout.write(
            self.style.SUCCESS(
                "Done. You can now assign users to these groups in Django Admin → Users → Groups."
            )
        )
