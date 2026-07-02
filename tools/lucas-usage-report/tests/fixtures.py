"""
Fixtures JSONL para testes unitários do parser.
Geram conteúdo de ficheiro JSONL realista (schema verificado nos logs reais do cristiano).
"""

import json
import datetime


def _ts(dt: datetime.datetime) -> str:
    """Formata datetime como timestamp ISO 8601 UTC com Z."""
    return dt.strftime("%Y-%m-%dT%H:%M:%S.000Z")


BASE = datetime.datetime(2026, 7, 1, 10, 0, 0)  # 10h UTC = 11h Lisboa (WEST +1)


def make_human_msg(uuid: str, parent_uuid: str | None, prompt_id: str,
                   ts: datetime.datetime, session_id: str, text: str = "faz algo") -> dict:
    return {
        "type": "user",
        "uuid": uuid,
        "parentUuid": parent_uuid,
        "timestamp": _ts(ts),
        "sessionId": session_id,
        "promptId": prompt_id,
        "origin": {"kind": "human"},
        "promptSource": "typed",
        "message": {
            "role": "user",
            "content": text,
        },
    }


def make_tool_result(uuid: str, parent_uuid: str, prompt_id: str,
                     ts: datetime.datetime, session_id: str) -> dict:
    return {
        "type": "user",
        "uuid": uuid,
        "parentUuid": parent_uuid,
        "timestamp": _ts(ts),
        "sessionId": session_id,
        "promptId": prompt_id,
        # SEM origin.kind — distingue de human msg
        "message": {
            "role": "user",
            "content": [
                {"type": "tool_result", "tool_use_id": "tu1", "content": "ok"},
            ],
        },
    }


def make_assistant(uuid: str, parent_uuid: str, ts: datetime.datetime,
                   session_id: str, model: str,
                   input_tok: int, output_tok: int,
                   cache_write: int = 0, cache_read: int = 0) -> dict:
    return {
        "type": "assistant",
        "uuid": uuid,
        "parentUuid": parent_uuid,
        "timestamp": _ts(ts),
        "sessionId": session_id,
        "message": {
            "id": f"msg_{uuid[:8]}",
            "model": model,
            "role": "assistant",
            "type": "message",
            "stop_reason": "end_turn",
            "content": [{"type": "text", "text": "resposta"}],
            "usage": {
                "input_tokens": input_tok,
                "output_tokens": output_tok,
                "cache_creation_input_tokens": cache_write,
                "cache_read_input_tokens": cache_read,
                "server_tool_use": {"web_search_requests": 0, "web_fetch_requests": 0},
                "service_tier": "standard",
                "cache_creation": {"ephemeral_1h_input_tokens": cache_write, "ephemeral_5m_input_tokens": 0},
                "inference_geo": "not_available",
                "iterations": [
                    {
                        "input_tokens": input_tok,
                        "output_tokens": output_tok,
                        "cache_read_input_tokens": cache_read,
                        "cache_creation_input_tokens": cache_write,
                        "cache_creation": {"ephemeral_5m_input_tokens": 0, "ephemeral_1h_input_tokens": cache_write},
                        "type": "message",
                    }
                ],
                "speed": "standard",
            },
        },
    }


def make_synthetic(uuid: str, parent_uuid: str, ts: datetime.datetime, session_id: str) -> dict:
    """Registo <synthetic> (erro rate-limit) — deve ser ignorado."""
    return {
        "type": "assistant",
        "uuid": uuid,
        "parentUuid": parent_uuid,
        "timestamp": _ts(ts),
        "sessionId": session_id,
        "isApiErrorMessage": True,
        "apiErrorStatus": 429,
        "message": {
            "model": "<synthetic>",
            "role": "assistant",
            "type": "message",
            "stop_reason": "stop_sequence",
            "usage": {
                "input_tokens": 0,
                "output_tokens": 0,
                "cache_creation_input_tokens": 0,
                "cache_read_input_tokens": 0,
            },
            "content": [{"type": "text", "text": "Rate limited"}],
        },
    }


def make_misc(record_type: str, session_id: str, ts: datetime.datetime) -> dict:
    """Registo genérico que não é user nem assistant (mode, last-prompt, etc.)."""
    return {
        "type": record_type,
        "sessionId": session_id,
        "timestamp": _ts(ts),
    }


# ---------------------------------------------------------------------------
# Cenários
# ---------------------------------------------------------------------------

SESSION_A = "sess-aaaa-0001"
SESSION_B = "sess-bbbb-0002"

OP = "claude-opus-4-8"
SN = "claude-sonnet-4-6"
HK = "claude-haiku-4-5"


def single_model_records() -> list[dict]:
    """
    Sessão simples: 2 tarefas, 1 modelo (opus).
    Tarefa 1: 1 assistente (in=1000, out=500)
    Tarefa 2: 1 assistente (in=2000, out=800)
    """
    t = BASE  # 2026-07-01 10:00 UTC
    records = [
        make_human_msg("u1", None, "p1", t, SESSION_A, "tarefa um"),
        make_assistant("a1", "u1", t + datetime.timedelta(seconds=5), SESSION_A, OP,
                       input_tok=1000, output_tok=500),
        make_human_msg("u2", "a1", "p2", t + datetime.timedelta(minutes=10), SESSION_A, "tarefa dois"),
        make_assistant("a2", "u2", t + datetime.timedelta(minutes=10, seconds=8), SESSION_A, OP,
                       input_tok=2000, output_tok=800),
    ]
    return records


def multi_model_records() -> list[dict]:
    """
    3 tarefas, 2 modelos: opus e sonnet.
    Tarefa 1: opus (in=1000, out=200)
    Tarefa 2: sonnet (in=500, out=100)
    Tarefa 3: opus (in=300, out=50) + sonnet (in=200, out=30)
    """
    t = BASE
    records = [
        # Tarefa 1 — opus
        make_human_msg("u1", None, "p1", t, SESSION_A),
        make_assistant("a1", "u1", t + datetime.timedelta(seconds=3), SESSION_A, OP,
                       input_tok=1000, output_tok=200),
        # Tarefa 2 — sonnet
        make_human_msg("u2", "a1", "p2", t + datetime.timedelta(minutes=5), SESSION_A),
        make_assistant("a2", "u2", t + datetime.timedelta(minutes=5, seconds=4), SESSION_A, SN,
                       input_tok=500, output_tok=100),
        # Tarefa 3 — opus + sonnet (subagente)
        make_human_msg("u3", "a2", "p3", t + datetime.timedelta(minutes=10), SESSION_A),
        make_assistant("a3", "u3", t + datetime.timedelta(minutes=10, seconds=2), SESSION_A, OP,
                       input_tok=300, output_tok=50),
        make_assistant("a4", "a3", t + datetime.timedelta(minutes=10, seconds=6), SESSION_A, SN,
                       input_tok=200, output_tok=30),
    ]
    return records


def cache_tokens_records() -> list[dict]:
    """
    1 tarefa com cache_write e cache_read.
    in=1000, out=500, cw=5000, cr=10000
    """
    t = BASE
    records = [
        make_human_msg("u1", None, "p1", t, SESSION_A),
        make_assistant("a1", "u1", t + datetime.timedelta(seconds=5), SESSION_A, OP,
                       input_tok=1000, output_tok=500, cache_write=5000, cache_read=10000),
    ]
    return records


def multi_task_records() -> list[dict]:
    """
    5 tarefas numa sessão: soma total in=10000, out=4000.
    """
    t = BASE
    tasks = [
        (f"u{i}", f"a{i}", f"p{i}", i * 1000, i * 500)
        for i in range(1, 6)
    ]
    records = []
    prev_uuid = None
    for uuid_u, uuid_a, pid, inp, out in tasks:
        offset = datetime.timedelta(minutes=tasks.index((uuid_u, uuid_a, pid, inp, out)) * 5)
        parent = prev_uuid
        records.append(make_human_msg(uuid_u, parent, pid, t + offset, SESSION_A))
        records.append(make_assistant(uuid_a, uuid_u, t + offset + datetime.timedelta(seconds=3),
                                      SESSION_A, OP, inp, out))
        prev_uuid = uuid_a
    return records


def multi_session_records() -> list[dict]:
    """
    2 sessões independentes no mesmo dia; mesmas métricas que single_model mas em sessões separadas.
    """
    t = BASE
    records = []
    # Sessão A: 1 tarefa, in=1000, out=500
    records.append(make_human_msg("u1", None, "p1", t, SESSION_A))
    records.append(make_assistant("a1", "u1", t + datetime.timedelta(seconds=5), SESSION_A, OP,
                                  input_tok=1000, output_tok=500))
    # Sessão B: 1 tarefa, in=2000, out=800
    records.append(make_human_msg("u2", None, "p2", t + datetime.timedelta(minutes=30), SESSION_B))
    records.append(make_assistant("a2", "u2", t + datetime.timedelta(minutes=30, seconds=7), SESSION_B, OP,
                                  input_tok=2000, output_tok=800))
    return records


def no_usage_records() -> list[dict]:
    """
    Dia sem uso: só registos de modo/sistema, sem assistente.
    """
    t = BASE
    return [
        make_misc("mode", SESSION_A, t),
        make_misc("last-prompt", SESSION_A, t),
        make_misc("system", SESSION_A, t),
    ]


def synthetic_ignored_records() -> list[dict]:
    """
    Tarefa com 1 real assistente + 1 synthetic (rate-limit): só o real deve contar.
    """
    t = BASE
    records = [
        make_human_msg("u1", None, "p1", t, SESSION_A),
        make_assistant("a1", "u1", t + datetime.timedelta(seconds=2), SESSION_A, OP,
                       input_tok=1000, output_tok=400),
        make_synthetic("s1", "a1", t + datetime.timedelta(seconds=3), SESSION_A),
    ]
    return records


def queued_duplicate_records() -> list[dict]:
    """
    Mesmo promptId enviado 3 vezes (queued) — deve contar como 1 tarefa.
    """
    t = BASE
    records = [
        make_human_msg("u1", None, "p1", t, SESSION_A, "pedido"),
        make_human_msg("u2", None, "p1", t + datetime.timedelta(milliseconds=100), SESSION_A, "pedido"),
        make_human_msg("u3", None, "p1", t + datetime.timedelta(milliseconds=200), SESSION_A, "pedido"),
        make_assistant("a1", "u1", t + datetime.timedelta(seconds=5), SESSION_A, OP,
                       input_tok=500, output_tok=200),
    ]
    return records
