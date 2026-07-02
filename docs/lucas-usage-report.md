# Design: Relatório diário de uso do Claude Code (estagiário Lucas) → Discord

> Autor: sessão Opus (arquiteto). Data: 2026-07-02. Implementação: agente Sonnet.
> Estado: desenho aprovado (fonte de custo = **estimado dos logs**). Sem segredos neste ficheiro.

## Objetivo
Todos os dias à **meia-noite**, enviar para um **webhook do Discord** um relatório do uso do Claude Code
pelo estagiário **Lucas** (na VM-IA-1), com:
- **Diário**: custo do dia + tarefas executadas, tempo total, tokens, média de tokens/tarefa — **total e por modelo**.
- **Mensal** (por baixo): a mesma totalização acumulada do mês.

## Onde corre
- Host **`.130`** (sempre ligado, **fora** da VM do estagiário — o Lucas tem root na VM, nada sensível vai para lá).
- **systemd timer** `OnCalendar=*-*-* 00:00:00` (+ `Persistent=true`) → dispara o gerador.
- Corre como o utilizador `cristiano`.

## Fonte dos dados
- **Logs de sessão do Claude Code do Lucas**, lidos por **SSH** (a `.130` já tem chave para `lucas@192.168.122.85`):
  `~/.claude/projects/*/*.jsonl`. Cada linha = registo de mensagem; as mensagens do assistente trazem
  `message.usage` (input/output/cache tokens) + `model` + timestamp + session id.
- **Ground truth do schema**: o agente inspeciona os logs **reais do próprio `cristiano`** em `~/.claude/projects/`
  na `.130` (mesmo formato) para acertar o parser antes de haver dados do Lucas.

## Definição de "tarefa"
**1 tarefa = 1 pedido de topo do utilizador** (uma mensagem `user` que não é `tool_result`), agregando toda a
atividade de assistente/ferramentas/subagentes até ao próximo pedido. "Tempo por tarefa" = do 1.º ao último
evento desse pedido.

## Métricas (total e por modelo)
Por dia e por mês (mês corrente até à data):
- **nº de tarefas**
- **tokens**: input, output, cache-write, cache-read (e total)
- **tempo total de uso** (soma das durações das tarefas/sessões)
- **média de tokens por tarefa**
- **custo estimado**

## Custo (estimado dos logs)
`custo = input×preço_in + output×preço_out + cache_write×(preço_in×1.25) + cache_read×(preço_in×0.10)`
por modelo, com tabela de preços em config (fácil de atualizar). Valores por 1M tokens à data:
| Modelo | Input | Output |
|---|---|---|
| claude-opus-4-8 | $5 | $25 |
| claude-sonnet-4-6 | $3 | $15 |
| claude-haiku-4-5 | $1 | $5 |
> É uma **estimativa** (não o valor faturado exato). Reconciliação autoritativa via Admin API fica como upgrade futuro.

## Saída (Discord)
Um *embed* com secção **DIÁRIO** (bloco total + um bloco por modelo) e, por baixo, secção **MENSAL** (idem).
URL do webhook lido de **`/home/cristiano/Lucas_Claude_Hook.txt`** na `.130` (**`chmod 600`**, fora do repo/git).

## Segurança e privacidade
- Webhook URL nunca no git; ficheiro `0600`.
- O relatório contém **só métricas agregadas** — nunca o conteúdo dos prompts/trabalho do Lucas.
- Nada de admin key. Nada sensível na VM.

## Testes (obrigatórios antes de "verde")
- Unit tests da agregação + cálculo de custo com **fixtures `.jsonl`** de exemplo (casos: multi-modelo, cache,
  múltiplas tarefas/sessões, dia sem uso).
- Sanidade contra os **logs reais do `cristiano`** na `.130`.
- **`--dry-run`**: imprime o embed sem postar. **O 1.º envio real ao Discord é gated** (ação externa) — só após
  o URL estar no sítio e aprovação do dono. Nada é postado nos testes.

## Estado / pré-requisitos
- [ ] URL do webhook em `/home/cristiano/Lucas_Claude_Hook.txt` na `.130` (`0600`).
- [ ] Lucas com Claude Code autenticado (API key) e **uso real** → validação end-to-end do 1.º relatório.
- Reversível: desativar o systemd timer remove o agendamento; nada mais é tocado.
