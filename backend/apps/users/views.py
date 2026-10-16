from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.throttling import ScopedRateThrottle

from .permissions import IsAuthor, IsEditor, IsReader
from .serializers import UserRegistrationSerializer, UserSerializer


class RegisterView(APIView):
    permission_classes = [permissions.AllowAny]
    def post(self, request):
        serializer = UserRegistrationSerializer(data=request.data)

        if serializer.is_valid():
            user = serializer.save()

            return Response(
                {
                    "message": "User registered successfully.",
                    "user": {
                        "id": user.id,
                        "username": user.username,
                        "email": user.email,
                        "first_name": user.first_name,
                        "last_name": user.last_name,
                        "role": user.role,
                    },
                },
                status=status.HTTP_201_CREATED,
            )

        return Response(
            serializer.errors,
            status=status.HTTP_400_BAD_REQUEST,
        )



class MeView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        serializer = UserSerializer(request.user)
        return Response(serializer.data)


class ReaderOnlyView(APIView):
    permission_classes = [IsReader]

    def get(self, request):
        return Response({"message": "Reader access granted."})


class AuthorOnlyView(APIView):
    permission_classes = [IsAuthor]

    def get(self, request):
        return Response({"message": "Author access granted."})


class EditorOnlyView(APIView):
    permission_classes = [IsEditor]

    def get(self, request):
        return Response({"message": "Editor access granted."})

class LogoutView(APIView):
    """Revoke all JWT sessions for this account, including already-issued access tokens."""
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        from django.db.models import F
        from django.contrib.auth import logout
        from .models import User
        User.objects.filter(pk=request.user.pk).update(auth_version=F('auth_version') + 1)
        logout(request)
        return Response(status=status.HTTP_204_NO_CONTENT)


class PasswordResetRequestView(APIView):
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'password_recovery'
    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    def post(self, request):
        from django.contrib.auth.tokens import default_token_generator
        from django.core.mail import send_mail
        from django.utils.encoding import force_bytes
        from django.utils.http import urlsafe_base64_encode
        from django.conf import settings
        from rest_framework import serializers
        from .models import User
        class Input(serializers.Serializer):
            email = serializers.EmailField()
        payload = Input(data=request.data)
        payload.is_valid(raise_exception=True)
        email = payload.validated_data['email']
        # Identical response for unknown and inactive accounts. Never return the
        # recovery secret through the API; delivery goes to the registered email.
        for user in User.objects.filter(email__iexact=email, is_active=True):
            if user.has_usable_password():
                uid = urlsafe_base64_encode(force_bytes(user.pk))
                token = default_token_generator.make_token(user)
                send_mail('Katiba password recovery',
                          f'Use this recovery code in your Katiba client:\nAccount reference: {uid}\nRecovery code: {token}\n'
                          'If you did not request this, ignore this message.',
                          settings.DEFAULT_FROM_EMAIL, [user.email])
        return Response({'detail': 'If an eligible account exists, recovery instructions have been sent.'})


class PasswordResetConfirmView(APIView):
    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    def post(self, request):
        from django.contrib.auth.tokens import default_token_generator
        from django.contrib.auth.password_validation import validate_password
        from django.core.exceptions import ValidationError
        from django.db import transaction
        from django.utils.http import urlsafe_base64_decode
        from rest_framework import serializers
        from .models import User
        class Input(serializers.Serializer):
            uid = serializers.CharField(max_length=100)
            token = serializers.CharField(max_length=200)
            password = serializers.CharField(min_length=8, trim_whitespace=False)
        payload = Input(data=request.data)
        payload.is_valid(raise_exception=True)
        try:
            uid = urlsafe_base64_decode(payload.validated_data['uid']).decode()
            token = payload.validated_data['token']
            with transaction.atomic():
                user = User.objects.select_for_update().get(pk=uid, is_active=True)
                if not default_token_generator.check_token(user, token):
                    raise ValueError
                password = payload.validated_data['password']
                try:
                    validate_password(password, user)
                except ValidationError as exc:
                    raise serializers.ValidationError({'password': exc.messages})
                user.set_password(password)
                user.auth_version += 1
                user.save(update_fields=['password', 'auth_version'])
        except (User.DoesNotExist, ValueError, TypeError, OverflowError, UnicodeDecodeError):
            raise serializers.ValidationError({'token': 'Invalid or expired recovery code.'})
        return Response({'detail': 'Password reset. Sign in again.'})
