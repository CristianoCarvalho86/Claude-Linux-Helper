#!/usr/bin/env python3
"""
Relatório diário de uso do Claude Code do estagiário Lucas → Discord webhook.

Uso:
    python3 report.py                        # dia anterior (hora local)
    python3 report.py --dry-run              # imprime o embed, não envia
    python3 report.py --date 2026-07-01      # dia específico
    python3 report.py --logs-dir /path/dir   # ler de dir local (bypass SSH)
    python3 report.py --dry-run --logs-dir ~/.claude/projects

Segurança:
    - Webhook URL lido de /home/cristiano/Lucas_Claude_Hook.txt (0600, fora do git).
    - O relatório contém APENAS métricas agregadas — nunca conteúdo de prompts.
"""

import argparse
import datetime
import glob
import json
import os
import subprocess
import sys
import tarfile
import tempfile
import urllib.request
from collections import defaultdict
from pathlib import Path
from zoneinfo import ZoneInfo  # Python 3.9+

# ---------------------------------------------------------------------------
# Configuração
# ---------------------------------------------------------------------------

WEBHOOK_FILE = "/home/cristiano/Lucas_Claude_Hook.txt"
PRICING_FILE = Path(__file__).parent / "pricing.json"
SSH_TARGET = "lucas@192.168.122.85"
REMOTE_PROJECTS_DIR = "~/.claude/projects"

# ---------------------------------------------------------------------------
# Preços
# ---------------------------------------------------------------------------

def load_pricing() -> dict:
    """Carrega pricing.json. Retorna {} em caso de erro (custo fica 0 + aviso)."""
    try:
        with open(PRICING_FILE) as f:
            data = json.load(f)
        return data.get("models", {})
    except Exception as e:
        print(f"[aviso] Não foi possível ler {PRICING_FILE}: {e}", file=sys.stderr)
        return {}


def compute_cost(model: str, input_tok: int, output_tok: int,
                 cache_write: int, cache_read: int, pricing: dict) -> float:
    """
    custo = input×p_in + output×p_out
           + cache_write×(p_in×1.25)
           + cache_read×(p_in×0.10)
    Valores em pricing são por 1M tokens.
    """
    if model not in pricing:
        return 0.0
    p = pricing[model]
    p_in = p["input"] / 1_000_000
    p_out = p["output"] / 1_000_000
    cost = (input_tok * p_in
            + output_tok * p_out
            + cache_write * p_in * 1.25
            + cache_read * p_in * 0.10)
    return cost

# ---------------------------------------------------------------------------
# Leitura de logs
# ---------------------------------------------------------------------------

def fetch_logs_ssh(tmp_dir: str) -> bool:
    """
    Copia ~/.claude/projects/*/*.jsonl do Lucas via SSH para tmp_dir.
    Retorna True se algo foi copiado, False se dir remoto não existe / vazio.
    """
    cmd = [
        "ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=10",
        SSH_TARGET,
        # Criar tar do dir se existir; se não existir, cria tar vazio do /dev/null
        (
            f"if [ -d {REMOTE_PROJECTS_DIR} ]; then "
            f"  tar czf - -C $(eval echo {REMOTE_PROJECTS_DIR}) . 2>/dev/null; "
            f"else "
            f"  exit 42; "
            f"fi"
        ),
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, timeout=60)
    except subprocess.TimeoutExpired:
        print("[erro] SSH timeout ao ligar ao host do Lucas.", file=sys.stderr)
        return False

    if result.returncode == 42:
        # Directório remoto não existe — sem uso ainda
        return False
    if result.returncode != 0:
        print(f"[erro] SSH falhou (rc={result.returncode}): {result.stderr.decode()}", file=sys.stderr)
        return False

    if not result.stdout:
        return False

    # Extrair tar
    with tempfile.NamedTemporaryFile(delete=False, suffix=".tar.gz") as tf:
        tf.write(result.stdout)
        tf_path = tf.name

    try:
        with tarfile.open(tf_path, "r:gz") as tar:
            tar.extractall(tmp_dir)
    except Exception as e:
        print(f"[erro] Não foi possível extrair tar: {e}", file=sys.stderr)
        return False
    finally:
        os.unlink(tf_path)

    return True


def read_jsonl_files(base_dir: str) -> list[dict]:
    """Lê todos os *.jsonl dentro de base_dir (recursivo)."""
    records = []
    pattern = os.path.join(base_dir, "**", "*.jsonl")
    for fpath in glob.glob(pattern, recursive=True):
        try:
            with open(fpath, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            records.append(json.loads(line))
                        except json.JSONDecodeError:
                            pass
        except Exception as e:
            print(f"[aviso] Não foi possível ler {fpath}: {e}", file=sys.stderr)
    return records

# ---------------------------------------------------------------------------
# Classificação de registos
# ---------------------------------------------------------------------------

def is_real_assistant(r: dict) -> bool:
    """Registo de assistente real (com tokens e modelo válido)."""
    if r.get("type") != "assistant":
        return False
    msg = r.get("message", {})
    model = msg.get("model", "")
    if not model or model == "<synthetic>":
        return False
    if r.get("isApiErrorMessage"):
        return False
    return True


def is_human_top_level(r: dict) -> bool:
    """
    Mensagem de utilizador de topo (pedido real do humano).
    Critério: type=user, origin.kind=human, content não é só tool_result.
    """
    if r.get("type") != "user":
        return False
    if r.get("origin", {}).get("kind") != "human":
        return False
    content = r.get("message", {}).get("content", "")
    if isinstance(content, list) and content and content[0].get("type") == "tool_result":
        return False
    return True

# ---------------------------------------------------------------------------
# Agrupamento em tarefas
# ---------------------------------------------------------------------------

def extract_usage(msg: dict) -> tuple[int, int, int, int]:
    """Extrai (input, output, cache_write, cache_read) do objeto message.usage."""
    usage = msg.get("usage", {})
    return (
        usage.get("input_tokens", 0),
        usage.get("output_tokens", 0),
        usage.get("cache_creation_input_tokens", 0),
        usage.get("cache_read_input_tokens", 0),
    )


def segment_tasks(records: list[dict]) -> list[dict]:
    """
    Ordena todos os registos por timestamp e segmenta em tarefas.
    Uma tarefa começa em cada mensagem human top-level única (por promptId).
    Todos os registos que se seguem até à próxima tarefa pertencem à tarefa actual.
    Retorna lista de {start, end, model_usage: {model: {in,out,cw,cr}}}.
    """
    records_sorted = sorted(records, key=lambda r: r.get("timestamp", ""))

    tasks: list[dict] = []
    current: dict | None = None
    seen_pids: set = set()

    for r in records_sorted:
        if is_human_top_level(r):
            pid = r.get("promptId") or r.get("uuid", "")
            if pid in seen_pids:
                # Duplicado queued — não conta como nova tarefa
                continue
            seen_pids.add(pid)
            if current:
                tasks.append(current)
            current = {
                "start": r["timestamp"],
                "end": r["timestamp"],
                "model_usage": defaultdict(lambda: [0, 0, 0, 0]),
            }
        elif current is not None:
            ts = r.get("timestamp", "")
            if ts and ts > current["end"]:
                current["end"] = ts

        if current is not None and is_real_assistant(r):
            model = r["message"]["model"]
            inp, out, cw, cr = extract_usage(r["message"])
            mu = current["model_usage"][model]
            mu[0] += inp
            mu[1] += out
            mu[2] += cw
            mu[3] += cr

    if current:
        tasks.append(current)

    return tasks

# ---------------------------------------------------------------------------
# Agregação por dia/mês
# ---------------------------------------------------------------------------

def parse_ts(ts_str: str, tz: ZoneInfo) -> datetime.datetime:
    """Converte timestamp UTC (ISO 8601 com Z) para datetime local."""
    dt = datetime.datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
    return dt.astimezone(tz)


def aggregate(tasks: list[dict], target_date: datetime.date, tz: ZoneInfo,
              pricing: dict) -> dict:
    """
    Agrega as tarefas em estatísticas diárias (target_date) e mensais
    (1.º do mês até target_date inclusive).
    Retorna {daily: {...}, monthly: {...}}.
    """
    month_start = target_date.replace(day=1)

    def empty_stats():
        return {
            "tasks": 0,
            "by_model": defaultdict(lambda: {
                "tasks": 0,
                "input": 0, "output": 0,
                "cache_write": 0, "cache_read": 0,
                "duration_s": 0.0,
            }),
        }

    daily = empty_stats()
    monthly = empty_stats()

    unknown_models: set = set()

    for task in tasks:
        start_local = parse_ts(task["start"], tz)
        end_local = parse_ts(task["end"], tz)
        task_date = start_local.date()

        duration_s = (end_local - start_local).total_seconds()
        if duration_s < 0:
            duration_s = 0.0

        is_daily = (task_date == target_date)
        is_monthly = (month_start <= task_date <= target_date)

        if not is_daily and not is_monthly:
            continue

        for model, (inp, out, cw, cr) in task["model_usage"].items():
            if model not in pricing and model not in unknown_models:
                print(f"[aviso] Modelo desconhecido '{model}' — custo=0.", file=sys.stderr)
                unknown_models.add(model)

            for stats in ([daily] if is_daily else []) + ([monthly] if is_monthly else []):
                stats["tasks"] += 1
                bm = stats["by_model"][model]
                bm["tasks"] += 1
                bm["input"] += inp
                bm["output"] += out
                bm["cache_write"] += cw
                bm["cache_read"] += cr
                bm["duration_s"] += duration_s

    # Deduplicate task count: tasks counted once per period, not once per model
    # Redo: count tasks correctly (1 task = 1 human msg, regardless of models used)
    daily2 = empty_stats()
    monthly2 = empty_stats()

    for task in tasks:
        start_local = parse_ts(task["start"], tz)
        end_local = parse_ts(task["end"], tz)
        task_date = start_local.date()
        duration_s = max((end_local - start_local).total_seconds(), 0.0)

        is_daily = (task_date == target_date)
        is_monthly = (month_start <= task_date <= target_date)

        if is_daily:
            daily2["tasks"] += 1
        if is_monthly:
            monthly2["tasks"] += 1

        for model, (inp, out, cw, cr) in task["model_usage"].items():
            for flag, stats in [(is_daily, daily2), (is_monthly, monthly2)]:
                if not flag:
                    continue
                bm = stats["by_model"][model]
                bm["tasks"] += 1
                bm["input"] += inp
                bm["output"] += out
                bm["cache_write"] += cw
                bm["cache_read"] += cr
                bm["duration_s"] += duration_s

    return {"daily": daily2, "monthly": monthly2, "pricing": pricing}

# ---------------------------------------------------------------------------
# Formatação do embed Discord
# ---------------------------------------------------------------------------

def fmt_tokens(n: int) -> str:
    if n >= 1_000_000:
        return f"{n/1_000_000:.2f}M"
    if n >= 1_000:
        return f"{n/1_000:.1f}k"
    return str(n)


def fmt_duration(seconds: float) -> str:
    seconds = int(seconds)
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    if h:
        return f"{h}h{m:02d}m"
    if m:
        return f"{m}m{s:02d}s"
    return f"{s}s"


def fmt_cost(usd: float) -> str:
    if usd < 0.01:
        return f"${usd:.4f}"
    return f"${usd:.2f}"


def build_model_block(model: str, bm: dict, pricing: dict) -> str:
    """Linha(s) com stats de um modelo."""
    total_tok = bm["input"] + bm["output"] + bm["cache_write"] + bm["cache_read"]
    avg_tok = total_tok // bm["tasks"] if bm["tasks"] else 0
    cost = compute_cost(model, bm["input"], bm["output"],
                        bm["cache_write"], bm["cache_read"], pricing)
    dur = fmt_duration(bm["duration_s"])
    short_model = model.replace("claude-", "").replace("-4-", "-4.")
    lines = [
        f"**{short_model}** ({bm['tasks']} tarefas, {dur})",
        f"  in={fmt_tokens(bm['input'])} | out={fmt_tokens(bm['output'])} "
        f"| cw={fmt_tokens(bm['cache_write'])} | cr={fmt_tokens(bm['cache_read'])}",
        f"  total={fmt_tokens(total_tok)} | avg/task={fmt_tokens(avg_tok)} | custo={fmt_cost(cost)}",
    ]
    return "\n".join(lines)


def build_period_field(label: str, stats: dict, pricing: dict) -> dict:
    """Constrói um campo de embed Discord para diário ou mensal."""
    by_model = stats["by_model"]
    n_tasks = stats["tasks"]

    if n_tasks == 0:
        return {"name": label, "value": "_(sem uso)_", "inline": False}

    # Totais globais
    total_in = sum(bm["input"] for bm in by_model.values())
    total_out = sum(bm["output"] for bm in by_model.values())
    total_cw = sum(bm["cache_write"] for bm in by_model.values())
    total_cr = sum(bm["cache_read"] for bm in by_model.values())
    total_tok = total_in + total_out + total_cw + total_cr
    total_dur = sum(bm["duration_s"] for bm in by_model.values())
    total_cost = sum(
        compute_cost(m, bm["input"], bm["output"], bm["cache_write"], bm["cache_read"], pricing)
        for m, bm in by_model.items()
    )
    avg_tok = total_tok // n_tasks if n_tasks else 0

    lines = [
        f"**TOTAL** — {n_tasks} tarefas | {fmt_duration(total_dur)} | {fmt_cost(total_cost)}",
        f"  in={fmt_tokens(total_in)} | out={fmt_tokens(total_out)} "
        f"| cw={fmt_tokens(total_cw)} | cr={fmt_tokens(total_cr)}",
        f"  total={fmt_tokens(total_tok)} | avg/task={fmt_tokens(avg_tok)}",
        "",
    ]

    for model in sorted(by_model.keys()):
        lines.append(build_model_block(model, by_model[model], pricing))
        lines.append("")

    value = "\n".join(lines).strip()
    # Discord limita campos a 1024 chars
    if len(value) > 1024:
        value = value[:1020] + "…"

    return {"name": label, "value": value, "inline": False}


def build_embed(target_date: datetime.date, agg: dict) -> dict:
    """Constrói o payload do embed Discord."""
    pricing = agg["pricing"]
    daily_stats = agg["daily"]
    monthly_stats = agg["monthly"]

    date_str = target_date.strftime("%d/%m/%Y")
    month_str = target_date.strftime("%B %Y")

    fields = [
        build_period_field(f"DIARIO — {date_str}", daily_stats, pricing),
        build_period_field(f"MENSAL — {month_str} (1.º→{date_str})", monthly_stats, pricing),
    ]

    embed = {
        "embeds": [
            {
                "title": f"Uso Claude Code — Lucas — {date_str}",
                "color": 0x5865F2,  # azul Discord
                "fields": fields,
                "footer": {"text": "Fonte: logs ~/.claude/projects | Custo estimado"},
                "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z"),
            }
        ]
    }
    return embed

# ---------------------------------------------------------------------------
# Envio / dry-run
# ---------------------------------------------------------------------------

def read_webhook_url() -> str | None:
    """Lê o URL do webhook de WEBHOOK_FILE. Retorna None se não existir."""
    try:
        with open(WEBHOOK_FILE) as f:
            url = f.read().strip()
        if not url:
            print(f"[erro] {WEBHOOK_FILE} está vazio.", file=sys.stderr)
            return None
        return url
    except FileNotFoundError:
        print(f"[erro] Ficheiro de webhook não encontrado: {WEBHOOK_FILE}", file=sys.stderr)
        print("       Crie-o com: echo 'https://discord.com/api/webhooks/...' > " + WEBHOOK_FILE,
              file=sys.stderr)
        print("       E proteja-o: chmod 600 " + WEBHOOK_FILE, file=sys.stderr)
        return None


def send_to_discord(embed: dict, url: str) -> bool:
    """Envia o embed para o webhook Discord. Retorna True em sucesso."""
    payload = json.dumps(embed).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=payload,
        headers={
            "Content-Type": "application/json",
            # Discord/Cloudflare rejeita POSTs sem User-Agent (403, Cloudflare 1010)
            "User-Agent": "LucasUsageReport/1.0 (CodeHeroes; +https://github.com/CristianoCarvalho86)",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            if resp.status in (200, 204):
                return True
            body = resp.read().decode()
            print(f"[erro] Discord devolveu {resp.status}: {body}", file=sys.stderr)
            return False
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        print(f"[erro] Discord HTTP {e.code}: {body}", file=sys.stderr)
        return False
    except Exception as e:
        print(f"[erro] Falha ao enviar para Discord: {e}", file=sys.stderr)
        return False

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Relatório diário uso Claude Code (Lucas)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Imprime o embed JSON em vez de enviar")
    parser.add_argument("--date", type=str, default=None,
                        help="Data a reportar (YYYY-MM-DD). Default: dia anterior.")
    parser.add_argument("--logs-dir", type=str, default=None,
                        help="Dir local de logs em vez de SSH (para testes)")
    args = parser.parse_args()

    # Timezone local
    try:
        local_tz = ZoneInfo("localtime")
    except Exception:
        local_tz = ZoneInfo("UTC")

    # Data alvo
    if args.date:
        try:
            target_date = datetime.date.fromisoformat(args.date)
        except ValueError:
            print(f"[erro] Data inválida: {args.date}. Use YYYY-MM-DD.", file=sys.stderr)
            sys.exit(1)
    else:
        today_local = datetime.datetime.now(tz=local_tz).date()
        target_date = today_local - datetime.timedelta(days=1)

    # Preços
    pricing = load_pricing()

    # Obter logs
    records: list[dict] = []
    if args.logs_dir:
        logs_dir = os.path.expanduser(args.logs_dir)
        if not os.path.isdir(logs_dir):
            print(f"[erro] Dir não existe: {logs_dir}", file=sys.stderr)
            sys.exit(1)
        records = read_jsonl_files(logs_dir)
    else:
        with tempfile.TemporaryDirectory() as tmp_dir:
            has_logs = fetch_logs_ssh(tmp_dir)
            if has_logs:
                records = read_jsonl_files(tmp_dir)

    if not records:
        print("[info] Sem logs disponíveis — relatório de 'sem uso'.")

    # Segmentar em tarefas e agregar
    tasks = segment_tasks(records)
    agg = aggregate(tasks, target_date, local_tz, pricing)

    # Construir embed
    embed = build_embed(target_date, agg)

    if args.dry_run:
        print("=== DRY-RUN — embed que seria enviado ===")
        print(json.dumps(embed, indent=2, ensure_ascii=False))
        print("=== FIM DRY-RUN ===")
        return

    # Ler webhook URL
    webhook_url = read_webhook_url()
    if not webhook_url:
        sys.exit(1)

    # Enviar
    ok = send_to_discord(embed, webhook_url)
    if ok:
        print(f"[ok] Relatório de {target_date} enviado para Discord.")
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
