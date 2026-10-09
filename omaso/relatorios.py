"""Relatórios HTML: mensal por propriedade, anual por propriedade, consolidado da inscrição e planejamento de fechamento."""
import collections, datetime as dt, json, os, re
from .util import E, brl, money, m0, MESES, MESES_TXT, ABR, S, H, is_idn, notas_abertas, ativos

CSS = '''@page{size:A4;margin:14mm 14mm 16mm}
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
.card{border:1px solid #d7ded8;border-radius:8px;padding:10px 12px}
.card .lbl{font-size:10px;text-transform:uppercase;letter-spacing:.06em;color:#5b6b60}
.card .val{font-size:19px;font-weight:700;margin-top:4px}
.card .sub{font-size:10.5px;color:#5b6b60;margin-top:2px}
.card.venda .val{color:#2f5d3a}.card.compra .val{color:#7a4b12}.card.desp .val{color:#8a2a2a}
h2{font-size:13px;margin:14px 0 6px;color:#2f5d3a;text-transform:uppercase;letter-spacing:.05em}
table{width:100%;border-collapse:collapse}
th,td{padding:4px 6px;border-bottom:1px solid #e3e8e4;text-align:left;vertical-align:top}
th{font-size:10px;text-transform:uppercase;color:#5b6b60;background:#f5f7f5}
td.n,th.n{text-align:right;white-space:nowrap}
tr.tot td{font-weight:700;border-top:2px solid #2f5d3a}
.ok{color:#2f7a45;font-weight:700}.warn{color:#b25a00;font-weight:700}
ul.pend{margin:4px 0 10px 16px;padding:0}
ul.pend li{margin:3px 0}
.box{border:1px solid #f0d9b5;background:#fff8ee;border-radius:8px;padding:8px 12px;margin-bottom:10px}
.box.idn{border-color:#d7ded8;background:#f7f9f7}
.empty{color:#2f7a45;font-weight:600}
.foot{margin-top:14px;font-size:9.5px;color:#7b877f}'''
CSS_ANUAL = CSS + '''
.cards{grid-template-columns:repeat(4,1fr)}
.card .val{font-size:15.5px;white-space:nowrap}
.card.res .val{color:#1d2a22}
.card.res.neg .val{color:#8a2a2a}
table.mx{font-size:9.5px}
table.mx th,table.mx td{padding:3px 4px}
td.z{color:#b9c2bb}
.note{font-size:10.5px;color:#4b5a50;margin:4px 0 10px}
'''
CSS_CONS = CSS_ANUAL + '''
table.mx td:first-child{white-space:nowrap}
table.mx{font-size:8.3px} table.mx th,table.mx td{padding:2px 2px!important}
'''
CSS_PLAN = CSS + '''
.cards{grid-template-columns:repeat(4,1fr)} .card .val{font-size:15.5px;white-space:nowrap}
.big{font-size:26px;font-weight:700;color:#1d2a22} .hl{background:#eef5ee;border:1px solid #cfe0cf;border-radius:8px;padding:12px 16px;margin:10px 0}
.hl .lbl{font-size:10px;text-transform:uppercase;letter-spacing:.06em;color:#4b5a50}
.note{font-size:10.5px;color:#4b5a50;margin:4px 0 10px} ol.p li,ul.p li{font-size:11px;margin:3px 0}
'''
FALTA = re.compile(r'^falta|sem comprovante|sem nf|sem recibo|sem a |só o boleto', re.I)


def _doc(ie):
    d = re.sub(r'\D', '', ie.get('doc', ''))
    if len(d) == 11:
        return 'CPF ' + f'{d[:3]}.{d[3:6]}.{d[6:9]}-{d[9:]}'
    if len(d) == 14:
        return 'CNPJ ' + f'{d[:2]}.{d[2:5]}.{d[5:8]}/{d[8:12]}-{d[12:]}'
    return ie.get('doc', '')


def _meta(ie, linha3):
    return (f"<div class='meta'>Produtor: <b>{E(ie['nome'])}</b><br>{_doc(ie)} · Inscrição Estadual {E(ie['ie'])}"
            f"<br>{linha3}</div>")


def _desc(t):
    return E((t.get('label') or '').replace('_', ' · ').replace('-', ' '))


def _dm(t):
    return f"{t['date'][8:]}/{t['date'][5:7]}"


def _ul(l):
    return '<ul class="pend">' + ''.join(f'<li>{E(x)}</li>' for x in l) + '</ul>'


def _props(ie, ts):
    ordem = [p['nome'] for p in ie.get('propriedades', [])]
    extra = sorted({t['prop'] for t in ts} - set(ordem))
    return [p for p in ordem + extra if any(t['prop'] == p for t in ts)]


def _split(ts):
    desp = [t for t in ts if t['kind'] == 'desp' and not is_idn(t)]
    comp = [t for t in ts if t['kind'] == 'compra']
    vend = [t for t in ts if t['kind'] == 'venda']
    idn = [t for t in ts if is_idn(t)]
    return desp, comp, vend, idn


def _npend(ts):
    """pendências abertas + itens a identificar"""
    return sum(len(notas_abertas(t)) for t in ts if not is_idn(t)) + sum(1 for t in ts if is_idn(t))


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
        return (f"<tr><td>{_dm(t)}</td><td>{E(t['cat'])}</td><td>{_desc(t)}</td><td class='n'>{cab}</td>"
                f"<td class='n'>{money(t.get('value'))}</td><td>{st}</td></tr>")
    lanc = ''.join(txrow(t) for t in sorted(ts, key=lambda t: (t['date'], t['cat'])) if not is_idn(t))
    pend = [n for t in ts if not is_idn(t) for n in notas_abertas(t)]
    falta = [n for n in pend if FALTA.search(n)]
    outros = [n for n in pend if n not in falta]
    p2 = ''
    if falta:
        p2 += f"<h2>Documentos faltando</h2><div class='box'>{_ul(falta)}</div>"
    if outros:
        p2 += f"<h2>Divergências e pontos a conferir</h2><div class='box'>{_ul(outros)}</div>"
    if idn:
        idtxt = [f"{_dm(t)} — {money(t.get('value')) if t.get('value') else 's/ valor'} — {n}"
                 for t in idn for n in (t.get('notes') or ['Sem documento fiscal'])]
        p2 += ("<h2>Pagamentos a identificar</h2><div class='box idn'>" + _ul(idtxt) +
               "<div style='font-size:10px;color:#5b6b60'>Estão na pasta “000 - A Identificar” e não entram nos totais até você dizer se são da atividade rural.</div></div>")
    if not p2:
        p2 = "<p class='empty'>Nenhuma pendência neste mês.</p>"
    head = (f"<header><div><div class='brand'>OMASO</div><h1>Relatório de {mes}</h1><div style='font-size:12px;color:#4b5a50;margin-top:2px'>{E(prop)}</div></div>\n"
            + _meta(ie, f'Propriedade: {E(prop)}') + "</header>")
    return f"""<!doctype html><html lang='pt-BR'><head><meta charset='utf-8'><title>Relatório {mes} — {E(prop)}</title><style>{CSS}</style></head><body>
<div class='page'>{head}
<div class='cards'>
<div class='card desp'><div class='lbl'>Despesas</div><div class='val'>{money(sd) if sd else 'R$ 0,00'}</div><div class='sub'>{len(desp)} lançamento(s)</div></div>
<div class='card compra'><div class='lbl'>Compra de animais</div><div class='val'>{money(sc) if sc else 'R$ 0,00'}</div><div class='sub'>{H(comp)} cabeça(s) · {len(comp)} operação(ões)</div></div>
<div class='card venda'><div class='lbl'>Venda de animais</div><div class='val'>{money(sv) if sv else 'R$ 0,00'}</div><div class='sub'>{H(vend)} cabeça(s) · {len(vend)} operação(ões)</div></div>
</div>
<h2>Despesas por categoria</h2><table><tr><th>Categoria</th><th class='n'>Lanç.</th><th class='n'>Valor</th></tr>{rows}</table>
<h2>Lançamentos do mês</h2><table style='table-layout:fixed'><colgroup><col style='width:7%'><col style='width:21%'><col style='width:42%'><col style='width:9%'><col style='width:13%'><col style='width:8%'></colgroup><tr><th>Data</th><th>Categoria</th><th>Operação</th><th class='n'>Cab.</th><th class='n'>Valor</th><th>Docs</th></tr>{lanc or "<tr><td colspan=6>Nenhum lançamento.</td></tr>"}</table>
<div class='foot'>Mês de lançamento = data do pagamento/recebimento (sem comprovante, usa-se a data do documento). Valores de venda incluem complementos e descontam devoluções.</div>
</div>
<div class='page'>{head}<h2 style='margin-top:4px'>Pendências de {mes}</h2>{p2}</div>
</body></html>"""


def _mes_a_mes(y, ts, months):
    desp, comp, vend, _ = _split(ts)
    sd, sc, sv = S(desp), S(comp), S(vend)
    rows = ''
    for m in months:
        f = lambda l: [t for t in l if int(t['date'][5:7]) == m]
        d, c, v = S(f(desp)), S(f(comp)), S(f(vend))
        r = v - c - d
        neg = ' style="color:#8a2a2a"' if r < 0 else ''
        np_ = _npend(f(ts))
        rows += (f"<tr><td>{MESES_TXT[m]}</td><td class='n'>{m0(d)}</td><td class='n'>{m0(c)}</td><td class='n'>{H(f(comp)) or '—'}</td>"
                 f"<td class='n'>{m0(v)}</td><td class='n'>{H(f(vend)) or '—'}</td><td class='n'{neg}>{brl(r)}</td><td class='n'>{np_ or '—'}</td></tr>")
    rows += (f"<tr class='tot'><td>Total {y}</td><td class='n'>{m0(sd)}</td><td class='n'>{m0(sc)}</td><td class='n'>{H(comp) or '—'}</td>"
             f"<td class='n'>{m0(sv)}</td><td class='n'>{H(vend) or '—'}</td><td class='n'>{brl(sv - sc - sd)}</td><td></td></tr>")
    return rows


def _matriz(ts, months):
    desp, comp, vend, _ = _split(ts)
    bc = collections.defaultdict(list)
    for t in desp:
        bc[t['cat']].append(t)
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


def _cards4(desp, comp, vend):
    sd, sc, sv = S(desp), S(comp), S(vend)
    res = sv - sc - sd
    return f"""<div class='cards'>
<div class='card venda'><div class='lbl'>Venda de animais</div><div class='val'>{money(sv)}</div><div class='sub'>{H(vend)} cabeça(s) · {len(vend)} operação(ões)</div></div>
<div class='card compra'><div class='lbl'>Compra de animais</div><div class='val'>{money(sc)}</div><div class='sub'>{H(comp)} cabeça(s) · {len(comp)} operação(ões)</div></div>
<div class='card desp'><div class='lbl'>Despesas</div><div class='val'>{money(sd)}</div><div class='sub'>{len(desp)} lançamento(s)</div></div>
<div class='card res{' neg' if res < 0 else ''}'><div class='lbl'>Resultado de caixa</div><div class='val'>R$ {brl(res)}</div><div class='sub'>vendas − compras − despesas</div></div>
</div>"""


def anual(ie, prop, y, ts):
    desp, comp, vend, idn = _split(ts)
    sd = S(desp)
    months = sorted({int(t['date'][5:7]) for t in ts})
    bc = collections.defaultdict(list)
    for t in desp:
        bc[t['cat']].append(t)
    crow = ''.join(f"<tr><td>{E(c)}</td><td class='n'>{len(bc[c])}</td><td class='n'>{money(S(bc[c]))}</td><td class='n'>{S(bc[c]) / sd * 100:.1f}%</td></tr>"
                   for c in sorted(bc, key=lambda c: -S(bc[c])))
    crow += (f"<tr class='tot'><td>Total de despesas</td><td class='n'>{len(desp)}</td><td class='n'>{money(sd)}</td><td class='n'>100%</td></tr>"
             if desp else "<tr><td colspan=4>Sem despesas no ano.</td></tr>")
    pend = [(t, n) for t in ts if not is_idn(t) for n in notas_abertas(t)]
    pl = ''.join(f"<li><b>{_dm(t)}</b> — {E(n)}</li>" for t, n in sorted(pend, key=lambda x: x[0]['date']))
    il = ''.join(f"<li><b>{_dm(t)}</b> — {money(t.get('value')) if t.get('value') else 's/ valor'} — {_desc(t)}</li>" for t in sorted(idn, key=lambda t: t['date']))
    p2 = f"<h2>Movimento por categoria e mês (R$)</h2>{_matriz(ts, months)}"
    p2 += (f"<h2>Pendências do ano ({len(pend)})</h2><div class='box'><ul class='pend'>{pl}</ul></div>" if pend
           else "<h2>Pendências do ano</h2><p class='empty'>Nenhuma pendência.</p>")
    if idn:
        p2 += f"<h2>Pagamentos a identificar ({len(idn)} · {money(S(idn))})</h2><div class='box idn'><ul class='pend'>{il}</ul><div style='font-size:10px;color:#5b6b60'>Fora dos totais até serem classificados.</div></div>"
    periodo = f"{MESES_TXT[months[0]]} a {MESES_TXT[months[-1]]} de {y}" if len(months) > 1 else f"{MESES_TXT[months[0]]} de {y}"
    head = (f"<header><div><div class='brand'>OMASO</div><h1>Relatório Anual {y}</h1><div style='font-size:12px;color:#4b5a50;margin-top:2px'>{E(prop)} · {periodo}</div></div>\n"
            + _meta(ie, f'Propriedade: {E(prop)}') + "</header>")
    return f"""<!doctype html><html lang='pt-BR'><head><meta charset='utf-8'><title>Relatório Anual {y} — {E(prop)}</title><style>{CSS_ANUAL}</style></head><body>
<div class='page'>{head}
{_cards4(desp, comp, vend)}
<h2>Mês a mês (R$)</h2><table><tr><th>Mês</th><th class='n'>Despesas</th><th class='n'>Compras</th><th class='n'>Cab.</th><th class='n'>Vendas</th><th class='n'>Cab.</th><th class='n'>Resultado</th><th class='n'>Pend.</th></tr>{_mes_a_mes(y, ts, months)}</table>
<h2>Despesas por categoria no ano</h2><table><tr><th>Categoria</th><th class='n'>Lanç.</th><th class='n'>Valor</th><th class='n'>% das despesas</th></tr>{crow}</table>
<div class='foot'>Totais somam os relatórios mensais desta propriedade. Mês de lançamento = data do pagamento/recebimento. Pagamentos “A Identificar” ficam fora dos totais. “Pend.” = pendências + itens a identificar do mês.</div>
</div>
<div class='page'>{head}{p2}</div>
</body></html>"""


def consolidado(ie, y, ts):
    desp, comp, vend, idn = _split(ts)
    sd, sc, sv = S(desp), S(comp), S(vend)
    res = sv - sc - sd
    props = _props(ie, ts)
    pr = ''
    for p in props:
        f = lambda l: [t for t in l if t['prop'] == p]
        d, c, v = S(f(desp)), S(f(comp)), S(f(vend))
        r = v - c - d
        neg = ' style="color:#8a2a2a"' if r < 0 else ''
        pr += f"<tr><td>{E(p)}</td><td class='n'>{m0(v)}</td><td class='n'>{H(f(vend)) or '—'}</td><td class='n'>{m0(c)}</td><td class='n'>{H(f(comp)) or '—'}</td><td class='n'>{m0(d)}</td><td class='n'{neg}>{brl(r)}</td></tr>"
    pr += f"<tr class='tot'><td>Total da inscrição</td><td class='n'>{m0(sv)}</td><td class='n'>{H(vend) or '—'}</td><td class='n'>{m0(sc)}</td><td class='n'>{H(comp) or '—'}</td><td class='n'>{m0(sd)}</td><td class='n'>{brl(res)}</td></tr>"
    months = sorted({int(t['date'][5:7]) for t in ts})
    bc = collections.defaultdict(list)
    for t in desp:
        bc[t['cat']].append(t)
    ab = lambda p: p.replace('Estancia', 'Est.').replace('Fazenda', 'Faz.').replace('Sitio', 'Sítio')
    ph = ''.join(f"<th class='n'>{E(ab(p))}</th>" for p in props)
    cr = ''
    for c in sorted(bc, key=lambda c: -S(bc[c])):
        cells = ''.join(f"<td class='n'>{m0(S([t for t in bc[c] if t['prop'] == p]))}</td>" for p in props)
        cr += f"<tr><td>{E(c)}</td>{cells}<td class='n'><b>{m0(S(bc[c]))}</b></td><td class='n'>{S(bc[c]) / sd * 100:.1f}%</td></tr>"
    cells = ''.join(f"<td class='n'>{m0(S([t for t in desp if t['prop'] == p]))}</td>" for p in props)
    cr += f"<tr class='tot'><td>Total de despesas</td>{cells}<td class='n'>{m0(sd)}</td><td class='n'>100%</td></tr>"
    npend = sum(len(notas_abertas(t)) for t in ts if not is_idn(t))
    pp = ''.join(f"<li><b>{E(p)}</b>: {sum(len(notas_abertas(t)) for t in ts if t['prop'] == p and not is_idn(t))} pendência(s), "
                 f"{len([t for t in idn if t['prop'] == p])} pagamento(s) a identificar ({money(S([t for t in idn if t['prop'] == p]))})</li>" for p in props)
    periodo = f"{MESES_TXT[months[0]]} a {MESES_TXT[months[-1]]} de {y}"
    head = (f"<header><div><div class='brand'>OMASO</div><h1>Relatório Anual Consolidado {y}</h1><div style='font-size:12px;color:#4b5a50;margin-top:2px'>Todas as propriedades da Inscrição Estadual {E(ie['ie'])} · {periodo}</div></div>\n"
            + _meta(ie, f"Propriedades: {E(', '.join(props))}") + "</header>")
    return f"""<!doctype html><html lang='pt-BR'><head><meta charset='utf-8'><title>Relatório Anual Consolidado {y} — IE {E(ie['ie'])}</title><style>{CSS_CONS}</style></head><body>
<div class='page'>{head}
{_cards4(desp, comp, vend)}
<h2>Por propriedade (R$)</h2><table><tr><th>Propriedade</th><th class='n'>Vendas</th><th class='n'>Cab.</th><th class='n'>Compras</th><th class='n'>Cab.</th><th class='n'>Despesas</th><th class='n'>Resultado</th></tr>{pr}</table>
<h2>Mês a mês — todas as propriedades (R$)</h2><table><tr><th>Mês</th><th class='n'>Despesas</th><th class='n'>Compras</th><th class='n'>Cab.</th><th class='n'>Vendas</th><th class='n'>Cab.</th><th class='n'>Resultado</th><th class='n'>Pend.</th></tr>{_mes_a_mes(y, ts, months)}</table>
<div class='foot'>Soma dos relatórios anuais de cada propriedade da mesma inscrição estadual. Mês de lançamento = data do pagamento/recebimento. Pagamentos “A Identificar” e documentos fora da atividade rural ficam fora dos totais. Cabeças de compra negativas = devoluções.</div>
</div>
<div class='page'>{head}
<h2>Despesas por categoria e propriedade (R$)</h2><table class='mx'><tr><th>Categoria</th>{ph}<th class='n'>Total</th><th class='n'>%</th></tr>{cr}</table>
</div>
<div class='page'>{head}
<h2>Movimento por categoria e mês (R$)</h2>{_matriz(ts, months)}
<h2>Pendências ({npend}) e pagamentos a identificar ({len(idn)} · {money(S(idn))})</h2><div class='box'><ul class='pend'>{pp}</ul><div style='font-size:10px;color:#5b6b60'>O detalhe de cada pendência está no relatório anual e nos relatórios mensais de cada propriedade.</div></div>
</div></body></html>"""


def planejamento(ie, y, ts, hoje):
    mo = lambda v: 'R$ ' + brl(v)
    desp, comp, vend, idn = _split(ts)
    sv, sc, sd = S(vend), S(comp), S(desp)
    res = sv - sc - sd
    lim = (hoje - dt.timedelta(days=90)).isoformat()
    rc = [t for t in comp if t['date'] >= lim and (t.get('heads') or 0) > 0 and (t.get('value') or 0) > 0]
    if H(rc) < 50:
        rc = [t for t in comp if (t.get('heads') or 0) > 0 and (t.get('value') or 0) > 0]
    preco = S(rc) / H(rc) if H(rc) else 0
    precos = sorted(t['value'] / t['heads'] for t in rc)
    fech = sorted({t['date'][:7] for t in desp if t['date'][:7] < hoje.strftime('%Y-%m')})
    media = sum(t.get('value') or 0 for t in desp if t['date'][:7] in fech) / max(1, len(fech))
    falt = max(0, 12 - hoje.month + (1 if hoje.day <= 15 else 0)) if str(hoje.year) == str(y) else 0
    proj = media * falt
    need0, need1 = max(0, res), max(0, res - proj)
    cab = lambda v, p=preco: (int(v // p) + 1 if v > 0 else 0) if p else 0
    props = _props(ie, ts)
    pr = ''
    for p in props:
        f = lambda l: [t for t in l if t['prop'] == p]
        r = S(f(vend)) - S(f(comp)) - S(f(desp))
        pr += f"<tr><td>{E(p)}</td><td class='n'>{brl(S(f(vend)))}</td><td class='n'>{brl(S(f(comp)))}</td><td class='n'>{brl(S(f(desp)))}</td><td class='n'{' style=color:#8a2a2a' if r < 0 else ''}>{brl(r)}</td></tr>"
    pr += f"<tr class='tot'><td>Total da IE {E(ie['ie'])}</td><td class='n'>{brl(sv)}</td><td class='n'>{brl(sc)}</td><td class='n'>{brl(sd)}</td><td class='n'>{brl(res)}</td></tr>"
    if len(precos) >= 4:
        pc = [round(precos[len(precos) // 4], -1), round(preco, -1), round(precos[3 * len(precos) // 4], -1)]
    else:
        pc = [round(preco * 0.85, -1), round(preco, -1), round(preco * 1.15, -1)]
    cen = ''
    for lab, v in [('Só com o que já está lançado', need0), (f'Descontando despesas previstas até 31/12 (≈ {mo(proj)})', need1)]:
        cen += f"<tr><td>{lab}</td><td class='n'><b>{brl(v)}</b></td>" + ''.join(f"<td class='n'>{cab(v, p)}</td>" for p in pc) + "</tr>"
    ex = ''.join(f"<tr><td>Se vender mais {mo(v)} até 31/12</td><td class='n'>{brl(need1 + v)}</td><td class='n'>{cab(need1 + v)}</td></tr>" for v in [100000, 300000, 500000, 1000000])
    npend = sum(len(notas_abertas(t)) for t in ts if not is_idn(t))
    cond = ("<li><b>“e Outro”:</b> se a exploração for em condomínio/parceria, o resultado é dividido entre os participantes na proporção de cada um — confirme a porcentagem com o contador.</li>"
            if re.search(r'\be outr', ie['nome'], re.I) else '')
    hj = hoje.strftime('%d/%m/%Y')
    return f"""<!doctype html><html lang='pt-BR'><head><meta charset='utf-8'><title>Planejamento de Fechamento {y} — IE {E(ie['ie'])}</title><style>{CSS_PLAN}</style></head><body>
<div class='page'><header><div><div class='brand'>OMASO</div><h1>Planejamento de Fechamento {y}</h1><div style='font-size:12px;color:#4b5a50;margin-top:2px'>Quanto comprar em gado para o resultado da atividade rural de {y} ficar negativo · posição em {hj}</div></div>
{_meta(ie, 'Todas as propriedades')}</header>
<h2>Resultado de {y} até agora (R$)</h2>
<table><tr><th>Propriedade</th><th class='n'>Vendas</th><th class='n'>Compras de gado</th><th class='n'>Despesas</th><th class='n'>Resultado</th></tr>{pr}</table>
<div class='hl'><div class='lbl'>Para fechar {y} com resultado negativo, ainda é preciso comprar e PAGAR até 31/12 mais de</div>
<div class='big'>{mo(need1)} ≈ {cab(need1)} cabeças</div>
<div class='note'>Considerando nenhuma venda nova até o fim do ano, despesas normais de ≈ {mo(media)}/mês nos {falt} mês(es) restantes e preço médio de compra de {mo(preco)} por cabeça ({H(rc)} cabeças, {mo(S(rc))} nas compras usadas como base). Sem contar as despesas previstas: {mo(need0)} ≈ {cab(need0)} cabeças.</div></div>
<h2>Cabeças necessárias conforme o preço pago</h2>
<table><tr><th>Cenário</th><th class='n'>Valor a comprar</th>{''.join(f"<th class='n'>a {mo(p)}/cab</th>" for p in pc)}</tr>{cen}</table>
<h2>Cada venda nova aumenta a compra necessária no mesmo valor</h2>
<table><tr><th>Cenário</th><th class='n'>Valor a comprar</th><th class='n'>Cab. (a {mo(preco)})</th></tr>{ex}</table>
<div class='foot'>Regime de caixa: entra no ano o que foi efetivamente recebido ou pago até 31/12 (a data do pagamento manda, não a da nota). Pagamentos “A Identificar” e documentos fora da atividade rural não entram.</div>
</div>
<div class='page'><header><div><div class='brand'>OMASO</div><h1>Planejamento de Fechamento {y}</h1></div><div class='meta'>IE {E(ie['ie'])} · posição em {hj}</div></header>
<h2>Como funciona (Imposto de Renda – atividade rural)</h2>
<ul class='p'>
<li><b>Resultado = receitas recebidas − despesas pagas</b> no ano (livro caixa). A compra de gado para cria/recria/engorda entra como despesa no mês em que é paga.</li>
<li><b>Prejuízo não se perde:</b> o resultado negativo de um ano pode ser compensado com o resultado positivo dos anos seguintes.</li>
<li><b>É adiamento, não eliminação:</b> o gado comprado agora vira receita quando for vendido em {int(y) + 1}. O imposto é empurrado para frente.</li>
<li><b>Alternativa – resultado presumido (20% da receita bruta):</b> hoje daria {mo(0.2 * sv)} de resultado, contra {mo(max(res, 0))} pelo livro caixa. Quem escolhe os 20% perde o direito de compensar prejuízos daquele ano. Compras não reduzem esse valor.</li>
{cond}
<li><b>Rebanho no fim do ano:</b> as cabeças em estoque em 31/12 são informadas na declaração (quantidade), mas não mudam o resultado; o que muda é o que foi pago e recebido.</li>
</ul>
<h2>O que ainda pode mudar este número</h2>
<ul class='p'>
<li>{npend} pendência(s) em aberto e {len(idn)} pagamento(s) “A Identificar” ({mo(S(idn))}) — ver Relatório Anual Consolidado.</li>
<li>Vendas registradas pelo valor da nota: se algum comprador pagou valor diferente, a receita de caixa muda.</li>
<li>Compras sem comprovante de pagamento só podem ser deduzidas se foram pagas no ano.</li>
<li>Documentos do ano ainda não enviados ao OMASO.</li>
</ul>
<div class='foot'>Relatório de apoio gerado pelo OMASO a partir dos lançamentos. Não substitui a orientação do contador — confirme os valores e a estratégia antes de comprar.</div>
</div></body></html>"""


def gerar(db, out, ie_num=None, anos=None, meses=None, hoje=None):
    """Gera os relatórios e devolve a lista [{caminho, nome, ie, tipo, ano, mes?, prop?}].
    meses: lista de (prop|'*', 'AAAA-MM'); None = todos. anos: lista de 'AAAA'; None = todos."""
    hoje = hoje or dt.date.today()
    gerados = []

    def w(rel, nome, html, **kw):
        os.makedirs(os.path.join(out, rel), exist_ok=True)
        with open(os.path.join(out, rel, nome), 'w', encoding='utf-8') as f:
            f.write(html)
        gerados.append(dict(caminho=f'{rel}/{nome}', nome=nome, **kw))

    for ie in db.ies:
        if ie_num and re.sub(r'\D', '', ie['ie']).lstrip('0') != re.sub(r'\D', '', ie_num).lstrip('0'):
            continue
        ts = [t for t in ativos(db.txs_da_ie(ie['ie'])) if t.get('date')]
        base = ie['pasta']
        grupos = collections.defaultdict(list)
        for t in ts:
            grupos[(t['prop'], t['date'][:7])].append(t)
        for (prop, ym), g in sorted(grupos.items()):
            if meses is not None and not any((p in ('*', prop)) and m == ym for p, m in meses):
                continue
            y, m = ym.split('-')
            nome = f"Relatorio_{ym}_{MESES[int(m)]}_{prop.replace(' ', '-')}.html"
            w(f"{base}/{prop}/{ym} {MESES[int(m)]}", nome, mensal(ie, prop, ym, g), ie=ie['ie'], tipo='mensal', ano=y, mes=int(m), prop=prop)
        porano = collections.defaultdict(list)
        for t in ts:
            porano[t['date'][:4]].append(t)
        for y, g in sorted(porano.items()):
            if anos is not None and y not in anos:
                continue
            for prop in _props(ie, g):
                gp = [t for t in g if t['prop'] == prop]
                w(f"{base}/{prop}", f"Relatorio_Anual_{y}_{prop.replace(' ', '-')}.html", anual(ie, prop, y, gp), ie=ie['ie'], tipo='anual', ano=y, prop=prop)
            w(base, f"Relatorio_Anual_Consolidado_{y}_IE-{ie['ie']}.html", consolidado(ie, y, g), ie=ie['ie'], tipo='consolidado', ano=y)
            if y == str(hoje.year):
                w(base, f"Planejamento_Fechamento_{y}_IE-{ie['ie']}.html", planejamento(ie, y, g, hoje), ie=ie['ie'], tipo='planejamento', ano=y)
    with open(os.path.join(out, '_gerados.json'), 'w', encoding='utf-8') as f:
        json.dump(gerados, f, ensure_ascii=False, indent=1)
    return gerados
