"""Extrai anexos de uma mensagem do Gmail baixada em formato RAW (resultado da ferramenta get_message)."""
import base64, email, json, os, re
from email import policy


def _raw_bytes(path):
    data = open(path, 'rb').read()
    try:
        j = json.loads(data)
    except Exception:
        return data  # já é .eml
    # procura o maior texto base64 dentro do JSON
    best = ''

    def walk(x):
        nonlocal best
        if isinstance(x, dict):
            for v in x.values():
                walk(v)
        elif isinstance(x, list):
            for v in x:
                walk(v)
        elif isinstance(x, str) and len(x) > len(best):
            best = x
    walk(j)
    s = best.strip()
    if s.startswith('From ') or 'Content-Type' in s[:2000]:
        return s.encode()
    s = s.replace('-', '+').replace('_', '/')
    return base64.b64decode(s + '=' * (-len(s) % 4))


def extrair(path, out):
    msg = email.message_from_bytes(_raw_bytes(path), policy=policy.default)
    os.makedirs(out, exist_ok=True)
    res = {'assunto': str(msg.get('subject', '')), 'de': str(msg.get('from', '')), 'data': str(msg.get('date', '')), 'anexos': []}
    for part in msg.iter_attachments():
        nome = part.get_filename() or 'anexo'
        nome = re.sub(r'[\\/:*?"<>|]+', '-', nome)
        p = os.path.join(out, nome)
        i = 1
        while os.path.exists(p):
            b, e = os.path.splitext(nome); p = os.path.join(out, f'{b}_{i}{e}'); i += 1
        payload = part.get_payload(decode=True) or b''
        open(p, 'wb').write(payload)
        res['anexos'].append({'arquivo': p, 'tipo': part.get_content_type(), 'bytes': len(payload)})
    return res
