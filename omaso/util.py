"""Funções pequenas usadas em todo o motor."""
import hashlib, html, re, unicodedata

E = html.escape
MESES = ['', 'Janeiro', 'Fevereiro', 'Marco', 'Abril', 'Maio', 'Junho', 'Julho',
         'Agosto', 'Setembro', 'Outubro', 'Novembro', 'Dezembro']          # nomes de pasta (sem acento)
MESES_TXT = ['', 'Janeiro', 'Fevereiro', 'Março', 'Abril', 'Maio', 'Junho', 'Julho',
             'Agosto', 'Setembro', 'Outubro', 'Novembro', 'Dezembro']      # texto dos relatórios
ABR = ['', 'Jan', 'Fev', 'Mar', 'Abr', 'Mai', 'Jun', 'Jul', 'Ago', 'Set', 'Out', 'Nov', 'Dez']


def sem_acento(s):
    return ''.join(c for c in unicodedata.normalize('NFKD', s or '') if not unicodedata.combining(c))


def limpo(s, maxlen=60):
    """Texto seguro para nome de arquivo/pasta: sem acento, palavras unidas por hífen."""
    s = sem_acento(s)
    s = re.sub(r'[^A-Za-z0-9 .,&-]+', ' ', s)
    s = re.sub(r'\s+', ' ', s).strip().title().replace(' ', '-')
    return s[:maxlen].strip('-')


def brl(v):
    """1234.5 -> '1.234,50'"""
    v = float(v or 0)
    s = f'{abs(v):,.2f}'.replace(',', 'X').replace('.', ',').replace('X', '.')
    return ('-' if v < 0 else '') + s


def money(v):
    return '—' if not v else 'R$ ' + brl(v)


def m0(v):
    return '—' if not v else brl(v)


def pasta_mes(data):
    """'2026-03-05' -> '2026-03 Marco'"""
    return f'{data[:7]} {MESES[int(data[5:7])]}'


def sha256(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''):
            h.update(b)
    return h.hexdigest()


def tx_id(pasta):
    return 't' + hashlib.sha1(pasta.encode('utf-8')).hexdigest()[:12]


def is_idn(t):
    return t.get('kind') == 'idn' or (t.get('cat') or '').startswith('000')


def S(l):
    return sum(t.get('value') or 0 for t in l)


def H(l):
    return sum(t.get('heads') or 0 for t in l)


def notas_abertas(t):
    """Notas (pendências) ainda não marcadas como resolvidas na interface."""
    res = t.get('resolvidas') or {}
    return [n for i, n in enumerate(t.get('notes') or []) if not (res.get(n) or res.get(str(i)))]


def ativos(ts):
    """Lançamentos válidos para relatório (exclui os marcados como excluídos)."""
    return [t for t in ts if not t.get('excluido')]
