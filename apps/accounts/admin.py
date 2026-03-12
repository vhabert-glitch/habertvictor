from django.contrib import admin
from .models import TeamMembership, TeamInvitation


@admin.register(TeamMembership)
class TeamMembershipAdmin(admin.ModelAdmin):
    list_display = ('user', 'role', 'joined_at')
    list_filter = ('role',)


@admin.register(TeamInvitation)
class TeamInvitationAdmin(admin.ModelAdmin):
    list_display = ('email', 'role', 'invited_by', 'created_at', 'accepted')
    list_filter = ('accepted', 'role')
