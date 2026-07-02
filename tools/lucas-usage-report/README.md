# lucas-usage-report

Gerador de relatório diário de uso do Claude Code do estagiário Lucas, enviado para um webhook do Discord.

## Schema JSONL (verificado nos logs reais do cristiano, 2026-07-02)

Cada sessão do Claude Code produz um ficheiro `~/.claude/projects/<slug>/<session-uuid>.jsonl`.
Cada linha é um objecto JSON independente. Tipos relevantes:

### `type: "user"` — mensagem do utilizador
Discriminar pedido real vs. tool_result:
- **Pedido de topo** (nova tarefa): `origin.kind == "human"` e `message.content` é `string`
  ou lista cujo primeiro item **não** é `tool_result`.
- **Resultado de ferramenta**: `message.content` é lista com `[{type: "tool_result", ...}]`.
- **Queued duplicate**: mesmo `promptId`, timestamps a < 1 s de diferença — contar como 1 tarefa.

Campos relevantes:
```json
{
  "type": "user",
  "uuid": "<msg-uuid>",
  "parentUuid": "<parent-uuid-or-null>",
  "timestamp": "2026-06-28T18:58:07.599Z",
  "sessionId": "<session-uuid>",
  "promptId": "<shared-per-human-request>",
  "origin": {"kind": "human"},
  "promptSource": "typed",
  "message": {"role": "user", "content": "texto do pedido"}
}
```

### `type: "assistant"` — resposta do assistente (com tokens)

```json
{
  "type": "assistant",
  "uuid": "<msg-uuid>",
  "parentUuid": "<parent-uuid>",
  "timestamp": "2026-06-28T18:58:29.966Z",
  "sessionId": "<session-uuid>",
  "message": {
    "model": "claude-opus-4-8",
    "usage": {
      "input_tokens": 9943,
      "output_tokens": 165,
      "cache_creation_input_tokens": 17233,
      "cache_read_input_tokens": 16529
    }
  }
}
```

**Importante:**
- Usar apenas `message.usage.*` de topo — o array `iterations` é contabilidade interna e NÃO deve
  ser somado (verificado: com `advisor_message` dentro de iterations, a soma NÃO coincide com o topo).
- Registos com `model == "<synthetic>"` ou `isApiErrorMessage == true` são erros de rate-limit —
  tokens zerados, devem ser ignorados.

### Tipos ignorados no parser
`last-prompt`, `mode`, `permission-mode`, `attachment`, `file-history-snapshot`, `system`,
`ai-title`, `queue-operation`, `bridge-session` — sem informação de tokens.

### Segmentação de tarefas (timestamp-based)
1. Ordenar todos os registos da sessão por `timestamp`.
2. Cada `user` com `origin.kind == "human"` (e content não é tool_result) inicia uma nova tarefa.
3. Deduplica por `promptId` (queued prompts têm o mesmo `promptId`).
4. Todos os registos assistente até ao próximo pedido humano pertencem à tarefa actual.
5. Tempo por tarefa = `end_timestamp - start_timestamp`.

## Fórmula de custo

```
custo = input×p_in/1M + output×p_out/1M
      + cache_write×(p_in×1.25)/1M
      + cache_read×(p_in×0.10)/1M
```

Preços em `pricing.json` (editar para actualizar sem tocar no código).

## Como correr

### Pré-requisitos
- Python 3.9+ (usa `zoneinfo`)
- Acesso SSH sem senha a `lucas@192.168.122.85` (chave já configurada)
- Ficheiro `/home/cristiano/Lucas_Claude_Hook.txt` com o URL do webhook (ver abaixo)

### Comandos

```bash
# Dry-run (imprime o embed, não envia) — para validar antes do 1.º envio real
python3 report.py --dry-run

# Dry-run contra logs locais do cristiano (sanidade)
python3 report.py --dry-run --logs-dir ~/.claude/projects

# Relatório de um dia específico
python3 report.py --dry-run --date 2026-07-01

# Envio real (requer URL do webhook no ficheiro)
python3 report.py
```

### Configurar o webhook URL

```bash
echo 'https://discord.com/api/webhooks/CHANNEL_ID/TOKEN' > /home/cristiano/Lucas_Claude_Hook.txt
chmod 600 /home/cristiano/Lucas_Claude_Hook.txt
```

**NUNCA** commitar este ficheiro (está fora do repo por design).

## Agendamento com systemd user timer

### Instalar

```bash
# Copiar as units para o directório de user units
mkdir -p ~/.config/systemd/user/
cp lucas-usage-report.service ~/.config/systemd/user/
cp lucas-usage-report.timer ~/.config/systemd/user/

# Recarregar e activar
systemctl --user daemon-reload
systemctl --user enable --now lucas-usage-report.timer

# Verificar
systemctl --user list-timers lucas-usage-report.timer
```

### Nota: linger (para sessões sem login activo)

Se o utilizador `cristiano` não tem sessão de login activa 24/7, o timer pode não disparar.
Activar o **linger** para garantir que os user units correm mesmo sem sessão:

```bash
# Requer sudo
sudo loginctl enable-linger cristiano
```

### Alternativa: cron

```bash
# Adicionar com `crontab -e`:
0 0 * * * /usr/bin/python3 /home/cristiano/Git/Claude-Linux-Helper/tools/lucas-usage-report/report.py
```

### Verificar logs do timer

```bash
journalctl --user -u lucas-usage-report.service --since today
```

### Desactivar

```bash
systemctl --user disable --now lucas-usage-report.timer
```

## Testes

```bash
# Instalar pytest (se necessário)
python3 -m pip install --user pytest

# Correr todos os testes
python3 -m pytest tools/lucas-usage-report/tests/ -v
# ou (dentro do directório)
pytest tests/ -v
```

## Checklist para activação end-to-end

- [ ] Criar `/home/cristiano/Lucas_Claude_Hook.txt` com o URL do webhook Discord (`chmod 600`)
- [ ] Validar: `python3 report.py --dry-run` (imprime embed, não envia)
- [ ] Instalar e activar o systemd timer (ou cron)
- [ ] Activar linger se necessário (`sudo loginctl enable-linger cristiano`)
- [ ] Aguardar uso real do Lucas (Claude Code autenticado com API key na VM-IA-1)
- [ ] Após 1.º dia de uso: `python3 report.py --dry-run --date <ONTEM>` para confirmar dados
- [ ] Aprovação do dono → remover `--dry-run` do timer / correr uma vez manualmente

## Ficheiros

| Ficheiro | Descrição |
|---|---|
| `report.py` | Script principal |
| `pricing.json` | Tabela de preços por modelo (editar aqui) |
| `lucas-usage-report.service` | Unit systemd |
| `lucas-usage-report.timer` | Timer systemd (00:00 hora local, Persistent) |
| `tests/fixtures.py` | Fixtures JSONL para testes |
| `tests/test_report.py` | 42 testes unitários |
