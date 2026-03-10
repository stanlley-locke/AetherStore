# apps/accounts/permissions.py
from rest_framework.permissions import BasePermission


class IsNetworkAdmin(BasePermission):
    """
    Allows access only to users who have the `is_network_admin` flag set.
    This flag is managed by the root admin wallet created via init_network_admin.py.
    """
    message = 'Access restricted to AetherNode network administrators.'

    def has_permission(self, request, view):
        return bool(
            request.user and
            request.user.is_authenticated and
            getattr(request.user, 'is_network_admin', False)
        )
