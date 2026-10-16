from rest_framework import serializers
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.contrib.auth.models import Group
from django.db import transaction
from .access import READER

from .models import User


class UserRegistrationSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8, trim_whitespace=False)

    class Meta:
        model = User
        fields = (
            "username",
            "email",
            "password",
            "first_name",
            "last_name",
            "role",
        )

    def validate_role(self, role):
        # Newsroom privileges are granted by administrators, never public signup.
        if role != User.Role.READER:
            raise serializers.ValidationError('Newsroom roles must be assigned by an administrator.')
        return role

    def validate(self, attrs):
        candidate = User(**{key: value for key, value in attrs.items() if key != 'password'})
        try:
            validate_password(attrs['password'], candidate)
        except ValidationError as exc:
            raise serializers.ValidationError({'password': exc.messages})
        return attrs

    @transaction.atomic
    def create(self, validated_data):
        password = validated_data.pop("password")
        validated_data["role"] = User.Role.READER
        user = User(**validated_data)
        user.set_password(password)
        user.save()
        user.groups.add(Group.objects.get_or_create(name=READER)[0])
        return user


class UserSerializer(serializers.ModelSerializer):
    groups = serializers.SlugRelatedField(many=True, read_only=True, slug_field='name')
    permissions = serializers.SerializerMethodField()

    def get_permissions(self, user):
        return sorted(user.get_all_permissions()) if user.is_active else []

    class Meta:
        model = User
        fields = (
            "groups",
            "permissions",
            "id",
            "username",
            "email",
            "first_name",
            "last_name",
            "role",
        )