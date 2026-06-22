import hashlib

from django.core.management.base import BaseCommand
from django.db.models import CharField, Value
from django.db.models.functions import Coalesce, Length

from apps.inventory.models import InventoryItem


class Command(BaseCommand):
    help = "Override barcodes longer than 20 characters with unique 20-char values."

    def add_arguments(self, parser):
        parser.add_argument(
            "--apply",
            action="store_true",
            help=(
                "Actually update matching items. Without this flag, command is dry-run."
            ),
        )

    def handle(self, *_args, **options):
        items = (
            InventoryItem.objects.annotate(
                barcode_len=Length(
                    Coalesce("barcode", Value("", output_field=CharField()))
                )
            )
            .filter(barcode_len__gt=20)
            .order_by("id")
        )

        total = items.count()
        if total == 0:
            self.stdout.write(
                self.style.SUCCESS("No inventory items found with barcode length > 20.")
            )
            return

        self.stdout.write(
            self.style.WARNING(
                f"Found {total} inventory item(s) with barcode length > 20."
            )
        )
        for item in items[:50]:
            self.stdout.write(
                " - "
                f"id={item.id} "
                f"name={item.name} "
                f"barcode={item.barcode} "
                f"(len={item.barcode_len})"
            )
        if total > 50:
            self.stdout.write(f" ... and {total - 50} more")

        if not options["apply"]:
            self.stdout.write(
                self.style.WARNING(
                    "Dry-run only. Re-run with --apply to update these items."
                )
            )
            existing = set(
                InventoryItem.objects.exclude(barcode__isnull=True)
                .exclude(barcode="")
                .values_list("barcode", flat=True)
            )
            for preview_count, item in enumerate(items, start=1):
                new_barcode = self._generate_unique_barcode(item, existing)
                existing.add(new_barcode)
                if preview_count <= 50:
                    self.stdout.write(
                        f"   id={item.id}: {item.barcode} -> {new_barcode}"
                    )
            if total > 50:
                self.stdout.write(f"   ... and {total - 50} more updates")
            return

        existing = set(
            InventoryItem.objects.exclude(barcode__isnull=True)
            .exclude(barcode="")
            .values_list("barcode", flat=True)
        )
        updated = 0
        for item in items:
            new_barcode = self._generate_unique_barcode(item, existing)
            old_barcode = item.barcode
            item.barcode = new_barcode
            item.save(update_fields=["barcode"])
            existing.add(new_barcode)
            updated += 1
            self.stdout.write(f"Updated id={item.id}: {old_barcode} -> {new_barcode}")

        self.stdout.write(
            self.style.SUCCESS(f"Update complete. Updated={updated}, Total={total}.")
        )

    def _generate_unique_barcode(self, item, existing_barcodes):
        """
        Build deterministic unique barcode with max length 20.
        Format: 'BC' + 18 hex chars.
        """
        attempt = 0
        while True:
            source = f"{item.id}|{item.barcode}|{attempt}"
            digest = hashlib.sha1(source.encode("utf-8")).hexdigest().upper()
            candidate = f"BC{digest[:18]}"
            if candidate not in existing_barcodes:
                return candidate
            attempt += 1
