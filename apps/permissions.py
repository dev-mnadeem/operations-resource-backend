"""
Permission utilities for role-based access control in Django Admin.
"""

# Role group names
ADMIN_GROUP = "Admin"
PURCHASER_GROUP = "Purchaser"
BRANCH_MANAGER_GROUP = "Branch Manager"
WAREHOUSE_MANAGER_GROUP = "Warehouse Manager"


def is_admin(user):
    """Check if user is in Admin group or is superuser."""
    return user.is_superuser or user.groups.filter(name=ADMIN_GROUP).exists()


def is_purchaser(user):
    """Check if user is in Purchaser group."""
    return user.groups.filter(name=PURCHASER_GROUP).exists()


def is_branch_manager(user):
    """Check if user is in Branch Manager group."""
    return user.groups.filter(name=BRANCH_MANAGER_GROUP).exists()


def is_warehouse_manager(user):
    """Check if user is in Warehouse Manager group."""
    return user.groups.filter(name=WAREHOUSE_MANAGER_GROUP).exists()


def has_role(user, role_name):
    """Check if user has a specific role."""
    return user.groups.filter(name=role_name).exists()


def has_any_role(user, *role_names):
    """Check if user has any of the specified roles."""
    return user.groups.filter(name__in=role_names).exists()


def get_user_roles(user):
    """Get list of role names for a user."""
    return list(user.groups.values_list("name", flat=True))
