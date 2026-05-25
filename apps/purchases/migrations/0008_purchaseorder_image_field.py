from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('purchases', '0007_goodsreceipt_image_file'),
    ]

    operations = [
        migrations.AddField(
            model_name='purchaseorder',
            name='image_field',
            field=models.FileField(blank=True, help_text='Optional image attachment for this purchase order.', null=True, upload_to='purchase_orders/'),
        ),
    ]
