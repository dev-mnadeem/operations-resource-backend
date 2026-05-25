from django.contrib.auth.models import Group, Permission
from django.db.models.signals import post_migrate
from django.dispatch import receiver


@receiver(post_migrate)
def create_user_groups(
    sender,
    **kwargs,  # noqa: ARG001
):
    if sender.name != "apps.users":
        return

    roles = ["Admin", "Purchaser", "Branch Manager", "Warehouse Manager"]
    for role in roles:
        group, created = Group.objects.get_or_create(name=role)
        print(f"Group '{role}' created")

    admin_group = Group.objects.get(name="Admin")
    all_permissions = Permission.objects.all()
    admin_group.permissions.set(all_permissions)
    admin_group.save()
