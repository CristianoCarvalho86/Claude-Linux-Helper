"""
Testes unitários do relatório de uso do Claude Code (Lucas).

Cobre:
- Segmentação de tarefas (timestamp-based)
- Soma correcta de tokens por modelo
- Cálculo de custo (fórmula completa com cache)
- Filtragem de registos <synthetic> / isApiErrorMessage
- Contagem de tarefas deduplicada (queued prompts)
- Período diário vs mensal
- Dia sem uso (stats zeradas)
- Multi-sessão
- Média de tokens por tarefa
"""

import datetime
import sys
from pathlib import Path
from zoneinfo import ZoneInfo

# Adicionar o dir do tool ao path para import
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from report import (
    segment_tasks,
    aggregate,
    compute_cost,
    is_human_top_level,
    is_real_assistant,
)
from tests.fixtures import (
    BASE,
    OP,
    SN,
    HK,
    single_model_records,
    multi_model_records,
    cache_tokens_records,
    multi_task_records,
    multi_session_records,
    no_usage_records,
    synthetic_ignored_records,
    queued_duplicate_records,
)

# Preços de teste (idênticos ao pricing.json)
PRICING = {
    "claude-opus-4-8":   {"input": 5.00,  "output": 25.00},
    "claude-sonnet-4-6": {"input": 3.00,  "output": 15.00},
    "claude-haiku-4-5":  {"input": 1.00,  "output":  5.00},
}

# Data alvo: 2026-07-01 (BASE está em 10:00 UTC = 11:00 WEST; mesmo dia local)
TARGET_DATE = datetime.date(2026, 7, 1)
TZ = ZoneInfo("UTC")  # Usar UTC nos testes para simplificar (sem conversão)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def agg_daily(records):
    tasks = segment_tasks(records)
    return aggregate(tasks, TARGET_DATE, TZ, PRICING)["daily"]


def agg_monthly(records):
    tasks = segment_tasks(records)
    return aggregate(tasks, TARGET_DATE, TZ, PRICING)["monthly"]


# ---------------------------------------------------------------------------
# compute_cost
# ---------------------------------------------------------------------------

class TestComputeCost:
    def test_opus_input_only(self):
        # 1M input = $5
        cost = compute_cost(OP, 1_000_000, 0, 0, 0, PRICING)
        assert abs(cost - 5.0) < 1e-9

    def test_opus_output_only(self):
        # 1M output = $25
        cost = compute_cost(OP, 0, 1_000_000, 0, 0, PRICING)
        assert abs(cost - 25.0) < 1e-9

    def test_cache_write_premium(self):
        # cache_write = input × 1.25; 1M cache_write opus = 5 × 1.25 = $6.25
        cost = compute_cost(OP, 0, 0, 1_000_000, 0, PRICING)
        assert abs(cost - 6.25) < 1e-9

    def test_cache_read_discount(self):
        # cache_read = input × 0.10; 1M cache_read opus = 5 × 0.10 = $0.50
        cost = compute_cost(OP, 0, 0, 0, 1_000_000, PRICING)
        assert abs(cost - 0.50) < 1e-9

    def test_combined(self):
        # in=1M, out=1M, cw=1M, cr=1M opus
        # = 5 + 25 + 6.25 + 0.50 = 36.75
        cost = compute_cost(OP, 1_000_000, 1_000_000, 1_000_000, 1_000_000, PRICING)
        assert abs(cost - 36.75) < 1e-9

    def test_unknown_model_zero_cost(self):
        cost = compute_cost("claude-unknown-99", 1_000_000, 1_000_000, 0, 0, PRICING)
        assert cost == 0.0

    def test_sonnet_pricing(self):
        # 1M in + 1M out sonnet = 3 + 15 = 18
        cost = compute_cost(SN, 1_000_000, 1_000_000, 0, 0, PRICING)
        assert abs(cost - 18.0) < 1e-9


# ---------------------------------------------------------------------------
# is_human_top_level
# ---------------------------------------------------------------------------

class TestIsHumanTopLevel:
    def test_human_string_content(self):
        r = {
            "type": "user",
            "origin": {"kind": "human"},
            "message": {"role": "user", "content": "hello"},
        }
        assert is_human_top_level(r)

    def test_tool_result_not_top_level(self):
        r = {
            "type": "user",
            "origin": {"kind": "human"},
            "message": {
                "role": "user",
                "content": [{"type": "tool_result", "tool_use_id": "x", "content": "ok"}],
            },
        }
        assert not is_human_top_level(r)

    def test_no_origin_not_top_level(self):
        r = {
            "type": "user",
            "message": {"role": "user", "content": "hello"},
        }
        assert not is_human_top_level(r)

    def test_assistant_type_not_top_level(self):
        r = {
            "type": "assistant",
            "origin": {"kind": "human"},
            "message": {"role": "assistant", "content": "hi"},
        }
        assert not is_human_top_level(r)


# ---------------------------------------------------------------------------
# is_real_assistant
# ---------------------------------------------------------------------------

class TestIsRealAssistant:
    def test_real_assistant(self):
        r = {
            "type": "assistant",
            "message": {"model": OP, "usage": {}},
        }
        assert is_real_assistant(r)

    def test_synthetic_excluded(self):
        r = {
            "type": "assistant",
            "message": {"model": "<synthetic>", "usage": {}},
        }
        assert not is_real_assistant(r)

    def test_api_error_excluded(self):
        r = {
            "type": "assistant",
            "isApiErrorMessage": True,
            "message": {"model": OP, "usage": {}},
        }
        assert not is_real_assistant(r)

    def test_user_type_excluded(self):
        r = {
            "type": "user",
            "message": {"model": OP, "usage": {}},
        }
        assert not is_real_assistant(r)


# ---------------------------------------------------------------------------
# segment_tasks
# ---------------------------------------------------------------------------

class TestSegmentTasks:
    def test_single_model_two_tasks(self):
        tasks = segment_tasks(single_model_records())
        assert len(tasks) == 2

    def test_multi_model_three_tasks(self):
        tasks = segment_tasks(multi_model_records())
        assert len(tasks) == 3

    def test_queued_duplicate_one_task(self):
        tasks = segment_tasks(queued_duplicate_records())
        assert len(tasks) == 1, f"Esperado 1 tarefa, obtido {len(tasks)}"

    def test_no_usage_zero_tasks(self):
        tasks = segment_tasks(no_usage_records())
        assert len(tasks) == 0

    def test_synthetic_excluded_from_task(self):
        tasks = segment_tasks(synthetic_ignored_records())
        assert len(tasks) == 1
        model_usage = dict(tasks[0]["model_usage"])
        assert OP in model_usage
        assert "<synthetic>" not in model_usage

    def test_multi_task_five_tasks(self):
        tasks = segment_tasks(multi_task_records())
        assert len(tasks) == 5

    def test_multi_session_two_tasks(self):
        tasks = segment_tasks(multi_session_records())
        assert len(tasks) == 2


# ---------------------------------------------------------------------------
# Tokens e somas
# ---------------------------------------------------------------------------

class TestTokenSums:
    def test_single_model_input_sum(self):
        daily = agg_daily(single_model_records())
        # 1000 + 2000 = 3000
        total_in = sum(bm["input"] for bm in daily["by_model"].values())
        assert total_in == 3000

    def test_single_model_output_sum(self):
        daily = agg_daily(single_model_records())
        total_out = sum(bm["output"] for bm in daily["by_model"].values())
        assert total_out == 1300  # 500 + 800

    def test_cache_tokens_correct(self):
        daily = agg_daily(cache_tokens_records())
        bm = daily["by_model"][OP]
        assert bm["input"] == 1000
        assert bm["output"] == 500
        assert bm["cache_write"] == 5000
        assert bm["cache_read"] == 10000

    def test_multi_model_per_model_split(self):
        daily = agg_daily(multi_model_records())
        # Opus: tarefa1 (in=1000,out=200) + tarefa3 (in=300,out=50) = in=1300, out=250
        bm_op = daily["by_model"][OP]
        assert bm_op["input"] == 1300
        assert bm_op["output"] == 250
        # Sonnet: tarefa2 (in=500,out=100) + tarefa3 (in=200,out=30) = in=700, out=130
        bm_sn = daily["by_model"][SN]
        assert bm_sn["input"] == 700
        assert bm_sn["output"] == 130

    def test_multi_task_total_tokens(self):
        daily = agg_daily(multi_task_records())
        # sum in = 1*1000 + 2*1000 + 3*1000 + 4*1000 + 5*1000 = 15000
        # (tasks use i*1000 for input, i*500 for output)
        total_in = sum(bm["input"] for bm in daily["by_model"].values())
        assert total_in == 15000  # 1k+2k+3k+4k+5k

    def test_multi_session_combined(self):
        daily = agg_daily(multi_session_records())
        # sess A: in=1000, sess B: in=2000
        total_in = sum(bm["input"] for bm in daily["by_model"].values())
        assert total_in == 3000


# ---------------------------------------------------------------------------
# Contagem de tarefas
# ---------------------------------------------------------------------------

class TestTaskCount:
    def test_daily_task_count(self):
        daily = agg_daily(single_model_records())
        assert daily["tasks"] == 2

    def test_multi_model_task_count(self):
        daily = agg_daily(multi_model_records())
        assert daily["tasks"] == 3

    def test_no_usage_zero_tasks(self):
        daily = agg_daily(no_usage_records())
        assert daily["tasks"] == 0

    def test_queued_duplicate_one_task(self):
        daily = agg_daily(queued_duplicate_records())
        assert daily["tasks"] == 1


# ---------------------------------------------------------------------------
# Custo
# ---------------------------------------------------------------------------

class TestCostCalculation:
    def test_opus_simple_cost(self):
        # in=1000, out=500 opus: 1000/1M*5 + 500/1M*25 = 0.000005 + 0.0000125 = 0.0000175
        tasks = segment_tasks(single_model_records())
        agg = aggregate(tasks, TARGET_DATE, TZ, PRICING)
        bm = agg["daily"]["by_model"][OP]
        expected = compute_cost(OP, bm["input"], bm["output"],
                                bm["cache_write"], bm["cache_read"], PRICING)
        assert expected > 0

    def test_cache_write_increases_cost(self):
        # Sem cache
        base_cost = compute_cost(OP, 1000, 500, 0, 0, PRICING)
        # Com cache_write
        with_cw = compute_cost(OP, 1000, 500, 5000, 0, PRICING)
        assert with_cw > base_cost

    def test_cache_read_less_than_input(self):
        # cache_read é mais barato que input equivalente
        cost_input = compute_cost(OP, 10000, 0, 0, 0, PRICING)
        cost_cr = compute_cost(OP, 0, 0, 0, 10000, PRICING)
        assert cost_cr < cost_input

    def test_full_cache_cost_formula(self):
        # in=1000, out=500, cw=5000, cr=10000 com opus
        # = 1000/1M*5 + 500/1M*25 + 5000/1M*5*1.25 + 10000/1M*5*0.10
        p_in = 5.0 / 1_000_000
        p_out = 25.0 / 1_000_000
        expected = (1000 * p_in + 500 * p_out
                    + 5000 * p_in * 1.25
                    + 10000 * p_in * 0.10)
        actual = compute_cost(OP, 1000, 500, 5000, 10000, PRICING)
        assert abs(actual - expected) < 1e-12


# ---------------------------------------------------------------------------
# Período mensal
# ---------------------------------------------------------------------------

class TestMonthlyPeriod:
    def test_monthly_includes_daily(self):
        # Tudo em TARGET_DATE = 2026-07-01: mensal deve == diário
        daily = agg_daily(single_model_records())
        monthly = agg_monthly(single_model_records())
        assert monthly["tasks"] == daily["tasks"]
        assert sum(bm["input"] for bm in monthly["by_model"].values()) == \
               sum(bm["input"] for bm in daily["by_model"].values())

    def test_monthly_excludes_future_day(self):
        """Registos num dia futuro não devem entrar no mensal."""
        import datetime
        # Criar registos com timestamp 2026-07-15 (fora do período 1-1)
        future = datetime.datetime(2026, 7, 15, 10, 0, 0)
        from tests.fixtures import make_human_msg, make_assistant, SESSION_A
        records = [
            make_human_msg("u1", None, "p1", BASE, SESSION_A),
            make_assistant("a1", "u1", BASE + datetime.timedelta(seconds=5), SESSION_A, OP,
                           input_tok=1000, output_tok=500),
            make_human_msg("u2", None, "p2", future, SESSION_A),
            make_assistant("a2", "u2", future + datetime.timedelta(seconds=5), SESSION_A, OP,
                           input_tok=9000, output_tok=5000),
        ]
        monthly = agg_monthly(records)
        # Só a tarefa do dia 1 deve estar no mensal (target=2026-07-01)
        total_in = sum(bm["input"] for bm in monthly["by_model"].values())
        assert total_in == 1000, f"Esperado 1000, obtido {total_in}"


# ---------------------------------------------------------------------------
# Dia sem uso
# ---------------------------------------------------------------------------

class TestNoUsage:
    def test_no_records_zero_tasks(self):
        daily = agg_daily([])
        assert daily["tasks"] == 0
        assert len(daily["by_model"]) == 0

    def test_misc_records_only_zero_tasks(self):
        daily = agg_daily(no_usage_records())
        assert daily["tasks"] == 0

    def test_synthetic_only_zero_real_tasks(self):
        from tests.fixtures import make_synthetic, SESSION_A
        records = [
            make_synthetic("s1", None, BASE, SESSION_A),
        ]
        daily = agg_daily(records)
        assert daily["tasks"] == 0


# ---------------------------------------------------------------------------
# Média tokens/tarefa
# ---------------------------------------------------------------------------

class TestAvgTokens:
    def test_avg_tokens_per_task(self):
        """
        single_model: 2 tarefas opus, in total=3000, out total=1300 → total=4300
        avg = 4300/2 = 2150 (total inclui in+out+cw+cr)
        """
        daily = agg_daily(single_model_records())
        bm = daily["by_model"][OP]
        n_tasks = bm["tasks"]
        total_tok = bm["input"] + bm["output"] + bm["cache_write"] + bm["cache_read"]
        avg = total_tok // n_tasks if n_tasks else 0
        assert avg == (3000 + 1300) // 2  # = 2150
