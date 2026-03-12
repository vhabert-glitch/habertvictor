from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib import messages
from django.core.mail import send_mail
from django.conf import settings
from .models import TeamMembership, TeamInvitation


@login_required
def team_view(request):
    membership = getattr(request.user, 'membership', None)
    if not membership:
        TeamMembership.objects.create(user=request.user, role='admin')
        membership = request.user.membership

    members = TeamMembership.objects.select_related('user').all()
    invitations = TeamInvitation.objects.filter(accepted=False).order_by('-created_at')

    return render(request, 'accounts/team.html', {
        'members': members,
        'invitations': invitations,
        'is_admin': membership.is_admin,
    })


@login_required
def invite_member(request):
    membership = getattr(request.user, 'membership', None)
    if not membership or not membership.is_admin:
        messages.error(request, "Seuls les administrateurs peuvent inviter des membres.")
        return redirect('accounts:team')

    if request.method == 'POST':
        email = request.POST.get('email', '').strip()
        role = request.POST.get('role', 'member')

        if not email:
            messages.error(request, "Veuillez saisir un email.")
            return redirect('accounts:team')

        if User.objects.filter(email=email).exists():
            messages.warning(request, f"{email} est déjà inscrit.")
            return redirect('accounts:team')

        invitation = TeamInvitation.objects.create(
            email=email,
            role=role,
            invited_by=request.user,
        )

        invite_url = request.build_absolute_uri(f'/accounts/join/{invitation.token}/')
        send_mail(
            subject='Invitation à rejoindre IA Formation Radar',
            message=f"Vous avez été invité(e) à rejoindre l'équipe IA Formation Radar.\n\n"
                    f"Cliquez ici pour accepter : {invite_url}",
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[email],
            fail_silently=True,
        )

        messages.success(request, f"Invitation envoyée à {email}.")
        return redirect('accounts:team')

    return redirect('accounts:team')


def accept_invitation(request, token):
    invitation = get_object_or_404(TeamInvitation, token=token, accepted=False)

    if request.user.is_authenticated:
        TeamMembership.objects.update_or_create(
            user=request.user,
            defaults={'role': invitation.role}
        )
        invitation.accepted = True
        invitation.save()
        messages.success(request, "Vous avez rejoint l'équipe !")
        return redirect('dashboard:index')

    request.session['pending_invitation'] = str(token)
    messages.info(request, "Créez un compte pour rejoindre l'équipe.")
    return redirect('account_signup')


@login_required
def remove_member(request, user_id):
    membership = getattr(request.user, 'membership', None)
    if not membership or not membership.is_admin:
        messages.error(request, "Action non autorisée.")
        return redirect('accounts:team')

    if request.method == 'POST' and user_id != request.user.id:
        TeamMembership.objects.filter(user_id=user_id).delete()
        messages.success(request, "Membre retiré de l'équipe.")

    return redirect('accounts:team')
