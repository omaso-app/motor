"""Extrai anexos de uma mensagem do Gmail baixada em RAW (get_message messageFormat=RAW)."""
import base64, email, json, os, re
from email import policy


def _raw(obj):
    if isinstance(obj, dict):
        for k in ('raw', 'rawContent', 'raw_message'):
            if isinstance(obj.get(k), str):
                return obj[k]
        for v in obj.values():
            r = _raw(v)
            if r:
                return r
    if isinstance(obj, list):
        for v in obj:
            r = _raw(v)
            if r:
                return r
    return None


def extrair(raw_json, out):
    """raw_json: arquivo salvo pela ferramenta (JSON com o campo raw em base64url) ou o .eml.
    Grava os anexos em `out` e devolve [{nome, caminho, tipo, bytes}]."""
    data = open(raw_json, 'rb').read()
    try:
        raw = _raw(json.loads(data))
        msgb = base64.urlsafe_b64decode(raw + '=' * (-len(raw) % 4)) if raw else data
    except (ValueError, UnicodeDecodeError):
        msgb = data
    msg = email.message_from_bytes(msgb, policy=policy.default)
    os.makedirs(out, exist_ok=True)
    res = []
    for part in msg.walk():
        fn = part.get_filename()
        if not fn or part.is_multipart():
            continue
        nome = re.sub(r'[\\/:*?"<>|]+', '_', fn).strip()
        payload = part.get_payload(decode=True) or b''
        caminho = os.path.join(out, nome)
        i = 1
        while os.path.exists(caminho):
            base, ext = os.path.splitext(nome)
            caminho = os.path.join(out, f'{base}_{i}{ext}')
            i += 1
        open(caminho, 'wb').write(payload)
        res.append({'nome': os.path.basename(caminho), 'caminho': caminho, 'tipo': part.get_content_type(), 'bytes': len(payload)})
    meta = {'assunto': str(msg.get('subject', '')), 'de': str(msg.get('from', '')), 'data': str(msg.get('date', '')), 'anexos': res}
    json.dump(meta, open(os.path.join(out, '_anexos.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    return meta
