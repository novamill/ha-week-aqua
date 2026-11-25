/*
 * Week Aqua dashboard cards for Home Assistant.
 *
 *   type: custom:week-aqua-light-card
 *   entity: light.mini9pro_30
 *
 *   type: custom:week-aqua-pump-card
 *   entity: fan.es350
 *
 * Served by the integration itself; no separate install is needed. The cards
 * find the device's other entities (channels, schedule, feed...) through the
 * entity registry, so only the light or fan entity has to be configured.
 */

const DOMAIN = "week_aqua";

const STRINGS = {
  en: {
    on: "On",
    off: "Off",
    unavailable: "Unavailable",
    brightness: "Brightness",
    channels: "Colour channels",
    red: "Red",
    green: "Green",
    blue: "Blue",
    uv: "UV",
    power_limited: "Power limit: output scaled to {pct}%",
    schedule: "Built-in schedule",
    schedule_hint: "The lamp switches itself on and off, even when Home Assistant is offline.",
    on_time: "On",
    off_time: "Off",
    midnight: "00:00 = midnight",
    ramp: "Sunrise / sunset",
    ramp_off: "Off",
    min: "min",
    strength: "Strength",
    mode: "Mode",
    constant: "Constant",
    wavy: "Wavy",
    surge: "Surge",
    tide: "Tide",
    cycle: "Cycle",
    feed: "Feed",
    feed_pause: "Feed pause",
    feeding: "Feeding: {time} left",
    not_found: "Entity {entity} not found",
    choose_entity: "Choose a Week Aqua light or pump",
    light_card: "Week Aqua light",
    light_card_desc: "Colour channels, brightness and the lamp's built-in schedule.",
    pump_card: "Week Aqua pump",
    pump_card_desc: "Strength, wave pattern and feed pause.",
  },
  hu: {
    on: "Be",
    off: "Ki",
    unavailable: "Nem elérhető",
    brightness: "Fényerő",
    channels: "Színcsatornák",
    red: "Piros",
    green: "Zöld",
    blue: "Kék",
    uv: "UV",
    power_limited: "Teljesítménykorlát: a kimenet {pct}%-ra csökkentve",
    schedule: "Beépített időzítés",
    schedule_hint: "A lámpa magától be- és kikapcsol, akkor is, ha a Home Assistant nem fut.",
    on_time: "Be",
    off_time: "Ki",
    midnight: "00:00 = éjfél",
    ramp: "Napfelkelte / naplemente",
    ramp_off: "Ki",
    min: "perc",
    strength: "Erősség",
    mode: "Üzemmód",
    constant: "Állandó",
    wavy: "Hullámzó",
    surge: "Lökésszerű",
    tide: "Árapály",
    cycle: "Ciklikus",
    feed: "Etetés",
    feed_pause: "Etetési szünet",
    feeding: "Etetés: még {time}",
    not_found: "A(z) {entity} entitás nem található",
    choose_entity: "Válassz egy Week Aqua lámpát vagy pumpát",
    light_card: "Week Aqua lámpa",
    light_card_desc: "Színcsatornák, fényerő és a lámpa beépített időzítése.",
    pump_card: "Week Aqua pumpa",
    pump_card_desc: "Erősség, hullámminta és etetési szünet.",
  },
};

const LANG = () => {
  const lang = (document.querySelector("home-assistant")?.hass?.locale?.language ||
    navigator.language || "en").slice(0, 2);
  return STRINGS[lang] ? lang : "en";
};

function tr(hass, key, vars = {}) {
  const lang = (hass?.locale?.language || hass?.language || LANG()).slice(0, 2);
  let s = (STRINGS[lang] || STRINGS.en)[key] ?? STRINGS.en[key] ?? key;
  for (const [k, v] of Object.entries(vars)) s = s.replace(`{${k}}`, v);
  return s;
}

const CHANNELS = [
  { key: "red", color: "#e53935" },
  { key: "green", color: "#43a047" },
  { key: "blue", color: "#1e88e5" },
  { key: "uv", color: "#8e24aa" },
];

const RAMPS = ["0", "30", "60", "90", "120", "150"];

const PUMP_MODES = [
  { key: "constant", icon: "mdi:arrow-right-thin" },
  { key: "wavy", icon: "mdi:sine-wave" },
  { key: "surge", icon: "mdi:pulse" },
  { key: "tide", icon: "mdi:waves" },
  { key: "cycle", icon: "mdi:autorenew" },
];

// Entity-id suffixes (from the English entity names), used when the registry
// entry has no translation key.
const SUFFIX = {
  channel_red: "_red",
  channel_green: "_green",
  channel_blue: "_blue",
  channel_uv: "_uv",
  schedule: "_built_in_schedule",
  schedule_on_time: "_schedule_on_time",
  schedule_off_time: "_schedule_off_time",
  schedule_ramp: "_sunrise_sunset_length",
  feed: "_feed_pause",
  feed_duration: "_feed_pause_duration",
};

/** Map translation keys to entity ids for the device that owns `entityId`. */
function deviceEntities(hass, entityId) {
  const reg = hass.entities || {};
  const deviceId = reg[entityId]?.device_id;
  const found = {};
  if (!deviceId) return found;
  const siblings = Object.values(reg).filter(
    (e) => e.device_id === deviceId && (!e.platform || e.platform === DOMAIN),
  );
  for (const [key, suffix] of Object.entries(SUFFIX)) {
    const byKey = siblings.find((e) => e.translation_key === key);
    const bySuffix = siblings.find((e) => e.entity_id.endsWith(suffix) &&
      // "_feed_pause" must not match "_feed_pause_duration".
      !Object.values(SUFFIX).some((s) => s !== suffix && s.endsWith(suffix) && e.entity_id.endsWith(s)));
    const hit = byKey || bySuffix;
    if (hit) found[key] = hit.entity_id;
  }
  return found;
}

const num = (state, fallback = 0) => {
  const v = parseFloat(state?.state);
  return Number.isFinite(v) ? v : fallback;
};
const isUnavailable = (state) => !state || state.state === "unavailable";
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => `&#${c.charCodeAt(0)};`);

const STYLE = `
  :host { display: block; }
  ha-card { padding: 16px; display: flex; flex-direction: column; gap: 16px; }
  .header { display: flex; align-items: center; gap: 12px; }
  .badge { width: 40px; height: 40px; border-radius: 50%; display: grid; place-items: center;
    flex: none; background: var(--secondary-background-color); color: var(--secondary-text-color);
    transition: background .3s, color .3s; }
  .badge ha-icon { --mdc-icon-size: 22px; }
  .titles { flex: 1; min-width: 0; }
  .name { font-size: 16px; font-weight: 500; color: var(--primary-text-color);
    white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .state { font-size: 13px; color: var(--secondary-text-color); }
  .section { display: flex; flex-direction: column; gap: 10px; }
  .section-title { font-size: 12px; font-weight: 500; letter-spacing: .04em; text-transform: uppercase;
    color: var(--secondary-text-color); display: flex; align-items: center; justify-content: space-between; gap: 8px; }
  .row { display: grid; grid-template-columns: 72px 1fr 44px; align-items: center; gap: 10px; }
  .row .label { font-size: 14px; color: var(--primary-text-color); }
  .row .value { font-size: 14px; text-align: right; color: var(--secondary-text-color);
    font-variant-numeric: tabular-nums; }
  .note { font-size: 12px; color: var(--warning-color, #f4b400); }
  .hint { font-size: 12px; color: var(--secondary-text-color); }
  .disabled { opacity: .45; pointer-events: none; }
  .dim { opacity: .55; }

  input[type=range] { -webkit-appearance: none; appearance: none; width: 100%; height: 28px;
    background: transparent; margin: 0; cursor: pointer; --c: var(--primary-color); --p: 0%; }
  input[type=range]::-webkit-slider-runnable-track { height: 8px; border-radius: 4px;
    background: linear-gradient(to right, var(--c) var(--p), var(--divider-color, #ccc) var(--p)); }
  input[type=range]::-moz-range-track { height: 8px; border-radius: 4px; background: var(--divider-color, #ccc); }
  input[type=range]::-moz-range-progress { height: 8px; border-radius: 4px; background: var(--c); }
  input[type=range]::-webkit-slider-thumb { -webkit-appearance: none; width: 20px; height: 20px;
    margin-top: -6px; border-radius: 50%; background: var(--c); border: 2px solid var(--card-background-color, #fff);
    box-shadow: 0 1px 3px rgba(0,0,0,.4); }
  input[type=range]::-moz-range-thumb { width: 16px; height: 16px; border-radius: 50%; background: var(--c);
    border: 2px solid var(--card-background-color, #fff); box-shadow: 0 1px 3px rgba(0,0,0,.4); }
  input[type=range].big { height: 36px; }
  input[type=range].big::-webkit-slider-runnable-track { height: 14px; border-radius: 7px; }
  input[type=range].big::-moz-range-track, input[type=range].big::-moz-range-progress { height: 14px; border-radius: 7px; }
  input[type=range].big::-webkit-slider-thumb { width: 24px; height: 24px; margin-top: -5px; }

  .toggle { position: relative; width: 44px; height: 24px; flex: none; cursor: pointer; }
  .toggle input { opacity: 0; width: 0; height: 0; position: absolute; }
  .toggle span { position: absolute; inset: 0; border-radius: 12px; background: var(--divider-color, #bbb);
    transition: background .2s; }
  .toggle span::after { content: ""; position: absolute; left: 3px; top: 3px; width: 18px; height: 18px;
    border-radius: 50%; background: #fff; transition: transform .2s; box-shadow: 0 1px 2px rgba(0,0,0,.3); }
  .toggle input:checked + span { background: var(--primary-color); }
  .toggle input:checked + span::after { transform: translateX(20px); }
  .toggle input:focus-visible + span { outline: 2px solid var(--primary-color); outline-offset: 2px; }

  .chips { display: flex; flex-wrap: wrap; gap: 6px; }
  .chip { flex: 1 1 0; min-width: 0; border: 1px solid var(--divider-color, #ccc); border-radius: 18px;
    background: transparent; color: var(--primary-text-color); font: inherit; font-size: 13px;
    padding: 7px 4px; cursor: pointer; white-space: nowrap; transition: background .15s, color .15s; }
  .chip:hover { background: var(--secondary-background-color); }
  .chip.active { background: var(--primary-color); border-color: var(--primary-color);
    color: var(--text-primary-color, #fff); }
  .chip:focus-visible { outline: 2px solid var(--primary-color); outline-offset: 2px; }

  .modes { display: grid; grid-template-columns: repeat(5, 1fr); gap: 6px; }
  .mode { display: flex; flex-direction: column; align-items: center; gap: 4px; padding: 10px 2px;
    border: 1px solid var(--divider-color, #ccc); border-radius: 12px; background: transparent;
    color: var(--primary-text-color); font: inherit; font-size: 12px; cursor: pointer; min-width: 0; }
  .mode span { max-width: 100%; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .mode:hover { background: var(--secondary-background-color); }
  .mode.active { background: var(--primary-color); border-color: var(--primary-color);
    color: var(--text-primary-color, #fff); }
  .mode:focus-visible { outline: 2px solid var(--primary-color); outline-offset: 2px; }

  .times { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
  .time { display: flex; flex-direction: column; gap: 4px; font-size: 12px; color: var(--secondary-text-color); }
  .time input { font: inherit; font-size: 18px; padding: 8px 10px; border-radius: 8px;
    border: 1px solid var(--divider-color, #ccc); background: var(--secondary-background-color);
    color: var(--primary-text-color); color-scheme: light dark; min-width: 0; }

  .feed { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
  .stepper { display: flex; align-items: center; border: 1px solid var(--divider-color, #ccc); border-radius: 18px; }
  .stepper button { width: 36px; height: 36px; border: none; background: transparent; cursor: pointer;
    color: var(--primary-text-color); font-size: 20px; border-radius: 18px; }
  .stepper button:hover { background: var(--secondary-background-color); }
  .stepper .v { min-width: 64px; text-align: center; font-variant-numeric: tabular-nums; font-size: 14px;
    color: var(--primary-text-color); }
  .feed-btn { flex: 1; display: flex; align-items: center; justify-content: center; gap: 8px; min-width: 120px;
    height: 38px; border-radius: 19px; border: none; cursor: pointer; font: inherit; font-weight: 500;
    background: var(--primary-color); color: var(--text-primary-color, #fff); }
  .feed-btn:hover { filter: brightness(1.08); }
  .feeding { font-size: 13px; color: var(--primary-color); font-weight: 500; }
  .error { color: var(--error-color, #db4437); }
`;

/** Shared plumbing: shadow DOM, hass updates, optimistic values while a command is in flight. */
class WeekAquaBaseCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._pending = new Map(); // key -> {value, until}
    this._dragging = new Set();
  }

  setConfig(config) {
    if (!config || !config.entity) throw new Error("entity is required");
    this._config = config;
    this._built = false;
    if (this._hass) this._render();
  }

  set hass(hass) {
    this._hass = hass;
    this._render();
  }

  getCardSize() {
    return 6;
  }

  getGridOptions() {
    return { columns: 12, min_columns: 6 };
  }

  static getConfigElement() {
    return document.createElement("week-aqua-card-editor");
  }

  _call(domain, service, data) {
    return this._hass.callService(domain, service, data).catch((err) => {
      this._pending.clear();
      this._render();
      const msg = err?.message || String(err);
      this.dispatchEvent(new CustomEvent("hass-notification", {
        detail: { message: msg }, bubbles: true, composed: true,
      }));
    });
  }

  /** Show `value` for `key` until the state catches up (or 5 s pass). */
  _optimistic(key, value) {
    this._pending.set(key, { value, until: Date.now() + 5000 });
  }

  _shown(key, actual, same = (a, b) => a === b) {
    const p = this._pending.get(key);
    if (!p) return actual;
    if (Date.now() > p.until || same(actual, p.value)) {
      this._pending.delete(key);
      return actual;
    }
    return p.value;
  }

  _setRange(el, value) {
    if (!el || this._dragging.has(el)) return;
    el.value = value;
    this._paintRange(el);
  }

  _paintRange(el) {
    const min = +el.min || 0;
    const max = +el.max || 100;
    el.style.setProperty("--p", `${((el.value - min) / (max - min)) * 100}%`);
  }

  _wireRange(el, onInput, onChange) {
    const start = () => this._dragging.add(el);
    const stop = () => this._dragging.delete(el);
    el.addEventListener("pointerdown", start);
    el.addEventListener("pointerup", stop);
    el.addEventListener("pointercancel", stop);
    el.addEventListener("input", () => {
      this._paintRange(el);
      onInput?.(+el.value);
    });
    el.addEventListener("change", () => {
      stop();
      onChange(+el.value);
    });
  }

  _renderMissing(entity) {
    this.shadowRoot.innerHTML = `<style>${STYLE}</style><ha-card><div class="error">${
      esc(tr(this._hass, "not_found", { entity }))}</div></ha-card>`;
    this._built = false;
  }
}

/* ------------------------------------------------------------------ light */

class WeekAquaLightCard extends WeekAquaBaseCard {
  static getStubConfig(hass) {
    const e = Object.values(hass.entities || {}).find(
      (x) => x.platform === DOMAIN && x.entity_id.startsWith("light."),
    );
    return { entity: e?.entity_id || "" };
  }

  getCardSize() {
    return 9;
  }

  _build() {
    const h = this._hass;
    const ch = CHANNELS.map((c) => `
      <div class="row" data-ch="${c.key}">
        <span class="label">${esc(tr(h, c.key))}</span>
        <input type="range" min="0" max="100" step="1" style="--c:${c.color}" aria-label="${esc(tr(h, c.key))}">
        <span class="value"></span>
      </div>`).join("");
    const ramps = RAMPS.map((r) => `<button class="chip" data-ramp="${r}">${
      r === "0" ? esc(tr(h, "ramp_off")) : `${r} ${esc(tr(h, "min"))}`}</button>`).join("");
    this.shadowRoot.innerHTML = `<style>${STYLE}</style>
      <ha-card>
        <div class="header">
          <div class="badge"><ha-icon icon="mdi:lightbulb"></ha-icon></div>
          <div class="titles"><div class="name"></div><div class="state"></div></div>
          <label class="toggle"><input type="checkbox" class="power" aria-label="${esc(tr(h, "on"))}"><span></span></label>
        </div>
        <div class="section main">
          <div class="row master">
            <span class="label">${esc(tr(h, "brightness"))}</span>
            <input type="range" class="big" min="1" max="100" step="1" aria-label="${esc(tr(h, "brightness"))}">
            <span class="value"></span>
          </div>
        </div>
        <div class="section channels">
          <div class="section-title">${esc(tr(h, "channels"))}</div>
          ${ch}
          <div class="note limit" hidden></div>
        </div>
        <div class="section schedule">
          <div class="section-title">
            <span>${esc(tr(h, "schedule"))}</span>
            <label class="toggle"><input type="checkbox" class="sched" aria-label="${esc(tr(h, "schedule"))}"><span></span></label>
          </div>
          <div class="hint">${esc(tr(h, "schedule_hint"))}</div>
          <div class="sched-body">
            <div class="times">
              <label class="time">${esc(tr(h, "on_time"))}<input type="time" class="t-on"></label>
              <label class="time">${esc(tr(h, "off_time"))} (${esc(tr(h, "midnight"))})<input type="time" class="t-off"></label>
            </div>
            <div class="section" style="margin-top:12px">
              <div class="section-title">${esc(tr(h, "ramp"))}</div>
              <div class="chips ramps">${ramps}</div>
            </div>
          </div>
        </div>
      </ha-card>`;

    const $ = (s) => this.shadowRoot.querySelector(s);
    this._el = {
      card: $("ha-card"), badge: $(".badge"), name: $(".name"), state: $(".state"), power: $(".power"),
      master: $(".master input"), masterValue: $(".master .value"), limit: $(".limit"),
      sched: $(".sched"), schedBody: $(".sched-body"), tOn: $(".t-on"), tOff: $(".t-off"),
      body: [$(".main"), $(".channels"), $(".schedule")],
      ch: Object.fromEntries(CHANNELS.map((c) => {
        const row = $(`[data-ch="${c.key}"]`);
        return [c.key, { input: row.querySelector("input"), value: row.querySelector(".value") }];
      })),
      ramps: [...this.shadowRoot.querySelectorAll("[data-ramp]")],
    };

    this._el.power.addEventListener("change", (ev) => {
      const on = ev.target.checked;
      this._optimistic("on", on);
      this._call("light", on ? "turn_on" : "turn_off", { entity_id: this._config.entity });
    });

    this._wireRange(this._el.master,
      (v) => this._previewMaster(v),
      (v) => {
        this._optimistic("master", v);
        const peak = Math.max(...CHANNELS.map((c) => this._requested(c.key)), 0);
        for (const c of CHANNELS) {
          const r = this._requested(c.key);
          this._optimistic(`ch_${c.key}`, peak > 0 ? Math.round((r * v) / peak) : v);
        }
        this._optimistic("on", true);
        this._call("light", "turn_on", { entity_id: this._config.entity, brightness_pct: v });
      });

    for (const c of CHANNELS) {
      const { input, value } = this._el.ch[c.key];
      this._wireRange(input,
        (v) => { value.textContent = `${v}%`; },
        (v) => {
          const id = this._ents[`channel_${c.key}`];
          if (!id) return;
          this._optimistic(`ch_${c.key}`, v);
          this._call("number", "set_value", { entity_id: id, value: v });
        });
    }

    this._el.sched.addEventListener("change", (ev) => {
      const id = this._ents.schedule;
      if (!id) return;
      this._optimistic("sched", ev.target.checked);
      this._call("switch", ev.target.checked ? "turn_on" : "turn_off", { entity_id: id });
    });

    for (const [el, key] of [[this._el.tOn, "schedule_on_time"], [this._el.tOff, "schedule_off_time"]]) {
      el.addEventListener("change", () => {
        const id = this._ents[key];
        if (!id || !el.value) return;
        this._optimistic(key, el.value);
        this._call("time", "set_value", { entity_id: id, time: `${el.value}:00` });
      });
    }

    for (const btn of this._el.ramps) {
      btn.addEventListener("click", () => {
        const id = this._ents.schedule_ramp;
        if (!id) return;
        this._optimistic("ramp", btn.dataset.ramp);
        this._call("select", "select_option", { entity_id: id, option: btn.dataset.ramp });
        this._render();
      });
    }
    this._built = true;
  }

  _requested(key) {
    const id = this._ents?.[`channel_${key}`];
    const actual = num(this._hass.states[id]);
    return this._shown(`ch_${key}`, actual, (a, b) => Math.abs(a - b) < 1.01);
  }

  /** While dragging the master slider, preview the scaled channels. */
  _previewMaster(v) {
    this._el.masterValue.textContent = `${v}%`;
    const peak = Math.max(...CHANNELS.map((c) => this._requested(c.key)), 0);
    for (const c of CHANNELS) {
      const r = this._requested(c.key);
      const scaled = peak > 0 ? Math.round((r * v) / peak) : v;
      const { input, value } = this._el.ch[c.key];
      input.value = scaled;
      this._paintRange(input);
      value.textContent = `${scaled}%`;
    }
  }

  _render() {
    const hass = this._hass;
    if (!hass || !this._config) return;
    const entity = this._config.entity;
    const st = hass.states[entity];
    if (!st) return this._renderMissing(entity);
    if (!this._built) this._build();
    this._ents = deviceEntities(hass, entity);
    const e = this._el;
    const unavailable = isUnavailable(st);
    const isOn = this._shown("on", st.state === "on");

    const requested = Object.fromEntries(CHANNELS.map((c) => [c.key, this._requested(c.key)]));
    const peak = Math.max(...Object.values(requested));
    const master = this._dragging.has(e.master) ? +e.master.value : Math.max(1, Math.round(peak));

    e.name.textContent = this._config.name || st.attributes.friendly_name || entity;
    e.state.textContent = unavailable ? tr(hass, "unavailable")
      : isOn ? `${tr(hass, "on")} · ${master}%` : tr(hass, "off");
    e.power.checked = isOn;
    e.power.disabled = unavailable;
    for (const b of e.body) b.classList.toggle("disabled", unavailable);

    // Badge shows the current mix (UV adds violet).
    if (isOn && peak > 0) {
      const k = (v) => v / peak;
      const r = Math.round(255 * Math.min(1, k(requested.red) + 0.45 * k(requested.uv)));
      const g = Math.round(255 * Math.min(1, k(requested.green)));
      const b = Math.round(255 * Math.min(1, k(requested.blue) + 0.8 * k(requested.uv)));
      e.badge.style.background = `rgba(${r}, ${g}, ${b}, 0.25)`;
      e.badge.style.color = `rgb(${r}, ${g}, ${b})`;
    } else {
      e.badge.style.background = "";
      e.badge.style.color = "";
    }

    this._setRange(e.master, master);
    if (!this._dragging.has(e.master)) e.masterValue.textContent = `${master}%`;
    const peakColor = `rgb(${CHANNELS.map((c) => c.key).slice(0, 3)
      .map((k) => Math.round(255 * (peak > 0 ? requested[k] / peak : 1))).join(",")})`;
    e.master.style.setProperty("--c", peak > 0 ? peakColor : "var(--primary-color)");
    e.main = e.master.closest(".section");
    e.main.classList.toggle("dim", !isOn);

    if (!this._dragging.has(e.master)) {
      for (const c of CHANNELS) {
        const { input, value } = e.ch[c.key];
        this._setRange(input, Math.round(requested[c.key]));
        if (!this._dragging.has(input)) value.textContent = `${Math.round(requested[c.key])}%`;
      }
    }

    // Actual output after the lamp's power budget (light attributes).
    const outPeak = Math.max(...CHANNELS.map((c) => +st.attributes[c.key] || 0));
    if (isOn && peak > 0 && outPeak > 0 && outPeak < peak - 0.6) {
      e.limit.hidden = false;
      e.limit.textContent = tr(hass, "power_limited", { pct: Math.round((outPeak / peak) * 100) });
    } else {
      e.limit.hidden = true;
    }

    const schedOn = this._shown("sched", hass.states[this._ents.schedule]?.state === "on");
    e.sched.checked = schedOn;
    e.sched.disabled = !this._ents.schedule;
    e.schedBody.classList.toggle("dim", !schedOn);
    for (const [el, key] of [[e.tOn, "schedule_on_time"], [e.tOff, "schedule_off_time"]]) {
      const v = (hass.states[this._ents[key]]?.state || "").slice(0, 5);
      if (this.shadowRoot.activeElement !== el) el.value = this._shown(key, v);
    }
    const ramp = this._shown("ramp", hass.states[this._ents.schedule_ramp]?.state);
    for (const b of e.ramps) b.classList.toggle("active", b.dataset.ramp === ramp);
  }
}

/* ------------------------------------------------------------------- pump */

class WeekAquaPumpCard extends WeekAquaBaseCard {
  static getStubConfig(hass) {
    const e = Object.values(hass.entities || {}).find(
      (x) => x.platform === DOMAIN && x.entity_id.startsWith("fan."),
    );
    return { entity: e?.entity_id || "" };
  }

  connectedCallback() {
    this._timer = setInterval(() => this._feedTick(), 1000);
  }

  disconnectedCallback() {
    clearInterval(this._timer);
  }

  _build() {
    const h = this._hass;
    const modes = PUMP_MODES.map((m) => `
      <button class="mode" data-mode="${m.key}" title="${esc(tr(h, m.key))}">
        <ha-icon icon="${m.icon}"></ha-icon><span>${esc(tr(h, m.key))}</span>
      </button>`).join("");
    this.shadowRoot.innerHTML = `<style>${STYLE}</style>
      <ha-card>
        <div class="header">
          <div class="badge"><ha-icon icon="mdi:pump"></ha-icon></div>
          <div class="titles"><div class="name"></div><div class="state"></div></div>
          <label class="toggle"><input type="checkbox" class="power" aria-label="${esc(tr(h, "on"))}"><span></span></label>
        </div>
        <div class="section flow">
          <div class="row strength">
            <span class="label">${esc(tr(h, "strength"))}</span>
            <input type="range" class="big" min="1" max="100" step="1" aria-label="${esc(tr(h, "strength"))}">
            <span class="value"></span>
          </div>
          <div class="section-title">${esc(tr(h, "mode"))}</div>
          <div class="modes">${modes}</div>
        </div>
        <div class="section feed-section">
          <div class="section-title">${esc(tr(h, "feed_pause"))}</div>
          <div class="feed">
            <div class="stepper">
              <button class="minus" aria-label="-5 ${esc(tr(h, "min"))}">−</button>
              <span class="v"></span>
              <button class="plus" aria-label="+5 ${esc(tr(h, "min"))}">+</button>
            </div>
            <button class="feed-btn"><ha-icon icon="mdi:fish"></ha-icon>${esc(tr(h, "feed"))}</button>
          </div>
          <div class="feeding" hidden></div>
        </div>
      </ha-card>`;

    const $ = (s) => this.shadowRoot.querySelector(s);
    this._el = {
      badge: $(".badge"), name: $(".name"), state: $(".state"), power: $(".power"),
      strength: $(".strength input"), strengthValue: $(".strength .value"),
      modes: [...this.shadowRoot.querySelectorAll("[data-mode]")],
      minus: $(".minus"), plus: $(".plus"), duration: $(".stepper .v"), feedBtn: $(".feed-btn"),
      feeding: $(".feeding"), flow: $(".flow"), feedSection: $(".feed-section"),
    };

    this._el.power.addEventListener("change", (ev) => {
      const on = ev.target.checked;
      this._optimistic("on", on);
      this._call("fan", on ? "turn_on" : "turn_off", { entity_id: this._config.entity });
    });

    this._wireRange(this._el.strength,
      (v) => { this._el.strengthValue.textContent = `${v}%`; },
      (v) => {
        this._optimistic("pct", v);
        this._optimistic("on", true);
        this._call("fan", "set_percentage", { entity_id: this._config.entity, percentage: v });
      });

    for (const btn of this._el.modes) {
      btn.addEventListener("click", () => {
        this._optimistic("mode", btn.dataset.mode);
        this._optimistic("on", true);
        this._call("fan", "set_preset_mode", { entity_id: this._config.entity, preset_mode: btn.dataset.mode });
        this._render();
      });
    }

    const step = (delta) => {
      const id = this._ents.feed_duration;
      if (!id) return;
      const st = this._hass.states[id];
      const min = +st?.attributes?.min || 5;
      const max = +st?.attributes?.max || 60;
      const v = Math.min(max, Math.max(min, this._duration() + delta));
      this._optimistic("duration", v);
      this._call("number", "set_value", { entity_id: id, value: v });
      this._render();
    };
    this._el.minus.addEventListener("click", () => step(-5));
    this._el.plus.addEventListener("click", () => step(5));

    this._el.feedBtn.addEventListener("click", () => {
      const id = this._ents.feed;
      if (!id) return;
      this._feedStarted = { at: Date.now(), minutes: this._duration() };
      this._call("button", "press", { entity_id: id });
      this._render();
    });
    this._built = true;
  }

  _duration() {
    const id = this._ents?.feed_duration;
    return Math.round(this._shown("duration", num(this._hass.states[id], 10)));
  }

  /** End of the current feed pause (ms), from the button's last-pressed time. */
  _feedEnd() {
    const id = this._ents?.feed;
    const pressed = Date.parse(this._hass.states[id]?.state);
    let start = Number.isFinite(pressed) ? pressed : 0;
    let minutes = this._duration();
    if (this._feedStarted && this._feedStarted.at > start) {
      ({ at: start, minutes } = this._feedStarted);
    }
    return start ? start + minutes * 60000 : 0;
  }

  _feedTick() {
    if (!this._built || !this._hass) return;
    const left = this._feedEnd() - Date.now();
    const e = this._el;
    if (left > 0) {
      const m = Math.floor(left / 60000);
      const s = Math.floor((left % 60000) / 1000);
      e.feeding.hidden = false;
      e.feeding.textContent = tr(this._hass, "feeding", { time: `${m}:${String(s).padStart(2, "0")}` });
      e.flow.classList.add("dim");
    } else if (!e.feeding.hidden) {
      e.feeding.hidden = true;
      e.flow.classList.remove("dim");
    }
  }

  _render() {
    const hass = this._hass;
    if (!hass || !this._config) return;
    const entity = this._config.entity;
    const st = hass.states[entity];
    if (!st) return this._renderMissing(entity);
    if (!this._built) this._build();
    this._ents = deviceEntities(hass, entity);
    const e = this._el;
    const unavailable = isUnavailable(st);
    const isOn = this._shown("on", st.state === "on");
    const pct = Math.round(this._shown("pct", +st.attributes.percentage || 0, (a, b) => Math.abs(a - b) < 1.01));
    const mode = this._shown("mode", st.attributes.preset_mode || "constant");

    e.name.textContent = this._config.name || st.attributes.friendly_name || entity;
    e.state.textContent = unavailable ? tr(hass, "unavailable")
      : isOn ? `${tr(hass, "on")} · ${tr(hass, mode)} · ${pct}%` : tr(hass, "off");
    e.power.checked = isOn;
    e.power.disabled = unavailable;
    e.flow.classList.toggle("disabled", unavailable);
    e.feedSection.classList.toggle("disabled", unavailable);
    e.badge.style.background = isOn ? "rgba(var(--rgb-primary-color, 3, 169, 244), 0.2)" : "";
    e.badge.style.color = isOn ? "var(--primary-color)" : "";

    this._setRange(e.strength, isOn ? Math.max(1, pct) : 1);
    if (!this._dragging.has(e.strength)) e.strengthValue.textContent = isOn ? `${pct}%` : "–";
    for (const b of e.modes) b.classList.toggle("active", isOn && b.dataset.mode === mode);
    e.duration.textContent = `${this._duration()} ${tr(hass, "min")}`;
    this._feedTick();
  }
}

/* ----------------------------------------------------------------- editor */

class WeekAquaCardEditor extends HTMLElement {
  setConfig(config) {
    this._config = config;
    this._render();
  }

  set hass(hass) {
    this._hass = hass;
    this._render();
  }

  _render() {
    if (!this._hass || !this._config) return;
    if (!this._form) {
      this._form = document.createElement("ha-form");
      this._form.computeLabel = (s) => (s.name === "entity" ? "Entity" : "Name");
      this._form.addEventListener("value-changed", (ev) => {
        this._config = { ...this._config, ...ev.detail.value };
        this.dispatchEvent(new CustomEvent("config-changed", {
          detail: { config: this._config }, bubbles: true, composed: true,
        }));
      });
      this.appendChild(this._form);
    }
    this._form.hass = this._hass;
    this._form.data = this._config;
    this._form.schema = [
      { name: "entity", required: true,
        selector: { entity: { filter: { integration: DOMAIN, domain: ["light", "fan"] } } } },
      { name: "name", selector: { text: {} } },
    ];
  }
}

const define = (tag, cls) => {
  if (!customElements.get(tag)) customElements.define(tag, cls);
};
define("week-aqua-light-card", WeekAquaLightCard);
define("week-aqua-pump-card", WeekAquaPumpCard);
define("week-aqua-card-editor", WeekAquaCardEditor);

window.customCards = window.customCards || [];
for (const [type, name, description] of [
  ["week-aqua-light-card", "light_card", "light_card_desc"],
  ["week-aqua-pump-card", "pump_card", "pump_card_desc"],
]) {
  if (!window.customCards.some((c) => c.type === type)) {
    window.customCards.push({
      type,
      name: STRINGS[LANG()][name],
      description: STRINGS[LANG()][description],
      preview: true,
      documentationURL: "https://github.com/novamill/ha-week-aqua#dashboard-cards",
    });
  }
}
