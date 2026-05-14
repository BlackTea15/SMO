from django.urls import path

from . import views

app_name = "simulator"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("api/scenarios/<int:scenario_id>/state/", views.scenario_state, name="scenario_state"),
    path("api/scenarios/<int:scenario_id>/step/", views.simulate_step, name="simulate_step"),
    path("api/scenarios/<int:scenario_id>/resupply/", views.resupply, name="resupply"),
    path("api/scenarios/<int:scenario_id>/report/", views.generate_report, name="generate_report"),
    path("api/scenarios/<int:scenario_id>/complete/", views.complete, name="complete"),
    path("api/scenarios/<int:scenario_id>/restart/", views.restart, name="restart"),
]
