from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    # Master Django Admin Control Room Panel
    path("admin/", admin.site.urls),
    
    # Colleague's Authentication API App
    path("api/users/", include("apps.users.urls")),
    
    # YOUR APPS: Formal News & Community Blog Systems
    path("api/articles/", include("apps.articles.urls")),
    path("api/blogs/", include("apps.blogs.urls")),
]
