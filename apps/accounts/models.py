import uuid
from django.db import models
from django.conf import settings


class TeamMembership(models.Model):
    ROLE_CHOICES = [
        ('admin', 'Administrateur'),
        ('member', 'Membre'),
    ]

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='membership'
    )
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default='member')
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Membre d\'équipe'
        verbose_name_plural = 'Membres d\'équipe'

    def __str__(self):
        return f"{self.user.email} ({self.get_role_display()})"

    @property
    def is_admin(self):
        return self.role == 'admin'


class TeamInvitation(models.Model):
    email = models.EmailField()
    role = models.CharField(max_length=10, choices=TeamMembership.ROLE_CHOICES, default='member')
    token = models.UUIDField(default=uuid.uuid4, unique=True)
    invited_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='sent_invitations'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    accepted = models.BooleanField(default=False)

    class Meta:
        verbose_name = 'Invitation'

    def __str__(self):
        return f"Invitation pour {self.email}"
