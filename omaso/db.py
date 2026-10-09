"""Lê o banco do OMASO exportado pela ferramenta ArtifactData (action list/query com out_dir).

Estrutura esperada: <dir>/txs/<id>.json e <dir>/meta/<id>.json (cada arquivo = campos do documento).
"""
import json, os, glob


def _load(path):
    with open(path, encoding='utf-8') as f:
        d = json.load(f)
    # aceita tanto o documento puro quanto {"id","data","version"}
    if isinstance(d, dict) and 'data' in d and isinstance(d['data'], dict) and set(d) <= {'id', 'data', 'version', 'updatedAt'}:
        return d['data']
    return d


class DB:
    def __init__(self, root):
        self.root = root
        self.txs = {}
        for p in glob.glob(os.path.join(root, 'txs', '*.json')):
            self.txs[os.path.splitext(os.path.basename(p))[0]] = _load(p)
        self.meta = {}
        for p in glob.glob(os.path.join(root, 'meta', '*.json')):
            self.meta[os.path.splitext(os.path.basename(p))[0]] = _load(p)

    # ---- produtores (inscrições) ----
    @property
    def ies(self):
        return (self.meta.get('ies') or {}).get('lista') or []

    def ie(self, numero=None):
        L = self.ies
        if not L:
            raise SystemExit('meta/ies está vazio: cadastre a inscrição no OMASO primeiro.')
        if numero is None:
            return L[0]
        for x in L:
            if str(x.get('ie')) == str(numero):
                return x
        raise SystemExit(f'Inscrição {numero} não está em meta/ies.')

    def ie_de(self, t):
        return str(t.get('ie') or self.ies[0]['ie'])

    def txs_da_ie(self, ie, vivos=True):
        out = []
        for i, t in self.txs.items():
            if self.ie_de(t) != str(ie):
                continue
            if vivos and t.get('excluido'):
                continue
            if not t.get('date'):
                continue
            out.append(dict(t, id=i))
        return out

    @property
    def regras(self):
        return self.meta.get('regras') or {}

    @property
    def shas(self):
        return set((self.meta.get('hashes') or {}).get('shas') or [])

    @property
    def chaves(self):
        s = set()
        for t in self.txs.values():
            for k in t.get('chaves') or []:
                s.add(k)
        for k in (self.meta.get('chaves') or {}).get('lista') or []:
            s.add(k)
        return s
