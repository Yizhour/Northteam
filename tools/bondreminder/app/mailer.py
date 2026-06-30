import smtplib
import ssl
import threading
import time
from email import policy

from .config import DEFAULT_SMTP_HOST, DEFAULT_SMTP_TIMEOUT

_send_lock = threading.Lock()
_last_successful_send_at = 0.0
_last_successful_candidate = None
_SMTP_LOCAL_HOSTNAME = "localhost"
_SMTP_SSL_PORT = 465


class DeliveryAttemptedError(RuntimeError):
    pass


def _configured_interval():
    try:
        from .storage import load_config

        config = load_config()
        return max(30, int(config.get("send_interval_seconds", config.get("birthday_send_interval_seconds", 30)) or 30))
    except Exception:
        return 30


def _smtp_timeout():
    try:
        from .storage import load_config

        config = load_config()
        return max(3, int(config.get("smtp_timeout_seconds", DEFAULT_SMTP_TIMEOUT) or DEFAULT_SMTP_TIMEOUT))
    except Exception:
        return DEFAULT_SMTP_TIMEOUT


def _normalize_message_headers(message):
    for name, value in list(message.raw_items()):
        if not isinstance(value, str):
            message.replace_header(name, str(value))
    return message


def _unique_receivers(receivers):
    result = []
    seen = set()
    for receiver in receivers:
        email = str(receiver or "").strip()
        key = email.lower()
        if email and key not in seen:
            result.append(email)
            seen.add(key)
    return result


def _send_ssl465(host, timeout, context, sender, password, receivers, message_bytes):
    server = None
    delivery_started = False
    delivery_done = False
    try:
        server = smtplib.SMTP_SSL(
            host,
            _SMTP_SSL_PORT,
            timeout=timeout,
            context=context,
            local_hostname=_SMTP_LOCAL_HOSTNAME,
        )
        server.login(sender, password)
        delivery_started = True
        server.sendmail(sender, receivers, message_bytes)
        delivery_done = True
        try:
            server.quit()
        except Exception:
            pass
    except Exception as exc:
        if delivery_started:
            raise DeliveryAttemptedError(f"ssl:465 delivery phase failed; stopped retrying to avoid duplicate delivery: {exc}") from exc
        raise
    finally:
        if server is not None and not delivery_done:
            try:
                server.close()
            except Exception:
                pass


def send_mail(sender, password, receivers, message):
    global _last_successful_candidate, _last_successful_send_at
    receivers = _unique_receivers(receivers if isinstance(receivers, list) else [receivers])
    if not receivers:
        raise RuntimeError("收件人列表为空")

    _normalize_message_headers(message)
    message_bytes = message.as_bytes(policy=policy.SMTP)
    context = ssl.create_default_context()
    timeout = _smtp_timeout()

    with _send_lock:
        interval = _configured_interval()
        elapsed = time.monotonic() - _last_successful_send_at
        if _last_successful_send_at and elapsed < interval:
            wait_seconds = interval - elapsed
            try:
                from .logging_utils import append_log

                append_log(f"发送间隔保护：距离上次发送不足 {interval} 秒，等待 {wait_seconds:.1f} 秒。")
            except Exception:
                pass
            time.sleep(wait_seconds)

        _send_ssl465(DEFAULT_SMTP_HOST, timeout, context, sender, password, receivers, message_bytes)
        _last_successful_send_at = time.monotonic()
        _last_successful_candidate = ("ssl", _SMTP_SSL_PORT)
        return {"mode": "ssl", "port": _SMTP_SSL_PORT, "interval_seconds": interval}
