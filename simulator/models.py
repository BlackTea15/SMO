from django.db import models


class Scenario(models.Model):
    STATUS_ACTIVE = "active"
    STATUS_WON = "won"
    STATUS_LOST = "lost"

    STATUS_CHOICES = (
        (STATUS_ACTIVE, "Активна"),
        (STATUS_WON, "Победа"),
        (STATUS_LOST, "Поражение"),
    )

    title = models.CharField(max_length=180)
    description = models.TextField(blank=True)
    phase = models.CharField(max_length=64, default="Разведка")
    step_number = models.PositiveIntegerField(default=0)
    step_limit = models.PositiveIntegerField(default=12)
    intel_confidence = models.PositiveSmallIntegerField(default=72)
    tempo = models.PositiveSmallIntegerField(default=3)
    weather_index = models.PositiveSmallIntegerField(default=35)
    pressure_index = models.PositiveSmallIntegerField(default=45)
    reserve_supplies = models.PositiveSmallIntegerField(default=120)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=STATUS_ACTIVE)
    end_reason = models.CharField(max_length=260, blank=True)
    ended_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-updated_at",)

    def __str__(self):
        return self.title


class Unit(models.Model):
    scenario = models.ForeignKey(Scenario, on_delete=models.CASCADE, related_name="units")
    name = models.CharField(max_length=80)
    role = models.CharField(max_length=80)
    readiness = models.PositiveSmallIntegerField(default=80)
    supply = models.PositiveSmallIntegerField(default=80)
    morale = models.PositiveSmallIntegerField(default=75)
    pos_x = models.PositiveSmallIntegerField(default=20)
    pos_y = models.PositiveSmallIntegerField(default=20)
    sort_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ("sort_order", "id")

    def __str__(self):
        return f"{self.name} ({self.role})"


class Objective(models.Model):
    scenario = models.ForeignKey(Scenario, on_delete=models.CASCADE, related_name="objectives")
    text = models.CharField(max_length=220)
    progress = models.PositiveSmallIntegerField(default=0)
    is_completed = models.BooleanField(default=False)
    sort_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ("sort_order", "id")

    def __str__(self):
        return self.text


class SituationReport(models.Model):
    scenario = models.ForeignKey(Scenario, on_delete=models.CASCADE, related_name="reports")
    title = models.CharField(max_length=140)
    text = models.TextField()
    state = models.CharField(max_length=60)
    sort_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ("sort_order", "id")

    def __str__(self):
        return self.title


class EventLog(models.Model):
    LEVEL_INFO = "info"
    LEVEL_WARNING = "warning"
    LEVEL_CRITICAL = "critical"

    LEVEL_CHOICES = (
        (LEVEL_INFO, "Инфо"),
        (LEVEL_WARNING, "Предупреждение"),
        (LEVEL_CRITICAL, "Критично"),
    )

    scenario = models.ForeignKey(Scenario, on_delete=models.CASCADE, related_name="events")
    level = models.CharField(max_length=16, choices=LEVEL_CHOICES, default=LEVEL_INFO)
    title = models.CharField(max_length=140)
    description = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)

    def __str__(self):
        return self.title


class DecisionEntry(models.Model):
    scenario = models.ForeignKey(Scenario, on_delete=models.CASCADE, related_name="decisions")
    text = models.CharField(max_length=260)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)

    def __str__(self):
        return self.text


class SimulationStep(models.Model):
    scenario = models.ForeignKey(Scenario, on_delete=models.CASCADE, related_name="steps")
    step_number = models.PositiveIntegerField()
    phase = models.CharField(max_length=64)
    tempo = models.PositiveSmallIntegerField()
    intel_confidence = models.PositiveSmallIntegerField()
    weather_index = models.PositiveSmallIntegerField()
    pressure_index = models.PositiveSmallIntegerField()
    readiness_avg = models.PositiveSmallIntegerField()
    supply_avg = models.PositiveSmallIntegerField()
    morale_avg = models.PositiveSmallIntegerField()
    risk_score = models.DecimalField(max_digits=5, decimal_places=2)
    details = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)

    def __str__(self):
        return f"{self.scenario.title} / шаг {self.step_number}"
