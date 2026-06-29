# users/forms.py
from django import forms
from django.contrib.auth.forms import UserChangeForm, UserCreationForm
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError

from apps.branch.models import Branch

from .models import User
from .widgets import PermissionGridWidget

# Constants for group names
ADMIN_GROUP = "Admin"
WAREHOUSE_GROUP = "Warehouse Manager"
PURCHASER_GROUP = "Purchaser"


class AdminUserCreationForm(UserCreationForm):
    role_group = forms.ModelChoiceField(
        queryset=Group.objects.all(),
        required=False,
        label="Role group",
    )

    class Meta:
        model = User
        fields = (
            "username",
            "password1",
            "password2",
            "branch",
            "purchaser_branches",
            "warehouse",
            "first_name",
            "last_name",
            "email",
            "phone",
        )

    def clean(self):
        cleaned_data = super().clean()
        group = cleaned_data.get("role_group")
        branch = cleaned_data.get("branch")
        purchaser_branches = cleaned_data.get("purchaser_branches")
        warehouse = cleaned_data.get("warehouse")

        is_admin = group and group.name == ADMIN_GROUP
        is_warehouse_manager = group and group.name == WAREHOUSE_GROUP
        is_purchaser = group and group.name == PURCHASER_GROUP

        if is_admin:
            if branch or warehouse or purchaser_branches:
                raise ValidationError(
                    "Admins must not be assigned to branch, purchaser branches, or warehouse."
                )
            return cleaned_data

        if is_warehouse_manager:
            if branch or purchaser_branches:
                raise ValidationError(
                    "Warehouse Managers must not be assigned to branch or purchaser branches."
                )
            if not warehouse:
                raise ValidationError(
                    "Warehouse Managers must be assigned a warehouse."
                )
            return cleaned_data

        if is_purchaser:
            if warehouse:
                raise ValidationError("Purchasers must not be assigned a warehouse.")

            if (not purchaser_branches or purchaser_branches.count() == 0) and branch:
                purchaser_branches = Branch.objects.filter(pk=branch.pk)
                cleaned_data["purchaser_branches"] = purchaser_branches

            if not purchaser_branches or purchaser_branches.count() == 0:
                raise ValidationError(
                    "Purchasers must have at least one assigned purchaser branch."
                )
            cleaned_data["branch"] = None
            return cleaned_data

        if not branch:
            raise ValidationError("Branch is required for this user.")
        if warehouse:
            raise ValidationError(
                "Only Warehouse Managers can be assigned a warehouse."
            )
        if purchaser_branches:
            raise ValidationError("Only Purchasers can be assigned purchaser branches.")

        return cleaned_data

    def save(self, commit=True):
        user = super().save(commit=commit)

        def apply_relations():
            group = self.cleaned_data.get("role_group")
            if group:
                user.groups.set([group])
            else:
                user.groups.clear()

            if group and group.name == PURCHASER_GROUP:
                selected_ids = set(
                    self.cleaned_data["purchaser_branches"].values_list("pk", flat=True)
                )
                if user.branch_id:
                    selected_ids.add(user.branch_id)
                user.purchaser_branches.set(selected_ids)
            else:
                user.purchaser_branches.clear()

        if commit:
            apply_relations()
        else:
            old_save_m2m = self.save_m2m

            def save_m2m():
                old_save_m2m()
                apply_relations()

            self.save_m2m = save_m2m
        return user


class AdminUserChangeForm(UserChangeForm):
    password = None

    role_group = forms.ModelChoiceField(
        queryset=Group.objects.all(),
        required=False,
        label="Role group",
    )

    class Meta:
        model = User
        fields = (
            "username",
            "phone",
            "branch",
            "purchaser_branches",
            "warehouse",
            "first_name",
            "last_name",
            "email",
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            group = self.instance.groups.first()
            if group and "role_group" in self.fields:
                self.fields["role_group"].initial = group

    def clean(self):
        cleaned_data = super().clean()
        group = cleaned_data.get("role_group")
        branch = cleaned_data.get("branch")
        purchaser_branches = cleaned_data.get("purchaser_branches")
        warehouse = cleaned_data.get("warehouse")

        is_admin = (group and group.name == ADMIN_GROUP) or (
            self.instance and self.instance.is_superuser
        )
        is_warehouse_manager = group and group.name == WAREHOUSE_GROUP
        is_purchaser = group and group.name == PURCHASER_GROUP

        if is_admin:
            if branch or warehouse or purchaser_branches:
                raise ValidationError(
                    "Admins must not be assigned to branch, purchaser branches, or warehouse."
                )
            return cleaned_data

        if is_warehouse_manager:
            if branch or purchaser_branches:
                raise ValidationError(
                    "Warehouse Managers must not be assigned to branch or purchaser branches."
                )
            if not warehouse:
                raise ValidationError(
                    "Warehouse Managers must be assigned a warehouse."
                )
            return cleaned_data

        if is_purchaser:
            if warehouse:
                raise ValidationError("Purchasers must not be assigned a warehouse.")

            if (not purchaser_branches or purchaser_branches.count() == 0) and branch:
                purchaser_branches = Branch.objects.filter(pk=branch.pk)
                cleaned_data["purchaser_branches"] = purchaser_branches

            if not purchaser_branches or purchaser_branches.count() == 0:
                raise ValidationError(
                    "Purchasers must have at least one assigned purchaser branch."
                )
            cleaned_data["branch"] = None
            return cleaned_data

        if not branch:
            raise ValidationError("Branch is required for this user.")
        if warehouse:
            raise ValidationError(
                "Only Warehouse Managers can be assigned a warehouse."
            )
        if purchaser_branches:
            raise ValidationError("Only Purchasers can be assigned purchaser branches.")

        return cleaned_data

    def save(self, commit=True):
        user = super().save(commit=commit)

        def apply_relations():
            group = self.cleaned_data.get("role_group")
            if group:
                user.groups.set([group])
            else:
                user.groups.clear()

            if group and group.name == PURCHASER_GROUP:
                selected_ids = set(
                    self.cleaned_data["purchaser_branches"].values_list("pk", flat=True)
                )
                if user.branch_id:
                    selected_ids.add(user.branch_id)
                user.purchaser_branches.set(selected_ids)
            else:
                user.purchaser_branches.clear()

        if commit:
            apply_relations()
        else:
            old_save_m2m = self.save_m2m

            def save_m2m():
                old_save_m2m()
                apply_relations()

            self.save_m2m = save_m2m
        return user


class GroupAdminForm(forms.ModelForm):
    class Meta:
        model = Group
        fields = ("name", "permissions")
        widgets = {
            "permissions": PermissionGridWidget,
        }
