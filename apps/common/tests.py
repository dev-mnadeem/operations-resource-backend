from decimal import Decimal

from django.contrib.auth.models import AnonymousUser, Permission
from django.core.cache import cache
from django.http import HttpResponse, HttpResponseRedirect
from django.test import RequestFactory, SimpleTestCase, TestCase
from django.urls import reverse

from apps.branch.models import Branch
from apps.common.middleware import IdempotencyMiddleware
from apps.common.testing import (
    PLAIN_STATIC_FILES,
    make_branch,
    make_item,
    make_user,
    set_branch_qty,
)


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


class IdempotencyMiddlewareTests(SimpleTestCase):
    def setUp(self):
        cache.clear()
        self.calls = 0

    def view(self, _request):
        self.calls += 1
        return HttpResponseRedirect(f"/admin/thing/{self.calls}/")

    def post(self, request_id="abc"):
        request = RequestFactory().post(
            "/admin/thing/add/", HTTP_X_CLIENT_REQUEST_ID=request_id
        )
        request.user = AnonymousUser()
        return IdempotencyMiddleware(self.view)(request)

    def test_a_replayed_post_returns_the_first_redirect_without_rerunning(self):
        first = self.post()
        replay = self.post()
        self.assertEqual(self.calls, 1)
        self.assertEqual(replay.status_code, 302)
        self.assertEqual(replay["Location"], first["Location"])

    def test_a_different_request_id_runs_the_view(self):
        self.post("one")
        self.post("two")
        self.assertEqual(self.calls, 2)

    def test_errors_are_not_remembered(self):
        def failing(_request):
            self.calls += 1
            return HttpResponse(status=500)

        self.view = failing
        self.post()
        self.post()
        self.assertEqual(self.calls, 2)


@PLAIN_STATIC_FILES
class IdempotentAdminFormTests(TestCase):
    def test_replaying_an_admin_add_form_creates_one_record(self):
        self.client.force_login(make_user(is_superuser=True))
        form = {"branch_code": "NEW", "name": "New", "address": "x", "phone": ""}
        for _ in range(2):
            response = self.client.post(
                reverse("admin:branch_branch_add"),
                form,
                HTTP_X_CLIENT_REQUEST_ID="offline-1",
            )
            self.assertEqual(response.status_code, 302)
        self.assertEqual(Branch.objects.filter(pk="NEW").count(), 1)
