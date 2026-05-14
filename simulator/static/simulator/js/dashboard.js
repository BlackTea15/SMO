const app = document.getElementById("simulator-app");

if (app) {
    const urls = {
        step: app.dataset.stepUrl,
        state: app.dataset.stateUrl,
        resupply: app.dataset.resupplyUrl,
        report: app.dataset.reportUrl,
        complete: app.dataset.completeUrl,
        restart: app.dataset.restartUrl,
    };

    const csrfTokenInput = document.querySelector(".csrf-holder input[name='csrfmiddlewaretoken']");
    const csrfToken = csrfTokenInput ? csrfTokenInput.value : "";

    const timelineNode = document.getElementById("timeline");
    const phaseLabel = document.getElementById("current-phase");
    const lastSync = document.getElementById("last-sync");
    const statusCard = document.getElementById("operation-status");
    const statusLabel = document.getElementById("operation-status-label");
    const endReason = document.getElementById("operation-end-reason");
    const reserveValue = document.getElementById("reserve-value");
    const objectiveSummary = document.getElementById("objective-summary");
    const nextActionNode = document.getElementById("next-action");

    const finalScreen = document.getElementById("final-screen");
    const finalStatus = document.getElementById("final-status");
    const finalReason = document.getElementById("final-reason");
    const finalSteps = document.getElementById("final-steps");
    const finalObjectives = document.getElementById("final-objectives");
    const finalReadiness = document.getElementById("final-readiness");
    const finalSupply = document.getElementById("final-supply");
    const finalMorale = document.getElementById("final-morale");
    const finalRisk = document.getElementById("final-risk");
    const finalAdvice = document.getElementById("final-advice");
    const finalRestartBtn = document.getElementById("final-restart-btn");
    const gameOverOverlay = document.getElementById("game-over-overlay");
    const gameOverTitle = document.getElementById("game-over-title");
    const gameOverReason = document.getElementById("game-over-reason");
    const overlayRestartBtn = document.getElementById("overlay-restart-btn");

    const weatherLevel = document.getElementById("weather-level");
    const weatherImpact = document.getElementById("weather-impact");
    const pressureLevel = document.getElementById("pressure-level");
    const pressureImpact = document.getElementById("pressure-impact");

    const intelValue = document.getElementById("intel-value");
    const intelSliderValue = document.getElementById("intel-slider-value");
    const intelRange = document.getElementById("intel-range");

    const tempoValue = document.getElementById("tempo-value");
    const tempoRange = document.getElementById("tempo-range");
    const resupplySource = document.getElementById("resupply-source");

    const telemetryStep = document.getElementById("telemetry-step");
    const telemetryWeather = document.getElementById("telemetry-weather");
    const telemetryPressure = document.getElementById("telemetry-pressure");
    const telemetryRiskScore = document.getElementById("telemetry-risk-score");

    const simulateBtn = document.getElementById("simulate-btn");
    const resupplyBtn = document.getElementById("resupply-btn");
    const reportBtn = document.getElementById("report-btn");
    const completeBtn = document.getElementById("complete-btn");
    const restartBtn = document.getElementById("restart-btn");
    const simulateStatus = document.getElementById("simulate-status");

    const unitList = document.getElementById("unit-list");
    const mapShell = document.getElementById("map-shell");
    const eventList = document.getElementById("event-list");
    const decisionList = document.getElementById("decision-list");
    const objectiveList = document.getElementById("objective-list");
    const reportList = document.getElementById("report-list");

    let currentActions = {
        can_simulate: true,
        can_resupply: true,
        can_generate_report: false,
        can_complete: false,
        can_restart: true,
    };
    let isBusy = false;

    const stageButtons = () => (timelineNode ? timelineNode.querySelectorAll(".timeline-step") : []);

    const setStatus = (text, isError = false) => {
        if (!simulateStatus) {
            return;
        }
        simulateStatus.textContent = text;
        simulateStatus.classList.toggle("is-error", isError);
    };

    const setButtonsState = () => {
        if (simulateBtn) {
            simulateBtn.disabled = isBusy || !currentActions.can_simulate;
            simulateBtn.textContent = isBusy ? "Обработка..." : "Запустить шаг";
        }
        if (resupplyBtn) {
            resupplyBtn.disabled = isBusy || !currentActions.can_resupply;
        }
        if (completeBtn) {
            completeBtn.disabled = isBusy || !currentActions.can_complete;
        }
        if (reportBtn) {
            reportBtn.disabled = isBusy || !currentActions.can_generate_report;
        }
        if (restartBtn) {
            restartBtn.disabled = isBusy || !currentActions.can_restart;
        }
        if (finalRestartBtn) {
            finalRestartBtn.disabled = isBusy || !currentActions.can_restart;
        }
        if (intelRange) {
            intelRange.disabled = isBusy || !currentActions.can_simulate;
        }
        if (tempoRange) {
            tempoRange.disabled = isBusy || !currentActions.can_simulate;
        }
        if (resupplySource) {
            resupplySource.disabled = isBusy || !currentActions.can_resupply;
        }
    };

    const getKpiNode = (kpiId) => document.querySelector(`[data-kpi-id='${kpiId}'] strong`);

    const applyKpis = (kpis) => {
        if (!Array.isArray(kpis)) {
            return;
        }

        kpis.forEach((kpi) => {
            const node = getKpiNode(kpi.id);
            if (node) {
                node.textContent = kpi.value;
            }
        });
    };

    const applyTimeline = (timeline) => {
        if (!Array.isArray(timeline)) {
            return;
        }

        stageButtons().forEach((button, index) => {
            const stage = timeline[index];
            if (!stage) {
                return;
            }

            button.dataset.stage = stage.name;
            button.classList.remove("is-active", "is-done");
            if (stage.status === "active") {
                button.classList.add("is-active");
            }
            if (stage.status === "done") {
                button.classList.add("is-done");
            }

            const labels = button.querySelectorAll("span");
            if (labels.length > 1) {
                labels[1].textContent = stage.name;
            }
        });
    };

    const createUnitListItem = (unit) => {
        const item = document.createElement("li");
        item.className = "unit-item";
        item.dataset.unitId = String(unit.id);
        item.innerHTML = `
            <div class="unit-head">
                <strong>${unit.name}</strong>
                <span>${unit.type}</span>
            </div>
            <div class="meter">
                <label>Готовность <span class="value-readiness">${unit.readiness}%</span></label>
                <div class="bar"><span class="bar-readiness" style="width:${unit.readiness}%"></span></div>
            </div>
            <div class="meter">
                <label>Снабжение <span class="value-supply">${unit.supply}%</span></label>
                <div class="bar"><span class="bar-supply" style="width:${unit.supply}%"></span></div>
            </div>
            <div class="meter">
                <label>Мораль <span class="value-morale">${unit.morale}%</span></label>
                <div class="bar"><span class="bar-morale" style="width:${unit.morale}%"></span></div>
            </div>
        `;
        return item;
    };

    const createMapMarker = (unit) => {
        const marker = document.createElement("button");
        marker.type = "button";
        marker.className = "map-unit";
        marker.dataset.mapUnitId = String(unit.id);
        marker.style.left = `${unit.pos_x}%`;
        marker.style.top = `${unit.pos_y}%`;
        marker.textContent = unit.name;
        return marker;
    };

    const renderUnitsAndMap = (units) => {
        if (!Array.isArray(units)) {
            return;
        }

        if (unitList) {
            unitList.innerHTML = "";
            units.forEach((unit) => unitList.appendChild(createUnitListItem(unit)));
        }

        if (mapShell) {
            mapShell.querySelectorAll(".map-unit").forEach((node) => node.remove());
            units.forEach((unit) => mapShell.appendChild(createMapMarker(unit)));
        }
    };

    const renderObjectives = (objectives) => {
        if (!Array.isArray(objectives) || !objectiveList) {
            return;
        }

        objectiveList.innerHTML = "";
        objectives.forEach((objective) => {
            const item = document.createElement("li");
            item.dataset.objectiveId = String(objective.id);
            if (objective.is_completed) {
                item.classList.add("done");
            }
            item.innerHTML = `
                <p>${objective.text}</p>
                <div class="objective-progress">
                    <span class="objective-progress-bar" style="width:${objective.progress}%"></span>
                </div>
                <small class="objective-progress-value">${objective.progress}%</small>
            `;
            objectiveList.appendChild(item);
        });
    };

    const renderReports = (reports) => {
        if (!Array.isArray(reports) || !reportList) {
            return;
        }

        reportList.innerHTML = "";
        reports.forEach((report, index) => {
            const item = document.createElement("li");
            item.dataset.reportIndex = String(index);
            item.innerHTML = `
                <strong class="report-title">${report.title}</strong>
                <p class="report-text">${report.text}</p>
                <span class="state report-state">${report.state}</span>
            `;
            reportList.appendChild(item);
        });
    };

    const renderEvents = (events) => {
        if (!Array.isArray(events) || !eventList) {
            return;
        }

        eventList.innerHTML = "";
        events.forEach((event) => {
            const item = document.createElement("li");
            item.className = `event event-${event.level}`;
            item.innerHTML = `
                <span class="event-time">${event.time}</span>
                <div>
                    <strong>${event.title}</strong>
                    <p>${event.description}</p>
                </div>
            `;
            eventList.appendChild(item);
        });
    };

    const renderDecisions = (decisions) => {
        if (!Array.isArray(decisions) || !decisionList) {
            return;
        }

        decisionList.innerHTML = "";
        decisions.forEach((decision) => {
            const item = document.createElement("li");
            item.innerHTML = `
                <span>${decision.time}</span>
                <p>${decision.text}</p>
            `;
            decisionList.appendChild(item);
        });
    };

    const applyFinalSummary = (state) => {
        if (!finalScreen || !state || !state.final_summary) {
            return;
        }

        const summary = state.final_summary;
        finalScreen.classList.toggle("is-hidden", !state.is_game_over);

        if (finalStatus) {
            finalStatus.textContent = summary.status_label || "";
        }
        if (finalReason) {
            finalReason.textContent =
                summary.end_reason || "Операция еще не завершена. Этот экран будет заполнен после победы или поражения.";
        }
        if (finalSteps) {
            finalSteps.textContent = `${summary.steps_used}/${summary.steps_limit}`;
        }
        if (finalObjectives) {
            finalObjectives.textContent = `${summary.completed_objectives}/${summary.total_objectives}`;
        }
        if (finalReadiness) {
            finalReadiness.textContent = `${summary.readiness_avg}%`;
        }
        if (finalSupply) {
            finalSupply.textContent = `${summary.supply_avg}%`;
        }
        if (finalMorale) {
            finalMorale.textContent = `${summary.morale_avg}%`;
        }
        if (finalRisk) {
            finalRisk.textContent = `${summary.risk_label} (${summary.risk_score})`;
        }
        if (finalAdvice) {
            finalAdvice.textContent = summary.advice || "";
        }

        if (gameOverOverlay) {
            gameOverOverlay.classList.toggle("is-hidden", !state.is_game_over);
        }
        if (gameOverTitle) {
            if (state.status === "won") {
                gameOverTitle.textContent = "Операция завершена: победа";
            } else if (state.status === "lost") {
                gameOverTitle.textContent = "Операция завершена: поражение";
            } else {
                gameOverTitle.textContent = "Операция в процессе";
            }
        }
        if (gameOverReason) {
            gameOverReason.textContent = summary.end_reason || "Операция продолжается.";
        }
    };

    const applyState = (state) => {
        if (!state) {
            return;
        }

        if (phaseLabel && state.phase) {
            phaseLabel.textContent = `Текущая фаза: ${state.phase}`;
        }
        if (lastSync && state.last_sync) {
            lastSync.textContent = state.last_sync;
        }

        if (statusCard && state.status) {
            statusCard.dataset.status = state.status;
        }
        if (statusLabel && state.status_label) {
            statusLabel.textContent = state.status_label;
        }
        if (endReason) {
            endReason.textContent = state.end_reason || "Операция активна. Следуйте этапам и контролируйте снабжение.";
        }
        if (reserveValue && state.reserve_supplies !== undefined) {
            reserveValue.textContent = String(state.reserve_supplies);
        }
        if (objectiveSummary && state.summary) {
            objectiveSummary.textContent = `${state.summary.completed_objectives}/${state.summary.total_objectives}`;
        }
        if (nextActionNode && state.next_action_hint) {
            nextActionNode.textContent = state.next_action_hint;
        }

        if (state.index_guides) {
            if (weatherLevel) {
                weatherLevel.textContent = state.index_guides.weather.level;
            }
            if (weatherImpact) {
                weatherImpact.textContent = state.index_guides.weather.impact;
            }
            if (pressureLevel) {
                pressureLevel.textContent = state.index_guides.pressure.level;
            }
            if (pressureImpact) {
                pressureImpact.textContent = state.index_guides.pressure.impact;
            }
        }

        if (state.intel_confidence !== undefined && intelRange) {
            const intelText = `${state.intel_confidence}%`;
            intelRange.value = state.intel_confidence;
            if (intelValue) {
                intelValue.textContent = intelText;
            }
            if (intelSliderValue) {
                intelSliderValue.textContent = intelText;
            }
        }
        if (state.tempo !== undefined && tempoRange) {
            tempoRange.value = state.tempo;
            if (tempoValue) {
                tempoValue.textContent = String(state.tempo);
            }
        }

        if (telemetryStep && state.step_number !== undefined) {
            telemetryStep.textContent = String(state.step_number);
        }
        if (telemetryWeather && state.weather_index !== undefined) {
            telemetryWeather.textContent = String(state.weather_index);
        }
        if (telemetryPressure && state.pressure_index !== undefined) {
            telemetryPressure.textContent = String(state.pressure_index);
        }
        if (telemetryRiskScore && state.risk && state.risk.score !== undefined) {
            telemetryRiskScore.textContent = String(state.risk.score);
        }

        if (state.actions) {
            currentActions = {
                can_simulate: Boolean(state.actions.can_simulate),
                can_resupply: Boolean(state.actions.can_resupply),
                can_generate_report: Boolean(state.actions.can_generate_report),
                can_complete: Boolean(state.actions.can_complete),
                can_restart: Boolean(state.actions.can_restart),
            };
            setButtonsState();
        }

        applyKpis(state.kpis);
        applyTimeline(state.timeline);
        renderUnitsAndMap(state.units);
        renderObjectives(state.objectives);
        renderReports(state.reports);
        renderEvents(state.events);
        renderDecisions(state.decision_log);
        applyFinalSummary(state);
    };

    const fetchState = async () => {
        const response = await fetch(urls.state, { method: "GET" });
        const payload = await response.json();
        if (!response.ok || payload.ok === false) {
            throw new Error("state_request_failed");
        }
        applyState(payload.state);
        setStatus("Состояние синхронизировано.");
    };

    const postAction = async (url, body = {}) => {
        const response = await fetch(url, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "X-CSRFToken": csrfToken,
            },
            body: JSON.stringify(body),
        });

        let payload = {};
        try {
            payload = await response.json();
        } catch (error) {
            payload = {};
        }

        if (!response.ok || payload.ok === false) {
            const err = new Error(payload.error && payload.error.message ? payload.error.message : "request_failed");
            err.state = payload.state;
            throw err;
        }

        return payload;
    };

    const handleAction = async (fn, fallbackErrorText) => {
        isBusy = true;
        setButtonsState();

        try {
            const payload = await fn();
            applyState(payload.state);
            setStatus(payload.message || "Действие выполнено.");
        } catch (error) {
            if (error.state) {
                applyState(error.state);
            }
            console.error(error);
            setStatus(error.message || fallbackErrorText, true);
        } finally {
            isBusy = false;
            setButtonsState();
        }
    };

    stageButtons().forEach((button) => {
        button.addEventListener("click", () => {
            if (phaseLabel) {
                phaseLabel.textContent = `Текущая фаза: ${button.dataset.stage}`;
            }
        });
    });

    if (intelRange) {
        intelRange.addEventListener("input", () => {
            const value = `${intelRange.value}%`;
            if (intelValue) {
                intelValue.textContent = value;
            }
            if (intelSliderValue) {
                intelSliderValue.textContent = value;
            }
        });
    }

    if (tempoRange) {
        tempoRange.addEventListener("input", () => {
            if (tempoValue) {
                tempoValue.textContent = tempoRange.value;
            }
        });
    }

    if (simulateBtn) {
        simulateBtn.addEventListener("click", async () => {
            await handleAction(
                () =>
                    postAction(urls.step, {
                        tempo: Number(tempoRange ? tempoRange.value : 3),
                        intel_confidence: Number(intelRange ? intelRange.value : 72),
                    }),
                "Не удалось рассчитать шаг."
            );
        });
    }

    if (resupplyBtn) {
        resupplyBtn.addEventListener("click", async () => {
            await handleAction(
                () =>
                    postAction(urls.resupply, {
                        source: resupplySource ? resupplySource.value : "",
                    }),
                "Не удалось запросить припасы."
            );
        });
    }

    if (completeBtn) {
        completeBtn.addEventListener("click", async () => {
            await handleAction(() => postAction(urls.complete), "Не удалось завершить операцию.");
        });
    }

    if (reportBtn) {
        reportBtn.addEventListener("click", async () => {
            await handleAction(() => postAction(urls.report), "Не удалось сформировать итоговый отчет.");
        });
    }

    const restartAction = async () =>
        handleAction(() => postAction(urls.restart), "Не удалось перезапустить сценарий.");

    if (restartBtn) {
        restartBtn.addEventListener("click", restartAction);
    }
    if (finalRestartBtn) {
        finalRestartBtn.addEventListener("click", restartAction);
    }
    if (overlayRestartBtn) {
        overlayRestartBtn.addEventListener("click", restartAction);
    }

    fetchState().catch((error) => {
        console.error(error);
        setStatus("Не удалось синхронизировать состояние сценария.", true);
    });
}
