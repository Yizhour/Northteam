"""Custom administrative screens for NorthTeam2."""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect, render

from .models import FeatureAccess
from .permissions import (
    ACTION_LABELS,
    ACTION_ORDER,
    ROLE_LABELS,
    ROLE_ORDER,
    features_for_user,
    has_feature_access,
    is_super_admin,
    sync_default_permissions,
)


@login_required
def access_control(request):
    if not is_super_admin(request.user):
        raise PermissionDenied

    sync_default_permissions()

    if request.method == 'POST':
        for access in FeatureAccess.objects.select_related('feature'):
            checkbox_name = f'access_{access.feature_id}_{access.role}_{access.action}'
            access.allowed = checkbox_name in request.POST
            access.save(update_fields=['allowed'])
        messages.success(request, '权限配置已保存。')
        return redirect('access_control')

    features = features_for_user(request.user)
    access_map = {
        (item.feature_id, item.role, item.action): item.allowed
        for item in FeatureAccess.objects.select_related('feature')
    }
    rows = []
    for feature in features:
        cells = []
        for role in ROLE_ORDER:
            actions = []
            for action in ACTION_ORDER:
                actions.append(
                    {
                        'name': f'access_{feature.id}_{role}_{action}',
                        'label': ACTION_LABELS[action],
                        'checked': access_map.get((feature.id, role, action), False),
                    }
                )
            cells.append({'role': ROLE_LABELS[role], 'actions': actions})
        rows.append({'feature': feature, 'cells': cells})

    return render(
        request,
        'admin/access_control.html',
        {
            'title': '权限控制台',
            'rows': rows,
            'roles': [ROLE_LABELS[role] for role in ROLE_ORDER],
        },
    )
