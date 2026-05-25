"""Small fixture builders shared by the app test suites."""

from decimal import Decimal
from itertools import count

from django.contrib.auth.models import Group

from apps.branch.models import Branch
from apps.inventory.models import BranchInventory, InventoryItem, UnitOfMeasure
from apps.users.models import User
from apps.warehouse.models import Warehouse, WarehouseInventory

_seq = count(1)


def make_user(*groups, **fields):
    n = next(_seq)
    fields.setdefault("username", f"user{n}")
    fields.setdefault("email", f"user{n}@example.com")
    fields.setdefault("phone", "+920000000000")
    fields.setdefault("is_staff", True)
    user = User.objects.create_user(password="unused-in-tests", **fields)
    for name in groups:
        user.groups.add(Group.objects.get_or_create(name=name)[0])
    return user


def make_branch(code=None, name="Test branch"):
    return Branch.objects.create(
        branch_code=code or f"BR{next(_seq):03d}", name=name, address="Test street"
    )


def make_item(name=None):
    unit, _ = UnitOfMeasure.objects.get_or_create(
        abbreviation="kg", defaults={"name": "Kilogram"}
    )
    return InventoryItem.objects.create(name=name or f"Item {next(_seq)}", unit=unit)


def branch_qty(branch, item):
    return BranchInventory.objects.get(branch=branch, item=item).quantity


def set_branch_qty(branch, item, qty):
    BranchInventory.objects.update_or_create(
        branch=branch, item=item, defaults={"quantity": Decimal(qty)}
    )


def make_warehouse(name="Central"):
    return Warehouse.objects.create(name=name)


def warehouse_qty(warehouse, item):
    return WarehouseInventory.objects.get(
        warehouse=warehouse, inventory_item=item
    ).quantity
