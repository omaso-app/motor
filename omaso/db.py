"""Leitura do banco do OMASO exportado pelo ArtifactData (out_dir):
<dir>/meta/<doc>.json e <dir>/txs/<id>.json."""
import glob, json, os, re


def _num(s):
    return re.sub(r'\D', '', str(s or '')).lstrip('0')


class DB:
    def __init__(self, root):
        self.root = root
        self.meta = {}
        for f in glob.glob(os.path.join(root, 'meta', '*.json')):
            self.meta[os.path.basename(f)[:-5]] = json.load(open(f, encoding='utf-8'))
        self.txs = []
        for f in sorted(glob.glob(os.path.join(root, 'txs', '*.json'))):
            t = json.load(open(f, encoding='utf-8'))
            t.setdefault('id', os.path.basename(f)[:-5])
            self.txs.append(t)

    @property
    def ies(self):
        return (self.meta.get('ies') or {}).get('lista') or []

    def ie(self, numero):
        n = _num(numero)
        for i in self.ies:
            if _num(i.get('ie')) == n:
                return i
        return None

    def ie_de(self, doc):
        """Inscrição cujo CPF/CNPJ é `doc` (primeira encontrada)."""
        d = re.sub(r'\D', '', str(doc or ''))
        for i in self.ies:
            if re.sub(r'\D', '', i.get('doc', '')) == d:
                return i
        return None

    def ie_do_tx(self, t):
        if t.get('ie'):
            return _num(t['ie'])
        if len(self.ies) == 1:
            return _num(self.ies[0]['ie'])
        top = (t.get('pasta') or '').split('/')[0]
        for i in self.ies:
            if top and (top == i.get('pasta') or i.get('pasta', '').startswith(top) or top.endswith(_num(i['ie']))):
                return _num(i['ie'])
        return ''

    def txs_da_ie(self, ie):
        n = _num(ie)
        return [t for t in self.txs if self.ie_do_tx(t) == n]

    def regras_ie(self, ie):
        r = self.meta.get('regras') or {}
        return (r.get('por_ie') or {}).get(str(ie)) or (r.get('por_ie') or {}).get(_num(ie)) or r

    @property
    def shas(self):
        return set((self.meta.get('hashes') or {}).get('shas') or [])

    @property
    def chaves(self):
        return {c for t in self.txs for c in (t.get('chaves') or [])}
