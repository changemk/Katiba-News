from django.db import models
from django.conf import settings
from django.utils.text import slugify

class BlogPost(models.Model):
    title = models.CharField(max_length=255)
    # db_index=True makes looking up blog posts via web URLs lightning-fast
    slug = models.SlugField(max_length=255, unique=True, blank=True, db_index=True)
    content = models.TextField()  # Holds the blog post text body from your UI editor
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='blog_posts'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.title


class Comment(models.Model):
    post = models.ForeignKey(
        BlogPost,
        on_delete=models.CASCADE,
        related_name='comments'
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='blog_comments'
    )
    content = models.TextField()  # Holds the text a citizen types into BlogView.tsx
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Comment by {self.user.username} on {self.post.title}"


class Like(models.Model):
    post = models.ForeignKey(
        BlogPost,
        on_delete=models.CASCADE,
        related_name='likes'
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='blog_likes'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        # Prevents a single user from clicking 'Like' multiple times on the same post
        unique_together = ('post', 'user')

    def __str__(self):
        return f"{self.user.username} liked {self.post.title}"
