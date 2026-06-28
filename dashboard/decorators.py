"""View decorators for feature-level authorization."""

from functools import wraps

from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import PermissionDenied

from .models import FeatureAccess
from .permissions import has_feature_access


def feature_required(feature_key, action=FeatureAccess.ACTION_VIEW):
    def decorator(view_func):
        @wraps(view_func)
        def wrapped(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect_to_login(request.get_full_path())
            if has_feature_access(request.user, feature_key, action):
                return view_func(request, *args, **kwargs)
            raise PermissionDenied

        return wrapped

    return decorator
