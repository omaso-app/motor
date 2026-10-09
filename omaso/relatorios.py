"""Relatórios em HTML (mensal, anual por propriedade, consolidado e planejamento) gerados a partir do banco.

Cada função devolve uma lista de (caminho_relativo_a_INSCRICOES, html, info).
"""
import collections, datetime as dt
from .util import E, brl, money, m0, MESES, MESES_TXT, ABR, is_idn, S, H, notas_abertas, limpo

CSS = '''
@page{size:A4;margin:14mm 14mm 16mm}
*{box-sizing:border-box}
body{font-family:"Segoe UI",Roboto,Helvetica,Arial,sans-serif;color:#1d2a22;margin:0;background:#eef1ec;font-size:11.5px}
.page{width:210mm;min-height:297mm;margin:10px auto;background:#fff;padding:14mm;box-shadow:0 1px 6px rgba(0,0,0,.12);page-break-after:always}
.page:last-child{page-break-after:auto}
@media print{body{background:#fff}.page{margin:0;box-shadow:none;width:auto;min-height:auto;padding:0}}
header{display:flex;justify-content:space-between;align-items:flex-end;border-bottom:3px solid #2f5d3a;padding-bottom:8px;margin-bottom:12px}
.brand{font-weight:800;letter-spacing:.18em;color:#2f5d3a;font-size:13px}
h1{font-size:20px;margin:2px 0 0}
.meta{text-align:right;font-size:10.5px;color:#4b5a50;line-height:1.5}
.cards{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin:10px 0 14px}
.cards.c4{grid-template-columns:repeat(4,1fr)}
.card{border:1px solid #d7ded8;border-radius:8px;padding:10px 12px}
.card .lbl{font-size:10px;text-transform:uppercase;letter-spacing:.06em;color:#5b6b60}
.card .val{font-size:19px;font-weight:700;margin-top:4px}
.cards.c4 .card .val{font-size:15.5px;white-space:nowrap}
.card .sub{font-size:10.5px;color:#5b6b60;margin-top:2px}
.card.venda .val{color:#2f5d3a}.card.compra .val{color:#7a4b12}.card.desp .val{color:#8a2a2a}.card.res.neg .val{color:#8a2a2a}
h2{font-size:13px;margin:14px 0 6px;color:#2f5d3a;text-transform:uppercase;letter-spacing:.05em}
table{width:100%;border-collapse:collapse}
th,td{padding:4px 6px;border-bottom:1px solid #e3e8e4;text-align:left;vertical-align:top}
th{font-size:10px;text-transform:uppercase;color:#5b6b60;background:#f5f7f5}
td.n,th.n{text-align:right;white-space:nowrap}
tr.tot td{font-weight:700;border-top:2px solid #2f5d3a}
table.mx{font-size:8.6px} table.mx th,table.mx td{padding:2px 3px} td.z{color:#b9c2bb} table.mx td:first-child{white-space:nowrap}
.ok{color:#2f7a45;font-weight:700}.warn{color:#b25a00;font-weight:700}
ul.pend{margin:4px 0 10px 16px;padding:0} ul.pend li{margin:3px 0}
.box{border:1px solid #f0d9b5;background:#fff8ee;border-radius:8px;padding:8px 12px;margin-bottom:10px}
.box.idn{border-color:#d7ded8;background:#f7f9f7}
.empty{color:#2f7a45;font-weight:600}
.foot{margin-top:14px;font-size:9.5px;color:#7b877f}
.big{font-size:26px;font-weight:700} .hl{background:#eef5ee;border:1px solid #cfe0cf;border-radius:8px;padding:12px 16px;margin:10px 0}
.hl .lbl{font-size:10px;text-transform:uppercase;letter-spacing:.06em;color:#4b5a50} .note{font-size:10.5px;color:#4b5a50;margin:4px 0 10px}
ul.p li{font-size:11px;margin:3px 0}
'''

FALTA = ('falta', 'sem comprovante', 'sem nf', 'sem recibo', 'só o boleto')


def _meta(ie, linha3):
    d = ''.join(c for c in (ie.get('doc') or '') if c.isdigit())
    doc = f"{'CPF' if len(d) == 11 else 'CNPJ'} {E(ie.get('doc'))} · " if d else ''
    return f"<div class='meta'>Produtor: <b>{E(ie['nome'])}</b><br>{doc}Inscrição Estadual {E(str(ie['ie']))}<br>{linha3}</div>"


def _doc(title, pages):
    return (f"<!doctype html><html lang='pt-BR'><head><meta charset='utf-8'><title>{E(title)}</title>"
            f"<style>{CSS}</style></head><body>" + ''.join(f"<div class='page'>{p}</div>" for p in pages) + "</body></html>")


def _split(ts):
    desp = [t for t in ts if t.get('kind') == 'desp' and not is_idn(t)]
    comp = [t for t in ts if t.get('kind') == 'compra']
    vend = [t for t in ts if t.get('kind') == 'venda']
    idn = [t for t in ts if is_idn(t)]
    return desp, comp, vend, idn


def _pend(ts):
    return [(t, n) for t in ts if not is_idn(t) for n in notas_abertas(t)]


def _lbl(t):
    return (t.get('label') or '').replace('_', ' · ').replace('-', ' ')


def props_da_ie(ie, ts):
    ordem = [p.get('nome') for p in ie.get('propriedades') or []]
    usadas = {t.get('prop') for t in ts}
    return [p for p in ordem if p in usadas] + sorted(p for p in usadas if p and p not in ordem)


# --------------------------------------------------------------- mensal
def mensal(ie, prop, ym, ts):
    y, m = ym.split('-')
    mes = f"{MESES_TXT[int(m)]} de {y}"
    desp, comp, vend, idn = _split(ts)
    sd, sc, sv = S(desp), S(comp), S(vend)
    bycat = collections.OrderedDict()
    for t in sorted(desp, key=lambda t: t['cat']):
        bycat.setdefault(t['cat'], []).append(t)
    rows = ''.join(f"<tr><td>{E(c)}</td><td class='n'>{len(l)}</td><td class='n'>{money(S(l))}</td></tr>" for c, l in bycat.items())
    rows += (f"<tr class='tot'><td>Total de despesas</td><td class='n'>{len(desp)}</td><td class='n'>{money(sd)}</td></tr>"
             if desp else "<tr><td colspan=3>Sem despesas no mês.</td></tr>")

    def txrow(t):
        st = "<span class='warn'>pendente</span>" if notas_abertas(t) else "<span class='ok'>ok</span>"
        cab = f"{t['heads']} cab." if t.get('heads') else ''
        return (f"<tr><td>{t['date'][8:]}/{t['date'][5:7]}</td><td>{E(t['cat'])}</td><td>{E(_lbl(t))}</td>"
                f"<td class='n'>{cab}</td><td class='n'>{money(t.get('value'))}</td><td>{st}</td></tr>")
    lanc = ''.join(txrow(t) for t in sorted(ts, key=lambda t: (t['date'], t['cat'])) if not is_idn(t))
    pend = _pend(ts)
    falta = [n for t, n in pend if any(k in n.lower() for k in FALTA)]
    outros = [n for t, n in pend if n not in falta]
    idnl = [(t, n) for t in idn for n in (notas_abertas(t) or ['Sem documento fiscal'])]
    ul = lambda l: '<ul class="pend">' + ''.join(f'<li>{E(x)}</li>' for x in l) + '</ul>'
    p2 = ''
    if falta:
        p2 += f"<h2>Documentos faltando</h2><div class='box'>{ul(falta)}</div>"
    if outros:
        p2 += f"<h2>Divergências e pontos a conferir</h2><div class='box'>{ul(outros)}</div>"
    if idnl:
        it = [f"{t['date'][8:]}/{t['date'][5:7]} — {money(t.get('value')) if t.get('value') else 's/ valor'} — {n}" for t, n in idnl]
        p2 += (f"<h2>Pagamentos a identificar</h2><div class='box idn'>{ul(it)}<div style='font-size:10px;color:#5b6b60'>"
               "Estão na pasta “000 - A Identificar” e não entram nos totais até você dizer se são da atividade rural.</div></div>")
    if not p2:
        p2 = "<p class='empty'>Nenhuma pendência neste mês.</p>"
    head = (f"<header><div><div class='brand'>OMASO</div><h1>Relatório de {mes}</h1><div style='font-size:12px;color:#4b5a50;margin-top:2px'>{E(prop)}</div></div>"
            + _meta(ie, 'Propriedade: ' + E(prop)) + "</header>")
    p1 = (f"{head}<div class='cards'>"
          f"<div class='card desp'><div class='lbl'>Despesas</div><div class='val'>{money(sd)}</div><div class='sub'>{len(desp)} lançamento(s)</div></div>"
          f"<div class='card compra'><div class='lbl'>Compra de animais</div><div class='val'>{money(sc)}</div><div class='sub'>{H(comp)} cabeça(s) · {len(comp)} operação(ões)</div></div>"
          f"<div class='card venda'><div class='lbl'>Venda de animais</div><div class='val'>{money(sv)}</div><div class='sub'>{H(vend)} cabeça(s) · {len(vend)} operação(ões)</div></div></div>"
          f"<h2>Despesas por categoria</h2><table><tr><th>Categoria</th><th class='n'>Lanç.</th><th class='n'>Valor</th></tr>{rows}</table>"
          "<h2>Lançamentos do mês</h2><table style='table-layout:fixed'><colgroup><col style='width:7%'><col style='width:21%'><col style='width:42%'><col style='width:9%'><col style='width:13%'><col style='width:8%'></colgroup>"
          f"<tr><th>Data</th><th>Categoria</th><th>Operação</th><th class='n'>Cab.</th><th class='n'>Valor</th><th>Docs</th></tr>{lanc or '<tr><td colspan=6>Nenhum lançamento.</td></tr>'}</table>"
          "<div class='foot'>Mês de lançamento = data do pagamento/recebimento (sem comprovante, usa-se a data do documento). Valores de venda incluem complementos e descontam devoluções.</div>")
    html = _doc(f"Relatório {mes} — {prop}", [p1, f"{head}<h2 style='margin-top:4px'>Pendências de {mes}</h2>{p2}"])
    path = f"{ie['pasta']}/{prop}/{ym} {MESES[int(m)]}/Relatorio_{ym}_{MESES[int(m)]}_{prop.replace(' ', '-')}.html"
    return path, html, dict(tipo='mensal', ie=str(ie['ie']), ano=y, mes=int(m), prop=prop,
                            npend=len(falta) + len(outros), nidn=len(idnl))


# --------------------------------------------------------------- anual por propriedade
def _mes_a_mes(ts, y, months, desp, comp, vend):
    rows = ''
    for m in months:
        f = lambda l: [t for t in l if int(t['date'][5:7]) == m]
        d, c, v = S(f(desp)), S(f(comp)), S(f(vend)); r = v - c - d
        tm = [t for t in ts if int(t['date'][5:7]) == m]
        npd = len(_pend(tm)) + len([t for t in tm if is_idn(t)])
        neg = ' style="color:#8a2a2a"' if r < 0 else ''
        rows += (f"<tr><td>{MESES_TXT[m]}</td><td class='n'>{m0(d)}</td><td class='n'>{m0(c)}</td><td class='n'>{H(f(comp)) or '—'}</td>"
                 f"<td class='n'>{m0(v)}</td><td class='n'>{H(f(vend)) or '—'}</td><td class='n'{neg}>{brl(r)}</td><td class='n'>{npd or '—'}</td></tr>")
    sd, sc, sv = S(desp), S(comp), S(vend)
    rows += (f"<tr class='tot'><td>Total {y}</td><td class='n'>{m0(sd)}</td><td class='n'>{m0(sc)}</td><td class='n'>{H(comp) or '—'}</td>"
             f"<td class='n'>{m0(sv)}</td><td class='n'>{H(vend) or '—'}</td><td class='n'>{brl(sv - sc - sd)}</td><td></td></tr>")
    return ("<table><tr><th>Mês</th><th class='n'>Despesas</th><th class='n'>Compras</th><th class='n'>Cab.</th><th class='n'>Vendas</th>"
            f"<th class='n'>Cab.</th><th class='n'>Resultado</th><th class='n'>Pend.</th></tr>{rows}</table>")


def _matriz(months, vend, comp, bc):
    mh = ''.join(f"<th class='n'>{ABR[m]}</th>" for m in months)
    mx = ''
    for c, l in [('Venda de Bovinos', vend), ('Compra de Animais Bovinos', comp)] + [(c, bc[c]) for c in sorted(bc)]:
        if not l:
            continue
        cells = ''
        for m in months:
            v = S([t for t in l if int(t['date'][5:7]) == m])
            cells += f"<td class='n{' z' if not v else ''}'>{m0(v) if v else '·'}</td>"
        mx += f"<tr><td>{E(c)}</td>{cells}<td class='n'><b>{m0(S(l))}</b></td></tr>"
    return f"<table class='mx'><tr><th>Categoria</th>{mh}<th class='n'>Total</th></tr>{mx}</table>"


def _cards4(sv, sc, sd, vend, comp, desp):
    res = sv - sc - sd
    return ("<div class='cards c4'>"
            f"<div class='card venda'><div class='lbl'>Venda de animais</div><div class='val'>{money(sv)}</div><div class='sub'>{H(vend)} cabeça(s) · {len(vend)} operação(ões)</div></div>"
            f"<div class='card compra'><div class='lbl'>Compra de animais</div><div class='val'>{money(sc)}</div><div class='sub'>{H(comp)} cabeça(s) · {len(comp)} operação(ões)</div></div>"
            f"<div class='card desp'><div class='lbl'>Despesas</div><div class='val'>{money(sd)}</div><div class='sub'>{len(desp)} lançamento(s)</div></div>"
            f"<div class='card res{' neg' if res < 0 else ''}'><div class='lbl'>Resultado de caixa</div><div class='val'>R$ {brl(res)}</div><div class='sub'>vendas − compras − despesas</div></div></div>")


def anual(ie, prop, y, ts):
    desp, comp, vend, idn = _split(ts)
    sd, sc, sv = S(desp), S(comp), S(vend)
    months = sorted({int(t['date'][5:7]) for t in ts})
    bc = collections.defaultdict(list)
    for t in desp:
        bc[t['cat']].append(t)
    crow = ''.join(f"<tr><td>{E(c)}</td><td class='n'>{len(bc[c])}</td><td class='n'>{money(S(bc[c]))}</td><td class='n'>{S(bc[c]) / sd * 100:.1f}%</td></tr>"
                   for c in sorted(bc, key=lambda c: -S(bc[c]))) if sd else ''
    crow += (f"<tr class='tot'><td>Total de despesas</td><td class='n'>{len(desp)}</td><td class='n'>{money(sd)}</td><td class='n'>100%</td></tr>"
             if desp else "<tr><td colspan=4>Sem despesas no ano.</td></tr>")
    pend = _pend(ts)
    pl = ''.join(f"<li><b>{t['date'][8:]}/{t['date'][5:7]}</b> — {E(n)}</li>" for t, n in sorted(pend, key=lambda x: x[0]['date']))
    il = ''.join(f"<li><b>{t['date'][8:]}/{t['date'][5:7]}</b> — {money(t.get('value')) if t.get('value') else 's/ valor'} — {E(_lbl(t))}</li>"
                 for t in sorted(idn, key=lambda t: t['date']))
    p2 = f"<h2>Movimento por categoria e mês (R$)</h2>{_matriz(months, vend, comp, bc)}"
    p2 += (f"<h2>Pendências do ano ({len(pend)})</h2><div class='box'><ul class='pend'>{pl}</ul></div>" if pend
           else "<h2>Pendências do ano</h2><p class='empty'>Nenhuma pendência.</p>")
    if idn:
        p2 += f"<h2>Pagamentos a identificar ({len(idn)} · {money(S(idn))})</h2><div class='box idn'><ul class='pend'>{il}</ul></div>"
    periodo = (f"{MESES_TXT[months[0]]} a {MESES_TXT[months[-1]]} de {y}" if len(months) > 1 else f"{MESES_TXT[months[0]]} de {y}")
    head = (f"<header><div><div class='brand'>OMASO</div><h1>Relatório Anual {y}</h1><div style='font-size:12px;color:#4b5a50;margin-top:2px'>{E(prop)} · {periodo}</div></div>"
            + _meta(ie, 'Propriedade: ' + E(prop)) + "</header>")
    p1 = (head + _cards4(sv, sc, sd, vend, comp, desp)
          + f"<h2>Mês a mês (R$)</h2>{_mes_a_mes(ts, y, months, desp, comp, vend)}"
          + f"<h2>Despesas por categoria no ano</h2><table><tr><th>Categoria</th><th class='n'>Lanç.</th><th class='n'>Valor</th><th class='n'>% das despesas</th></tr>{crow}</table>"
          + "<div class='foot'>Mês de lançamento = data do pagamento/recebimento. Pagamentos “A Identificar” ficam fora dos totais. “Pend.” = pendências + itens a identificar do mês.</div>")
    path = f"{ie['pasta']}/{prop}/Relatorio_Anual_{y}_{prop.replace(' ', '-')}.html"
    return path, _doc(f"Relatório Anual {y} — {prop}", [p1, head + p2]), dict(tipo='anual', ie=str(ie['ie']), ano=y, prop=prop)


# --------------------------------------------------------------- consolidado da inscrição
def consolidado(ie, y, ts):
    desp, comp, vend, idn = _split(ts)
    sd, sc, sv = S(desp), S(comp), S(vend); res = sv - sc - sd
    props = props_da_ie(ie, ts)
    pr = ''
    for p in props:
        f = lambda l: [t for t in l if t.get('prop') == p]
        r = S(f(vend)) - S(f(comp)) - S(f(desp))
        pr += (f"<tr><td>{E(p)}</td><td class='n'>{m0(S(f(vend)))}</td><td class='n'>{H(f(vend)) or '—'}</td><td class='n'>{m0(S(f(comp)))}</td>"
               f"<td class='n'>{H(f(comp)) or '—'}</td><td class='n'>{m0(S(f(desp)))}</td><td class='n'{' style=color:#8a2a2a' if r < 0 else ''}>{brl(r)}</td></tr>")
    pr += (f"<tr class='tot'><td>Total da inscrição</td><td class='n'>{m0(sv)}</td><td class='n'>{H(vend) or '—'}</td><td class='n'>{m0(sc)}</td>"
           f"<td class='n'>{H(comp) or '—'}</td><td class='n'>{m0(sd)}</td><td class='n'>{brl(res)}</td></tr>")
    months = sorted({int(t['date'][5:7]) for t in ts})
    bc = collections.defaultdict(list)
    for t in desp:
        bc[t['cat']].append(t)
    ph = ''.join(f"<th class='n'>{E(p)}</th>" for p in props)
    cr = ''
    for c in sorted(bc, key=lambda c: -S(bc[c])):
        cells = ''.join(f"<td class='n'>{m0(S([t for t in bc[c] if t.get('prop') == p]))}</td>" for p in props)
        cr += f"<tr><td>{E(c)}</td>{cells}<td class='n'><b>{m0(S(bc[c]))}</b></td><td class='n'>{S(bc[c]) / sd * 100:.1f}%</td></tr>"
    if sd:
        cells = ''.join(f"<td class='n'>{m0(S([t for t in desp if t.get('prop') == p]))}</td>" for p in props)
        cr += f"<tr class='tot'><td>Total de despesas</td>{cells}<td class='n'>{m0(sd)}</td><td class='n'>100%</td></tr>"
    npend = len(_pend(ts))
    pp = ''.join(f"<li><b>{E(p)}</b>: {len(_pend([t for t in ts if t.get('prop') == p]))} pendência(s), "
                 f"{len([t for t in idn if t.get('prop') == p])} pagamento(s) a identificar ({money(S([t for t in idn if t.get('prop') == p]))})</li>" for p in props)
    periodo = f"{MESES_TXT[months[0]]} a {MESES_TXT[months[-1]]} de {y}" if months else str(y)
    head = (f"<header><div><div class='brand'>OMASO</div><h1>Relatório Anual Consolidado {y}</h1><div style='font-size:12px;color:#4b5a50;margin-top:2px'>"
            f"Todas as propriedades da Inscrição Estadual {E(str(ie['ie']))} · {periodo}</div></div>" + _meta(ie, 'Propriedades: ' + E(', '.join(props))) + "</header>")
    p1 = (head + _cards4(sv, sc, sd, vend, comp, desp)
          + "<h2>Por propriedade (R$)</h2><table><tr><th>Propriedade</th><th class='n'>Vendas</th><th class='n'>Cab.</th><th class='n'>Compras</th><th class='n'>Cab.</th><th class='n'>Despesas</th><th class='n'>Resultado</th></tr>" + pr + "</table>"
          + f"<h2>Mês a mês — todas as propriedades (R$)</h2>{_mes_a_mes(ts, y, months, desp, comp, vend)}"
          + "<div class='foot'>Mês de lançamento = data do pagamento/recebimento. Pagamentos “A Identificar” e documentos fora da atividade rural ficam fora dos totais. Cabeças de compra negativas = devoluções.</div>")
    p2 = head + f"<h2>Despesas por categoria e propriedade (R$)</h2><table class='mx'><tr><th>Categoria</th>{ph}<th class='n'>Total</th><th class='n'>%</th></tr>{cr}</table>"
    p3 = (head + f"<h2>Movimento por categoria e mês (R$)</h2>{_matriz(months, vend, comp, bc)}"
          + f"<h2>Pendências ({npend}) e pagamentos a identificar ({len(idn)} · {money(S(idn))})</h2><div class='box'><ul class='pend'>{pp}</ul></div>")
    path = f"{ie['pasta']}/Relatorio_Anual_Consolidado_{y}_IE-{ie['ie']}.html"
    return path, _doc(f"Relatório Anual Consolidado {y} — IE {ie['ie']}", [p1, p2, p3]), dict(tipo='consolidado', ie=str(ie['ie']), ano=y)


# --------------------------------------------------------------- planejamento de fechamento
def planejamento(ie, y, ts, hoje=None):
    hoje = hoje or dt.date.today()
    desp, comp, vend, idn = _split(ts)
    sv, sc, sd = S(vend), S(comp), S(desp); res = sv - sc - sd
    lim = (hoje - dt.timedelta(days=90)).isoformat()
    rc = [t for t in comp if t['date'] >= lim and (t.get('heads') or 0) > 0 and (t.get('value') or 0) > 0]
    if sum(t['heads'] for t in rc) < 50:
        rc = [t for t in comp if (t.get('heads') or 0) > 0 and (t.get('value') or 0) > 0]
    cabs = sum(t['heads'] for t in rc)
    preco = S(rc) / cabs if cabs else None
    precos = sorted(t['value'] / t['heads'] for t in rc)
    fechados = sorted({t['date'][:7] for t in desp if t['date'][:7] < hoje.strftime('%Y-%m')})
    media = sum(t.get('value') or 0 for t in desp if t['date'][:7] in fechados) / max(1, len(fechados))
    falt = max(0, 12 - hoje.month + (1 if hoje.day <= 15 else 0)) if str(hoje.year) == str(y) else 0
    proj = media * falt
    need0, need1 = max(0, res), max(0, res - proj)
    cab = lambda v, p=preco: (int(v // p) + 1 if v > 0 else 0) if p else '—'
    props = props_da_ie(ie, ts)
    pr = ''
    for p in props:
        f = lambda l: [t for t in l if t.get('prop') == p]; r = S(f(vend)) - S(f(comp)) - S(f(desp))
        pr += f"<tr><td>{E(p)}</td><td class='n'>{brl(S(f(vend)))}</td><td class='n'>{brl(S(f(comp)))}</td><td class='n'>{brl(S(f(desp)))}</td><td class='n'{' style=color:#8a2a2a' if r < 0 else ''}>{brl(r)}</td></tr>"
    pr += f"<tr class='tot'><td>Total da IE {E(str(ie['ie']))}</td><td class='n'>{brl(sv)}</td><td class='n'>{brl(sc)}</td><td class='n'>{brl(sd)}</td><td class='n'>{brl(res)}</td></tr>"
    if preco:
        pc = ([round(precos[len(precos) // 4], -1), round(preco, -1), round(precos[3 * len(precos) // 4], -1)]
              if len(precos) >= 4 else [round(preco * .85, -1), round(preco, -1), round(preco * 1.15, -1)])
        cen = ''
        for lab, v in [('Só com o que já está lançado', need0), (f'Descontando despesas previstas até 31/12 (≈ {money(proj)})', need1)]:
            cen += f"<tr><td>{lab}</td><td class='n'><b>{brl(v)}</b></td>" + ''.join(f"<td class='n'>{cab(v, p)}</td>" for p in pc) + "</tr>"
        tab = (f"<h2>Cabeças necessárias conforme o preço pago</h2><table><tr><th>Cenário</th><th class='n'>Valor a comprar</th>"
               + ''.join(f"<th class='n'>a {money(p)}/cab</th>" for p in pc) + f"</tr>{cen}</table>")
        ex = ''.join(f"<tr><td>Se vender mais {money(v)} até 31/12</td><td class='n'>{brl(need1 + v)}</td><td class='n'>{cab(need1 + v)}</td></tr>"
                     for v in (100000, 300000, 500000, 1000000))
        tab += (f"<h2>Cada venda nova aumenta a compra necessária no mesmo valor</h2><table><tr><th>Cenário</th><th class='n'>Valor a comprar</th>"
                f"<th class='n'>Cab. (a {money(preco)})</th></tr>{ex}</table>")
        nota = (f"Considerando nenhuma venda nova até o fim do ano, despesas normais de ≈ {money(media)}/mês nos {falt} mês(es) restantes e preço médio "
                f"de compra de {money(preco)} por cabeça ({cabs} cabeças, {money(S(rc))}). Sem contar as despesas previstas: {money(need0)} ≈ {cab(need0)} cabeças.")
        big = f"{money(need1)} ≈ {cab(need1)} cabeças"
    else:
        tab, nota, big = '', 'Ainda não há compras de gado com número de cabeças para calcular o preço médio.', money(need1)
    head = (f"<header><div><div class='brand'>OMASO</div><h1>Planejamento de Fechamento {y}</h1><div style='font-size:12px;color:#4b5a50;margin-top:2px'>"
            f"Quanto comprar em gado para o resultado da atividade rural de {y} ficar negativo · posição em {hoje.strftime('%d/%m/%Y')}</div></div>"
            + _meta(ie, 'Todas as propriedades') + "</header>")
    p1 = (head + f"<h2>Resultado de {y} até agora (R$)</h2><table><tr><th>Propriedade</th><th class='n'>Vendas</th><th class='n'>Compras de gado</th>"
          f"<th class='n'>Despesas</th><th class='n'>Resultado</th></tr>{pr}</table>"
          f"<div class='hl'><div class='lbl'>Para fechar {y} com resultado negativo, ainda é preciso comprar e PAGAR até 31/12 mais de</div><div class='big'>{big}</div><div class='note'>{nota}</div></div>"
          + tab + "<div class='foot'>Regime de caixa: entra no ano o que foi efetivamente recebido ou pago até 31/12. Pagamentos “A Identificar” e documentos fora da atividade rural não entram.</div>")
    pres = .2 * sv
    p2 = (head + "<h2>Como funciona (Imposto de Renda – atividade rural)</h2><ul class='p'>"
          "<li><b>Resultado = receitas recebidas − despesas pagas</b> no ano (livro caixa). A compra de gado para cria/recria/engorda entra como despesa no mês em que é paga.</li>"
          "<li><b>Prejuízo não se perde:</b> o resultado negativo de um ano pode ser compensado com o resultado positivo dos anos seguintes.</li>"
          f"<li><b>É adiamento, não eliminação:</b> o gado comprado agora vira receita quando for vendido em {int(y) + 1}.</li>"
          f"<li><b>Alternativa – resultado presumido (20% da receita bruta):</b> hoje daria {money(pres)}, contra {money(max(res, 0))} pelo livro caixa. Quem escolhe os 20% perde o direito de compensar prejuízos daquele ano.</li>"
          "<li><b>Condomínio/parceria:</b> o resultado é dividido entre os participantes na proporção de cada um — confirme com o contador.</li>"
          "</ul><div class='foot'>Relatório de apoio gerado pelo OMASO a partir dos lançamentos. Não substitui a orientação do contador.</div>")
    path = f"{ie['pasta']}/Planejamento_Fechamento_{y}_IE-{ie['ie']}.html"
    return path, _doc(f"Planejamento de Fechamento {y} — IE {ie['ie']}", [p1, p2]), dict(tipo='planejamento', ie=str(ie['ie']), ano=y)


# --------------------------------------------------------------- todos / afetados
def gerar(db, ie_num=None, anos=None, meses=None, hoje=None):
    """meses: conjunto de (prop, 'AAAA-MM') a refazer (None = todos). anos: anos do anual/consolidado (None = todos)."""
    out = []
    for ie in ([db.ie(ie_num)] if ie_num else db.ies):
        ts = [t for t in db.txs_da_ie(ie['ie']) if not (t.get('pasta') or '').split('/')[1:2] == ['_Fora da Atividade Rural']]
        g = collections.defaultdict(list)
        for t in ts:
            g[(t.get('prop'), t['date'][:7])].append(t)
        for (prop, ym), l in sorted(g.items()):
            if meses is None or (prop, ym) in meses or ('*', ym) in meses:
                out.append(mensal(ie, prop, ym, l))
        ya = collections.defaultdict(list)
        for t in ts:
            ya[t['date'][:4]].append(t)
        for y, l in sorted(ya.items()):
            if anos is not None and y not in anos:
                continue
            bp = collections.defaultdict(list)
            for t in l:
                bp[t.get('prop')].append(t)
            for p, lp in bp.items():
                out.append(anual(ie, p, y, lp))
            out.append(consolidado(ie, y, l))
            out.append(planejamento(ie, y, l, hoje))
    return out
