from django.db import migrations, models


def populate_existing_purchaser_branches(apps, schema_editor):  
    User = apps.get_model("users", "User")
    Group = apps.get_model("auth", "Group")

    purchaser_group = Group.objects.filter(name="Purchaser").first()
    if not purchaser_group:
        return

    purchasers = User.objects.filter(groups=purchaser_group).exclude(
        branch_id__isnull=True
    )
    for purchaser in purchasers.iterator():
        purchaser.purchaser_branches.add(purchaser.branch_id)


class Migration(migrations.Migration):
    dependencies = [
        ("branch", "0001_initial"),
        ("users", "0003_alter_user_email"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="purchaser_branches",
            field=models.ManyToManyField(
                blank=True,
                help_text="Branches this purchaser handles notifications/workflows for.",
                related_name="purchaser_users",
                to="branch.branch",
            ),
        ),
        migrations.RunPython(
            populate_existing_purchaser_branches,
            reverse_code=migrations.RunPython.noop,
        ),
    ]
