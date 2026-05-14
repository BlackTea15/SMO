import json

from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_POST

from .models import Scenario
from .services import (
    SimulationError,
    bootstrap_active_scenario,
    complete_operation,
    dashboard_context,
    generate_operation_report,
    request_resupply,
    restart_operation,
    run_simulation_step,
)


def _payload_or_empty(request):
    if not request.body:
        return {}

    try:
        payload = json.loads(request.body.decode("utf-8"))
    except json.JSONDecodeError:
        raise SimulationError("BAD_PAYLOAD", "Некорректный JSON в теле запроса.", 400) from None

    if not isinstance(payload, dict):
        raise SimulationError("BAD_PAYLOAD", "Тело запроса должно быть JSON-объектом.", 400)

    return payload


def _error_response(*, scenario: Scenario, error: SimulationError):
    return JsonResponse(
        {
            "ok": False,
            "error": {"code": error.code, "message": error.message},
            "state": dashboard_context(scenario),
        },
        status=error.http_status,
    )


def dashboard(request):
    scenario = bootstrap_active_scenario()
    return render(request, "simulator/dashboard.html", dashboard_context(scenario))


def scenario_state(request, scenario_id: int):
    scenario = get_object_or_404(Scenario, id=scenario_id)
    return JsonResponse({"ok": True, "state": dashboard_context(scenario)})


@require_POST
def simulate_step(request, scenario_id: int):
    scenario = get_object_or_404(Scenario, id=scenario_id)

    try:
        payload = _payload_or_empty(request)
        tempo = payload.get("tempo", scenario.tempo)
        intel_confidence = payload.get("intel_confidence", scenario.intel_confidence)
        result = run_simulation_step(scenario, tempo=tempo, intel_confidence=intel_confidence)
    except SimulationError as error:
        return _error_response(scenario=scenario, error=error)

    return JsonResponse(result)


@require_POST
def resupply(request, scenario_id: int):
    scenario = get_object_or_404(Scenario, id=scenario_id)

    try:
        payload = _payload_or_empty(request)
        result = request_resupply(scenario, source=payload.get("source"))
    except SimulationError as error:
        return _error_response(scenario=scenario, error=error)

    return JsonResponse(result)


@require_POST
def complete(request, scenario_id: int):
    scenario = get_object_or_404(Scenario, id=scenario_id)

    try:
        result = complete_operation(scenario)
    except SimulationError as error:
        return _error_response(scenario=scenario, error=error)

    return JsonResponse(result)


@require_POST
def restart(request, scenario_id: int):
    scenario = get_object_or_404(Scenario, id=scenario_id)

    try:
        result = restart_operation(scenario)
    except SimulationError as error:
        return _error_response(scenario=scenario, error=error)

    return JsonResponse(result)


@require_POST
def generate_report(request, scenario_id: int):
    scenario = get_object_or_404(Scenario, id=scenario_id)

    try:
        result = generate_operation_report(scenario)
    except SimulationError as error:
        return _error_response(scenario=scenario, error=error)

    return JsonResponse(result)
