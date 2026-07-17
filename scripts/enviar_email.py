#!/usr/bin/env python3
"""
enviar_email.py | v1.0.0
Notifica por email (Resend) que um post foi publicado.
Env: RESEND_API_KEY, MAIL_TO, POST_TITLE, POST_URL.
Sem chave -> não faz nada (não bloqueia). Falha de envio -> non-fatal.
"""
import os, json, sys, urllib.request

key   = os.environ.get("RESEND_API_KEY", "").strip()
to    = os.environ.get("MAIL_TO", "").strip()
title = os.environ.get("POST_TITLE", "(sem título)").strip()
url   = os.environ.get("POST_URL", "").strip()

if not key or not to:
    print("email: sem RESEND_API_KEY/MAIL_TO — pulando (posts continuam publicando).")
    sys.exit(0)

html = (f"<p>Publiquei um post novo no blog da Água Mineral Campo Grande:</p>"
        f"<p><a href='{url}'>{title}</a></p>"
        f"<p>Se ler e quiser mudar algo, é só me pedir no chat.</p>")
body = json.dumps({
    "from": "Água CG Bot <onboarding@resend.dev>",
    "to": to,
    "subject": f"✅ Post publicado: {title}",
    "html": html,
}).encode()
req = urllib.request.Request("https://api.resend.com/emails", data=body, method="POST",
    headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
try:
    with urllib.request.urlopen(req, timeout=30) as r:
        print("email enviado:", r.status)
except Exception as e:
    print("email falhou (non-fatal):", e)
sys.exit(0)
