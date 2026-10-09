"""Funções comuns do motor OMASO (sem dados de nenhum produtor)."""
import re, unicodedata, hashlib, html

MESES = ['', 'Janeiro', 'Fevereiro', 'Marco', 'Abril', 'Maio', 'Junho', 'Julho', 'Agosto',
         'Setembro', 'Outubro', 'Novembro', 'Dezembro']
MESES_TXT = ['', 'Janeiro', 'Fevereiro', 'Março', 'Abril', 'Maio', 'Junho', 'Julho', 'Agosto',
             'Setembro', 'Outubro', 'Novembro', 'Dezembro']
ABR = ['', 'Jan', 'Fev', 'Mar', 'Abr', 'Mai', 'Jun', 'Jul', 'Ago', 'Set', 'Out', 'Nov', 'Dez']
E = html.escape


def sem_acento(s):
    return unicodedata.normalize('NFKD', s or '').encode('ascii', 'ignore').decode()


def limpo(s, n=60):
    """Texto seguro para nome de pasta/arquivo: sem acento, sem símbolos."""
    s = sem_acento(s)
    s = re.sub(r'[^A-Za-z0-9\.,\-_ $]+', ' ', s).strip()
    s = re.sub(r'\s+', '-', s)
    return s[:n].strip('-')


def brl(v):
    if v is None:
        return ''
    s = f"{abs(v):,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
    return ('-' if v < 0 else '') + s


def money(v):
    return '—' if not v else 'R$ ' + brl(v)


def m0(v):
    return '—' if not v else brl(v)


def pasta_mes(date):
    y, m, _ = date.split('-')
    return f"{y}-{m} {MESES[int(m)]}"


def sha256(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for b in iter(lambda: f.read(1 << 16), b''):
            h.update(b)
    return h.hexdigest()


def is_idn(t):
    return t.get('kind') == 'idn' or (t.get('cat') or '').startswith('000')


def S(l):
    return sum(t.get('value') or 0 for t in l)


def H(l):
    return sum(t.get('heads') or 0 for t in l)


def notas_abertas(t):
    res = t.get('resolvidas') or {}
    return [n for i, n in enumerate(t.get('notes') or []) if str(i) not in res and i not in res]
