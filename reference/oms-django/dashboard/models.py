from django.db import models
from django.conf import settings


class Notice(models.Model):
    title = models.CharField(max_length=200, verbose_name='제목')
    content = models.TextField(verbose_name='내용')
    is_pinned = models.BooleanField(default=False, verbose_name='상단 고정')
    is_active = models.BooleanField(default=True, verbose_name='활성')
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, verbose_name='작성자'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-is_pinned', '-created_at']
        verbose_name = '공지사항'
        verbose_name_plural = '공지사항'

    def __str__(self):
        return self.title


class Notification(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='notifications', verbose_name='수신자'
    )
    message = models.CharField(max_length=300, verbose_name='메시지')
    link = models.CharField(max_length=200, blank=True, verbose_name='링크')
    is_read = models.BooleanField(default=False, verbose_name='읽음')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = '알림'
        verbose_name_plural = '알림'

    def __str__(self):
        return self.message
