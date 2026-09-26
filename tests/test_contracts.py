"""Contracts must hold their structural guarantees without needing a DB."""
from stance.contracts import ComputationSpec, Operand, Plan, PlanStep, Scope


def test_computation_spec_has_no_numeric_field():
    """The calculator's output schema must never have a place to put a value —
    that's what makes 'the LLM never does arithmetic' a structural fact."""
    fields = ComputationSpec.model_fields.keys()
    for name in fields:
        assert "value" not in name and "result" not in name and "amount" not in name


def test_computation_spec_round_trip():
    spec = ComputationSpec(
        operation="growth_rate",
        operands=[
            Operand(role="current", fact_id="f-1"),
            Operand(role="prior", fact_id="f-2"),
        ],
        output_unit="percent",
    )
    dumped = spec.model_dump_json()
    restored = ComputationSpec.model_validate_json(dumped)
    assert restored.operation == "growth_rate"
    assert restored.spec_id == spec.spec_id


def test_plan_step_typing():
    scope = Scope(ciks=["0000320193"], tickers=["AAPL"], fiscal_years=[2024])
    step = PlanStep(sub_question="What was AAPL FY24 revenue?", kind="numeric", scope=scope)
    plan = Plan(question="What was AAPL FY24 revenue?", steps=[step])
    assert plan.steps[0].kind == "numeric"
    assert plan.steps[0].depends_on == []
