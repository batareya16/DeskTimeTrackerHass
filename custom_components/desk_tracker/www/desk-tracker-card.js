if (!customElements.get("desk-tracker-card")) {
  class DeskTrackerCard extends HTMLElement {
    constructor() {
      super();
      this.attachShadow({ mode: "open" });
    }

    setConfig(config) {
      if (!config.entity) throw new Error("desk-tracker-card: 'entity' is required");
      this._config = config;
    }

    set hass(hass) {
      this._hass = hass;
      this._render();
    }

    _fmt(h) {
      if (h == null || isNaN(h)) return "0.0h";
      const hh = Math.floor(h);
      const mm = Math.round((h - hh) * 60);
      return mm > 0 ? `${hh}h ${mm}m` : `${hh}h`;
    }

    _render() {
      const hass = this._hass;
      const config = this._config;
      const stateObj = hass.states[config.entity];

      if (!stateObj) {
        this.shadowRoot.innerHTML = `<div style="padding:16px;color:var(--error-color)">Entity not found: ${config.entity}</div>`;
        return;
      }

      const attr = stateObj.attributes;
      const todayHours  = parseFloat(attr.today_hours   ?? 0);
      const todayLogged = attr.today_logged ?? false;
      const weekDays    = attr.week_days    ?? [];
      const streak      = attr.streak       ?? 0;
      const monthHours  = parseFloat(attr.month_hours   ?? 0);
      const monthReq    = parseFloat(attr.month_required ?? 0);
      const dailyGoal   = parseFloat(attr.daily_goal    ?? 6);

      const monthPct = monthReq > 0 ? Math.min(100, (monthHours / monthReq) * 100) : 0;
      const todayPct = dailyGoal > 0 ? Math.min(100, (todayHours / dailyGoal) * 100) : 0;

      // ---- week dots ----
      const DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri"];
      const dotsHtml = weekDays.map((d) => {
        const h = parseFloat(d.hours ?? 0);
        const pct = dailyGoal > 0 ? Math.min(1, h / dailyGoal) : 0;

        let dotClass = "dot-empty";
        let label = d.weekday;
        let hoursLabel = "";

        if (d.is_future) {
          dotClass = "dot-future";
        } else if (h >= dailyGoal) {
          dotClass = "dot-full";
          hoursLabel = `<span class="dot-hours">${this._fmt(h)}</span>`;
        } else if (h > 0) {
          dotClass = "dot-partial";
          hoursLabel = `<span class="dot-hours">${this._fmt(h)}</span>`;
        } else {
          hoursLabel = `<span class="dot-hours dot-zero">—</span>`;
        }

        const todayRing = d.is_today ? ' dot-today' : '';

        return `
          <div class="day-col">
            <div class="dot ${dotClass}${todayRing}">
              ${h >= dailyGoal ? '<span class="check">✓</span>' : (h > 0 ? `<span class="partial-fill" style="height:${Math.round(pct*100)}%"></span>` : '')}
            </div>
            <span class="day-label${d.is_today ? ' day-label-today' : ''}">${label}</span>
            ${hoursLabel}
          </div>`;
      }).join("");

      // ---- bar color ----
      const barColor = monthPct >= 100
        ? "var(--success-color, #44cc62)"
        : monthPct >= 60
        ? "var(--warning-color, #ff9800)"
        : "var(--error-color, #e53935)";

      const todayBarColor = todayPct >= 100
        ? "var(--success-color, #44cc62)"
        : todayPct >= 50
        ? "var(--warning-color, #ff9800)"
        : "var(--primary-color, #3b82f6)";

      const streakBadge = streak > 0
        ? `<span class="streak-badge">${streak}🔥</span>`
        : "";

      this.shadowRoot.innerHTML = `
        <style>
          :host { display: block; }
          .card {
            background: rgba(255,255,255,0.15);
            backdrop-filter: blur(16px) saturate(180%);
            -webkit-backdrop-filter: blur(16px) saturate(180%);
            border-radius: var(--ha-card-border-radius, 12px);
            border: 1px solid rgba(255,255,255,0.25);
            box-shadow: 0 4px 24px rgba(0,0,0,0.12);
            padding: 16px 18px 14px;
            font-family: var(--paper-font-body1_-_font-family, sans-serif);
            color: var(--primary-text-color, #1a1a1a);
            position: relative;
          }
          .header {
            display: flex;
            align-items: center;
            justify-content: space-between;
            margin-bottom: 14px;
          }
          .title {
            font-size: 1.05rem;
            font-weight: 600;
            display: flex;
            align-items: center;
            gap: 6px;
          }
          .title ha-icon { --mdi-icon-size: 20px; color: var(--primary-color); }
          .streak-badge {
            background: var(--primary-color, #3b82f6);
            color: #fff;
            border-radius: 20px;
            padding: 2px 10px;
            font-size: 0.78rem;
            font-weight: 700;
            letter-spacing: .3px;
          }

          /* week dots */
          .week-row {
            display: flex;
            justify-content: space-around;
            align-items: flex-end;
            margin-bottom: 16px;
          }
          .day-col {
            display: flex;
            flex-direction: column;
            align-items: center;
            gap: 4px;
          }
          .dot {
            width: 38px;
            height: 38px;
            border-radius: 50%;
            border: 2.5px solid var(--divider-color, #e0e0e0);
            display: flex;
            align-items: center;
            justify-content: center;
            position: relative;
            overflow: hidden;
            background: var(--secondary-background-color, #f5f5f5);
            box-sizing: border-box;
          }
          .dot-full {
            border-color: var(--success-color, #44cc62);
            background: var(--success-color, #44cc62);
          }
          .dot-full .check { color: #fff; font-size: 1.1rem; font-weight: 700; z-index: 2; }
          .dot-partial {
            border-color: var(--warning-color, #ff9800);
            background: var(--secondary-background-color, #f5f5f5);
          }
          .partial-fill {
            position: absolute;
            bottom: 0; left: 0; right: 0;
            background: var(--warning-color, #ff9800);
            opacity: 0.45;
            border-radius: 0 0 50% 50%;
          }
          .dot-today {
            box-shadow: 0 0 0 3px var(--primary-color, #3b82f6);
          }
          .dot-future {
            border-color: var(--disabled-color, #ccc);
            opacity: .45;
          }
          .dot-empty {
            border-color: var(--error-color, #e53935);
          }
          .day-label {
            font-size: 0.68rem;
            color: var(--secondary-text-color, #888);
            font-weight: 500;
            letter-spacing: .3px;
          }
          .day-label-today { color: var(--primary-color, #3b82f6); font-weight: 700; }
          .dot-hours {
            font-size: 0.65rem;
            color: var(--secondary-text-color, #888);
            min-height: 14px;
          }
          .dot-zero { opacity: 0.4; }

          /* today section */
          .section-label {
            font-size: 0.72rem;
            text-transform: uppercase;
            letter-spacing: .6px;
            color: var(--secondary-text-color, #888);
            font-weight: 600;
            margin-bottom: 5px;
          }
          .today-row {
            display: flex;
            align-items: center;
            justify-content: space-between;
            margin-bottom: 6px;
          }
          .today-hours {
            font-size: 1.55rem;
            font-weight: 700;
            letter-spacing: -.5px;
            line-height: 1;
          }
          .today-goal {
            font-size: 0.8rem;
            color: var(--secondary-text-color, #888);
            align-self: flex-end;
            padding-bottom: 3px;
          }
          .today-status {
            font-size: 0.82rem;
            font-weight: 600;
          }
          .status-ok  { color: var(--success-color, #44cc62); }
          .status-go  { color: var(--warning-color, #ff9800); }

          /* progress bars */
          .bar-track {
            background: var(--divider-color, #e0e0e0);
            border-radius: 4px;
            height: 7px;
            overflow: hidden;
            margin-bottom: 14px;
          }
          .bar-fill {
            height: 100%;
            border-radius: 4px;
            transition: width 0.4s ease;
          }

          /* stats grid */
          .stats-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 8px;
            margin-top: 4px;
          }
          .stat-box {
            background: var(--secondary-background-color, #f5f5f5);
            border-radius: 8px;
            padding: 8px 10px;
          }
          .stat-value {
            font-size: 1.05rem;
            font-weight: 700;
            line-height: 1.2;
          }
          .stat-label {
            font-size: 0.68rem;
            color: var(--secondary-text-color, #888);
            margin-top: 2px;
          }
          .divider {
            height: 1px;
            background: var(--divider-color, #e0e0e0);
            margin: 12px 0;
          }
        </style>

        <div class="card">
          <div class="header">
            <div class="title">
              <ha-icon icon="mdi:monitor"></ha-icon>
              Desk Time
            </div>
            ${streakBadge}
          </div>

          <div class="week-row">${dotsHtml}</div>

          <div class="divider"></div>

          <div class="section-label">Today</div>
          <div class="today-row">
            <div>
              <div class="today-hours">${this._fmt(todayHours)}</div>
              <div class="today-goal">goal: ${this._fmt(dailyGoal)}</div>
            </div>
            <div class="today-status ${todayLogged ? 'status-ok' : 'status-go'}">
              ${todayLogged
                ? '✓ Done!'
                : todayHours > 0
                  ? `${this._fmt(dailyGoal - todayHours)} to go`
                  : 'Not started'}
            </div>
          </div>
          <div class="bar-track">
            <div class="bar-fill" style="width:${todayPct}%;background:${todayBarColor}"></div>
          </div>

          <div class="section-label">This month</div>
          <div class="bar-track" style="margin-bottom:8px">
            <div class="bar-fill" style="width:${monthPct}%;background:${barColor}"></div>
          </div>

          <div class="stats-grid">
            <div class="stat-box">
              <div class="stat-value">${this._fmt(monthHours)}</div>
              <div class="stat-label">logged this month</div>
            </div>
            <div class="stat-box">
              <div class="stat-value">${this._fmt(monthReq)}</div>
              <div class="stat-label">target so far</div>
            </div>
          </div>
        </div>
      `;
    }

    getCardSize() { return 4; }
  }

  customElements.define("desk-tracker-card", DeskTrackerCard);
  window.customCards = window.customCards || [];
  window.customCards.push({
    type: "desk-tracker-card",
    name: "Desk Tracker",
    description: "Track how long you sit at your desk each day",
    preview: false,
  });
}
