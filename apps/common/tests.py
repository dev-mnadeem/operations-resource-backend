from decimal import Decimal

from django.contrib.auth.models import Permission
from django.test import TestCase
from django.urls import reverse

from apps.common.testing import make_branch, make_item, make_user, set_branch_qty


class SnapshotScopeTests(TestCase):
    """The offline UI's reference data, filtered to what the user may see."""

    def setUp(self):
        self.north = make_branch("NTH")
        self.south = make_branch("STH")
        item = make_item()
        set_branch_qty(self.north, item, "3")
        set_branch_qty(self.south, item, "7")

    def snapshot(self, user):
        self.client.force_login(user)
        response = self.client.get(reverse("common:snapshot"))
        self.assertEqual(response.status_code, 200)
        return response.json()

    def grant_views(self, user):
        user.user_permissions.add(
            *Permission.objects.filter(
                codename__in=[
                    "view_branchinventory",
                    "view_branch",
                    "view_inventoryitem",
                ]
            )
        )

    def test_a_branch_manager_gets_only_their_branch(self):
        manager = make_user("Branch Manager", branch=self.north)
        self.grant_views(manager)
        data = self.snapshot(manager)
        self.assertEqual({row["branch_id"] for row in data["stock"]}, {"NTH"})
        self.assertEqual([b["code"] for b in data["branches"]], ["NTH"])

    def test_an_admin_group_member_gets_every_branch(self):
        admin = make_user("Admin")
        self.grant_views(admin)
        data = self.snapshot(admin)
        self.assertEqual({row["branch_id"] for row in data["stock"]}, {"NTH", "STH"})
        self.assertEqual(
            {row["quantity"] for row in data["stock"]}, {str(Decimal("3.00")), "7.00"}
        )

    def test_a_purchaser_gets_the_branches_they_buy_for(self):
        purchaser = make_user("Purchaser")
        purchaser.purchaser_branches.add(self.south)
        self.grant_views(purchaser)
        data = self.snapshot(purchaser)
        self.assertEqual({row["branch_id"] for row in data["stock"]}, {"STH"})

    def test_the_snapshot_carries_every_section(self):
        admin = make_user("Admin")
        self.grant_views(admin)
        data = self.snapshot(admin)
        self.assertTrue(
            {"server_time", "inventory_items", "stock", "branches", "warehouses"}
            <= set(data)
        )
        self.assertEqual(len(data["inventory_items"]), 1)

    def test_the_snapshot_needs_a_login(self):
        self.assertIn(
            self.client.get(reverse("common:snapshot")).status_code, (401, 403)
        )

    def test_ping_is_public_and_uncached(self):
        response = self.client.get(reverse("common:ping"))
        self.assertEqual(response.json(), {"ok": True})
        self.assertIn("no-store", response["Cache-Control"])
