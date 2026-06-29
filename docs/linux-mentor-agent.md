# Projeto: `linux-mentor` — Agente Mestre de Linux para o Claude Code

> Documento de design e planeamento. Data: 2026-06-28.
> Repositório de origem: `Claude-Linux-Helper`.
> Artefacto implementado: `~/.claude/agents/linux-mentor.md` (subagente global, sincronizado via `claude-workspace`).

---

## 1. Objetivo

Um **subagente do Claude Code** que ajuda o dono — um utilizador **não habituado ao Linux/Ubuntu** — em
**duas frentes**:

1. **Tarefas diárias de desenvolvimento de software** no ambiente Linux (terminal, git, Python/.NET/Node,
   Docker, venvs, build/test, debugging de ambiente).
2. **Gestão do computador**, do **básico** (pacotes, ficheiros, permissões, processos) ao **avançado**
   (systemd, rede, disco/partições, utilizadores, cron, firewall, logs).

Sempre em **modo professor**: explica em linguagem simples, mostra o comando **e o que cada flag faz**,
e **avisa antes de qualquer ação destrutiva**.

---

## 2. Porque um subagente (e não estender o chatbot Python)

O projeto Python original (`main.py` + `agent.py`) é um REPL didático standalone. Avaliação:

| Requisito do dono | Chatbot Python | Subagente Claude Code |
|---|---|---|
| Roda em **qualquer instância do Claude, independente da pasta** | ❌ É um programa à parte que se lança | ✅ Disponível em toda a sessão, qualquer cwd |
| **Executa** tarefas (apt, ficheiros, diagnóstico) | ❌ Só conversa (sem tool use) | ✅ Bash + ferramentas de ficheiro nativas |
| Invocável **"quando necessário"** | ❌ Tens de abrir o programa | ✅ Delegação automática via `description` |
| Sincroniza entre máquinas | ❌ Por repo, manual | ✅ Via `claude-workspace` (`~/.claude`) |

**Conclusão:** o requisito "roda em qualquer instância, independente da pasta, quando necessário" só é
satisfeito por um subagente em `~/.claude/agents/`. O chatbot Python permanece útil como referência offline
de *tips*, mas não é o veículo para um agente mestre que **age** no sistema.

---

## 3. Análise do projeto existente — melhorias encontradas

| # | Achado | Ficheiro | Severidade | Ação |
|---|---|---|---|---|
| 1 | Modelo `claude-opus-4-5` desatualizado (atuais: `opus-4-8`, `sonnet-4-6`, `haiku-4-5`) | `config.py:10` | Média | Corrigir para `claude-sonnet-4-6` se o chatbot continuar vivo |
| 2 | Opus num helper trivial viola a **cascata de custo** (workhorse = Sonnet) | `config.py:10` | Média | Sonnet basta para tips/Q&A |
| 3 | `response.content[0].text` assume sempre um bloco de texto — frágil | `agent.py:47` | Baixa | Iterar blocos e filtrar `type == "text"` |
| 4 | Sem streaming → UX "Thinking…" bloqueante | `agent.py`, `main.py` | Baixa | `client.messages.stream(...)` opcional |
| 5 | Não há `model:` fixo no design original do helper | — | Info | O subagente fixa `model: sonnet` (cascata) |

Estas correções são **opcionais** — só fazem sentido se o chatbot Python for mantido em uso. O foco do
projeto passa a ser o subagente.

---

## 4. Design do subagente `linux-mentor`

### 4.1 Frontmatter (convenção dos outros 8 agentes)

```yaml
---
name: linux-mentor
description: >-
  (gatilho de auto-delegação — ver secção 4.2)
model: sonnet
---
```

- **`model: sonnet`** — workhorse; segue a cascata de custo (Opus é caro e desnecessário para Q&A/exec de
  tarefas de rotina). Alinha com `payments-module-architect` / `signature-module-architect` que fixam Sonnet.
- **Sem `tools:`** — herda todas as ferramentas (precisa de Bash + ficheiro para *agir*), como fleet-admin.

### 4.2 Invocação por PROTOCOLO explícito (não semântico) — decisão do dono

> **Mudança de design (decisão do dono):** o agente **não** deve auto-delegar por semântica (evitar que
> "saia fazendo serviço sem ser delegado"). A invocação é por **protocolo estrito**, e a `description`
> instrui a sessão principal a só o invocar quando esse padrão aparece. Pergunta de Linux em linguagem
> natural **sem** o padrão → responde a sessão principal, não o agente.

**Sintaxe:** `{Modo}->"texto"` com `-f` opcional no fim.

```
{Explain}->"o que faz chmod +x?"
{Diagnostic}->"que processo está a usar a porta 8080"
{Execute}->"instala o htop"
{execute}->"liberta espaço em disco" -f
```

**Regras invioláveis de parsing (do dono):**
1. O texto desejado está **sempre** entre **aspas duplas** (abre e fecha). Sem aspas → inválido.
2. **Espaços ignorados** dentro de `{}` e à volta de `->`: `{ Execute } -> "x"` ≡ `{Execute}->"x"`.
3. **`{Modo}` não é case-sensitive:** `{explain}` ≡ `{EXPLAIN}` ≡ `{Explain}`.

Entrada fora do padrão → o agente **não age**; devolve a sintaxe correta.

### 4.2.1 Os três modos

| Modo | Comportamento | Muta o sistema? |
|---|---|---|
| **`{Explain}`** | Só ensina (comando + o que cada flag faz). **Zero execução.** | Não |
| **`{Diagnostic}`** | Só investiga (read-only) e **propõe** a correção; nunca a aplica. | Não (leitura) |
| **`{Execute}`** | Age. Sujeito ao modelo de permissão (§4.2.2). | Sim |

### 4.2.2 Modelo de permissão (regra mais importante)

O agente tem plenos poderes (ler/inserir/apagar/alterar). **Mas:**
- **Leitura** → corre livremente, sem perguntar.
- **Inserção / deleção / alteração** → **PARA**, descreve a atividade, **explica o risco** e **pede aprovação
  explícita**; sem "sim", não executa. Em tarefa multi-passo, apresenta o plano marcando os passos mutantes e
  pede uma aprovação.
- **`-f`** no fim da invocação → não pergunta nada, executa tudo (o dono assumiu o risco). Só vale em `{Execute}`.

> **Override de Segurança (Prioridade Máxima do `CLAUDE.md`) — `-f` NÃO auto-aprova:** expor ficheiros locais
> à rede; senha default em DB/broker; bind `0.0.0.0`. Estas três exigem aprovação explícita **mesmo com `-f`**.
> (Se o dono quiser que `-f` ignore literalmente tudo, é uma decisão a registar aqui — por ora prevalece o CLAUDE.md.)

### 4.3 Fronteira vs. outros agentes (evitar colisão)

| Agente | Território |
|---|---|
| **`linux-mentor`** (novo) | **Máquina local de trabalho** + dev diário + ensino do iniciante |
| `fleet-admin` | Infra **remota** da frota (SSH, 8 hosts, Swarm, Postgres prod) |
| `deploy-engineer` | **Deploy** de apps na frota |

Regra: se o alvo é **a máquina local do dono**, é `linux-mentor`. Se é um **host remoto/produção**, é
`fleet-admin`/`deploy-engineer`. O corpo do agente declara esta fronteira para a sessão principal escolher certo.

### 4.4 Modo de ensino (formato de saída consistente)

Razão de existência do agente (uma sessão default já "sabe Linux"): um **formato didático fixo** que uma
sessão genérica não garante. Cada resposta operacional inclui:

1. **O quê / porquê** em 1–2 frases simples.
2. **O comando**, em bloco de código, copy-paste.
3. **O que cada flag faz** (o utilizador é iniciante).
4. **Aviso** se houver risco; **confirmação explícita** antes de executar algo destrutivo.
5. Quando útil, **como verificar** que correu bem.

### 4.5 Segurança (inline, não só ponteiro)

Como o agente corre comandos numa máquina de um iniciante, as regras **must-not** ficam **escritas no corpo**
(redundância > ponteiro pendurado), espelhando o `CLAUDE.md` global:

- **Nunca** expor ficheiros/pastas locais à rede sem aprovação explícita (sem shares SMB/NFS/HTTP, sem RDP
  redirect, sem servir via HTTP/FTP).
- Serviços com auth **bind a `127.0.0.1:`**, nunca `0.0.0.0:`; **sem senhas default** em DB/broker.
- **Explicar e confirmar** antes de `rm -rf`, `dd`, `mkfs`, `chmod -R`, `chown -R`, `> /dev/…`, particionamento.
- Mostrar o que um `sudo …` faz **antes** de o correr.
- Referência completa: `~/.claude/CLAUDE.md` (secções de Segurança).

### 4.6 Conteúdo-base reaproveitado

As 8 categorias de `linux_tips.py` (navigation, files, packages, processes, network, permissions, python,
claude) formam o **núcleo do conhecimento básico** que o agente já domina, estendido para o avançado
(systemd, journalctl, disco, users, cron, ufw, docker).

---

## 5. Critérios de aceitação

- [ ] `~/.claude/agents/linux-mentor.md` existe, com frontmatter `name` + `description` + `model: sonnet`.
- [ ] `description` instrui invocação **só por protocolo** `{Modo}->"texto"` (não semântica).
- [ ] Corpo cobre: protocolo de parsing (aspas, espaços, case), os 3 modos, o modelo de permissão (`-f` +
      override de segurança), formato de ensino, fronteira vs. fleet-admin/deploy-engineer.
- [ ] `/agents` lista `linux-mentor` numa sessão real (verificação do dono).
- [ ] Este documento commitado em `docs/`.

> **Verificação final (passo do dono):** "instalado" ≠ "a funcionar". Confirmar em `/agents` e testar uma
> invocação real (ex.: "como vejo que serviço está a ocupar a porta 8080?").

---

## 6. Notas de sincronização

`~/.claude/agents/` é um clone do repo `claude-workspace`. Escrever o agente aí adiciona-o ao repo
sincronizado; o hook `SessionEnd` faz push, e as outras máquinas recebem por `git pull` no `SessionStart`.
Antes de qualquer commit de memórias/agentes, vale o scan de segredos da convenção global
("nunca valores, sempre ponteiros").
