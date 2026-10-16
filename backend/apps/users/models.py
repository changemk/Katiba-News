from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    class Role(models.TextChoices):
        READER = "READER", "Reader"
        AUTHOR = "AUTHOR", "Author"
        EDITOR = "EDITOR", "Editor"

    auth_version = models.PositiveIntegerField(default=0, editable=False)
    email = models.EmailField(unique=True)
    # Retained for migration compatibility only; never used for authorization.
    role = models.CharField(
        max_length=20,
        choices=Role.choices,
        default=Role.READER,
    )

    def __str__(self):
        return self.username
