from django.contrib import admin

from .models import (
    DecisionEntry,
    EventLog,
    Objective,
    Scenario,
    SimulationStep,
    SituationReport,
    Unit,
)


class UnitInline(admin.TabularInline):
    model = Unit
    extra = 0


class ObjectiveInline(admin.TabularInline):
    model = Objective
    extra = 0


class SituationReportInline(admin.TabularInline):
    model = SituationReport
    extra = 0


@admin.register(Scenario)
class ScenarioAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "phase",
        "step_number",
        "intel_confidence",
        "tempo",
        "weather_index",
        "pressure_index",
        "is_active",
        "updated_at",
    )
    list_filter = ("is_active", "phase")
    search_fields = ("title",)
    inlines = (UnitInline, ObjectiveInline, SituationReportInline)


@admin.register(EventLog)
class EventLogAdmin(admin.ModelAdmin):
    list_display = ("title", "scenario", "level", "created_at")
    list_filter = ("level", "scenario")
    search_fields = ("title", "description")


@admin.register(DecisionEntry)
class DecisionEntryAdmin(admin.ModelAdmin):
    list_display = ("scenario", "text", "created_at")
    list_filter = ("scenario",)
    search_fields = ("text",)


@admin.register(SimulationStep)
class SimulationStepAdmin(admin.ModelAdmin):
    list_display = (
        "scenario",
        "step_number",
        "phase",
        "tempo",
        "intel_confidence",
        "readiness_avg",
        "supply_avg",
        "morale_avg",
        "risk_score",
        "created_at",
    )
    list_filter = ("scenario", "phase")
    search_fields = ("scenario__title",)
    readonly_fields = (
        "scenario",
        "step_number",
        "phase",
        "tempo",
        "intel_confidence",
        "weather_index",
        "pressure_index",
        "readiness_avg",
        "supply_avg",
        "morale_avg",
        "risk_score",
        "details",
        "created_at",
    )
