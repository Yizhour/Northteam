"""Authentication helpers."""

from django.contrib.auth.views import LoginView


class WorkspaceLoginView(LoginView):
    template_name = 'registration/login.html'
    redirect_authenticated_user = True
