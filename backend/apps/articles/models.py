from django.db import models
from django.conf import settings
from django.utils.text import slugify

class Article(models.Model):
    # Using Django TextChoices is the cleanest, modern way to handle choice fields
    class Status(models.TextChoices):
        DRAFT = 'draft', 'Draft'
        PUBLISHED = 'published', 'Published'

    title = models.CharField(max_length=255)
    # db_index=True makes looking up articles via web links lightning fast
    slug = models.SlugField(max_length=255, unique=True, blank=True, db_index=True)
    content = models.TextField()  # Holds raw markdown data from ArticleEditor.tsx
    
    status = models.CharField(
        max_length=10, 
        choices=Status.choices, 
        default=Status.DRAFT
    )
    
    # Maps directly to your colleague's user profile identity schema
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        related_name='articles'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        # Automatically generate clean URL links from the title if missing
        if not self.slug:
            self.slug = slugify(self.title)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.title
