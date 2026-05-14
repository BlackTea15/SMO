import random
from decimal import Decimal
from typing import Any

from django.db import transaction
from django.utils import timezone

from .models import (
    DecisionEntry,
    EventLog,
    Objective,
    Scenario,
    SimulationStep,
    SituationReport,
    Unit,
)

PHASES = [
    "Разведка",
    "Подготовка",
    "Маневр",
    "Контакт",
    "Закрепление",
    "Разбор",
]
PHASE_SPAN = 3

UNIT_PHASE_TARGETS = {
    "Альфа-1": {
        "Разведка": (20, 26),
        "Подготовка": (18, 24),
        "Маневр": (22, 26),
        "Контакт": (24, 28),
        "Закрепление": (22, 25),
        "Разбор": (24, 30),
    },
    "Браво-2": {
        "Разведка": (34, 52),
        "Подготовка": (42, 48),
        "Маневр": (50, 44),
        "Контакт": (58, 46),
        "Закрепление": (48, 50),
        "Разбор": (40, 56),
    },
    "Чарли-3": {
        "Разведка": (64, 34),
        "Подготовка": (70, 35),
        "Маневр": (74, 36),
        "Контакт": (76, 35),
        "Закрепление": (75, 36),
        "Разбор": (72, 40),
    },
}

SECTOR_COORDS = {
    "A3": (18, 24),
    "D2": (75, 36),
}
SECTOR_CONTROL_RADIUS = 12
REPORT_TITLE = "Итоговый отчет операции"

STATUS_LABELS = {
    Scenario.STATUS_ACTIVE: "Операция в процессе",
    Scenario.STATUS_WON: "Победа",
    Scenario.STATUS_LOST: "Поражение",
}

SUPPLY_SOURCES = {
    "depot": {"name": "Центральный склад", "cost": 25, "gain": 20, "success": 1.0},
    "airdrop": {"name": "Авиадоставка", "cost": 35, "gain": 28, "success": 0.82},
    "local": {"name": "Локальные ресурсы", "cost": 15, "gain": 12, "success": 0.9},
}

ERROR_CATALOG = [
    {
        "code": "SCENARIO_CLOSED",
        "text": "Операция уже завершена. Для продолжения используйте перезапуск.",
    },
    {
        "code": "NO_RESERVE_SUPPLIES",
        "text": "Недостаточно резервных припасов для выбранного источника.",
    },
    {
        "code": "OBJECTIVES_NOT_COMPLETE",
        "text": "Нельзя завершить операцию, пока не выполнены все цели.",
    },
    {
        "code": "INVALID_SUPPLY_SOURCE",
        "text": "Указан неизвестный источник пополнения припасов.",
    },
    {
        "code": "BAD_PAYLOAD",
        "text": "В запрос переданы некорректные параметры.",
    },
    {
        "code": "REPORT_NOT_ENOUGH_DATA",
        "text": "Недостаточно шагов и решений для подготовки итогового отчета.",
    },
]

DEFAULT_UNITS = [
    {
        "name": "Альфа-1",
        "role": "мехгруппа",
        "readiness": 84,
        "supply": 71,
        "morale": 79,
        "pos_x": 18,
        "pos_y": 30,
    },
    {
        "name": "Браво-2",
        "role": "разведка",
        "readiness": 91,
        "supply": 66,
        "morale": 82,
        "pos_x": 30,
        "pos_y": 52,
    },
    {
        "name": "Чарли-3",
        "role": "инженеры",
        "readiness": 76,
        "supply": 88,
        "morale": 73,
        "pos_x": 70,
        "pos_y": 34,
    },
]

DEFAULT_OBJECTIVES = [
    "Удерживать контроль над секторами A3 и D2.",
    "Снизить потери снабжения ниже 25%.",
    "Удерживать выполнение плана в пределах 6 фаз.",
    "Подготовить отчет по ключевым решениям.",
]

DEFAULT_REPORTS = [
    {
        "title": "Северный коридор",
        "text": "Проходимость средняя, движение техники возможно с задержкой.",
        "state": "Стабильно",
    },
    {
        "title": "Южная группа",
        "text": "Требуется усиление инженерной поддержки на следующем шаге.",
        "state": "Внимание",
    },
    {
        "title": "Канал связи",
        "text": "Нагрузка 62%, запас пропускной способности сохраняется.",
        "state": "Стабильно",
    },
]

DEFAULT_EVENTS = [
    {
        "level": EventLog.LEVEL_INFO,
        "title": "Связь восстановлена",
        "description": "Резервный канал связи стабилен в северном секторе.",
    },
    {
        "level": EventLog.LEVEL_WARNING,
        "title": "Логистика замедлена",
        "description": "Скорость снабжения снижена из-за погодных условий.",
    },
    {
        "level": EventLog.LEVEL_CRITICAL,
        "title": "Ложный сигнал",
        "description": "Цель в квадрате C-7 не подтверждена повторной проверкой.",
    },
]

DEFAULT_DECISIONS = [
    "Переведен резервный канал связи на северный сектор.",
    "Уточнен маршрут снабжения через коридор B4.",
    "Подтверждена готовность группы Альфа-1.",
    "Скорректирован темп операции из-за погоды.",
    "Отменен выход в сектор C7 после проверки сигнала.",
    "Назначено усиление инженерной поддержки на юге.",
]

SIMULATION_DECISIONS = [
    "Подтвержден переход к следующему контрольному этапу.",
    "Утверждено перераспределение ресурсов между группами.",
    "Назначена дополнительная проверка северного сектора.",
    "Обновлены приоритеты логистики на текущую фазу.",
    "Добавлен резерв для снижения рисков по времени.",
    "Выполнена сверка готовности подразделений перед новым шагом.",
]


class SimulationError(Exception):
    def __init__(self, code: str, message: str, http_status: int = 400):
        super().__init__(message)
        self.code = code
        self.message = message
        self.http_status = http_status


def clamp(value: int, min_value: int, max_value: int) -> int:
    return max(min_value, min(max_value, value))


def avg(values: list[int]) -> int:
    if not values:
        return 0
    return int(round(sum(values) / len(values)))


def phase_for_step(step_number: int) -> str:
    index = min(len(PHASES) - 1, step_number // PHASE_SPAN)
    return PHASES[index]


def build_timeline(current_phase: str) -> list[dict[str, str]]:
    phase = current_phase if current_phase in PHASES else PHASES[0]
    active_index = PHASES.index(phase)
    timeline = []
    for idx, phase_name in enumerate(PHASES):
        if idx < active_index:
            status = "done"
        elif idx == active_index:
            status = "active"
        else:
            status = "pending"
        timeline.append({"name": phase_name, "status": status})
    return timeline


def risk_score(
    *,
    readiness_avg: int,
    supply_avg: int,
    morale_avg: int,
    intel_confidence: int,
    weather_index: int,
    pressure_index: int,
) -> float:
    score = (
        (100 - readiness_avg) * 0.30
        + (100 - supply_avg) * 0.30
        + (100 - morale_avg) * 0.12
        + (100 - intel_confidence) * 0.12
        + weather_index * 0.08
        + pressure_index * 0.08
    )
    return float(clamp(int(round(score)), 0, 100))


def risk_label(score: float) -> str:
    if score >= 70:
        return "Высокий"
    if score >= 45:
        return "Средний"
    return "Низкий"


def _status_label(status: str) -> str:
    return STATUS_LABELS.get(status, "Неизвестно")


def build_kpis(
    *,
    readiness_avg: int,
    supply_avg: int,
    morale_avg: int,
    risk_score_value: float,
    step_number: int,
    reserve_supplies: int,
) -> list[dict[str, str]]:
    return [
        {"name": "Готовность", "value": f"{readiness_avg}%", "id": "readiness"},
        {"name": "Снабжение", "value": f"{supply_avg}%", "id": "supply"},
        {"name": "Мораль", "value": f"{morale_avg}%", "id": "morale"},
        {"name": "Риск", "value": risk_label(risk_score_value), "id": "risk"},
        {"name": "Шаг", "value": str(step_number), "id": "step"},
        {"name": "Резерв", "value": str(reserve_supplies), "id": "reserve"},
    ]


def _serialize_units(units: list[Unit]) -> list[dict[str, Any]]:
    return [
        {
            "id": unit.id,
            "name": unit.name,
            "type": unit.role,
            "readiness": unit.readiness,
            "supply": unit.supply,
            "morale": unit.morale,
            "pos_x": unit.pos_x,
            "pos_y": unit.pos_y,
        }
        for unit in units
    ]


def _serialize_objectives(objectives: list[Objective]) -> list[dict[str, Any]]:
    return [
        {
            "id": objective.id,
            "text": objective.text,
            "progress": objective.progress,
            "is_completed": objective.is_completed or objective.progress >= 100,
        }
        for objective in objectives
    ]


def _serialize_reports(reports: list[SituationReport]) -> list[dict[str, str]]:
    return [{"title": report.title, "text": report.text, "state": report.state} for report in reports]


def _serialize_event(event: EventLog | None) -> dict[str, Any] | None:
    if not event:
        return None
    return {
        "time": timezone.localtime(event.created_at).strftime("%H:%M"),
        "title": event.title,
        "description": event.description,
        "level": event.level,
    }


def _serialize_decision(decision: DecisionEntry | None) -> dict[str, Any] | None:
    if not decision:
        return None
    return {
        "time": timezone.localtime(decision.created_at).strftime("%H:%M"),
        "text": decision.text,
    }


def _scenario_metrics(scenario: Scenario, units: list[Unit]) -> dict[str, Any]:
    readiness_avg = avg([unit.readiness for unit in units])
    supply_avg = avg([unit.supply for unit in units])
    morale_avg = avg([unit.morale for unit in units])

    risk_score_value = risk_score(
        readiness_avg=readiness_avg,
        supply_avg=supply_avg,
        morale_avg=morale_avg,
        intel_confidence=scenario.intel_confidence,
        weather_index=scenario.weather_index,
        pressure_index=scenario.pressure_index,
    )

    return {
        "readiness_avg": readiness_avg,
        "supply_avg": supply_avg,
        "morale_avg": morale_avg,
        "risk_score": risk_score_value,
        "risk_label": risk_label(risk_score_value),
    }


def _all_objectives_completed(objectives: list[Objective]) -> bool:
    return bool(objectives) and all(objective.is_completed or objective.progress >= 100 for objective in objectives)


def _refresh_reports(
    reports: list[SituationReport],
    *,
    weather_index: int,
    pressure_index: int,
    intel_confidence: int,
    supply_avg: int,
    morale_avg: int,
) -> None:
    if not reports:
        return

    states_payload = [
        {
            "state": "Нестабильно" if weather_index >= 65 else "Стабильно",
            "text": f"Погодный индекс: {weather_index} из 100. Требуется контроль маршрутов.",
        },
        {
            "state": "Внимание" if supply_avg < 65 or pressure_index >= 60 else "Стабильно",
            "text": f"Индекс давления: {pressure_index}. Средний запас снабжения: {supply_avg}%.",
        },
        {
            "state": "Внимание" if intel_confidence < 60 or morale_avg < 60 else "Стабильно",
            "text": f"Точность разведданных: {intel_confidence}%. Средняя мораль: {morale_avg}%.",
        },
    ]

    updated_reports: list[SituationReport] = []
    for index, report in enumerate(reports):
        source = states_payload[index % len(states_payload)]
        report.state = source["state"]
        report.text = source["text"]
        updated_reports.append(report)

    SituationReport.objects.bulk_update(updated_reports, ["state", "text"])


def _advance_objectives(
    objectives: list[Objective],
    *,
    scenario: Scenario,
    units: list[Unit],
    metrics: dict[str, Any],
    report_ready: bool,
) -> list[str]:
    if not objectives:
        return []

    completed_now: list[str] = []
    updated: list[Objective] = []

    objective_by_order = {objective.sort_order: objective for objective in objectives}
    supply_baseline = avg([unit["supply"] for unit in DEFAULT_UNITS])
    decisions_count = scenario.decisions.count()

    def finalize_objective(objective: Objective, progress: int, completed: bool) -> None:
        was_completed = objective.is_completed
        objective.progress = clamp(progress, 0, 100)
        objective.is_completed = completed and objective.progress >= 100
        if objective.is_completed and not was_completed:
            completed_now.append(objective.text)
        updated.append(objective)

    control_objective = objective_by_order.get(0)
    if control_objective:
        min_distance_a3 = min(
            (
                ((unit.pos_x - SECTOR_COORDS["A3"][0]) ** 2 + (unit.pos_y - SECTOR_COORDS["A3"][1]) ** 2) ** 0.5
                for unit in units
            ),
            default=100.0,
        )
        min_distance_d2 = min(
            (
                ((unit.pos_x - SECTOR_COORDS["D2"][0]) ** 2 + (unit.pos_y - SECTOR_COORDS["D2"][1]) ** 2) ** 0.5
                for unit in units
            ),
            default=100.0,
        )

        a3_controlled = min_distance_a3 <= SECTOR_CONTROL_RADIUS
        d2_controlled = min_distance_d2 <= SECTOR_CONTROL_RADIUS
        control_is_stable = a3_controlled and d2_controlled and metrics["readiness_avg"] >= 55

        gain = 18 if control_is_stable else 9 if (a3_controlled or d2_controlled) else 4
        progress = control_objective.progress + gain
        if control_is_stable and progress >= 82:
            progress = 100
        finalize_objective(control_objective, progress, control_is_stable or progress >= 100)

    supply_objective = objective_by_order.get(1)
    if supply_objective:
        supply_loss = max(0, supply_baseline - metrics["supply_avg"])
        if supply_loss <= 25:
            gain = 14 if metrics["supply_avg"] >= 65 else 10
        elif supply_loss <= 35:
            gain = 5
        else:
            gain = 2

        progress = supply_objective.progress + gain
        completed = supply_loss <= 25 and progress >= 86
        if completed:
            progress = 100
        finalize_objective(supply_objective, progress, completed or progress >= 100)

    report_objective = objective_by_order.get(3)
    if report_objective:
        if report_ready:
            progress = 100
            completed = decisions_count >= 4
        else:
            prep_progress = min(95, 20 + decisions_count * 6 + min(20, scenario.step_number * 2))
            progress = max(report_objective.progress, prep_progress)
            completed = False
        finalize_objective(report_objective, progress, completed)

    schedule_objective = objective_by_order.get(2)
    if schedule_objective:
        prerequisites = [objective_by_order.get(0), objective_by_order.get(1), objective_by_order.get(3)]
        prerequisites = [item for item in prerequisites if item is not None]
        prereq_progress = avg([item.progress for item in prerequisites]) if prerequisites else 0
        prereq_completed = bool(prerequisites) and all(item.is_completed for item in prerequisites)

        deadline_penalty = 0
        if scenario.step_number > scenario.step_limit:
            deadline_penalty = min(100, (scenario.step_number - scenario.step_limit) * 20)

        progress = clamp(prereq_progress - deadline_penalty, 0, 100)
        completed = prereq_completed and scenario.step_number <= scenario.step_limit
        if completed:
            progress = 100

        finalize_objective(schedule_objective, progress, completed)

    if updated:
        Objective.objects.bulk_update(updated, ["progress", "is_completed"])

    return completed_now


def _target_for_unit(unit: Unit, phase: str, unit_index: int) -> tuple[int, int]:
    unit_targets = UNIT_PHASE_TARGETS.get(unit.name)
    if unit_targets:
        target = unit_targets.get(phase) or unit_targets.get(PHASES[0])
        if target:
            return target

    # Fallback for custom squads not listed in UNIT_PHASE_TARGETS.
    default_targets = list(UNIT_PHASE_TARGETS.values())[unit_index % len(UNIT_PHASE_TARGETS)]
    return default_targets.get(phase, default_targets[PHASES[0]])


def _move_unit(
    *,
    unit: Unit,
    phase: str,
    unit_index: int,
    tempo: int,
    rng: random.Random,
) -> None:
    target_x, target_y = _target_for_unit(unit, phase, unit_index)

    mobility = clamp(int(round((unit.readiness + unit.supply + unit.morale) / 60)), 1, 5)
    step_move = clamp(mobility + tempo - 1, 2, 9)

    dx = target_x - unit.pos_x
    dy = target_y - unit.pos_y

    move_x = max(-step_move, min(step_move, dx * 0.45 + rng.uniform(-1.2, 1.2)))
    move_y = max(-step_move, min(step_move, dy * 0.45 + rng.uniform(-1.2, 1.2)))

    unit.pos_x = clamp(int(round(unit.pos_x + move_x)), 5, 95)
    unit.pos_y = clamp(int(round(unit.pos_y + move_y)), 5, 95)


def _pick_event(
    *,
    risk_score_value: float,
    min_supply: int,
    completed_objectives: list[str],
    weather_index: int,
    pressure_index: int,
) -> dict[str, str]:
    if completed_objectives:
        return {
            "level": EventLog.LEVEL_INFO,
            "title": "Цель операции достигнута",
            "description": f"Завершена цель: {completed_objectives[0]}",
        }

    if min_supply <= 20:
        return {
            "level": EventLog.LEVEL_CRITICAL,
            "title": "Критический уровень снабжения",
            "description": "У части подразделений запас ресурсов опасно низкий.",
        }

    if risk_score_value >= 72:
        return {
            "level": EventLog.LEVEL_CRITICAL,
            "title": "Резкий рост операционного риска",
            "description": "Требуется коррекция темпа и срочное пополнение снабжения.",
        }

    if weather_index >= 70 or pressure_index >= 70:
        return {
            "level": EventLog.LEVEL_WARNING,
            "title": "Сложные внешние условия",
            "description": "Внешняя обстановка ухудшает прогноз следующего шага.",
        }

    if risk_score_value >= 50:
        return {
            "level": EventLog.LEVEL_WARNING,
            "title": "Риск выше целевого",
            "description": "Нужна настройка параметров для стабилизации показателей.",
        }

    return {
        "level": EventLog.LEVEL_INFO,
        "title": "Шаг выполнен стабильно",
        "description": "Критических отклонений после шага не выявлено.",
    }


def _make_decision_text(*, tempo: int, risk_score_value: float, pressure_index: int) -> str:
    if risk_score_value >= 70:
        return "Решение: снизить темп и усилить контроль снабжения критичных групп."
    if pressure_index >= 65:
        return "Решение: перераспределить резервы на направления с высоким давлением."
    if tempo >= 4:
        return "Решение: сохранить высокий темп при усиленном мониторинге рисков."
    return random.choice(SIMULATION_DECISIONS)


def _step_rng(scenario: Scenario, next_step_number: int) -> random.Random:
    return random.Random(f"step:{scenario.id}:{next_step_number}")


def _resupply_rng(scenario: Scenario, source: str) -> random.Random:
    return random.Random(f"resupply:{scenario.id}:{scenario.step_number}:{source}:{scenario.reserve_supplies}")


def _reset_scenario_content(scenario: Scenario) -> None:
    scenario.step_number = 0
    scenario.step_limit = 18
    scenario.phase = PHASES[0]
    scenario.tempo = 3
    scenario.intel_confidence = 72
    scenario.weather_index = 35
    scenario.pressure_index = 45
    scenario.reserve_supplies = 120
    scenario.status = Scenario.STATUS_ACTIVE
    scenario.end_reason = ""
    scenario.ended_at = None
    scenario.save(
        update_fields=[
            "step_number",
            "step_limit",
            "phase",
            "tempo",
            "intel_confidence",
            "weather_index",
            "pressure_index",
            "reserve_supplies",
            "status",
            "end_reason",
            "ended_at",
            "updated_at",
        ]
    )

    scenario.units.all().delete()
    scenario.objectives.all().delete()
    scenario.reports.all().delete()
    scenario.steps.all().delete()
    scenario.events.all().delete()
    scenario.decisions.all().delete()

    Unit.objects.bulk_create(
        [
            Unit(
                scenario=scenario,
                sort_order=index,
                name=unit["name"],
                role=unit["role"],
                readiness=unit["readiness"],
                supply=unit["supply"],
                morale=unit["morale"],
                pos_x=unit["pos_x"],
                pos_y=unit["pos_y"],
            )
            for index, unit in enumerate(DEFAULT_UNITS)
        ]
    )

    Objective.objects.bulk_create(
        [Objective(scenario=scenario, text=text, sort_order=index) for index, text in enumerate(DEFAULT_OBJECTIVES)]
    )

    SituationReport.objects.bulk_create(
        [
            SituationReport(
                scenario=scenario,
                sort_order=index,
                title=report["title"],
                text=report["text"],
                state=report["state"],
            )
            for index, report in enumerate(DEFAULT_REPORTS)
        ]
    )

    EventLog.objects.bulk_create(
        [
            EventLog(
                scenario=scenario,
                level=event["level"],
                title=event["title"],
                description=event["description"],
            )
            for event in DEFAULT_EVENTS
        ]
    )

    DecisionEntry.objects.bulk_create([DecisionEntry(scenario=scenario, text=text) for text in DEFAULT_DECISIONS])


def _sanitize_int(value: Any, *, field: str, min_value: int, max_value: int) -> int:
    try:
        normalized = int(value)
    except (TypeError, ValueError):
        raise SimulationError("BAD_PAYLOAD", f"Параметр '{field}' должен быть числом.", 400) from None

    if normalized < min_value or normalized > max_value:
        raise SimulationError(
            "BAD_PAYLOAD",
            f"Параметр '{field}' должен быть в диапазоне {min_value}-{max_value}.",
            400,
        )
    return normalized


def _next_action_hint(
    *,
    scenario: Scenario,
    objectives: list[Objective],
    supply_avg: int,
    min_supply: int,
    risk_score_value: float,
) -> str:
    if scenario.status == Scenario.STATUS_WON:
        return "Операция завершена успешно. Можно перезапустить сценарий для новой попытки."
    if scenario.status == Scenario.STATUS_LOST:
        return "Операция завершена с поражением. Нажмите «Перезапуск», чтобы начать заново."
    if _all_objectives_completed(objectives):
        return "Все цели выполнены. Нажмите «Завершить операцию» для фиксации победы."
    report_objective = next((objective for objective in objectives if objective.sort_order == 3), None)
    if report_objective and not report_objective.is_completed and scenario.step_number >= 2:
        return "Сформируйте итоговый отчет, чтобы закрыть последнюю аналитическую цель."
    if min_supply <= 20 or supply_avg <= 35:
        return "Снабжение падает. Запросите припасы и только потом выполняйте следующий шаг."
    if risk_score_value >= 70:
        return "Риск высокий. Снизьте темп и увеличьте точность разведки перед следующим шагом."
    return "Скорректируйте параметры и выполните следующий шаг симуляции."


def _index_level(value: int) -> str:
    if value >= 70:
        return "Высокий"
    if value >= 45:
        return "Средний"
    return "Низкий"


def _weather_impact(weather_index: int) -> str:
    if weather_index >= 70:
        return "Погода сильно ухудшает логистику и повышает расход снабжения."
    if weather_index >= 45:
        return "Погода нестабильна: возможны задержки в снабжении и выполнении задач."
    return "Погодные условия стабильны, влияние на снабжение и темп минимальное."


def _pressure_impact(pressure_index: int) -> str:
    if pressure_index >= 70:
        return "Операционное давление высокое: быстрее падают мораль и готовность."
    if pressure_index >= 45:
        return "Давление умеренное: нужно контролировать темп, чтобы не перегрузить подразделения."
    return "Операционное давление низкое: подразделения работают в устойчивом режиме."


def _final_advice(*, status: str, supply_avg: int, risk_score_value: float, completed_all: bool) -> str:
    if status == Scenario.STATUS_WON:
        return "Победа зафиксирована. Для новой попытки можно изменить темп и стратегию снабжения."
    if completed_all:
        return "Цели выполнены. Завершите операцию и сохраните результат."
    if supply_avg <= 35:
        return "Главная ошибка: снабжение просело. В следующей попытке раньше запрашивайте пополнение."
    if risk_score_value >= 70:
        return "Главная ошибка: риск вышел из-под контроля. Снижайте темп и держите разведку выше 65%."
    return "Перезапустите сценарий и держите баланс между темпом, риском и логистикой."


def _action_response(
    *,
    scenario: Scenario,
    message: str,
    event: EventLog | None = None,
    decision: DecisionEntry | None = None,
) -> dict[str, Any]:
    return {
        "ok": True,
        "message": message,
        "state": dashboard_context(scenario),
        "event": _serialize_event(event),
        "decision": _serialize_decision(decision),
    }


def _close_as_lost(scenario: Scenario, *, reason: str) -> None:
    if scenario.status == Scenario.STATUS_LOST:
        return

    scenario.status = Scenario.STATUS_LOST
    scenario.end_reason = reason
    scenario.ended_at = timezone.now()
    scenario.save(update_fields=["status", "end_reason", "ended_at", "updated_at"])


def _close_as_won(scenario: Scenario, *, reason: str) -> None:
    if scenario.status == Scenario.STATUS_WON:
        return

    scenario.status = Scenario.STATUS_WON
    scenario.end_reason = reason
    scenario.ended_at = timezone.now()
    scenario.save(update_fields=["status", "end_reason", "ended_at", "updated_at"])


def _operation_report(scenario: Scenario) -> SituationReport | None:
    return scenario.reports.filter(title=REPORT_TITLE).first()


def bootstrap_active_scenario() -> Scenario:
    scenario = Scenario.objects.filter(is_active=True).order_by("-updated_at").first()

    if scenario is None:
        scenario = Scenario.objects.create(
            title="Операция Северный Вектор",
            description="Учебный сценарий координации разведки, снабжения и темпа операции.",
            is_active=True,
        )
        _reset_scenario_content(scenario)
        return scenario

    if (
        not scenario.units.exists()
        or not scenario.objectives.exists()
        or not scenario.reports.exists()
        or not scenario.events.exists()
        or not scenario.decisions.exists()
    ):
        _reset_scenario_content(scenario)
        return scenario

    update_fields: list[str] = []
    if scenario.step_limit < 18:
        scenario.step_limit = 18
        update_fields.append("step_limit")
    if update_fields:
        update_fields.append("updated_at")
        scenario.save(update_fields=update_fields)

    objectives_to_sync = []
    for objective in scenario.objectives.all():
        if 0 <= objective.sort_order < len(DEFAULT_OBJECTIVES):
            expected_text = DEFAULT_OBJECTIVES[objective.sort_order]
            if objective.text != expected_text:
                objective.text = expected_text
                objectives_to_sync.append(objective)
    if objectives_to_sync:
        Objective.objects.bulk_update(objectives_to_sync, ["text"])

    if scenario.status == Scenario.STATUS_ACTIVE:
        objectives = list(scenario.objectives.all())
        if _all_objectives_completed(objectives):
            _close_as_won(scenario, reason="Все цели выполнены. Операция успешно завершена.")

    return scenario


def dashboard_context(scenario: Scenario) -> dict[str, Any]:
    scenario = Scenario.objects.get(id=scenario.id)

    units = list(scenario.units.all())
    objectives = list(scenario.objectives.all())
    reports = list(scenario.reports.all())
    events = list(scenario.events.all()[:10])
    decisions = list(scenario.decisions.all()[:10])

    metrics = _scenario_metrics(scenario, units)
    completed_objectives = sum(1 for objective in objectives if objective.is_completed)
    min_supply = min((unit.supply for unit in units), default=0)
    all_objectives_done = _all_objectives_completed(objectives)
    operation_report = _operation_report(scenario)
    report_ready = operation_report is not None

    weather_level = _index_level(scenario.weather_index)
    pressure_level = _index_level(scenario.pressure_index)
    weather_impact = _weather_impact(scenario.weather_index)
    pressure_impact = _pressure_impact(scenario.pressure_index)

    sources = [
        {
            "id": source_id,
            "name": source_data["name"],
            "cost": source_data["cost"],
            "gain": source_data["gain"],
            "success_rate": int(source_data["success"] * 100),
        }
        for source_id, source_data in SUPPLY_SOURCES.items()
    ]

    return {
        "scenario_id": scenario.id,
        "operation_name": scenario.title,
        "description": scenario.description,
        "status": scenario.status,
        "status_label": _status_label(scenario.status),
        "is_game_over": scenario.status != Scenario.STATUS_ACTIVE,
        "end_reason": scenario.end_reason,
        "last_sync": timezone.localtime(scenario.updated_at).strftime("%H:%M:%S"),
        "phase": scenario.phase,
        "step_number": scenario.step_number,
        "step_limit": scenario.step_limit,
        "tempo": scenario.tempo,
        "intel_confidence": scenario.intel_confidence,
        "weather_index": scenario.weather_index,
        "pressure_index": scenario.pressure_index,
        "reserve_supplies": scenario.reserve_supplies,
        "risk": {"score": metrics["risk_score"], "label": metrics["risk_label"]},
        "risk_score": metrics["risk_score"],
        "kpis": build_kpis(
            readiness_avg=metrics["readiness_avg"],
            supply_avg=metrics["supply_avg"],
            morale_avg=metrics["morale_avg"],
            risk_score_value=metrics["risk_score"],
            step_number=scenario.step_number,
            reserve_supplies=scenario.reserve_supplies,
        ),
        "timeline": build_timeline(scenario.phase),
        "units": _serialize_units(units),
        "objectives": _serialize_objectives(objectives),
        "reports": _serialize_reports(reports),
        "events": [_serialize_event(item) for item in events],
        "decision_log": [_serialize_decision(item) for item in decisions],
        "supply_sources": sources,
        "error_catalog": ERROR_CATALOG,
        "report_ready": report_ready,
        "operation_report": operation_report.text if operation_report else "",
        "actions": {
            "can_simulate": scenario.status == Scenario.STATUS_ACTIVE,
            "can_resupply": scenario.status == Scenario.STATUS_ACTIVE and scenario.reserve_supplies > 0,
            "can_complete": scenario.status == Scenario.STATUS_ACTIVE and all_objectives_done,
            "can_generate_report": scenario.status == Scenario.STATUS_ACTIVE and scenario.step_number >= 2,
            "can_restart": True,
        },
        "summary": {
            "completed_objectives": completed_objectives,
            "total_objectives": len(objectives),
            "min_supply": min_supply,
        },
        "index_guides": {
            "weather": {
                "value": scenario.weather_index,
                "level": weather_level,
                "impact": weather_impact,
            },
            "pressure": {
                "value": scenario.pressure_index,
                "level": pressure_level,
                "impact": pressure_impact,
            },
        },
        "final_summary": {
            "status_label": _status_label(scenario.status),
            "end_reason": scenario.end_reason,
            "steps_used": scenario.step_number,
            "steps_limit": scenario.step_limit,
            "completed_objectives": completed_objectives,
            "total_objectives": len(objectives),
            "readiness_avg": metrics["readiness_avg"],
            "supply_avg": metrics["supply_avg"],
            "morale_avg": metrics["morale_avg"],
            "risk_score": metrics["risk_score"],
            "risk_label": metrics["risk_label"],
            "advice": _final_advice(
                status=scenario.status,
                supply_avg=metrics["supply_avg"],
                risk_score_value=metrics["risk_score"],
                completed_all=all_objectives_done,
            ),
        },
        "next_action_hint": _next_action_hint(
            scenario=scenario,
            objectives=objectives,
            supply_avg=metrics["supply_avg"],
            min_supply=min_supply,
            risk_score_value=metrics["risk_score"],
        ),
    }


@transaction.atomic
def run_simulation_step(scenario: Scenario, *, tempo: Any, intel_confidence: Any) -> dict[str, Any]:
    locked = Scenario.objects.select_for_update().get(id=scenario.id)
    if locked.status != Scenario.STATUS_ACTIVE:
        raise SimulationError(
            "SCENARIO_CLOSED",
            "Операция уже завершена. Для продолжения используйте перезапуск.",
            409,
        )

    tempo_value = _sanitize_int(tempo, field="tempo", min_value=1, max_value=5)
    intel_value = _sanitize_int(intel_confidence, field="intel_confidence", min_value=30, max_value=100)

    next_step_number = locked.step_number + 1
    rng = _step_rng(locked, next_step_number)

    locked.step_number = next_step_number
    locked.phase = phase_for_step(next_step_number)
    locked.tempo = tempo_value
    locked.intel_confidence = intel_value

    weather_shift = rng.randint(-6, 8) + max(0, tempo_value - 3) - (1 if intel_value >= 80 else 0)
    pressure_shift = rng.randint(-4, 7) + max(0, tempo_value - 2) + (2 if intel_value < 55 else 0)

    locked.weather_index = clamp(locked.weather_index + weather_shift, 5, 100)
    locked.pressure_index = clamp(locked.pressure_index + pressure_shift, 0, 100)
    locked.save(
        update_fields=[
            "step_number",
            "phase",
            "tempo",
            "intel_confidence",
            "weather_index",
            "pressure_index",
            "updated_at",
        ]
    )

    units = list(locked.units.all())
    if not units:
        raise SimulationError("BAD_PAYLOAD", "В сценарии отсутствуют подразделения.", 400)

    for index, unit in enumerate(units):
        readiness_delta = (
            rng.randint(-4, 3)
            - max(0, tempo_value - 3)
            - (2 if locked.pressure_index >= 75 else 0)
            + (1 if intel_value >= 85 else 0)
        )
        supply_delta = -rng.randint(3, 7) - max(0, tempo_value - 3) - (1 if locked.weather_index >= 74 else 0)
        morale_delta = rng.randint(-3, 3) - (2 if locked.weather_index >= 70 else 0) - (1 if unit.supply <= 22 else 0)

        if unit.supply <= 25:
            readiness_delta -= 1

        unit.readiness = clamp(unit.readiness + readiness_delta, 0, 100)
        unit.supply = clamp(unit.supply + supply_delta, 0, 100)
        unit.morale = clamp(unit.morale + morale_delta, 0, 100)
        _move_unit(unit=unit, phase=locked.phase, unit_index=index, tempo=tempo_value, rng=rng)

    Unit.objects.bulk_update(units, ["readiness", "supply", "morale", "pos_x", "pos_y"])

    metrics = _scenario_metrics(locked, units)

    objectives = list(locked.objectives.all())
    report_ready = _operation_report(locked) is not None
    completed_now = _advance_objectives(
        objectives,
        scenario=locked,
        units=units,
        metrics=metrics,
        report_ready=report_ready,
    )

    reports = list(locked.reports.all())
    _refresh_reports(
        reports,
        weather_index=locked.weather_index,
        pressure_index=locked.pressure_index,
        intel_confidence=locked.intel_confidence,
        supply_avg=metrics["supply_avg"],
        morale_avg=metrics["morale_avg"],
    )

    all_completed = _all_objectives_completed(objectives)
    min_supply = min((unit.supply for unit in units), default=0)

    event_payload = _pick_event(
        risk_score_value=metrics["risk_score"],
        min_supply=min_supply,
        completed_objectives=completed_now,
        weather_index=locked.weather_index,
        pressure_index=locked.pressure_index,
    )
    decision_text = _make_decision_text(
        tempo=tempo_value,
        risk_score_value=metrics["risk_score"],
        pressure_index=locked.pressure_index,
    )

    if min_supply <= 0:
        _close_as_lost(
            locked,
            reason="Снабжение ключевого подразделения достигло 0%. Операция провалена.",
        )
        event_payload = {
            "level": EventLog.LEVEL_CRITICAL,
            "title": "Операция провалена",
            "description": "Снабжение 0% привело к потере управляемости операции.",
        }
        decision_text = "Решение: признать срыв операции и подготовить перезапуск."
    elif locked.step_number >= locked.step_limit and not all_completed:
        _close_as_lost(
            locked,
            reason="Достигнут лимит шагов, а цели операции не выполнены.",
        )
        event_payload = {
            "level": EventLog.LEVEL_CRITICAL,
            "title": "Лимит шагов исчерпан",
            "description": "Операция завершена с поражением из-за невыполненных целей.",
        }
        decision_text = "Решение: зафиксировать поражение и начать сценарий заново."
    elif metrics["morale_avg"] <= 18:
        _close_as_lost(
            locked,
            reason="Средняя мораль подразделений критически низкая. Операция сорвана.",
        )
        event_payload = {
            "level": EventLog.LEVEL_CRITICAL,
            "title": "Потеря моральной устойчивости",
            "description": "Средняя мораль упала до критического уровня.",
        }
        decision_text = "Решение: прекратить операцию и выполнить перезапуск."
    elif all_completed:
        _close_as_won(
            locked,
            reason="Все цели выполнены. Операция успешно завершена.",
        )
        event_payload = {
            "level": EventLog.LEVEL_INFO,
            "title": "Операция завершена победой",
            "description": "Все цели достигнуты в пределах сценария.",
        }
        decision_text = "Решение: зафиксировать победу и перейти к разбору итогов."

    event = EventLog.objects.create(
        scenario=locked,
        level=event_payload["level"],
        title=event_payload["title"],
        description=event_payload["description"],
    )
    decision = DecisionEntry.objects.create(scenario=locked, text=decision_text)

    SimulationStep.objects.create(
        scenario=locked,
        step_number=locked.step_number,
        phase=locked.phase,
        tempo=locked.tempo,
        intel_confidence=locked.intel_confidence,
        weather_index=locked.weather_index,
        pressure_index=locked.pressure_index,
        readiness_avg=metrics["readiness_avg"],
        supply_avg=metrics["supply_avg"],
        morale_avg=metrics["morale_avg"],
        risk_score=Decimal(f"{metrics['risk_score']:.2f}"),
        details={
            "completed_now": completed_now,
            "all_objectives_completed": all_completed,
            "status": locked.status,
            "end_reason": locked.end_reason,
        },
    )

    if locked.status == Scenario.STATUS_LOST:
        message = "Операция завершена с поражением. Используйте кнопку «Перезапуск»."
    elif locked.status == Scenario.STATUS_WON:
        message = "Все цели выполнены. Операция завершена победой."
    else:
        message = f"Шаг {locked.step_number} успешно рассчитан."

    return _action_response(scenario=locked, message=message, event=event, decision=decision)


@transaction.atomic
def request_resupply(scenario: Scenario, *, source: Any) -> dict[str, Any]:
    locked = Scenario.objects.select_for_update().get(id=scenario.id)
    if locked.status != Scenario.STATUS_ACTIVE:
        raise SimulationError(
            "SCENARIO_CLOSED",
            "Операция уже завершена. Для продолжения используйте перезапуск.",
            409,
        )

    source_id = str(source or "").strip()
    if source_id not in SUPPLY_SOURCES:
        raise SimulationError("INVALID_SUPPLY_SOURCE", "Указан неизвестный источник пополнения припасов.", 400)

    source_data = SUPPLY_SOURCES[source_id]
    cost = int(source_data["cost"])
    if locked.reserve_supplies < cost:
        raise SimulationError(
            "NO_RESERVE_SUPPLIES",
            "Недостаточно резервных припасов для выбранного источника.",
            409,
        )

    locked.reserve_supplies = clamp(locked.reserve_supplies - cost, 0, 999)
    locked.save(update_fields=["reserve_supplies", "updated_at"])

    rng = _resupply_rng(locked, source_id)
    success = rng.random() <= float(source_data["success"])
    units = list(locked.units.all())

    if success:
        targets = sorted(units, key=lambda item: item.supply)[: max(1, min(2, len(units)))]
        total_gain = 0
        for unit in targets:
            gain = clamp(int(source_data["gain"]) + rng.randint(-4, 4), 6, 40)
            unit.supply = clamp(unit.supply + gain, 0, 100)
            unit.morale = clamp(unit.morale + rng.randint(1, 3), 0, 100)
            total_gain += gain
        Unit.objects.bulk_update(targets, ["supply", "morale"])

        event = EventLog.objects.create(
            scenario=locked,
            level=EventLog.LEVEL_INFO,
            title="Припасы получены",
            description=f"{source_data['name']} доставил ресурсы. Суммарное пополнение: +{total_gain}%.",
        )
        decision = DecisionEntry.objects.create(
            scenario=locked,
            text=f"Решение: задействовать источник «{source_data['name']}» для стабилизации снабжения.",
        )
        message = f"Пополнение из источника «{source_data['name']}» выполнено."
    else:
        impacted = [unit for unit in units if unit.supply <= 30]
        for unit in impacted:
            unit.morale = clamp(unit.morale - rng.randint(1, 4), 0, 100)
        if impacted:
            Unit.objects.bulk_update(impacted, ["morale"])

        event = EventLog.objects.create(
            scenario=locked,
            level=EventLog.LEVEL_WARNING,
            title="Пополнение сорвано",
            description=f"{source_data['name']} не смог доставить ресурсы в срок.",
        )
        decision = DecisionEntry.objects.create(
            scenario=locked,
            text=f"Решение: повторить логистический запрос и скорректировать маршрут для «{source_data['name']}».",
        )
        message = f"Пополнение из источника «{source_data['name']}» не удалось."

    min_supply = min((unit.supply for unit in locked.units.all()), default=0)
    if min_supply <= 0:
        _close_as_lost(
            locked,
            reason="Запас снабжения упал до 0%. Операция завершена с поражением.",
        )

    refreshed_units = list(locked.units.all())
    refreshed_objectives = list(locked.objectives.all())
    refreshed_metrics = _scenario_metrics(locked, refreshed_units)
    _advance_objectives(
        refreshed_objectives,
        scenario=locked,
        units=refreshed_units,
        metrics=refreshed_metrics,
        report_ready=_operation_report(locked) is not None,
    )
    if locked.status == Scenario.STATUS_ACTIVE and _all_objectives_completed(refreshed_objectives):
        _close_as_won(locked, reason="Все цели выполнены. Операция успешно завершена.")
        message = f"{message} Все цели закрыты, операция завершена победой."

    return _action_response(scenario=locked, message=message, event=event, decision=decision)


@transaction.atomic
def generate_operation_report(scenario: Scenario) -> dict[str, Any]:
    locked = Scenario.objects.select_for_update().get(id=scenario.id)
    if locked.status != Scenario.STATUS_ACTIVE:
        raise SimulationError(
            "SCENARIO_CLOSED",
            "Операция уже завершена. Для продолжения используйте перезапуск.",
            409,
        )

    recent_steps = list(locked.steps.all()[:5])
    recent_decisions = list(locked.decisions.all()[:6])
    if len(recent_steps) < 2 or len(recent_decisions) < 4:
        raise SimulationError(
            "REPORT_NOT_ENOUGH_DATA",
            "Недостаточно шагов и решений для подготовки итогового отчета.",
            409,
        )

    units = list(locked.units.all())
    metrics = _scenario_metrics(locked, units)
    top_decisions = list(reversed(recent_decisions[:4]))
    decisions_text = "; ".join(item.text for item in top_decisions)
    report_text = (
        f"Шаг: {locked.step_number}/{locked.step_limit}. "
        f"Фаза: {locked.phase}. "
        f"Готовность: {metrics['readiness_avg']}%, снабжение: {metrics['supply_avg']}%, "
        f"мораль: {metrics['morale_avg']}%, риск: {metrics['risk_score']}. "
        f"Ключевые решения: {decisions_text}"
    )

    report = _operation_report(locked)
    if report is None:
        sort_order = locked.reports.count()
        report = SituationReport.objects.create(
            scenario=locked,
            title=REPORT_TITLE,
            text=report_text,
            state="Готово",
            sort_order=sort_order,
        )
    else:
        report.text = report_text
        report.state = "Готово"
        report.save(update_fields=["text", "state"])

    event = EventLog.objects.create(
        scenario=locked,
        level=EventLog.LEVEL_INFO,
        title="Итоговый отчет подготовлен",
        description="Цель по подготовке отчета может быть закрыта после проверки сводки.",
    )
    decision = DecisionEntry.objects.create(
        scenario=locked,
        text="Решение: сформировать итоговый отчет по ключевым решениям операции.",
    )

    refreshed_objectives = list(locked.objectives.all())
    refreshed_metrics = _scenario_metrics(locked, list(locked.units.all()))
    _advance_objectives(
        refreshed_objectives,
        scenario=locked,
        units=list(locked.units.all()),
        metrics=refreshed_metrics,
        report_ready=True,
    )
    if locked.status == Scenario.STATUS_ACTIVE and _all_objectives_completed(refreshed_objectives):
        _close_as_won(locked, reason="Все цели выполнены. Операция успешно завершена.")

    return _action_response(
        scenario=locked,
        message=(
            "Итоговый отчет сформирован и добавлен в оперативные сводки."
            if locked.status == Scenario.STATUS_ACTIVE
            else "Итоговый отчет сформирован. Все цели закрыты, операция завершена победой."
        ),
        event=event,
        decision=decision,
    )


@transaction.atomic
def complete_operation(scenario: Scenario) -> dict[str, Any]:
    locked = Scenario.objects.select_for_update().get(id=scenario.id)
    if locked.status != Scenario.STATUS_ACTIVE:
        raise SimulationError(
            "SCENARIO_CLOSED",
            "Операция уже завершена. Для продолжения используйте перезапуск.",
            409,
        )

    objectives = list(locked.objectives.all())
    if not _all_objectives_completed(objectives):
        raise SimulationError(
            "OBJECTIVES_NOT_COMPLETE",
            "Нельзя завершить операцию, пока не выполнены все цели.",
            409,
        )

    locked.status = Scenario.STATUS_WON
    locked.end_reason = "Все цели выполнены. Операция успешно завершена."
    locked.ended_at = timezone.now()
    locked.save(update_fields=["status", "end_reason", "ended_at", "updated_at"])

    event = EventLog.objects.create(
        scenario=locked,
        level=EventLog.LEVEL_INFO,
        title="Операция завершена",
        description="Все цели подтверждены. Итоговый статус: победа.",
    )
    decision = DecisionEntry.objects.create(
        scenario=locked,
        text="Решение: завершить операцию и зафиксировать итоговые показатели.",
    )

    return _action_response(
        scenario=locked,
        message="Операция успешно завершена. Можно перезапустить сценарий для новой попытки.",
        event=event,
        decision=decision,
    )


@transaction.atomic
def restart_operation(scenario: Scenario) -> dict[str, Any]:
    locked = Scenario.objects.select_for_update().get(id=scenario.id)
    _reset_scenario_content(locked)

    event = EventLog.objects.create(
        scenario=locked,
        level=EventLog.LEVEL_INFO,
        title="Операция перезапущена",
        description="Сценарий сброшен. Все показатели возвращены к стартовым значениям.",
    )
    decision = DecisionEntry.objects.create(
        scenario=locked,
        text="Решение: начать операцию заново с базовыми параметрами.",
    )

    return _action_response(
        scenario=locked,
        message="Сценарий перезапущен. Можно снова запускать шаги.",
        event=event,
        decision=decision,
    )
