"""Project-level error views."""

from django.shortcuts import render

from .views import base_context


def permission_denied(request, exception=None):
    context = base_context(request, '无权限')
    return render(request, 'errors/403.html', context, status=403)
