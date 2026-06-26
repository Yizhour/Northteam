"""Mount selected Flask tools inside the Django site.

The bond reminder was imported as an existing Flask application.  Keeping it
behind a WSGI bridge lets NorthTeam2 deploy as one Django/Gunicorn service
without rewriting the tool's business routes.
"""

import sys
from io import BytesIO
from pathlib import Path

from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt


BASE_DIR = Path(__file__).resolve().parent.parent
INTERNAL_TOOLS_DIR = BASE_DIR / 'tools'
BOND_REMINDER_DIR = INTERNAL_TOOLS_DIR / 'bondreminder'

if str(BOND_REMINDER_DIR) not in sys.path:
    sys.path.insert(0, str(BOND_REMINDER_DIR))

from app import create_app  # noqa: E402


bond_reminder_app = create_app()


@csrf_exempt
def bond_reminder_view(request, path=''):
    """Forward a Django request to the mounted Flask bond reminder app."""
    script_name = '/tools/bond-reminder'
    path_info = f'/{path}' if path else '/'
    body = request.body or b''

    environ = {
        'REQUEST_METHOD': request.method,
        'SCRIPT_NAME': script_name,
        'PATH_INFO': path_info,
        'QUERY_STRING': request.META.get('QUERY_STRING', ''),
        'SERVER_NAME': request.META.get('SERVER_NAME', '127.0.0.1'),
        'SERVER_PORT': request.META.get('SERVER_PORT', '80'),
        'SERVER_PROTOCOL': request.META.get('SERVER_PROTOCOL', 'HTTP/1.1'),
        'REMOTE_ADDR': request.META.get('REMOTE_ADDR', ''),
        'CONTENT_TYPE': request.META.get('CONTENT_TYPE', ''),
        'CONTENT_LENGTH': str(len(body)),
        'wsgi.version': (1, 0),
        'wsgi.url_scheme': 'https' if request.is_secure() else 'http',
        'wsgi.input': BytesIO(body),
        'wsgi.errors': sys.stderr,
        'wsgi.multithread': True,
        'wsgi.multiprocess': False,
        'wsgi.run_once': False,
    }

    for key, value in request.META.items():
        if key.startswith('HTTP_'):
            environ[key] = value

    response_meta = {}

    def start_response(status, headers, exc_info=None):
        response_meta['status'] = status
        response_meta['headers'] = headers

    response_body = b''.join(bond_reminder_app.wsgi_app(environ, start_response))
    status_code = int(response_meta.get('status', '500').split()[0])
    response = HttpResponse(response_body, status=status_code)

    for header, value in response_meta.get('headers', []):
        if header.lower() not in {'content-length'}:
            response[header] = value

    return response
