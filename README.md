# OMASO — motor

Motor do OMASO, um sistema de organização fiscal para produtores rurais. Ele lê notas fiscais (XML de NF-e/NFA-e), sugere a classificação e gera os relatórios: mensais, anuais, consolidado, planejamento de fechamento e o resumo do IRPF em planilha.

O código **não tem dados de nenhum cliente**. Os dados de cada cliente ficam no banco do OMASO dele (`meta/ies`, `meta/regras`, `meta/config` e `txs`) e no Google Drive dele.

- `CONFERENCIA.md`: roteiro que a conferência automática na nuvem segue.
- `python -m omaso --help`: comandos disponíveis.

Pedido da tarefa agendada de cada cliente (só muda o link):

```
Conferência OMASO. Rode: git clone --depth 1 https://github.com/omaso-app/motor /tmp/motor
e siga /tmp/motor/CONFERENCIA.md com OMASO_URL = <link do artefato do cliente>.
```
