# core/permissions.py

from typing import Any

from django.contrib.auth import get_user_model
from rest_framework.permissions import BasePermission, SAFE_METHODS

User = get_user_model()


def _is_admin(user: User) -> bool:
    """
    Утилита: определение админа по суперпользователю или роли.
    """
    if not user.is_authenticated:
        return False

    role_cls = getattr(User, "Role", None)
    admin_value = None
    if role_cls is not None:
        admin_value = getattr(role_cls, "ADMIN", None)

    if admin_value is not None:
        return bool(user.is_superuser or getattr(user, "role", "") == admin_value)

    return bool(user.is_superuser or getattr(user, "is_staff", False))


class IsAdminOrReadOnly(BasePermission):
    """
    Разрешает только администраторам изменять данные, остальным — только чтение.
    """

    def has_permission(self, request, view) -> bool:
        if request.method in SAFE_METHODS:
            return True
        user: User = request.user
        return _is_admin(user)


class IsSelfOrAdmin(BasePermission):
    """
    Доступ к объекту пользователя: либо сам пользователь, либо админ.
    """

    def has_object_permission(self, request, view, obj: Any) -> bool:
        user: User = request.user
        if not user.is_authenticated:
            return False
        if _is_admin(user):
            return True
        return getattr(obj, "pk", None) == getattr(user, "pk", None)


class IsOwnerObject(BasePermission):
    """
    Доступ к объектам, у которых есть атрибут owner: только владелец или админ.
    """

    def has_object_permission(self, request, view, obj: Any) -> bool:
        user: User = request.user
        if not user.is_authenticated:
            return False
        if _is_admin(user):
            return True
        owner = getattr(obj, "owner", None)
        return owner == user
