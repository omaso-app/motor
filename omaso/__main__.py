"""python -m omaso <comando> ...   (use --help em cada comando)"""
import argparse, base64, datetime as dt, json, sys
from . import nfe, regras, relatorios, irpf, email_anexos
from .db import DB
from .util import sha256, tx_id


def main(argv=None):
    ap = argparse.ArgumentParser(prog='python -m omaso', description='Motor do OMASO')
    sp = ap.add_subparsers(dest='cmd', required=True)
    p = sp.add_parser('nfe', help='lê um XML de NF-e e mostra os dados em JSON'); p.add_argument('xml')
    p = sp.add_parser('classificar', help='sugere a classificação de um XML'); p.add_argument('xml'); p.add_argument('--db', required=True)
    p = sp.add_parser('relatorios', help='gera relatórios HTML')
    p.add_argument('--db', required=True); p.add_argument('--out', required=True); p.add_argument('--ie')
    p.add_argument('--anos', help='ex.: 2025,2026'); p.add_argument('--meses', help='ex.: "Fazenda X|2026-09;*|2026-10"')
    p.add_argument('--hoje', help='AAAA-MM-DD (padrão: hoje)')
    p = sp.add_parser('irpf', help='gera o Resumo IRPF Rural (xlsx)')
    p.add_argument('--db', required=True); p.add_argument('--out', required=True); p.add_argument('--ano', required=True); p.add_argument('--ie')
    p = sp.add_parser('sha', help='sha256 de arquivos'); p.add_argument('arquivos', nargs='+')
    p = sp.add_parser('id', help='id de lançamento para uma pasta'); p.add_argument('pasta')
    p = sp.add_parser('b64', help='conteúdo do arquivo em base64'); p.add_argument('arquivo')
    p = sp.add_parser('anexos', help='extrai anexos de mensagem RAW do Gmail'); p.add_argument('raw'); p.add_argument('--out', required=True)
    p = sp.add_parser('pastas', help='lista as pastas usadas pelos lançamentos'); p.add_argument('--db', required=True)
    a = ap.parse_args(argv)
    pr = lambda o: print(json.dumps(o, ensure_ascii=False, indent=1))

    if a.cmd == 'nfe':
        pr(nfe.ler(a.xml))
    elif a.cmd == 'classificar':
        rec = nfe.ler(a.xml)
        out = regras.classificar(DB(a.db), rec)
        if rec.get('tipo') == 'nfe':
            out['nota'] = {k: rec[k] for k in ('chave', 'numero', 'data', 'finalidade', 'valor', 'cfops', 'emitente', 'destinatario', 'refs', 'vencimentos')}
            out['nota']['produtos'] = [p['descricao'] for p in rec['produtos']][:10]
        pr(out)
    elif a.cmd == 'relatorios':
        meses = None
        if a.meses:
            meses = [tuple(x.split('|', 1)) for x in a.meses.split(';') if '|' in x]
        anos = [x.strip() for x in a.anos.split(',')] if a.anos else None
        hoje = dt.date.fromisoformat(a.hoje) if a.hoje else dt.date.today()
        g = relatorios.gerar(DB(a.db), a.out, a.ie, anos, meses, hoje)
        pr([x['caminho'] for x in g])
    elif a.cmd == 'irpf':
        db = DB(a.db)
        feitos = []
        for ie in db.ies:
            if a.ie and ie['ie'].lstrip('0') != a.ie.lstrip('0'):
                continue
            rel, _ = irpf.gerar(ie, a.ano, db.txs_da_ie(ie['ie']), a.out)
            feitos.append({'caminho': rel, 'nome': rel.split('/')[-1], 'ie': ie['ie'], 'tipo': 'irpf', 'ano': str(a.ano)})
        pr(feitos)
    elif a.cmd == 'sha':
        for f in a.arquivos:
            print(sha256(f), f)
    elif a.cmd == 'id':
        print(tx_id(a.pasta))
    elif a.cmd == 'b64':
        sys.stdout.write(base64.b64encode(open(a.arquivo, 'rb').read()).decode())
    elif a.cmd == 'anexos':
        pr(email_anexos.extrair(a.raw, a.out))
    elif a.cmd == 'pastas':
        for t in DB(a.db).txs:
            print(t.get('id'), t.get('pasta'))


if __name__ == '__main__':
    main()
