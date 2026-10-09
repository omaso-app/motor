"""Classificação sugerida de uma NF-e lida por nfe.ler(), a partir das regras do cliente.

Formato de meta/regras (banco do OMASO do cliente):
{
  "por_ie": {
    "<IE>": {
      "inicio": "AAAA-MM-DD",                 # notas anteriores vão para _Documentos Gerais
      "cat_padrao": "698 - Despesas Gerais",  # despesa sem regra
      "propriedade_por_data": [{"ate": "AAAA-MM-DD", "prop": "..."}, {"desde": "AAAA-MM-DD", "prop": "..."}],
      "fornecedores": [                       # a primeira regra que casar vale
        {"emitente_contem": ["POSTO"], "produto_contem": ["SAL"], "cat": "575 - Sal Mineral"}
      ],
      "apelidos": {"TEXTO NO NOME DO EMITENTE": "Apelido-Curto"},
      "decisoes": ["texto livre com decisões do produtor"]
    }
  }
}
"""
import re
from .util import sem_acento, limpo, brl, pasta_mes
from .nfe import eh_gado, cabecas

CAT_VENDA = 'Venda de Bovinos'
CAT_COMPRA = 'Compra de Animais Bovinos'
CAT_IDN = '000 - A Identificar'
GERAIS = '_Documentos Gerais'


def _n(s):
    return re.sub(r'\D', '', str(s or '')).lstrip('0')


def _U(s):
    return sem_acento(s or '').upper()


def nossa_ie(db, pessoa):
    """Inscrição do cliente que corresponde ao emitente/destinatário (pela IE; zeros à esquerda não contam)."""
    if not pessoa:
        return None
    ie = _n(pessoa.get('ie'))
    if ie:
        for i in db.ies:
            if _n(i['ie']) == ie:
                return i
    return None


def doc_do_cliente(db, pessoa):
    d = re.sub(r'\D', '', (pessoa or {}).get('doc', ''))
    return next((i for i in db.ies if re.sub(r'\D', '', i.get('doc', '')) == d), None) if d else None


def propriedade(ie, regras, rec, data):
    props = [p['nome'] for p in ie.get('propriedades', [])]
    texto = _U(rec.get('info', '') + ' ' + ' '.join(p['descricao'] for p in rec.get('produtos', [])))
    for p in props:
        if _U(p) in texto or _U(p.split(' ', 1)[-1]) in texto:
            return p, 'citada no documento'
    for r in regras.get('propriedade_por_data', []):
        if ('ate' in r and data <= r['ate']) or ('desde' in r and data >= r['desde']):
            return r['prop'], 'regra por data'
    return (props[0] if props else 'Propriedade'), 'primeira cadastrada'


def categoria(regras, rec):
    em = _U(rec['emitente'].get('nome'))
    prods = _U(' '.join(p['descricao'] for p in rec.get('produtos', [])))
    for r in regras.get('fornecedores', []):
        ok_e = not r.get('emitente_contem') or any(_U(x) in em for x in r['emitente_contem'])
        ok_p = not r.get('produto_contem') or any(_U(x) in prods for x in r['produto_contem'])
        if ok_e and ok_p:
            return r['cat']
    return regras.get('cat_padrao') or '698 - Despesas Gerais'


def apelido(regras, pessoa):
    nome = (pessoa or {}).get('nome', '')
    for k, v in (regras.get('apelidos') or {}).items():
        if _U(k) in _U(nome) or re.sub(r'\D', '', k) and re.sub(r'\D', '', k) == re.sub(r'\D', '', pessoa.get('doc', '')):
            return v
    palavras = [w for w in limpo(nome).split('-') if w.upper() not in ('LTDA', 'ME', 'EIRELI', 'SA', 'S.A', 'EPP', 'DE', 'DA', 'DO', 'DOS', 'DAS', 'E')]
    return '-'.join(palavras[:2]) or 'Sem-Nome'


def pasta_lancamento(ie, prop, cat, data, label):
    return f"{ie['pasta']}/{prop}/{pasta_mes(data)}/{sem_acento(cat)}/{data}_{label}"


def pasta_geral(ie, sub):
    return f"{ie['pasta']}/{GERAIS}/{sub}"


def classificar(db, rec):
    out = {'avisos': []}
    if rec.get('tipo') == 'evento':
        ie = db.ies[0] if db.ies else {'pasta': ''}
        if rec.get('cancelamento'):
            out.update(destino='geral', pasta=pasta_geral(ie, 'Notas Canceladas'),
                       avisos=[f"Cancelamento da chave {rec['chave']}: se houver lançamento com essa chave, ele deve ser excluído."])
        else:
            out.update(destino='geral', pasta=pasta_geral(ie, 'Outras Empresas e Terceiros'))
        return out
    if rec.get('tipo') != 'nfe':
        return {'destino': 'ler', 'avisos': ['Não é NF-e: ler o documento.']}

    if rec['chave'] and rec['chave'] in db.chaves:
        return {'destino': 'repetido', 'avisos': [f"Chave {rec['chave']} já lançada."]}

    em_ie, de_ie = nossa_ie(db, rec['emitente']), nossa_ie(db, rec['destinatario'])
    ie = em_ie or de_ie
    data = rec['data']
    if not ie:
        cli = doc_do_cliente(db, rec['destinatario']) or doc_do_cliente(db, rec['emitente'])
        base = cli or (db.ies[0] if db.ies else {'pasta': ''})
        if cli:
            out.update(destino='fora', ie=cli['ie'], pasta=f"{cli['pasta']}/_Fora da Atividade Rural/{pasta_mes(data)}")
        else:
            out.update(destino='geral', pasta=pasta_geral(base, 'Outras Empresas e Terceiros'))
        return out

    regras = db.regras_ie(ie['ie'])
    if regras.get('inicio') and data < regras['inicio']:
        y, m = regras['inicio'][:4], regras['inicio'][5:7]
        return {'destino': 'geral', 'ie': ie['ie'], 'pasta': pasta_geral(ie, f'Notas anteriores a {m}-{y}'), 'avisos': []}

    gado, cab = eh_gado(rec), cabecas(rec)
    dev = rec['finalidade'] == 'devolucao'
    comp = rec['finalidade'] == 'complementar'
    valor = rec['valor']
    if em_ie and not de_ie:                      # nota emitida pelo produtor
        outro = rec['destinatario']
        if dev:                                   # devolução de compra
            kind, cat, valor, cab = 'compra', CAT_COMPRA, -valor, -cab
            out['avisos'].append('Devolução emitida pelo produtor: lançada como compra negativa. Confira a nota de origem: ' + ', '.join(rec['refs']))
        elif rec['tpNF'] == '0' and gado:         # nota de entrada emitida pelo produtor (compra de gado)
            kind, cat = 'compra', CAT_COMPRA
        elif gado or comp:
            kind, cat = 'venda', CAT_VENDA
        else:
            kind, cat = 'venda', CAT_VENDA
            out['avisos'].append('Nota emitida pelo produtor sem gado nos itens: conferir se é venda da atividade rural.')
    else:                                         # nota recebida
        outro = rec['emitente']
        if dev:                                   # comprador devolveu gado vendido
            kind, cat, valor, cab = 'venda', CAT_VENDA, -valor, -cab
            out['avisos'].append('Devolução recebida: lançada como venda negativa. Nota de origem: ' + ', '.join(rec['refs']))
        elif gado:
            kind, cat = 'compra', CAT_COMPRA
        else:
            kind, cat, cab = 'desp', categoria(regras, rec), 0

    prop, como = propriedade(ie, regras, rec, data)
    ap = apelido(regras, outro)
    num = rec['numero']
    if kind in ('venda', 'compra'):
        if dev:
            label = f"{ap}_Devolucao-{abs(cab)}cab_NFe{num}" + (f"-ref-NF{int(rec['refs'][0][25:34])}" if rec['refs'] else '')
        elif comp:
            label = f"{ap}_Complemento_NF{num}"
        else:
            label = f"{ap}_{cab}-Bovinos_NF{num}"
    else:
        label = f"NFe{num}_{ap}_R{brl(valor)}"
    notes = []
    if kind == 'desp':
        notes.append(f"Falta o comprovante de pagamento da NF-e {num} ({ap} — R$ {brl(valor)})")
    elif kind == 'compra' and not dev:
        notes.append(f"Falta o comprovante de pagamento da NF {num} ({ap} — R$ {brl(valor)})")
    if rec['vencimentos']:
        out['avisos'].append('Nota a prazo: o mês do lançamento é o do pagamento. Vencimentos: ' +
                             ', '.join(f"{v['data']} R$ {brl(v['valor'])}" for v in rec['vencimentos']))
    out.update(destino='lancamento', ie=ie['ie'], prop=prop, prop_por=como, cat=cat, kind=kind, date=data,
               label=label, value=round(valor, 2), heads=cab or None, notes=notes, chaves=[rec['chave']],
               pasta=pasta_lancamento(ie, prop, cat, data, label),
               arquivo=f"{data}_NFe{num}{'_Devolucao' if dev else ''}{'_Complemento' if comp else ''}_{limpo(outro.get('nome',''), 28)}_R{brl(abs(valor))}")
    return out
