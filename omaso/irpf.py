"""Planilha anual de apoio ao IRPF (Livro Caixa da atividade rural), com totais por fórmula."""
import collections
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment
from .util import ABR, is_idn, notas_abertas, limpo

VERDE = PatternFill('solid', fgColor='2F5D3A')
CINZA = PatternFill('solid', fgColor='F5F7F5')
BRL = '#,##0.00;[Red]-#,##0.00'


def _head(ws, cols, widths):
    for i, (c, w) in enumerate(zip(cols, widths), 1):
        cell = ws.cell(row=1, column=i, value=c)
        cell.font = Font(bold=True, color='FFFFFF'); cell.fill = VERDE
        ws.column_dimensions[cell.column_letter].width = w
    ws.freeze_panes = 'A2'


def gerar(ie, ano, ts):
    """ts = lançamentos vivos da inscrição (todos os anos). Devolve (caminho_relativo, Workbook)."""
    ts = sorted([t for t in ts if t['date'][:4] == str(ano)], key=lambda t: (t['date'], t.get('cat') or ''))
    lanc = [t for t in ts if not is_idn(t) and t.get('kind') in ('desp', 'compra', 'venda')]
    idn = [t for t in ts if is_idn(t)]
    wb = Workbook()
    res = wb.active; res.title = 'Resumo'
    wl = wb.create_sheet('Lançamentos'); wm = wb.create_sheet('Mês a mês'); wi = wb.create_sheet('A identificar')

    _head(wl, ['Data', 'Mês', 'Propriedade', 'Tipo', 'Categoria (Livro Caixa)', 'Descrição / documento', 'Cabeças', 'Valor (R$)', 'Pendência aberta', 'Pasta'],
          [11, 6, 22, 10, 36, 48, 9, 16, 50, 60])
    for r, t in enumerate(lanc, 2):
        tipo = 'Receita' if t['kind'] == 'venda' else 'Despesa'
        wl.append([t['date'], int(t['date'][5:7]), t.get('prop'), tipo, t.get('cat'),
                   (t.get('label') or '').replace('_', ' · ').replace('-', ' '), t.get('heads'), t.get('value'),
                   ' | '.join(notas_abertas(t)) or None, t.get('pasta')])
        wl.cell(row=r, column=8).number_format = BRL
    n = max(2, len(lanc) + 1)
    rng = lambda col: f"Lançamentos!${col}$2:${col}${n}"

    res['A1'] = f"Resumo IRPF Rural {ano} — {ie['nome']}"; res['A1'].font = Font(bold=True, size=14)
    res['A2'] = f"CPF/CNPJ {ie.get('doc', '')} · IE {ie['ie']} · Livro Caixa da Atividade Rural (resultado de caixa: receitas recebidas − despesas pagas)"
    per = f"{ts[0]['date'][8:]}/{ts[0]['date'][5:7]} a {ts[-1]['date'][8:]}/{ts[-1]['date'][5:7]}/{ano}" if ts else '—'
    res['A3'] = f'Gerado pelo OMASO a partir dos lançamentos. Pagamentos "a identificar" ficam fora dos totais (aba A identificar). Período com dados: {per}.'
    for i, c in enumerate(['Categoria', 'Tipo', 'Lançamentos', 'Total (R$)'], 1):
        cell = res.cell(row=5, column=i, value=c); cell.font = Font(bold=True, color='FFFFFF'); cell.fill = VERDE
    for col, w in zip('ABCD', (58, 16, 14, 18)):
        res.column_dimensions[col].width = w
    cats = collections.OrderedDict()
    for t in lanc:
        if t['kind'] == 'venda':
            cats.setdefault(t['cat'], 'Receita')
    for t in sorted(lanc, key=lambda t: (t['kind'] != 'compra', t.get('cat') or '')):
        if t['kind'] != 'venda':
            cats.setdefault(t['cat'], 'Despesa')
    r = 6
    first = r
    for c, tipo in cats.items():
        res.cell(row=r, column=1, value=c); res.cell(row=r, column=2, value=tipo)
        res.cell(row=r, column=3, value=f'=COUNTIFS({rng("E")},A{r})')
        res.cell(row=r, column=4, value=f'=SUMIFS({rng("H")},{rng("E")},A{r})').number_format = BRL
        r += 1
    last = r - 1
    r += 1
    for lab, f in [('Total de receitas', f'=SUMIFS(D{first}:D{last},B{first}:B{last},"Receita")'),
                   ('Total de despesas', f'=SUMIFS(D{first}:D{last},B{first}:B{last},"Despesa")'),
                   ('Resultado da atividade rural (receitas − despesas)', f'=D{r}-D{r + 1}')]:
        res.cell(row=r, column=1, value=lab).font = Font(bold=True)
        c = res.cell(row=r, column=4, value=f); c.number_format = BRL; c.font = Font(bold=True)
        r += 1
    res.cell(row=r, column=1, value='Resultado presumido (20% das receitas) — alternativa').font = Font(italic=True)
    res.cell(row=r, column=4, value=f'=D{r - 3}*0.2').number_format = BRL
    r += 2
    res.cell(row=r, column=1, value=f'Pagamentos a identificar (fora dos totais): {len(idn)}').font = Font(italic=True)

    _head(wm, ['Mês', 'Receitas (R$)', 'Despesas (R$)', 'Resultado (R$)', 'Resultado acumulado (R$)'], [10, 18, 18, 18, 22])
    for m in range(1, 13):
        rr = m + 1
        wm.cell(row=rr, column=1, value=ABR[m]); wm.cell(row=rr, column=6, value=m)
        wm.cell(row=rr, column=2, value=f'=SUMIFS({rng("H")},{rng("B")},F{rr},{rng("D")},"Receita")')
        wm.cell(row=rr, column=3, value=f'=SUMIFS({rng("H")},{rng("B")},F{rr},{rng("D")},"Despesa")')
        wm.cell(row=rr, column=4, value=f'=B{rr}-C{rr}')
        wm.cell(row=rr, column=5, value=f'=D{rr}' if m == 1 else f'=E{rr - 1}+D{rr}')
        for c in range(2, 6):
            wm.cell(row=rr, column=c).number_format = BRL
    wm.cell(row=14, column=1, value='Total').font = Font(bold=True)
    for c, L in zip(range(2, 5), 'BCD'):
        x = wm.cell(row=14, column=c, value=f'=SUM({L}2:{L}13)'); x.number_format = BRL; x.font = Font(bold=True)
    wm.column_dimensions['F'].hidden = True

    _head(wi, ['Data', 'Propriedade', 'Descrição', 'Valor (R$)', 'Observação'], [11, 22, 48, 16, 60])
    for t in idn:
        wi.append([t['date'], t.get('prop'), (t.get('label') or '').replace('_', ' · ').replace('-', ' '), t.get('value'),
                   ' | '.join(notas_abertas(t)) or None])
    for row in wi.iter_rows(min_row=2, min_col=4, max_col=4):
        for c in row:
            c.number_format = BRL
    nome = ie.get('nome_arquivo') or limpo(ie['nome'].replace(' e Outro', ''), 40).replace('-', '_')
    path = f"{ie['pasta']}/Resumo_IRPF_Rural/Resumo_IRPF_Rural_{nome}_{ano}.xlsx"
    return path, wb
