    response = response or self.get_response(request)
                           ^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/opt/render/project/src/.venv/lib/python3.12/site-packages/django/core/handlers/exception.py", line 55, in inner
    response = get_response(request)
               ^^^^^^^^^^^^^^^^^^^^^
  File "/opt/render/project/src/.venv/lib/python3.12/site-packages/django/utils/deprecation.py", line 120, in __call__
    response = response or self.get_response(request)
                           ^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/opt/render/project/src/.venv/lib/python3.12/site-packages/django/core/handlers/exception.py", line 55, in inner
    response = get_response(request)
               ^^^^^^^^^^^^^^^^^^^^^
  File "/opt/render/project/src/.venv/lib/python3.12/site-packages/django/utils/deprecation.py", line 120, in __call__
    response = response or self.get_response(request)
                           ^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/opt/render/project/src/.venv/lib/python3.12/site-packages/django/core/handlers/exception.py", line 55, in inner
    response = get_response(request)
               ^^^^^^^^^^^^^^^^^^^^^
  File "/opt/render/project/src/.venv/lib/python3.12/site-packages/django/utils/deprecation.py", line 120, in __call__
    response = response or self.get_response(request)
                           ^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/opt/render/project/src/.venv/lib/python3.12/site-packages/django/core/handlers/exception.py", line 55, in inner
    response = get_response(request)
               ^^^^^^^^^^^^^^^^^^^^^
  File "/opt/render/project/src/.venv/lib/python3.12/site-packages/django/utils/deprecation.py", line 120, in __call__
    response = response or self.get_response(request)
                           ^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/opt/render/project/src/.venv/lib/python3.12/site-packages/django/core/handlers/exception.py", line 55, in inner
    response = get_response(request)
               ^^^^^^^^^^^^^^^^^^^^^
  File "/opt/render/project/src/.venv/lib/python3.12/site-packages/django/utils/deprecation.py", line 120, in __call__
    response = response or self.get_response(request)
                           ^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/opt/render/project/src/.venv/lib/python3.12/site-packages/django/core/handlers/exception.py", line 55, in inner
    response = get_response(request)
               ^^^^^^^^^^^^^^^^^^^^^
  File "/opt/render/project/src/.venv/lib/python3.12/site-packages/django/core/handlers/base.py", line 197, in _get_response
    response = wrapped_callback(request, *callback_args, **callback_kwargs)
               ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/opt/render/project/src/.venv/lib/python3.12/site-packages/django/contrib/auth/decorators.py", line 59, in _view_wrapper
    return view_func(request, *args, **kwargs)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/opt/render/project/src/.venv/lib/python3.12/site-packages/django/contrib/auth/decorators.py", line 59, in _view_wrapper
    return view_func(request, *args, **kwargs)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/opt/render/project/src/adminpanel/views.py", line 2569, in crm
    return render(request, 'adminpanel/crm/crm.html', build_crm_logic_context(request, tab))
                                                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/opt/render/project/src/adminpanel/crm_logic.py", line 420, in build_context
    send_dean_alert_email_once(request, alerts)
  File "/opt/render/project/src/adminpanel/crm_logic.py", line 272, in send_dean_alert_email_once
    send_mail(
  File "/opt/render/project/src/.venv/lib/python3.12/site-packages/django/core/mail/__init__.py", line 92, in send_mail
    return mail.send()
           ^^^^^^^^^^^
  File "/opt/render/project/src/.venv/lib/python3.12/site-packages/django/core/mail/message.py", line 307, in send
127.0.0.1 - - [26/May/2026:19:49:11 +0200] "GET /adminpanel/crm/centres/ HTTP/1.1" 500 0 "-" "-"
    return self.get_connection(fail_silently).send_messages([self])
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/opt/render/project/src/.venv/lib/python3.12/site-packages/django/core/mail/backends/smtp.py", line 128, in send_messages
    new_conn_created = self.open()
                       ^^^^^^^^^^^
  File "/opt/render/project/src/.venv/lib/python3.12/site-packages/django/core/mail/backends/smtp.py", line 86, in open
Menu
    self.connection = self.connection_class(
                      ^^^^^^^^^^^^^^^^^^^^^^
  File "/opt/render/project/python/Python-3.12.4/lib/python3.12/smtplib.py", line 255, in __init__
    (code, msg) = self.connect(host, port)
                  ^^^^^^^^^^^^^^^^^^^^^^^^
  File "/opt/render/project/python/Python-3.12.4/lib/python3.12/smtplib.py", line 341, in connect
    self.sock = self._get_socket(host, port, self.timeout)
                ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/opt/render/project/python/Python-3.12.4/lib/python3.12/smtplib.py", line 312, in _get_socket
    return socket.create_connection((host, port), timeout,
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/opt/render/project/python/Python-3.12.4/lib/python3.12/socket.py", line 838, in create_connection
    sock.connect(sa)
  File "/opt/render/project/src/.venv/lib/python3.12/site-packages/gunicorn/workers/base.py", line 204, in handle_abort
    sys.exit(1)
SystemExit: 1
[2026-05-26 19:49:11 +0200] [66] [INFO] Worker exiting (pid: 66)
[2026-05-26 19:49:12 +0200] [56] [ERROR] Worker (pid:66) was sent SIGKILL! Perhaps out of memory?
[2026-05-26 19:49:12 +0200] [74] [INFO] Booting worker with pid: 74
127.0.0.1 - - [26/May/2026:19:49:29 +0200] "GET /adminpanel/admin_kanban/ HTTP/1.1" 200 58025 "https://projectmanagementapp-finalboss.onrender.com/overview/" "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36 Edg/148.0.0.0"
127.0.0.1 - - [26/May/2026:19:49:29 +0200] "GET /static/img/logo_uj-removebg-preview.png HTTP/1.1" 304 0 "https://projectmanagementapp-finalboss.onrender.com/adminpanel/admin_kanban/" "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36 Edg/148.0.0.0"
127.0.0.1 - - [26/May/2026:19:49:29 +0200] "GET /static/css/style.css HTTP/1.1" 304 0 "https://projectmanagementapp-finalboss.onrender.com/adminpanel/admin_kanban/" "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36 Edg/148.0.0.0"
127.0.0.1 - - [26/May/2026:19:49:29 +0200] "GET /static/js/dashboard.js HTTP/1.1" 304 0 "https://projectmanagementapp-finalboss.onrender.com/adminpanel/admin_kanban/" "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36 Edg/148.0.0.0"
127.0.0.1 - - [26/May/2026:19:49:29 +0200] "GET /static/js/table-tooltips.js HTTP/1.1" 304 0 "https://projectmanagementapp-finalboss.onrender.com/adminpanel/admin_kanban/" "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36 Edg/148.0.0.0"
127.0.0.1 - - [26/May/2026:19:49:30 +0200] "GET /static/img/freepik__upload__83338.png HTTP/1.1" 304 0 "https://projectmanagementapp-finalboss.onrender.com/adminpanel/admin_kanban/" "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36 Edg/148.0.0.0"
127.0.0.1 - - [26/May/2026:19:49:30 +0200] "GET /static/img/2.png HTTP/1.1" 304 0 "https://projectmanagementapp-finalboss.onrender.com/adminpanel/admin_kanban/" "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36 Edg/148.0.0.0"
[2026-05-26 19:50:06 +0200] [56] [CRITICAL] WORKER TIMEOUT (pid:74)
[2026-05-26 19:50:06 +0200] [74] [ERROR] Error handling request /adminpanel/crm/reports/
Traceback (most recent call last):
  File "/opt/render/project/src/.venv/lib/python3.12/site-packages/gunicorn/workers/sync.py", line 134, in handle
    self.handle_request(listener, req, client, addr)
  File "/opt/render/project/src/.venv/lib/python3.12/site-packages/gunicorn/workers/sync.py", line 177, in handle_request
    respiter = self.wsgi(environ, resp.start_response)
               ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/opt/render/project/src/.venv/lib/python3.12/site-packages/django/core/handlers/wsgi.py", line 124, in __call__
    response = self.get_response(request)
               ^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/opt/render/project/src/.venv/lib/python3.12/site-packages/django/core/handlers/base.py", line 140, in get_response
    response = self._middleware_chain(request)
               ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/opt/render/project/src/.venv/lib/python3.12/site-packages/django/core/handlers/exception.py", line 55, in inner
    response = get_response(request)
               ^^^^^^^^^^^^^^^^^^^^^
  File "/opt/render/project/src/.venv/lib/python3.12/site-packages/django/utils/deprecation.py", line 120, in __call__
    response = response or self.get_response(request)
                           ^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/opt/render/project/src/.venv/lib/python3.12/site-packages/django/core/handlers/exception.py", line 55, in inner
    response = get_response(request)
               ^^^^^^^^^^^^^^^^^^^^^
  File "/opt/render/project/src/.venv/lib/python3.12/site-packages/whitenoise/middleware.py", line 123, in __call__
    return self.get_response(request)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/opt/render/project/src/.venv/lib/python3.12/site-packages/django/core/handlers/exception.py", line 55, in inner
    response = get_response(request)
               ^^^^^^^^^^^^^^^^^^^^^
  File "/opt/render/project/src/.venv/lib/python3.12/site-packages/django/utils/deprecation.py", line 120, in __call__
    response = response or self.get_response(request)
                           ^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/opt/render/project/src/.venv/lib/python3.12/site-packages/django/core/handlers/exception.py", line 55, in inner
    response = get_response(request)
               ^^^^^^^^^^^^^^^^^^^^^
  File "/opt/render/project/src/.venv/lib/python3.12/site-packages/django/utils/deprecation.py", line 120, in __call__
    response = response or self.get_response(request)
                           ^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/opt/render/project/src/.venv/lib/python3.12/site-packages/django/core/handlers/exception.py", line 55, in inner
    response = get_response(request)
               ^^^^^^^^^^^^^^^^^^^^^
  File "/opt/render/project/src/.venv/lib/python3.12/site-packages/django/utils/deprecation.py", line 120, in __call__
    response = response or self.get_response(request)
                           ^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/opt/render/project/src/.venv/lib/python3.12/site-packages/django/core/handlers/exception.py", line 55, in inner
    response = get_response(request)
               ^^^^^^^^^^^^^^^^^^^^^
  File "/opt/render/project/src/.venv/lib/python3.12/site-packages/django/utils/deprecation.py", line 120, in __call__
    response = response or self.get_response(request)
                           ^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/opt/render/project/src/.venv/lib/python3.12/site-packages/django/core/handlers/exception.py", line 55, in inner
    response = get_response(request)
               ^^^^^^^^^^^^^^^^^^^^^
  File "/opt/render/project/src/.venv/lib/python3.12/site-packages/django/utils/deprecation.py", line 120, in __call__
    response = response or self.get_response(request)
                           ^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/opt/render/project/src/.venv/lib/python3.12/site-packages/django/core/handlers/exception.py", line 55, in inner
    response = get_response(request)
               ^^^^^^^^^^^^^^^^^^^^^
  File "/opt/render/project/src/.venv/lib/python3.12/site-packages/django/utils/deprecation.py", line 120, in __call__
    response = response or self.get_response(request)
                           ^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/opt/render/project/src/.venv/lib/python3.12/site-packages/django/core/handlers/exception.py", line 55, in inner
    response = get_response(request)
               ^^^^^^^^^^^^^^^^^^^^^
  File "/opt/render/project/src/.venv/lib/python3.12/site-packages/django/core/handlers/base.py", line 197, in _get_response
    response = wrapped_callback(request, *callback_args, **callback_kwargs)
               ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/opt/render/project/src/.venv/lib/python3.12/site-packages/django/contrib/auth/decorators.py", line 59, in _view_wrapper
    return view_func(request, *args, **kwargs)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/opt/render/project/src/.venv/lib/python3.12/site-packages/django/contrib/auth/decorators.py", line 59, in _view_wrapper
    return view_func(request, *args, **kwargs)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/opt/render/project/src/adminpanel/views.py", line 2569, in crm
    return render(request, 'adminpanel/crm/crm.html', build_crm_logic_context(request, tab))
                                                      ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/opt/render/project/src/adminpanel/crm_logic.py", line 420, in build_context
    send_dean_alert_email_once(request, alerts)
  File "/opt/render/project/src/adminpanel/crm_logic.py", line 272, in send_dean_alert_email_once
    send_mail(
  File "/opt/render/project/src/.venv/lib/python3.12/site-packages/django/core/mail/__init__.py", line 92, in send_mail
    return mail.send()
           ^^^^^^^^^^^
  File "/opt/render/project/src/.venv/lib/python3.12/site-packages/django/core/mail/message.py", line 307, in send
    return self.get_connection(fail_silently).send_messages([self])
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/opt/render/project/src/.venv/lib/python3.12/site-packages/django/core/mail/backends/smtp.py", line 128, in send_messages
    new_conn_created = self.open()
                       ^^^^^^^^^^^
  File "/opt/render/project/src/.venv/lib/python3.12/site-packages/django/core/mail/backends/smtp.py", line 86, in open
    self.connection = self.connection_class(
                      ^^^^^^^^^^^^^^^^^^^^^^
  File "/opt/render/project/python/Python-3.12.4/lib/python3.12/smtplib.py", line 255, in __init__
    (code, msg) = self.connect(host, port)
                  ^^^^^^^^^^^^^^^^^^^^^^^^
  File "/opt/render/project/python/Python-3.12.4/lib/python3.12/smtplib.py", line 341, in connect
    self.sock = self._get_socket(host, port, self.timeout)
                ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/opt/render/project/python/Python-3.12.4/lib/python3.12/smtplib.py", line 312, in _get_socket
    return socket.create_connection((host, port), timeout,
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/opt/render/project/python/Python-3.12.4/lib/python3.12/socket.py", line 838, in create_connection
    sock.connect(sa)
  File "/opt/render/project/src/.venv/lib/python3.12/site-packages/gunicorn/workers/base.py", line 204, in handle_abort
    sys.exit(1)
SystemExit: 1
127.0.0.1 - - [26/May/2026:19:50:06 +0200] "GET /adminpanel/crm/reports/ HTTP/1.1" 500 0 "-" "-"
[2026-05-26 19:50:06 +0200] [74] [INFO] Worker exiting (pid: 74)
[2026-05-26 19:50:07 +0200] [56] [ERROR] Worker (pid:74) was sent SIGKILL! Perhaps out of memory?
[2026-05-26 19:50:07 +0200] [82] [INFO] Booting worker with pid: 82
127.0.0.1 - - [26/May/2026:19:50:53 +0200] "HEAD /users/login/ HTTP/1.1" 200 5097 "https://projectmanagementapp-finalboss.onrender.com/users/login/" "Mozilla/5.0+(compatible; UptimeRobot/2.0; http://www.uptimerobot.com/)"