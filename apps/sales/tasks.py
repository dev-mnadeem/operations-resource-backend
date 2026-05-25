import email
import imaplib
import logging
import os
from decimal import Decimal
from email.header import decode_header
from pathlib import Path

import xlrd
from celery import shared_task
from django.utils import timezone

from apps.branch.models import Branch
from apps.products.models import Product

from .models import SalesTransaction

logger = logging.getLogger(__name__)


@shared_task
def fetch_and_process_sales_emails():
    # IMAP credentials
    host = os.getenv("IMAP_HOST")
    user = os.getenv("IMAP_USER")
    password = os.getenv("IMAP_PASSWORD")
    port = os.getenv("IMAP_PORT", "993")

    if not all([host, user, password]):
        logger.warning("IMAP config missing. Skipping email fetch.")
        return

    try:
        mail = imaplib.IMAP4_SSL(host, port)
        mail.login(user, password)
        mail.select("inbox")

        # Search for unseen emails
        status, messages = mail.search(None, "UNSEEN")
        if status == "OK" and messages[0]:
            for email_id in messages[0].split():
                res, msg = mail.fetch(email_id, "(RFC822)")
                for response_part in msg:
                    if isinstance(response_part, tuple):
                        msg_obj = email.message_from_bytes(response_part[1])
                        # Process attachments
                        for part in msg_obj.walk():
                            if part.get_content_maintype() == "multipart":
                                continue
                            if part.get("Content-Disposition") is None:
                                continue

                            filename = part.get_filename()
                            if filename and filename.endswith(".xls"):
                                decoded_filename = decode_header(filename)[0][0]
                                if isinstance(decoded_filename, bytes):
                                    decoded_filename = decoded_filename.decode()

                                # Save attachment
                                file_path = f"/tmp/{decoded_filename}"
                                with Path(file_path).open("wb") as f:
                                    f.write(part.get_payload(decode=True))

                                logger.info(
                                    f"Downloaded sales attachment: {decoded_filename}"
                                )

                                # Process the excel file asynchronously via Celery
                                process_sales_excel.delay(file_path)

        mail.logout()
    except Exception as e:
        logger.error(f"Error fetching emails: {e}")


@shared_task
def process_sales_excel(file_path):
    try:
        workbook = xlrd.open_workbook(file_path)
        sheet = workbook.sheet_by_index(0)

        records_created = 0

        for row_idx in range(4, sheet.nrows):
            row = sheet.row_values(row_idx)

            # Skip empty or summary rows based on "Qty" column
            try:
                qty_raw = str(row[4]).strip() if row[4] else "0"
                qty = Decimal(qty_raw)
            except Exception:
                continue

            if qty <= 0:
                continue

            item_code_str = str(row[3]).strip()
            # Often xlrd parses numbers as floats like "442.0"
            if item_code_str.endswith(".0"):
                item_code_str = item_code_str[:-2]

            item_name_str = str(row[2]).strip()

            try:
                amount_raw = str(row[7]).strip() if row[7] else "0"
                total_amount = Decimal(amount_raw)
            except Exception:
                continue

            retail_outlet_id_raw = row[16]
            retail_outlet_id = str(retail_outlet_id_raw).strip()
            if retail_outlet_id.endswith(".0"):
                retail_outlet_id = retail_outlet_id[:-2]

            if not retail_outlet_id or retail_outlet_id == "":
                # If no branch code mapped on row, use branch "1" as default fallback
                # (matching the provided file defaults)
                retail_outlet_id = "1"

            occurred_at = timezone.now()

            # Lookup branch
            try:
                branch = Branch.objects.get(branch_code=retail_outlet_id)
            except Branch.DoesNotExist:
                logger.warning(
                    f"Branch {retail_outlet_id} not found. Skipping row {row_idx}."
                )
                continue

            # Lookup product logic:
            # 1. Try resolving using product_code if provided
            # 2. If it fails or is empty, try resolving by case-insensitive item name
            product = None
            if item_code_str:
                try:
                    product = Product.objects.get(product_code=item_code_str)
                except Product.DoesNotExist:
                    pass
                except ValueError:
                    logger.warning(
                        f"Invalid product code format '{item_code_str}' in row {row_idx}."
                    )
                    pass

            if not product and item_name_str:
                try:
                    product = Product.objects.get(name__iexact=item_name_str)
                except Product.DoesNotExist:
                    pass
                except Product.MultipleObjectsReturned:
                    product = Product.objects.filter(name__iexact=item_name_str).first()
                    logger.info(
                        f"Multiple products found for name '{item_name_str}'. Used product {product.product_code}."
                    )

            if not product:
                logger.warning(
                    f"Product (Code: '{item_code_str}', Name: '{item_name_str}') not found. Skipping row {row_idx}."
                )
                continue

            unit_price = total_amount / qty if qty else Decimal("0")

            # Create transaction
            SalesTransaction.objects.create(
                branch=branch,
                product=product,
                quantity_sold=int(qty),
                unit_price=unit_price,
                total_amount=total_amount,
                occurred_at=occurred_at,
            )
            records_created += 1

        logger.info(
            f"Successfully processed {file_path}. Created {records_created} tranasctions."
        )
    except Exception as e:
        logger.error(f"Error processing sales excel {file_path}: {e}")
