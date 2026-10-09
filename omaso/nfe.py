"""Leitura de XML de NF-e / NFA-e e de eventos (cancelamento)."""
import re
import xml.etree.ElementTree as ET

NS = '{http://www.portalfiscal.inf.br/nfe}'


def _p(path):
    return '/'.join(NS + p if p and not p.startswith('.') else p for p in path.split('/'))


def _t(el, path):
    if el is None:
        return ''
    x = el.find(_p(path))
    return x.text.strip() if x is not None and x.text else ''


def ler(path):
    """Devolve um dicionário com os dados principais, ou {'tipo':'desconhecido'}."""
    raw = open(path, 'rb').read().decode('utf-8', 'ignore').lstrip('\ufeff')
    try:
        root = ET.fromstring(raw)
    except ET.ParseError:
        return {'tipo': 'desconhecido', 'arquivo': path}
    tag = root.tag.replace(NS, '')
    # ---- evento (cancelamento, carta de correção) ----
    if 'Evento' in tag or root.find('.//' + NS + 'infEvento') is not None:
        ev = root.find('.//' + NS + 'infEvento')
        if ev is not None:
            return {
                'tipo': 'evento',
                'tpEvento': _t(ev, 'tpEvento'),
                'chave': _t(ev, 'chNFe'),
                'data': (_t(ev, 'dhEvento') or '')[:10],
                'descricao': _t(ev, 'detEvento/descEvento'),
                'arquivo': path,
            }
    inf = root.find('.//' + NS + 'infNFe')
    if inf is None:
        return {'tipo': 'desconhecido', 'arquivo': path}
    chave = (inf.get('Id') or '').replace('NFe', '')
    ide = inf.find(NS + 'ide')
    emit = inf.find(NS + 'emit')
    dest = inf.find(NS + 'dest')
    tot = inf.find(_p('total/ICMSTot'))
    prods = []
    for det in inf.findall(NS + 'det'):
        p = det.find(NS + 'prod')
        if p is None:
            continue
        prods.append({
            'descricao': _t(p, 'xProd'), 'cfop': _t(p, 'CFOP'), 'ncm': _t(p, 'NCM'),
            'qtd': _num(_t(p, 'qCom')), 'unidade': _t(p, 'uCom'), 'valor': _num(_t(p, 'vProd')),
        })
    refs = [r.text.strip() for r in inf.iter(NS + 'refNFe') if r.text]
    venc = [v.text for v in inf.iter(NS + 'dVenc') if v.text]
    prot = root.find('.//' + NS + 'infProt')
    return {
        'tipo': 'nfe',
        'chave': chave,
        'numero': _t(ide, 'nNF') if ide is not None else '',
        'serie': _t(ide, 'serie') if ide is not None else '',
        'modelo': _t(ide, 'mod') if ide is not None else '',
        'data': ((_t(ide, 'dhEmi') or _t(ide, 'dEmi')) if ide is not None else '')[:10],
        'natureza': _t(ide, 'natOp') if ide is not None else '',
        'finalidade': _t(ide, 'finNFe') if ide is not None else '',  # 1 normal, 2 compl., 3 ajuste, 4 devolução
        'emitente': {
            'nome': _t(emit, 'xNome') if emit is not None else '',
            'doc': (_t(emit, 'CNPJ') or _t(emit, 'CPF')) if emit is not None else '',
            'ie': _t(emit, 'IE') if emit is not None else '',
            'municipio': _t(emit, 'enderEmit/xMun') if emit is not None else '',
        },
        'destinatario': {
            'nome': _t(dest, 'xNome') if dest is not None else '',
            'doc': (_t(dest, 'CNPJ') or _t(dest, 'CPF')) if dest is not None else '',
            'ie': _t(dest, 'IE') if dest is not None else '',
        },
        'cfops': sorted({p['cfop'] for p in prods if p['cfop']}),
        'valor': _num(_t(tot, 'vNF')) if tot is not None else None,
        'produtos': prods,
        'refs': refs,
        'vencimentos': venc,
        'autorizada': (prot is not None and _t(prot, 'cStat') in ('100', '150')),
        'info': (_t(inf, 'infAdic/infCpl') or '')[:500],
        'arquivo': path,
    }


def _num(s):
    try:
        return float(s)
    except (TypeError, ValueError):
        return None


def cabecas(rec):
    """Estimativa de cabeças de gado pelos produtos (unidade CB/CAB/UN em produtos bovinos)."""
    n = 0
    for p in rec.get('produtos') or []:
        d = (p.get('descricao') or '').upper()
        if any(w in d for w in ('BOVIN', 'NOVILH', 'GARROT', 'BEZERR', 'VACA', 'BOI ', 'BOIS', 'TOURO', 'MACHO', 'FEMEA')):
            n += int(p.get('qtd') or 0)
    return n or None
