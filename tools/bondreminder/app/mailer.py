import smtplib
import ssl
import threading
import time
from email import policy

from .config import (
    DEFAULT_SMTP_ALT_SSL_PORT,
    DEFAULT_SMTP_HOST,
    DEFAULT_SMTP_PORT,
    DEFAULT_SMTP_STARTTLS_PORT,
    DEFAULT_SMTP_TIMEOUT,
)

_send_lock = threading.Lock()
_last_successful_send_at = 0.0
_last_successful_candidate = None
_SMTP_LOCAL_HOSTNAME = "localhost"


def _configured_interval():
    try:
        from .storage import load_config

        config = load_config()
        return max(30, int(config.get("send_interval_seconds", config.get("birthday_send_interval_seconds", 30)) or 30))
    except Exception:
        return 30


def _smtp_settings():
    try:
        from .storage import load_config

        config = load_config()
        return {
            "preferred": config.get("smtp_preferred_mode", "auto"),
            "timeout": max(3, int(config.get("smtp_timeout_seconds", DEFAULT_SMTP_TIMEOUT) or DEFAULT_SMTP_TIMEOUT)),
        }
    except Exception:
        return {"preferred": "auto", "timeout": DEFAULT_SMTP_TIMEOUT}


def _candidate_for_preference(preferred):
    return {
        "ssl465": ("ssl", 465),
        "ssl994": ("ssl", DEFAULT_SMTP_ALT_SSL_PORT),
        "starttls587": ("starttls", DEFAULT_SMTP_STARTTLS_PORT),
    }.get(preferred)


def _normalize_message_headers(message):
    for name, value in list(message.raw_items()):
        if not isinstance(value, str):
            message.replace_header(name, str(value))
    return message


def send_mail(sender, password, receivers, message):
    global _last_successful_candidate, _last_successful_send_at
    receivers = receivers if isinstance(receivers, list) else [receivers]
    host = DEFAULT_SMTP_HOST
    port = int(DEFAULT_SMTP_PORT)
    context = ssl.create_default_context()
    errors = []
    settings = _smtp_settings()
    timeout = settings["timeout"]
    _normalize_message_headers(message)
    message_bytes = message.as_bytes(policy=policy.SMTP)

    candidates = []
    if port == 465:
        candidates.append(("ssl", port))
        candidates.append(("ssl", DEFAULT_SMTP_ALT_SSL_PORT))
        candidates.append(("starttls", DEFAULT_SMTP_STARTTLS_PORT))
    else:
        candidates.append(("starttls", port))
        candidates.append(("ssl", 465))
        candidates.append(("ssl", DEFAULT_SMTP_ALT_SSL_PORT))
    preferred_candidate = _candidate_for_preference(settings["preferred"])
    if preferred_candidate in candidates:
        candidates.remove(preferred_candidate)
        candidates.insert(0, preferred_candidate)
    elif settings["preferred"] == "auto" and _last_successful_candidate in candidates:
        candidates.remove(_last_successful_candidate)
        candidates.insert(0, _last_successful_candidate)

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

        for mode, candidate_port in candidates:
            try:
                if mode == "ssl":
                    with smtplib.SMTP_SSL(
                        host,
                        candidate_port,
                        timeout=timeout,
                        context=context,
                        local_hostname=_SMTP_LOCAL_HOSTNAME,
                    ) as server:
                        server.login(sender, password)
                        server.sendmail(sender, receivers, message_bytes)
                else:
                    with smtplib.SMTP(host, candidate_port, timeout=timeout, local_hostname=_SMTP_LOCAL_HOSTNAME) as server:
                        server.ehlo()
                        server.starttls(context=context)
                        server.ehlo()
                        server.login(sender, password)
                        server.sendmail(sender, receivers, message_bytes)
                _last_successful_send_at = time.monotonic()
                _last_successful_candidate = (mode, candidate_port)
                return {"mode": mode, "port": candidate_port, "interval_seconds": interval}
            except Exception as exc:
                errors.append(f"{mode}:{candidate_port} {exc}")
    raise RuntimeError("; ".join(errors))
