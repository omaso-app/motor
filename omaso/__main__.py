"""Linha de comando do motor OMASO.

  python -m omaso nfe ARQUIVO.xml [...]            -> JSON com os dados de cada nota
  python -m omaso classificar --db DIR ARQ.xml...  -> sugestão de lançamento para cada nota
  python -m omaso relatorios --db DIR --out DIR [--ie N] [--anos 2026,2025] [--meses "Prop|2026-09;*|2026-10"]
  python -m omaso irpf --db DIR --out DIR --ano 2026 [--ie N]
  python -m omaso sha ARQUIVO [...]
  python -m omaso pastas --db DIR                  -> lista de pastas esperadas por inscrição
  python -m omaso anexos MENSAGEM_RAW.json --out DIR -> extrai os anexos de um e-mail (get_message RAW)
  python -m omaso id "CAMINHO/DA/PASTA"            -> id do lançamento no banco ("t" + sha1[:12])
  python -m omaso b64 ARQUIVO                      -> conteúdo em base64 (para create_file)

Os arquivos são gravados em OUT/<caminho relativo à pasta INSCRIÇÕES> e um índice OUT/_gerados.json
lista cada arquivo com tipo, ie, ano, mes e prop (para a lista de relatórios do OMASO).
"""
import argparse, json, os, sys, datetime as dt
from . import nfe, regras, relatorios, irpf, util, email_anexos
import hashlib, base64
from .db import DB


def _w(out, rel, content, mode='w'):
    p = os.path.join(out, rel)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    if mode == 'w':
        open(p, 'w', encoding='utf-8').write(content)
    else:
        content.save(p)
    return p


def main(argv=None):
    ap = argparse.ArgumentParser(prog='omaso')
    sp = ap.add_subparsers(dest='cmd', required=True)
    a = sp.add_parser('nfe'); a.add_argument('arquivos', nargs='+')
    a = sp.add_parser('classificar'); a.add_argument('--db', required=True); a.add_argument('arquivos', nargs='+')
    a = sp.add_parser('relatorios'); a.add_argument('--db', required=True); a.add_argument('--out', required=True)
    a.add_argument('--ie'); a.add_argument('--anos'); a.add_argument('--meses'); a.add_argument('--hoje')
    a = sp.add_parser('irpf'); a.add_argument('--db', required=True); a.add_argument('--out', required=True)
    a.add_argument('--ano', required=True); a.add_argument('--ie')
    a = sp.add_parser('sha'); a.add_argument('arquivos', nargs='+')
    a = sp.add_parser('pastas'); a.add_argument('--db', required=True)
    a = sp.add_parser('anexos'); a.add_argument('arquivo'); a.add_argument('--out', required=True)
    a = sp.add_parser('id'); a.add_argument('pasta')
    a = sp.add_parser('b64'); a.add_argument('arquivo')
    o = ap.parse_args(argv)

    if o.cmd == 'nfe':
        print(json.dumps([nfe.ler(f) for f in o.arquivos], ensure_ascii=False, indent=1))
    elif o.cmd == 'classificar':
        db = DB(o.db)
        res = []
        for f in o.arquivos:
            rec = nfe.ler(f)
            c = regras.classificar(db, rec)
            c['arquivo'] = f
            c['sha256'] = util.sha256(f)
            c['sha_repetido'] = c['sha256'] in db.shas
            c['nota'] = {k: rec.get(k) for k in ('tipo', 'numero', 'data', 'valor', 'emitente', 'destinatario', 'cfops', 'finalidade', 'refs', 'vencimentos')}
            if c.get('destino') == 'geral' and db.ies:
                ie = db.ie(c.get('ie')) if c.get('ie') else db.ies[0]
                c['pasta'] = regras.pasta_geral(ie, c['pasta_geral'])
            if c.get('destino') == 'fora':
                ie = db.ies[0]
                c['pasta'] = regras.pasta_geral(ie, c['pasta_geral'])
            res.append(c)
        print(json.dumps(res, ensure_ascii=False, indent=1))
    elif o.cmd == 'relatorios':
        db = DB(o.db)
        anos = set(o.anos.split(',')) if o.anos else None
        meses = None
        if o.meses:
            meses = set(tuple(x.split('|', 1)) for x in o.meses.split(';') if '|' in x)
        hoje = dt.date.fromisoformat(o.hoje) if o.hoje else None
        idx = []
        for rel, html, info in relatorios.gerar(db, o.ie, anos, meses, hoje):
            _w(o.out, rel, html)
            idx.append(dict(info, caminho=rel, nome=os.path.basename(rel)))
        _w(o.out, '_gerados.json', json.dumps(idx, ensure_ascii=False, indent=1))
        print(json.dumps(idx, ensure_ascii=False, indent=1))
    elif o.cmd == 'irpf':
        db = DB(o.db)
        idx = []
        for ie in ([db.ie(o.ie)] if o.ie else db.ies):
            rel, wb = irpf.gerar(ie, o.ano, db.txs_da_ie(ie['ie']))
            _w(o.out, rel, wb, mode='xlsx')
            idx.append(dict(tipo='irpf', ie=str(ie['ie']), ano=str(o.ano), caminho=rel, nome=os.path.basename(rel)))
        print(json.dumps(idx, ensure_ascii=False, indent=1))
    elif o.cmd == 'sha':
        for f in o.arquivos:
            print(util.sha256(f), f)
    elif o.cmd == 'anexos':
        print(json.dumps(email_anexos.extrair(o.arquivo, o.out), ensure_ascii=False, indent=1))
    elif o.cmd == 'id':
        print('t' + hashlib.sha1(o.pasta.encode('utf-8')).hexdigest()[:12])
    elif o.cmd == 'b64':
        sys.stdout.write(base64.b64encode(open(o.arquivo, 'rb').read()).decode())
    elif o.cmd == 'pastas':
        db = DB(o.db)
        for ie in db.ies:
            print(ie['pasta'])
            for p in ie.get('propriedades') or []:
                print('  ' + p['nome'])


if __name__ == '__main__':
    sys.exit(main())
