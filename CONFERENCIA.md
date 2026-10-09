# Conferência OMASO na nuvem

Roteiro que a tarefa agendada segue. Ela roda na nuvem, sem o computador do cliente, e usa só:
- **ArtifactData** (o banco do OMASO do cliente);
- **Google Drive** (search_files, download_file_content, create_file, update_file, trash_file);
- **Gmail** (search_threads, get_message);
- **este motor** (`python -m omaso ...`).

O único dado do cliente que vem no pedido da tarefa é `OMASO_URL`, o link do artefato dele. Todo o resto (inscrições, pastas, regras, e-mail) está no banco do OMASO.

Responda sempre em português. Escreva no banco só o que este roteiro manda. Nunca apague nada definitivamente: arquivo repetido é **movido** para `_Sistema/_Duplicados (conferir)`, e arquivo velho vai para a lixeira do Drive (trash_file), que guarda por 30 dias.

---

## 0. Preparar

```bash
pip install --break-system-packages -q openpyxl 2>/dev/null; which pdftotext || (apt-get install -y -q poppler-utils >/dev/null 2>&1 || true)
cd /tmp/motor   # já clonado pelo pedido da tarefa
```

Exporte o banco para o disco (o resultado vai para arquivos, não para a conversa):
- ArtifactData `list`, url = OMASO_URL, collection `meta`, query `{"limit":100}`, out_dir `/tmp/db`
- ArtifactData `list`, url = OMASO_URL, collection `txs`, query `{"limit":1000}`, out_dir `/tmp/db` (se vier `next_cursor`, repita com o cursor)

Leia `/tmp/db/meta/config.json`, `ies.json`, `regras.json`, `estado.json` (pode não existir), `pedido.json` (pode não existir).
- `config.inscricoes.id` = pasta INSCRIÇÕES no Drive; `config.inserir.id` = pasta INSERIR ARQUIVOS; `config.drive.id` = pasta-mãe.
- Se `ies.lista` estiver vazio: escreva uma linha ("OMASO ainda não configurado: falta cadastrar a inscrição") e ENCERRE.

## 1. Tem trabalho?

Junte:
1. **INSERIR ARQUIVOS**: `search_files` com `parentId = '<inserir.id>' and mimeType != 'application/vnd.google-apps.folder'` (excludeContentSnippets true).
2. **Gmail**: `search_threads` com `has:attachment (filename:xml OR filename:pdf OR nfe OR "nota fiscal" OR danfe) after:<AAAA/MM/DD>`, onde a data é `estado.gmail_after` (ou `config.email.desde` se não houver estado). Acrescente `OR` com os termos de `config.email.termos`. Ignore mensagens já processadas (ids em `estado.gmail_ids`).
3. **Interface**: lançamentos em `/tmp/db/txs` com `sync` = "novo" ou "alterado".
4. **Pedido**: `pedido.status` = "aguardando" ou "enviado" (alguém apertou ATUALIZAR).
5. **Semana**: `estado.last_run` há 7 dias ou mais.

Se nada disso tiver: escreva uma linha ("Nada novo — última conferência em <data>") e ENCERRE. Se só o item 4 ou 5 valer, pule direto para o passo 7 (relatórios) e o 8.

## 2. Pastas no Drive (função mental `pasta(caminho)`)

Os caminhos de pasta são relativos a INSCRIÇÕES, separados por `/`, ex.:
`<pasta da IE>/<Propriedade>/<AAAA-MM Mês>/<Categoria sem acento>/<AAAA-MM-DD_Descrição_R$valor>`.

Para achar ou criar cada nível: `search_files` com `parentId = '<id do nível de cima>' and title = '<nome>' and mimeType = 'application/vnd.google-apps.folder'`. Se não existir: `create_file` com `title`, `parentId` e `mimeType` de pasta (`application/vnd.google-apps.folder`). Guarde os ids num dicionário durante a execução para não buscar duas vezes.

Atenção: lançamentos antigos podem ter `pasta` começando com um nome antigo do produtor. O primeiro nível é sempre o campo `pasta` da inscrição em `meta/ies`.

## 3. Arquivos da pasta INSERIR ARQUIVOS

Para cada arquivo:
1. `download_file_content`. Se o resultado foi salvo em disco, decodifique o base64 com Python para `/tmp/in/<nome>`. Se veio na conversa (arquivo pequeno), grave você mesmo com Python a partir do base64.
2. `python -m omaso sha /tmp/in/<nome>`. Se o sha já está em `meta/hashes.shas` → é repetido: mova (`update_file` com `parentId`) para `_Sistema/_Duplicados (conferir)/<AAAA-MM-DD>` (pasta criada dentro da pasta-mãe `config.drive.id` → `_Sistema`) e siga para o próximo.
3. **XML**: `python -m omaso classificar --db /tmp/db /tmp/in/<nome>`. Use a sugestão, confira com bom senso e com `regras.decisoes`:
   - `destino: lancamento` → lançamento novo (passo 5).
   - `destino: repetido` → mover para Duplicados (como acima).
   - `destino: geral` ou `fora` → mover para a pasta indicada em `pasta` (sem lançamento).
   - Procure em INSERIR ARQUIVOS o PDF da mesma nota (mesmo número/chave no nome ou no texto) e trate os dois juntos.
4. **PDF / foto**: leia (pdftotext; para imagens e PDF escaneado, abra o arquivo e olhe). Decida:
   - é a nota/recibo de um lançamento que já existe (mesmo número, emitente e valor)? → mova o arquivo para a pasta desse lançamento e acrescente o arquivo em `arquivos`/`links` dele (e tire a pendência correspondente das notas, se for o comprovante que faltava);
   - é comprovante de pagamento de uma nota que já existe? → mesma coisa; se o pagamento muda o mês, avise no resumo (não mova o lançamento de mês sozinho);
   - é um documento novo de despesa/compra/venda → lançamento novo (passo 5), classificado pelas mesmas regras (propriedade por data, categoria pelo fornecedor);
   - pagamento sem documento fiscal → categoria `000 - A Identificar`, kind `idn`, com a nota "Pagamento/recebimento sem documento fiscal (<quem> — R$<valor>): informar se é da atividade rural";
   - boleto sozinho → não lance; deixe em INSERIR ARQUIVOS e diga no resumo;
   - não deu para entender → deixe em INSERIR ARQUIVOS e diga no resumo.
5. Nome do arquivo: ao mover, renomeie (`update_file` com `title`) no padrão `<AAAA-MM-DD>_<Tipo><número>_<Emitente>_R<valor>.<ext>` (ex.: `2026-09-12_NFe183510_Auto-Posto-Das-Bandeiras_R530,48.xml`).

## 4. E-mails

Para cada mensagem nova: `get_message` com `messageFormat: RAW` (o resultado vai para disco) e `python -m omaso anexos <arquivo> --out /tmp/mail/<id>`.
- Ignore boletos (nome com "boleto") e assinaturas/imagens de rodapé.
- XML de NF-e: classifique como no passo 3. Envie o XML ao Drive com `create_file` (`textContent` = conteúdo do XML, `contentMimeType: application/xml`, `disableConversionToGoogleType: true`, `parentId` = pasta destino).
- PDF: envie **só se a mensagem não tiver XML da mesma nota** (o XML é o documento oficial). Envio: `create_file` com `base64Content` (`python -m omaso b64 <arquivo>`), `contentMimeType: application/pdf`.
- Guarde o id da mensagem em `estado.gmail_ids` (mantenha só os últimos 500).

## 5. Lançamento novo

- Pasta: o `pasta` da sugestão (ou monte no mesmo padrão). Crie com `pasta()` e mova/envie os arquivos para lá.
- Id: `python -m omaso id "<pasta>"`.
- Documento em `txs` (ArtifactData `batch`, op `set`, sem if_version por ser novo):
  `{ie, prop, cat, kind, date, label, value, heads, notes: [...], resolvidas: {}, arquivos: [nomes], links: {nome: id no Drive}, chaves: [chave], pasta, origem: "nuvem", sync: "ok", criadoEm: <agora ISO>}`
  - `kind`: desp | compra | venda | idn. `cat` com acentos, como em `regras.fornecedores` (ex.: "347 - Combustíveis e Lubrificantes").
  - `notes`: pendências reais (falta comprovante, falta nota, divergência de valor). Não crie pendência de comprovante de recebimento de vendas.
- Acrescente os sha256 novos em `meta/hashes.shas` (update com if_version).

## 6. Lançamentos mexidos pela interface

Para cada txs com `sync` "novo" ou "alterado" (versão lida no passo 0):
- **anexos** (`anexos: [{id, nome}]`) que ainda não estão em `links`: baixe com a ferramenta Artifact (`action: read`, `url: OMASO_URL`, `path: <id do anexo>`), envie ao Drive na pasta do lançamento e acrescente em `arquivos`/`links`.
- **novo** sem pasta: monte a pasta pelo padrão, crie, envie os anexos.
- **alterado** com mudança de propriedade/mês/categoria/descrição: crie a pasta nova e MOVA os arquivos (`update_file parentId`) usando os ids de `links`; a pasta antiga vazia pode ir para a lixeira.
- **excluido: true**: mova a pasta do lançamento para `_Sistema/_Duplicados (conferir)/excluidos-pela-interface`. Não apague o documento de `txs`: deixe-o com `excluido: true` e `sync: "ok"`.
- Depois: `sync: "ok"`, `pasta` atualizada (update com if_version = versão lida).

## 7. Relatórios

Atualize o banco exportado (repita o `list` de `txs` para `/tmp/db`, depois de apagar `/tmp/db/txs`), e gere:
```bash
python -m omaso relatorios --db /tmp/db --out /tmp/rel --anos <anos afetados> --meses "<Prop>|<AAAA-MM>;..."
python -m omaso irpf --db /tmp/db --out /tmp/rel --ano <cada ano afetado>
```
(sem trabalho novo, mas com pedido/semana: `--anos <ano atual> --meses "*|<AAAA-MM atual>"`)

Para cada arquivo listado (`/tmp/rel/_gerados.json` e a saída do irpf):
1. Ache a pasta pelo `caminho` (função `pasta()`), sem o nome do arquivo.
2. Procure arquivo com o mesmo `title` nessa pasta e mande o antigo para a lixeira (trash_file) **depois** de enviar o novo.
3. Envie: HTML com `create_file` `textContent` (o conteúdo do arquivo), `contentMimeType: text/html`, `disableConversionToGoogleType: true`. XLSX com `base64Content` (`python -m omaso b64`), `contentMimeType: application/vnd.openxmlformats-officedocument.spreadsheetml.sheet`, `disableConversionToGoogleType: true`.
4. Em `meta/relatorios.lista`: troque (pelo `nome`) ou acrescente `{id, nome, ie, tipo, ano, mes (mensal), prop (mensal/anual)}`; `atualizadoEm` = agora.

## 8. Fechar

- `meta/geral.atualizadoEm` = agora (AAAA-MM-DDTHH:MM, horário de Brasília).
- `meta/pedido.status` = "concluido" (se existir).
- `meta/estado` (set): `{last_run: <hoje>, gmail_after: <hoje>, gmail_ids: [...], versao_motor: <git rev-parse --short HEAD>}`.
- Toda escrita em documento existente leva `if_version` (a versão lida). Se der conflito, leia de novo e refaça só aquela escrita.

## 9. Resumo (curto, em português)

Notas novas por inscrição/propriedade/categoria e valor; o que veio da interface; repetidos movidos; o que ficou em INSERIR ARQUIVOS e por quê; itens "A Identificar"; pendências abertas. Se nada mudou, uma linha.
