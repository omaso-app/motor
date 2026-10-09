"""Leitura de XML de NF-e / NFA-e (modelo 55) e de eventos (cancelamento etc.)."""
import re
import xml.etree.ElementTree as ET

FIN = {'1': 'normal', '2': 'complementar', '3': 'ajuste', '4': 'devolucao'}


def _strip(tag):
    return tag.split('}', 1)[-1]


def _idx(root):
    for el in root.iter():
        el.tag = _strip(el.tag)
    return root


def _t(el, path, default=''):
    if el is None:
        return default
    x = el.find(path)
    return (x.text or '').strip() if x is not None and x.text else default


def _f(s):
    try:
        return float(s)
    except (TypeError, ValueError):
        return 0.0


def _pessoa(el):
    if el is None:
        return {}
    return {'nome': _t(el, 'xNome'), 'doc': _t(el, 'CNPJ') or _t(el, 'CPF'),
            'ie': _t(el, 'IE'), 'uf': _t(el, 'enderEmit/UF') or _t(el, 'enderDest/UF'),
            'mun': _t(el, 'enderEmit/xMun') or _t(el, 'enderDest/xMun')}


def ler(path):
    try:
        root = _idx(ET.parse(path).getroot())
    except ET.ParseError as e:
        return {'tipo': 'desconhecido', 'erro': str(e)}
    ev = root.find('.//infEvento')
    if root.find('.//infNFe') is None and ev is not None:
        return {'tipo': 'evento', 'chave': _t(ev, 'chNFe'), 'evento': _t(ev, 'tpEvento'),
                'descricao': _t(ev, 'detEvento/descEvento'), 'data': _t(ev, 'dhEvento')[:10],
                'cancelamento': _t(ev, 'tpEvento') == '110111'}
    inf = root.find('.//infNFe')
    if inf is None:
        return {'tipo': 'desconhecido'}
    ide = inf.find('ide')
    chave = re.sub(r'\D', '', inf.get('Id', '')) or _t(root, './/protNFe/infProt/chNFe')
    prods = []
    for det in inf.findall('det'):
        p = det.find('prod')
        prods.append({'codigo': _t(p, 'cProd'), 'descricao': _t(p, 'xProd'), 'ncm': _t(p, 'NCM'),
                      'cfop': _t(p, 'CFOP'), 'unidade': _t(p, 'uCom'), 'qtd': _f(_t(p, 'qCom')),
                      'valor': _f(_t(p, 'vProd'))})
    refs = [_t(r, 'refNFe') for r in (ide.findall('NFref') if ide is not None else []) if _t(r, 'refNFe')]
    venc = [{'data': _t(d, 'dVenc'), 'valor': _f(_t(d, 'vDup'))} for d in inf.findall('cobr/dup')]
    tot = inf.find('total/ICMSTot')
    return {
        'tipo': 'nfe', 'chave': chave, 'numero': _t(ide, 'nNF'), 'serie': _t(ide, 'serie'),
        'modelo': _t(ide, 'mod'),
        'data': (_t(ide, 'dhEmi') or _t(ide, 'dEmi'))[:10],
        'finalidade': FIN.get(_t(ide, 'finNFe'), _t(ide, 'finNFe')),
        'natureza': _t(ide, 'natOp'), 'tpNF': _t(ide, 'tpNF'),
        'emitente': _pessoa(inf.find('emit')), 'destinatario': _pessoa(inf.find('dest')),
        'cfops': sorted({p['cfop'] for p in prods if p['cfop']}),
        'valor': _f(_t(tot, 'vNF')), 'produtos': prods, 'refs': refs, 'vencimentos': venc,
        'info': _t(inf, 'infAdic/infCpl') + ' ' + _t(inf, 'infAdic/infAdFisco'),
        'protocolo': _t(root, './/protNFe/infProt/nProt'),
    }


BOV = re.compile(r'BOVIN|NOVILH|GARROT|BEZERR|VACA|BOI\b|BOIS\b|TOURO|MAMOT|NELORE|ANELORAD|CABE', re.I)


def eh_gado(rec):
    return any(BOV.search(p['descricao']) for p in rec.get('produtos', []))


def cabecas(rec):
    """Cabeças de gado na nota (soma das quantidades dos itens bovinos)."""
    return int(round(sum(p['qtd'] for p in rec.get('produtos', []) if BOV.search(p['descricao']))))
