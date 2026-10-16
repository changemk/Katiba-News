"""Expose the sourcing API alongside the existing admin and user routes."""
from django.urls import include, path
from katiba_news.urls import urlpatterns as project_patterns

urlpatterns = [*project_patterns, path('api/news/', include('apps.news.urls'))]
