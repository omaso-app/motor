"""Sugestão de classificação de uma NF-e, usando as regras de cada cliente (meta/regras e meta/ies).

O Claude da conferência confere a sugestão e decide; nada aqui é definitivo.

Formato de meta/regras (todos os campos são opcionais):
{
  "inicio": "2025-10-01",                 # notas antes disso vão para "Notas anteriores a ..."
  "cat_padrao": "698 - Despesas Gerais",
  "propriedade_por_data": {"<ie>": [{"ate": "2026-04-30", "prop": "Fazenda X"}, {"desde": "2026-05-01", "prop": "Sítio Y"}]},
  "fornecedores": [{"emitente_contem": ["POSTO"], "produto_contem": [], "cat": "347 - Combustíveis e Lubrificantes"}],
  "apelidos": [{"contem": "POSTO CENTRAL", "nome": "Posto-Central"}],
  "canceladas": ["<chave de 44 dígitos>"],
  "decisoes": ["texto livre com decisões do produtor"]
}
"""
from .util import limpo, sem_acento, brl, pasta_mes
from .nfe import cabecas

VENDA_CFOPS = ('5101', '5102', '6101', '6102', '5103', '6103', '5105', '6105', '7101', '7102')
GADO = ('BOVIN', 'NOVILH', 'GARROT', 'BEZERR', 'VACA', 'BOI ', 'BOIS', 'TOURO', 'GADO')


def _digits(s):
    return ''.join(c for c in (s or '') if c.isdigit())


def produtor_por_doc(db, doc):
    d = _digits(doc)
    for x in db.ies:
        if _digits(x.get('doc')) == d and d:
            return x
    return None


def produtor_por_ie(db, ie):
    i = _digits(ie).lstrip('0')
    for x in db.ies:
        if _digits(x.get('ie')).lstrip('0') == i and i:
            return x
    return None


def propriedade(db, ie, data, texto=''):
    x = db.ie(ie)
    props = [p.get('nome') for p in x.get('propriedades') or [] if p.get('nome')]
    up = sem_acento(texto).upper()
    for p in props:  # o documento cita a propriedade?
        if sem_acento(p).upper() in up:
            return p, 'citada no documento'
    for r in (db.regras.get('propriedade_por_data') or {}).get(str(x['ie']), []):
        if (not r.get('desde') or data >= r['desde']) and (not r.get('ate') or data <= r['ate']):
            return r['prop'], 'regra por data'
    return (props[0] if props else 'Sem propriedade'), 'primeira propriedade cadastrada'


def apelido(db, nome):
    up = sem_acento(nome).upper()
    for a in db.regras.get('apelidos') or []:
        if a.get('contem', '').upper() in up:
            return a['nome']
    return limpo(nome.title(), 25)


def categoria(db, rec):
    em = sem_acento(rec['emitente']['nome']).upper()
    prods = rec.get('produtos') or []
    top = max(prods, key=lambda p: p.get('valor') or 0) if prods else {}
    desc = sem_acento(top.get('descricao') or '').upper()
    for r in db.regras.get('fornecedores') or []:
        if r.get('emitente_contem') and not any(sem_acento(s).upper() in em for s in r['emitente_contem']):
            continue
        if r.get('produto_contem') and not any(sem_acento(s).upper() in desc for s in r['produto_contem']):
            continue
        return r['cat'], 'regra de fornecedor'
    return db.regras.get('cat_padrao') or '698 - Despesas Gerais', 'categoria padrão (confira)'


def _tem_gado(rec):
    return any(any(g in sem_acento(p.get('descricao') or '').upper() for g in GADO) for p in rec.get('produtos') or [])


def classificar(db, rec):
    """Sugestão para um registro de nfe.ler()."""
    inicio = db.regras.get('inicio') or '1900-01-01'
    out = {'chave': rec.get('chave'), 'avisos': []}
    if rec['tipo'] == 'evento':
        out.update(destino='geral', pasta_geral='Notas Canceladas', motivo=f"evento {rec.get('tpEvento')}")
        return out
    if rec['tipo'] != 'nfe':
        out.update(destino='ler', motivo='não é XML de NF-e; ler o documento')
        return out
    if rec['chave'] in db.chaves:
        out.update(destino='repetido', motivo='chave já lançada')
        return out
    if rec['chave'] in set(db.regras.get('canceladas') or []):
        out.update(destino='geral', pasta_geral='Notas Canceladas', motivo='chave na lista de canceladas')
        return out
    emit_prod = produtor_por_doc(db, rec['emitente']['doc'])
    dest_prod = produtor_por_doc(db, rec['destinatario']['doc'])
    data = rec['data']
    v = rec.get('valor') or 0
    dev = rec.get('finalidade') == '4'
    if emit_prod and dev:
        # devolução emitida pelo próprio produtor (ex.: devolve parte do gado comprado)
        ie = produtor_por_ie(db, rec['emitente']['ie']) or emit_prod
        quem = apelido(db, rec['destinatario']['nome'])
        if set(rec['cfops']) & {'5202', '6202', '5201', '6201', '5209', '6209'} or _tem_gado(rec):
            kind, cat = 'compra', 'Compra de Animais Bovinos' if _tem_gado(rec) else 'Devolução de compra'
        else:
            kind, cat = 'desp', 'Devolução de compra'
        out['avisos'].append('devolução emitida pelo produtor: normalmente entra JUNTO do lançamento da compra original (mesma pasta), abatendo o valor')
    elif emit_prod and (set(rec['cfops']) & set(VENDA_CFOPS)):
        prod = emit_prod
        ie = produtor_por_ie(db, rec['emitente']['ie']) or prod
        kind, cat = 'venda', 'Venda de Bovinos' if _tem_gado(rec) else 'Outras Receitas'
        quem = apelido(db, rec['destinatario']['nome'])
    elif dest_prod:
        ie = produtor_por_ie(db, rec['destinatario']['ie'])
        if not ie:
            out.update(destino='fora', pasta_geral='_Fora da Atividade Rural/' + pasta_mes(data),
                       motivo='destinatário é o produtor, mas sem inscrição estadual na nota')
            return out
        quem = apelido(db, rec['emitente']['nome'])
        if _tem_gado(rec):
            kind, cat = 'compra', 'Compra de Animais Bovinos'
        else:
            kind = 'desp'
            cat, how = categoria(db, rec)
            if 'padrão' in how:
                out['avisos'].append('categoria pela regra padrão: confira')
    else:
        out.update(destino='geral', pasta_geral='Outras Empresas e Terceiros',
                   motivo='destinatário não é um produtor cadastrado')
        return out
    if data < inicio:
        out.update(destino='geral', pasta_geral=f"Notas anteriores a {inicio[5:7]}-{inicio[:4]}",
                   motivo=f'emitida antes de {inicio}')
        return out
    if dev:
        v = -abs(v)
        out['avisos'].append('devolução (finNFe 4): valor negativo; confira a categoria da nota original ' + ','.join(rec.get('refs') or []))
    prop, how = propriedade(db, ie['ie'], data, rec.get('info', ''))
    label = f"NFe{rec['numero']}_{quem}_R{brl(v)}"
    out.update(
        destino='lancamento', ie=str(ie['ie']), prop=prop, prop_motivo=how, cat=cat, kind=kind,
        date=data, label=label, value=round(v, 2), heads=cabecas(rec) if kind in ('compra', 'venda') else None,
        pasta=pasta_lancamento(ie, prop, data, cat, label),
    )
    if rec.get('vencimentos') and kind == 'desp':
        out['avisos'].append('nota com boleto: o mês do lançamento é o do pagamento; sem comprovante, fica a data da nota e uma pendência')
    return out


def pasta_lancamento(ie, prop, date, cat, label):
    """Caminho relativo à pasta INSCRIÇÕES."""
    return '/'.join([ie['pasta'], prop, pasta_mes(date), sem_acento(cat), f"{date}_{limpo(label, 70)}"])


def pasta_geral(ie, nome):
    if nome.startswith('_Fora'):
        return '/'.join([ie['pasta'], nome])
    return '/'.join([ie['pasta'], '_Documentos Gerais', nome])
