from django.urls import path
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from .views import (
    AuthorOnlyView,
    EditorOnlyView,
    MeView,
    ReaderOnlyView,
    RegisterView, LogoutView, PasswordResetRequestView, PasswordResetConfirmView,
)


urlpatterns = [
    path("register/", RegisterView.as_view(), name="register"),
    path("login/", TokenObtainPairView.as_view(), name="login"),
    path("token/refresh/", TokenRefreshView.as_view(), name="token-refresh"),
    path("logout/", LogoutView.as_view(), name="logout"),
    path("password-reset/", PasswordResetRequestView.as_view(), name="password-reset"),
    path("password-reset/confirm/", PasswordResetConfirmView.as_view(), name="password-reset-confirm"),
    path("me/", MeView.as_view(), name="me"),

    path("reader/", ReaderOnlyView.as_view(), name="reader"),
    path("author/", AuthorOnlyView.as_view(), name="author"),
    path("editor/", EditorOnlyView.as_view(), name="editor"),
]