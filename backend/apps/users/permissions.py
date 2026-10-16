from rest_framework.permissions import BasePermission
from .access import has_news_permission, eligible_author, READER


class IsReader(BasePermission):
    def has_permission(self, request, view):
        user = request.user
        return bool(user.is_authenticated and user.is_active and user.groups.filter(name=READER).exists())


class IsAuthor(BasePermission):
    def has_permission(self, request, view):
        return bool(request.user.is_authenticated and eligible_author(request.user))


class IsEditor(BasePermission):
    def has_permission(self, request, view):
        return has_news_permission(request.user, 'review_lead')
