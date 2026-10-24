/* Savannah Clinic — booking app
   Vanilla ES module. Hash routing, no build step, served by GitHub Pages and by
   nginx at clinic.dabotap.com. */

const API = /(^|\.)github\.io$/.test(location.hostname) ? "https://clinic.dabotap.com" : "";
const TZ = "Africa/Nairobi";

const $ = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));
const main = $("#main");

/* ------------------------------------------------------------------ utils */

const esc = (value) =>
  String(value ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

const timeFmt = new Intl.DateTimeFormat("en-GB", { hour: "2-digit", minute: "2-digit", timeZone: TZ, hour12: false });
const dayFmt = new Intl.DateTimeFormat("en-GB", { weekday: "short", timeZone: TZ });
const longFmt = new Intl.DateTimeFormat("en-GB", { weekday: "long", day: "numeric", month: "long", timeZone: TZ });
const monthFmt = new Intl.DateTimeFormat("en-GB", { month: "short", timeZone: TZ });
const domFmt = new Intl.DateTimeFormat("en-GB", { day: "numeric", timeZone: TZ });
const keyFmt = new Intl.DateTimeFormat("en-CA", { year: "numeric", month: "2-digit", day: "2-digit", timeZone: TZ });

const clock = (iso) => timeFmt.format(new Date(iso));
const weekday = (iso) => dayFmt.format(new Date(iso));
const longDate = (iso) => longFmt.format(new Date(iso));
const monthOf = (iso) => monthFmt.format(new Date(iso));
const dayOf = (iso) => domFmt.format(new Date(iso));
const dateKey = (iso) => keyFmt.format(new Date(iso));
const hourOf = (iso) => Number(clock(iso).slice(0, 2));

const initials = (name) =>
  name.replace(/^Dr\.?\s+/i, "").split(/\s+/).slice(0, 2).map((part) => part[0]?.toUpperCase() || "").join("");

const hueFor = (text) => [...text].reduce((acc, ch) => (acc * 31 + ch.charCodeAt(0)) % 360, 7);
const avatarStyle = (name) => {
  const hue = hueFor(name);
  return `background: linear-gradient(145deg, hsl(${hue} 46% 42%), hsl(${(hue + 28) % 360} 52% 30%))`;
};

function relativeDay(iso) {
  const today = dateKey(new Date().toISOString());
  const target = dateKey(iso);
  if (target === today) return "today";
  const diff = (new Date(target) - new Date(today)) / 86400000;
  if (diff === 1) return "tomorrow";
  return `${weekday(iso)} ${dayOf(iso)} ${monthOf(iso)}`;
}

/* --------------------------------------------------------------- storage */

function getPatient() {
  try {
    return JSON.parse(localStorage.getItem("clinic.patient") || "null");
  } catch {
    return null;
  }
}

function setPatient(patient) {
  if (patient) localStorage.setItem("clinic.patient", JSON.stringify(patient));
  else localStorage.removeItem("clinic.patient");
}

/* ------------------------------------------------------------------ api */

async function api(path, { method = "GET", body } = {}) {
  const res = await fetch(API + path, {
    method,
    headers: body ? { "content-type": "application/json" } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  });
  let data = null;
  try {
    data = await res.json();
  } catch {
    /* empty body */
  }
  if (!res.ok) {
    const error = new Error(data?.error?.message || `Request failed (${res.status})`);
    error.status = res.status;
    error.code = data?.error?.code;
    error.details = data?.error?.details;
    throw error;
  }
  return data;
}

/* --------------------------------------------------------------- toasts */

function toast(message, kind = "ok") {
  const node = document.createElement("div");
  node.className = `toast ${kind}`;
  node.innerHTML = `<div>${esc(message)}</div>`;
  $("#toasts").append(node);
  setTimeout(() => node.remove(), 4500);
}

/* --------------------------------------------------------------- modal */

function openModal({ title, body, footer = "", onMount }) {
  const backdrop = document.createElement("div");
  backdrop.className = "modal-backdrop";
  backdrop.innerHTML = `
    <div class="modal" role="dialog" aria-modal="true" aria-labelledby="modal-title">
      <div class="modal-head">
        <h3 id="modal-title">${esc(title)}</h3>
        <span class="spacer"></span>
        <button class="icon-btn" type="button" data-close aria-label="Close dialog">✕</button>
      </div>
      <div class="modal-body">${body}</div>
      ${footer ? `<div class="modal-foot">${footer}</div>` : ""}
    </div>`;
  document.body.append(backdrop);

  const previous = document.activeElement;
  const close = () => {
    backdrop.remove();
    document.removeEventListener("keydown", onKey);
    previous?.focus?.();
  };
  const onKey = (event) => {
    if (event.key === "Escape") close();
    if (event.key === "Tab") {
      const focusable = $$('button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])', backdrop).filter(
        (node) => !node.disabled && node.offsetParent !== null,
      );
      if (!focusable.length) return;
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    }
  };
  document.addEventListener("keydown", onKey);
  backdrop.addEventListener("click", (event) => {
    if (event.target === backdrop) close();
  });
  backdrop.querySelector("[data-close]").addEventListener("click", close);
  setTimeout(() => backdrop.querySelector("input, select, textarea, button")?.focus(), 40);

  if (onMount) onMount(backdrop, close);
  return { root: backdrop, close };
}

/* ---------------------------------------------------------------- doctors */

const doctorCache = new Map();

async function getDoctors() {
  if (!doctorCache.size) {
    for (const doctor of await api("/doctors")) doctorCache.set(doctor.id, doctor);
  }
  return [...doctorCache.values()];
}

async function getDoctor(id) {
  if (doctorCache.has(id)) return doctorCache.get(id);
  const doctor = await api(`/doctors/${id}`);
  doctorCache.set(id, doctor);
  return doctor;
}

/* -------------------------------------------------------------- calendar */

async function availabilitySummary(doctorId, { days = 21, from } = {}) {
  const query = new URLSearchParams({ days });
  if (from) query.set("from", from);
  return api(`/doctors/${doctorId}/availability/summary?${query}`);
}

async function availabilityFor(doctorId, date) {
  return api(`/doctors/${doctorId}/availability?date=${encodeURIComponent(date)}`);
}

/* ------------------------------------------------------------- fragments */

const doctorAvatar = (doctor, large = false) =>
  `<span class="avatar ${large ? "avatar-lg" : ""}" style="${avatarStyle(doctor.name)}" aria-hidden="true">${esc(initials(doctor.name))}</span>`;

const statusChip = (appointment) => {
  if (appointment.status === "cancelled") return `<span class="chip chip-danger"><span class="chip-dot"></span>Cancelled</span>`;
  if (appointment.status === "completed") return `<span class="chip">Completed</span>`;
  return `<span class="chip chip-accent"><span class="chip-dot"></span>Confirmed</span>`;
};

const emptyState = (title, copy, action = "") => `
  <div class="empty">
    <svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" aria-hidden="true">
      <rect x="3" y="4.5" width="18" height="16" rx="3"/><path d="M8 3v3M16 3v3M3 9.5h18M9 14h6"/>
    </svg>
    <h3>${esc(title)}</h3>
    <p>${esc(copy)}</p>
    ${action}
  </div>`;

const skeletonDoctors = () =>
  Array.from({ length: 4 })
    .map(() => `<div class="card doctor-card"><div class="row"><div class="skeleton" style="width:44px;height:44px;border-radius:50%"></div><div style="flex:1"><div class="skeleton" style="height:14px;width:60%"></div><div class="skeleton" style="height:11px;width:40%;margin-top:8px"></div></div></div><div class="skeleton" style="height:12px;width:90%"></div><div class="skeleton" style="height:12px;width:70%"></div></div>`)
    .join("");

/* ----------------------------------------------------------------- views */

async function home() {
  main.innerHTML = `
    <section class="hero">
      <div class="wrap hero-grid">
        <div>
          <span class="eyebrow">Same-week appointments</span>
          <h1>See a doctor<br>without the <em>waiting room</em>.</h1>
          <p class="lede">Five doctors, 30-minute appointments, and a calendar that only shows slots that are actually free. Book in under a minute — no account needed.</p>
          <div class="row" style="margin-top:26px">
            <button class="btn btn-primary" id="cta-doctors" type="button">Book an appointment</button>
            <a class="btn btn-ghost" href="#/appointments">Manage a booking</a>
          </div>
          <div class="row small muted" style="margin-top:22px;gap:18px">
            <span>Real-time availability</span>
            <span>·</span>
            <span>Free cancellation</span>
            <span>·</span>
            <span>Instant confirmation</span>
          </div>
        </div>
        <div class="card hero-panel" id="next-panel">
          <div style="padding:14px">
            ${Array.from({ length: 4 }).map(() => `<div class="row" style="padding:10px 0"><div class="skeleton" style="width:38px;height:38px;border-radius:50%"></div><div style="flex:1"><div class="skeleton" style="height:12px;width:50%"></div><div class="skeleton" style="height:10px;width:35%;margin-top:7px"></div></div><div class="skeleton" style="height:12px;width:56px"></div></div>`).join("")}
          </div>
        </div>
      </div>
    </section>

    <section class="section" id="doctors-section">
      <div class="wrap">
        <div class="section-head">
          <div>
            <h2>Our doctors</h2>
            <p class="small">Every doctor keeps their own hours. Pick someone and see the slots that are genuinely free.</p>
          </div>
        </div>
        <div class="doctor-grid" id="doctor-grid">${skeletonDoctors()}</div>
      </div>
    </section>

    <section class="section">
      <div class="wrap">
        <h2>Three steps, one minute</h2>
        <div class="steps" style="margin-top:22px">
          <div class="card step"><div class="num">1</div><h3>Pick a doctor and a time</h3><p class="small muted" style="margin-top:6px">Only free slots are shown — the ones already taken never appear.</p></div>
          <div class="card step"><div class="num">2</div><h3>Tell us who you are</h3><p class="small muted" style="margin-top:6px">Name, email and phone. Add a note for the doctor if it helps.</p></div>
          <div class="card step"><div class="num">3</div><h3>Get a reference</h3><p class="small muted" style="margin-top:6px">Your appointment is confirmed instantly. Cancel or move it yourself at any time.</p></div>
        </div>
      </div>
    </section>`;

  $("#cta-doctors").addEventListener("click", () => startBooking());

  try {
    const [doctors, next] = await Promise.all([getDoctors(), api("/doctors/next-available")]);
    renderNextPanel(next);
    renderDoctorGrid(doctors, next);
  } catch (error) {
    $("#next-panel").innerHTML = `<div class="error-box">Could not load availability. ${esc(error.message)}</div>`;
    $("#doctor-grid").innerHTML = `<div class="error-box">Could not load doctors. ${esc(error.message)}</div>`;
  }
}

async function startBooking(button) {
  const cta = button || $("#cta-doctors");
  const original = cta ? cta.textContent : "";
  if (cta) {
    cta.disabled = true;
    cta.textContent = "Finding the soonest time…";
  }
  try {
    const rows = await api("/doctors/next-available");
    const soonest = rows
      .filter((row) => row.next_slot)
      .sort((a, b) => new Date(a.next_slot) - new Date(b.next_slot));
    const target = soonest[0]?.doctor || rows[0]?.doctor;
    if (!target) {
      toast("No doctor is available right now — please call the clinic.", "err");
      return;
    }
    location.hash = `#/book/${target.id}`;
  } catch (error) {
    toast(error.message, "err");
  } finally {
    if (cta) {
      cta.disabled = false;
      cta.textContent = original;
    }
  }
}

function renderNextPanel(rows) {
  const available = rows.filter((row) => row.next_slot);
  if (!available.length) {
    $("#next-panel").innerHTML = `<div style="padding:18px" class="small muted">Fully booked for the next two weeks — call the clinic.</div>`;
    return;
  }
  $("#next-panel").innerHTML = `
    <div style="padding:10px 8px 4px 16px" class="tiny">Next available</div>
    <div class="next-list">
      ${available
        .slice(0, 5)
        .map(
          (row) => `
        <a class="next-item" href="#/book/${row.doctor.id}">
          <span class="avatar" style="${avatarStyle(row.doctor.name)}" aria-hidden="true">${esc(initials(row.doctor.name))}</span>
          <span class="who"><b>${esc(row.doctor.name)}</b><span>${esc(row.doctor.specialty)}</span></span>
          <span class="when">${clock(row.next_slot)}<span>${esc(relativeDay(row.next_slot))}</span></span>
        </a>`,
        )
        .join("")}
    </div>`;
}

function renderDoctorGrid(doctors, nextRows) {
  const byId = new Map(nextRows.map((row) => [row.doctor.id, row.next_slot]));
  $("#doctor-grid").innerHTML = doctors
    .map((doctor) => {
      const next = byId.get(doctor.id);
      return `
      <article class="card doctor-card">
        <div class="head">
          ${doctorAvatar(doctor)}
          <div style="min-width:0">
            <h3>${esc(doctor.name)}</h3>
            <div class="spec">${esc(doctor.specialty)}</div>
          </div>
        </div>
        <p class="bio">${esc(doctor.bio || "Available for 30-minute consultations.")}</p>
        <div class="foot">
          ${next
            ? `<span class="chip chip-ok"><span class="chip-dot"></span>Next ${esc(clock(next))} · ${esc(relativeDay(next))}</span>`
            : `<span class="chip chip-warn">Fully booked</span>`}
          <span class="spacer"></span>
          <a class="btn btn-sm btn-primary" href="#/book/${doctor.id}">Book</a>
        </div>
      </article>`;
    })
    .join("");
}

/* ------------------------------------------------------------ book a slot */

async function book(doctorId) {
  let doctor;
  try {
    [doctor] = await Promise.all([getDoctor(doctorId)]);
  } catch {
    return fatal(new Error("That doctor could not be found."));
  }

  const view = { doctor, days: [], date: null, slot: null, slots: [] };

  main.innerHTML = `
    <div class="wrap book-grid">
      <aside class="card summary-card" id="summary"></aside>
      <div>
        <section class="card panel">
          <div class="panel-head"><span class="num active">1</span><h2>Choose a time</h2></div>
          <div class="date-strip" id="dates" aria-label="Choose a date"></div>
          <div id="slots"><div class="skeleton" style="height:74px"></div></div>
        </section>

        <section class="card panel">
          <div class="panel-head"><span class="num">2</span><h2>Your details</h2></div>
          <form id="details" class="form-grid" novalidate>
            <div class="field"><label for="name">Full name</label><input id="name" name="name" autocomplete="name" required placeholder="Jane Wanjiku"></div>
            <div class="field"><label for="email">Email</label><input id="email" name="email" type="email" autocomplete="email" required placeholder="jane@example.com">
              <span class="hint">We use this to look up your bookings.</span></div>
            <div class="field"><label for="phone">Phone</label><input id="phone" name="phone" type="tel" autocomplete="tel" placeholder="+254 712 345 678">
              <span class="hint">Optional, for reminders.</span></div>
            <div class="field full"><label for="notes">Anything the doctor should know?</label>
              <textarea id="notes" name="notes" maxlength="500" placeholder="Optional — e.g. follow-up, symptoms, or a note about a child"></textarea></div>
          </form>
        </section>
      </div>
    </div>`;

  const stored = getPatient();
  if (stored) {
    $("#name").value = stored.name || "";
    $("#email").value = stored.email || "";
    $("#phone").value = stored.phone || "";
  }

  renderBookingSummary(view);

  try {
    const summary = await availabilitySummary(doctorId, { days: 21 });
    view.days = summary.days;
    const firstOpen = summary.days.find((day) => day.free_slots > 0);
    view.date = firstOpen?.date || summary.days[0]?.date || null;
    renderDates(view);
    if (view.date) await loadSlots(view);
  } catch (error) {
    $("#slots").innerHTML = `<div class="error-box">Could not load availability: ${esc(error.message)}</div>`;
  }

  $("#details").addEventListener("input", () => {
    renderBookingSummary(view);
  });
}

function renderDates(view) {
  const strip = $("#dates");
  strip.innerHTML = view.days
    .slice(0, 14)
    .map((day) => {
      const target = new Date(day.date + "T12:00:00+03:00").toISOString();
      return `
        <button class="date-chip" type="button" data-date="${day.date}" aria-pressed="${day.date === view.date}" ${day.free_slots === 0 ? "disabled" : ""}>
          <span class="dow">${esc(weekday(target))}</span>
          <span class="dom">${esc(dayOf(target))}</span>
          <span class="free">${day.free_slots === 0 ? "full" : `${day.free_slots} free`}</span>
        </button>`;
    })
    .join("");

  strip.querySelectorAll("[data-date]").forEach((button) => {
    button.addEventListener("click", async () => {
      view.date = button.dataset.date;
      renderDates(view);
      await loadSlots(view);
    });
  });
}

async function loadSlots(view) {
  const container = $("#slots");
  container.innerHTML = `<div class="slot-grid">${Array.from({ length: 8 }).map(() => `<div class="skeleton" style="height:40px"></div>`).join("")}</div>`;
  try {
    const data = await availabilityFor(view.doctor.id, view.date);
    view.slots = data.slots;
    if (!data.slots.length) {
      container.innerHTML = emptyState("No free slots that day", "Every slot is either booked or inside the one-hour booking window. Try another date.");
      return;
    }
    const groups = [
      ["Morning", data.slots.filter((slot) => hourOf(slot.starts_at) < 12)],
      ["Afternoon", data.slots.filter((slot) => hourOf(slot.starts_at) >= 12 && hourOf(slot.starts_at) < 17)],
      ["Evening", data.slots.filter((slot) => hourOf(slot.starts_at) >= 17)],
    ].filter(([, slots]) => slots.length);

    container.innerHTML = groups
      .map(
        ([label, slots]) => `
        <div class="slot-group">
          <h4>${label} · ${slots.length} slot${slots.length === 1 ? "" : "s"}</h4>
          <div class="slot-grid">
            ${slots
              .map(
                (slot) => `<button class="slot" type="button" data-start="${slot.starts_at}" aria-pressed="${view.slot?.starts_at === slot.starts_at}">${esc(clock(slot.starts_at))}</button>`,
              )
              .join("")}
          </div>
        </div>`,
      )
      .join("");

    container.querySelectorAll("[data-start]").forEach((button) => {
      button.addEventListener("click", () => {
        view.slot = data.slots.find((slot) => slot.starts_at === button.dataset.start);
        container.querySelectorAll("[data-start]").forEach((node) => node.setAttribute("aria-pressed", String(node === button)));
        renderBookingSummary(view);
      });
    });
  } catch (error) {
    container.innerHTML = `<div class="error-box">Could not load slots: ${esc(error.message)}</div>`;
  }
}

function renderBookingSummary(view) {
  const slot = view.slot;
  const patient = {
    name: $("#name")?.value.trim() || "",
    email: $("#email")?.value.trim() || "",
    phone: $("#phone")?.value.trim() || "",
  };
  const ready = slot && patient.name.length >= 2 && /^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(patient.email);

  $("#summary").innerHTML = `
    <div class="doc-head">
      ${doctorAvatar(view.doctor, true)}
      <div style="min-width:0"><h3>${esc(view.doctor.name)}</h3><div class="spec small" style="color:var(--accent);font-weight:600">${esc(view.doctor.specialty)}</div></div>
      <button class="btn btn-sm btn-ghost" id="change-doctor" type="button" style="margin-left:auto">Change</button>
    </div>
    <dl class="summary-lines">
      <div class="summary-line"><dt>Date</dt><dd>${slot ? esc(longDate(slot.starts_at)) : "—"}</dd></div>
      <div class="summary-line"><dt>Time</dt><dd>${slot ? `${esc(clock(slot.starts_at))} – ${esc(clock(slot.ends_at))}` : "—"}</dd></div>
      <div class="summary-line"><dt>Length</dt><dd>30 minutes</dd></div>
      <div class="summary-line"><dt>Where</dt><dd>One Padmore Place</dd></div>
    </dl>
    <button class="btn btn-primary btn-block" id="confirm" type="button" ${ready ? "" : "disabled"}>
      ${slot ? "Confirm booking" : "Choose a time first"}
    </button>
    <p class="tiny" style="margin-top:12px;text-align:center;text-transform:none;letter-spacing:0;font-weight:500">
      Free cancellation up to the appointment time.
    </p>`;

  $("#confirm")?.addEventListener("click", () => submitBooking(view, patient));
  $("#change-doctor")?.addEventListener("click", () => openDoctorPicker(view.doctor.id));
}

async function submitBooking(view, patient) {
  const button = $("#confirm");
  button.disabled = true;
  button.textContent = "Booking…";
  const notes = $("#notes")?.value.trim() || null;

  try {
    let record = getPatient();
    if (!record || record.email !== patient.email.toLowerCase()) {
      try {
        record = await api("/patients", { method: "POST", body: patient });
      } catch (error) {
        if (error.code === "patient_email_taken" && error.details?.patient_id) {
          record = await api(`/patients/lookup?email=${encodeURIComponent(patient.email)}`);
        } else {
          throw error;
        }
      }
      setPatient(record);
    }

    const appointment = await api("/appointments", {
      method: "POST",
      body: { doctor_id: view.doctor.id, patient_id: record.id, starts_at: view.slot.starts_at, notes },
    });
    renderSuccess(appointment, view.doctor);
  } catch (error) {
    if (error.code === "slot_taken") {
      toast("That slot was taken while you were filling the form. Pick another time.", "err");
      view.slot = null;
      renderBookingSummary(view);
      await loadSlots(view);
      return;
    }
    toast(error.message, "err");
    button.disabled = false;
    button.textContent = "Confirm booking";
  }
}

function renderSuccess(appointment, doctor) {
  window.scrollTo({ top: 0 });
  main.innerHTML = `
    <div class="wrap">
      <div class="card success">
        <div class="tick">
          <svg width="30" height="30" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="m4 12.5 5 5L20 6.5"/></svg>
        </div>
        <h1 style="font-size:1.6rem">You're booked</h1>
        <p class="muted" style="margin-top:8px">We've sent the details to your email. Keep this reference:</p>
        <div class="ref">${esc(appointment.reference)}</div>

        <dl style="margin:0">
          <div class="summary-line"><dt>Doctor</dt><dd>${esc(doctor.name)}</dd></div>
          <div class="summary-line"><dt>When</dt><dd>${esc(longDate(appointment.starts_at))}</dd></div>
          <div class="summary-line"><dt>Time</dt><dd>${esc(clock(appointment.starts_at))} – ${esc(clock(appointment.ends_at))}</dd></div>
          <div class="summary-line"><dt>Where</dt><dd>One Padmore Place, Nairobi</dd></div>
        </dl>

        <div class="row" style="margin-top:22px;justify-content:center">
          <button class="btn" id="add-calendar" type="button">Add to calendar</button>
          <a class="btn" href="#/appointment/${appointment.id}">Manage booking</a>
          <a class="btn btn-primary" href="#/">Done</a>
        </div>
      </div>
    </div>`;

  $("#add-calendar").addEventListener("click", () => downloadICS(appointment, doctor));
}

function downloadICS(appointment, doctor) {
  const stamp = (iso) => new Date(iso).toISOString().replace(/[-:]/g, "").split(".")[0] + "Z";
  const lines = [
    "BEGIN:VCALENDAR",
    "VERSION:2.0",
    "PRODID:-//Savannah Clinic//Booking//EN",
    "CALSCALE:GREGORIAN",
    "BEGIN:VEVENT",
    `UID:${appointment.id}@clinic.dabotap.com`,
    `DTSTAMP:${stamp(new Date().toISOString())}`,
    `DTSTART:${stamp(appointment.starts_at)}`,
    `DTEND:${stamp(appointment.ends_at)}`,
    `SUMMARY:Appointment with ${doctor.name}`,
    `LOCATION:One Padmore Place\\, Nairobi`,
    `DESCRIPTION:Reference ${appointment.reference}. Savannah Clinic.`,
    "END:VEVENT",
    "END:VCALENDAR",
  ];
  const blob = new Blob([lines.join("\r\n")], { type: "text/calendar;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = `${appointment.reference}.ics`;
  document.body.append(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
  toast("Calendar file downloaded.");
}

function openDoctorPicker(currentId) {
  openModal({
    title: "Choose a doctor",
    body: `<div id="picker" class="stack"><div class="skeleton" style="height:60px"></div><div class="skeleton" style="height:60px"></div><div class="skeleton" style="height:60px"></div></div>`,
    onMount(root, close) {
      (async () => {
        const [doctors, next] = await Promise.all([getDoctors(), api("/doctors/next-available")]);
        const byId = new Map(next.map((row) => [row.doctor.id, row.next_slot]));
        root.querySelector("#picker").innerHTML = doctors
          .map((doctor) => {
            const slot = byId.get(doctor.id);
            return `
            <button class="pick-row" type="button" data-pick="${doctor.id}" ${doctor.id === currentId ? 'aria-current="true"' : ""}>
              ${doctorAvatar(doctor)}
              <span class="who"><b>${esc(doctor.name)}</b><span>${esc(doctor.specialty)}</span></span>
              <span class="when">${slot ? `${esc(clock(slot))}<span>${esc(relativeDay(slot))}</span>` : "<span>Fully booked</span>"}</span>
            </button>`;
          })
          .join("");
        root.querySelectorAll("[data-pick]").forEach((button) => {
          button.addEventListener("click", () => {
            close();
            location.hash = `#/book/${button.dataset.pick}`;
          });
        });
      })().catch((error) => toast(error.message, "err"));
    },
  });
}

/* ------------------------------------------------------- my appointments */

async function appointmentsView() {
  const stored = getPatient();
  main.innerHTML = `
    <div class="wrap" style="padding-top:36px">
      <h1 style="font-size:1.9rem">My appointments</h1>
      <p class="muted" style="margin-top:8px;max-width:52ch">Enter the email you booked with to see your appointments and manage them.</p>

      <form class="card card-pad" id="lookup" style="margin-top:22px;display:grid;gap:14px;grid-template-columns:1fr auto;align-items:end">
        <div class="field"><label for="lookup-email">Email</label>
          <input id="lookup-email" type="email" autocomplete="email" placeholder="jane@example.com" value="${esc(stored?.email || "")}" required></div>
        <button class="btn btn-primary" type="submit" style="height:44px">Find my bookings</button>
      </form>

      <div id="results" style="margin-top:26px"></div>
    </div>`;

  $("#lookup").addEventListener("submit", (event) => {
    event.preventDefault();
    const email = $("#lookup-email").value.trim();
    if (email) loadAppointments(email);
  });

  if (stored?.email) loadAppointments(stored.email);
}

async function loadAppointments(email) {
  const results = $("#results");
  results.innerHTML = `<div class="stack">${Array.from({ length: 3 }).map(() => `<div class="skeleton" style="height:88px"></div>`).join("")}</div>`;

  try {
    const patient = await api(`/patients/lookup?email=${encodeURIComponent(email)}`);
    setPatient(patient);
    const appointments = await api(`/patients/${patient.id}/appointments?include_past=true`);
    if (!appointments.length) {
      results.innerHTML = emptyState(
        "No appointments yet",
        "When you book with this email, your appointments appear here.",
        `<a class="btn btn-primary" href="#/">Book your first visit</a>`,
      );
      return;
    }

    const doctors = new Map((await getDoctors()).map((doctor) => [doctor.id, doctor]));
    const now = Date.now();
    const upcoming = appointments.filter(
      (appointment) => appointment.status === "booked" && new Date(appointment.starts_at) >= now,
    );
    const past = appointments.filter((appointment) => !upcoming.includes(appointment));

    results.innerHTML = `
      ${upcoming.length ? `<h2 style="margin-bottom:14px">Upcoming</h2><div class="appt-list">${upcoming.map((appointment) => appointmentCard(appointment, doctors.get(appointment.doctor_id))).join("")}</div>` : ""}
      ${past.length ? `<h2 style="margin:${upcoming.length ? "34px" : "0"} 0 14px">Earlier</h2><div class="appt-list">${past.map((appointment) => appointmentCard(appointment, doctors.get(appointment.doctor_id), true)).join("")}</div>` : ""}`;

    $$("[data-cancel]").forEach((button) => {
      button.addEventListener("click", async () => {
        const appointment = appointments.find((item) => item.id === button.dataset.cancel);
        openCancelModal(appointment, doctors.get(appointment.doctor_id), () => loadAppointments(email));
      });
    });
    $$("[data-reschedule]").forEach((button) => {
      button.addEventListener("click", async () => {
        const appointment = appointments.find((item) => item.id === button.dataset.reschedule);
        openRescheduleModal(appointment, doctors.get(appointment.doctor_id), () => loadAppointments(email));
      });
    });
    $$("[data-book-again]").forEach((button) => {
      button.addEventListener("click", () => {
        const appointment = appointments.find((item) => item.id === button.dataset.bookAgain);
        location.hash = `#/book/${appointment.doctor_id}`;
      });
    });
  } catch (error) {
    if (error.status === 404) {
      results.innerHTML = emptyState(
        "No bookings under that email",
        "Check the address, or book a visit — it only takes a minute.",
        `<a class="btn btn-primary" href="#/">Book a visit</a>`,
      );
    } else {
      results.innerHTML = `<div class="error-box">${esc(error.message)}</div>`;
    }
  }
}

function appointmentCard(appointment, doctor, isPast = false) {
  const when = appointment.starts_at;
  const actionable = appointment.status === "booked" && new Date(when) >= Date.now();
  return `
    <article class="card appt ${isPast ? "past" : ""}">
      <div class="when-block">
        <div class="d">${esc(dayOf(when))}</div>
        <div class="m">${esc(monthOf(when))}</div>
      </div>
      <div class="who">
        <b>${esc(doctor?.name || "Doctor")}</b>
        <div class="meta">${esc(clock(when))} – ${esc(clock(appointment.ends_at))} · ${esc(relativeDay(when))} · ${esc(appointment.reference)}</div>
        ${appointment.cancel_reason ? `<div class="meta">Reason: ${esc(appointment.cancel_reason)}</div>` : ""}
        <div style="margin-top:8px">${statusChip(appointment)}</div>
      </div>
      <div class="actions">
        ${actionable ? `<button class="btn btn-sm" data-reschedule="${appointment.id}" type="button">Reschedule</button><button class="btn btn-sm btn-ghost" data-cancel="${appointment.id}" type="button">Cancel</button>` : ""}
        ${appointment.status === "cancelled" ? `<button class="btn btn-sm" data-book-again="${appointment.id}" type="button">Book again</button>` : ""}
        <a class="btn btn-sm btn-ghost" href="#/appointment/${appointment.id}">Details</a>
      </div>
    </article>`;
}

/* -------------------------------------------------------------- manage */

async function manageView(appointmentId) {
  main.innerHTML = `<div class="wrap" style="padding-top:36px"><div class="skeleton" style="height:200px"></div></div>`;
  try {
    const appointment = await api(`/appointments/${appointmentId}`);
    const doctor = await getDoctor(appointment.doctor_id);
    const actionable = appointment.status === "booked" && new Date(appointment.starts_at) >= Date.now();

    main.innerHTML = `
      <div class="wrap" style="padding-top:36px;max-width:760px">
        <a href="#/appointments" class="small muted" style="text-decoration:none">← My appointments</a>
        <div class="card card-pad" style="margin-top:16px">
          <div class="row" style="justify-content:space-between">
            <div class="row">${doctorAvatar(doctor, true)}
              <div><h1 style="font-size:1.4rem">${esc(doctor.name)}</h1>
                <div class="small muted">${esc(doctor.specialty)}</div></div>
            </div>
            ${statusChip(appointment)}
          </div>

          <dl class="summary-lines" style="margin-top:22px">
            <div class="summary-line"><dt>Reference</dt><dd style="font-family:var(--mono)">${esc(appointment.reference)}</dd></div>
            <div class="summary-line"><dt>Date</dt><dd>${esc(longDate(appointment.starts_at))}</dd></div>
            <div class="summary-line"><dt>Time</dt><dd>${esc(clock(appointment.starts_at))} – ${esc(clock(appointment.ends_at))}</dd></div>
            <div class="summary-line"><dt>Where</dt><dd>One Padmore Place, Nairobi</dd></div>
            ${appointment.notes ? `<div class="summary-line"><dt>Your note</dt><dd>${esc(appointment.notes)}</dd></div>` : ""}
            ${appointment.cancel_reason ? `<div class="summary-line"><dt>Cancelled because</dt><dd>${esc(appointment.cancel_reason)}</dd></div>` : ""}
          </dl>

          <div class="row" style="margin-top:20px">
            ${actionable
              ? `<button class="btn" id="move" type="button">Reschedule</button>
                 <button class="btn btn-ghost" id="cancel" type="button">Cancel appointment</button>`
              : `<a class="btn btn-primary" href="#/book/${appointment.doctor_id}">Book another visit</a>`}
            <span class="spacer"></span>
            <button class="btn btn-ghost" id="ics" type="button">Add to calendar</button>
          </div>
        </div>
      </div>`;

    $("#ics").addEventListener("click", () => downloadICS(appointment, doctor));
    $("#move")?.addEventListener("click", () =>
      openRescheduleModal(appointment, doctor, () => manageView(appointmentId)),
    );
    $("#cancel")?.addEventListener("click", () =>
      openCancelModal(appointment, doctor, () => manageView(appointmentId)),
    );
  } catch (error) {
    fatal(error);
  }
}

/* --------------------------------------------------------------- modals */

function openCancelModal(appointment, doctor, onDone) {
  openModal({
    title: "Cancel this appointment?",
    body: `
      <p class="small muted" style="margin-bottom:16px">${esc(doctor?.name || "Your doctor")} · ${esc(longDate(appointment.starts_at))} at ${esc(clock(appointment.starts_at))}. The slot will be released for other patients.</p>
      <div class="field"><label for="cancel-reason">Reason</label>
        <select id="cancel-reason">
          <option value="Schedule conflict">Schedule conflict</option>
          <option value="Feeling better">Feeling better</option>
          <option value="Booked by mistake">Booked by mistake</option>
          <option value="Found another doctor">Found another doctor</option>
          <option value="Other">Other</option>
        </select>
      </div>
      <div class="field" style="margin-top:12px" id="other-wrap" hidden><label for="cancel-other">Tell us more</label>
        <textarea id="cancel-other" maxlength="200" placeholder="A short reason helps the clinic"></textarea>
      </div>`,
    footer: `<button class="btn btn-ghost" data-dismiss type="button">Keep it</button>
             <button class="btn btn-danger" id="confirm-cancel" type="button">Cancel appointment</button>`,
    onMount(root, close) {
      root.querySelector("[data-dismiss]").addEventListener("click", close);
      root.querySelector("#cancel-reason").addEventListener("change", (event) => {
        root.querySelector("#other-wrap").hidden = event.target.value !== "Other";
      });
      root.querySelector("#confirm-cancel").addEventListener("click", async (event) => {
        const reason = root.querySelector("#cancel-reason").value;
        const other = root.querySelector("#cancel-other").value.trim();
        const finalReason = reason === "Other" ? other || "Other" : reason;
        const button = event.currentTarget;
        button.disabled = true;
        button.textContent = "Cancelling…";
        try {
          await api(`/appointments/${appointment.id}/cancel`, { method: "PATCH", body: { reason: finalReason } });
          close();
          toast("Appointment cancelled — the slot is free again.");
          onDone?.();
        } catch (error) {
          toast(error.message, "err");
          button.disabled = false;
          button.textContent = "Cancel appointment";
        }
      });
    },
  });
}

function openRescheduleModal(appointment, doctor, onDone) {
  const state = { date: null, slot: null, days: [] };

  const modal = openModal({
    title: "Move your appointment",
    body: `<p class="small muted" style="margin-bottom:14px">Currently ${esc(longDate(appointment.starts_at))} at ${esc(clock(appointment.starts_at))}.</p>
           <div id="rs-body"><div class="skeleton" style="height:120px"></div></div>`,
    footer: `<button class="btn btn-ghost" data-dismiss type="button">Never mind</button>
             <button class="btn btn-primary" id="confirm-move" type="button" disabled>Move appointment</button>`,
    onMount(root, close) {
      root.querySelector("[data-dismiss]").addEventListener("click", close);
      const button = root.querySelector("#confirm-move");
      button.addEventListener("click", async () => {
        if (!state.slot) return;
        button.disabled = true;
        button.textContent = "Moving…";
        try {
          await api(`/appointments/${appointment.id}/reschedule`, {
            method: "PATCH",
            body: { starts_at: state.slot.starts_at },
          });
          close();
          toast("Appointment moved.");
          onDone?.();
        } catch (error) {
          if (error.code === "slot_taken") {
            toast("That slot was just taken — pick another.", "err");
            button.disabled = false;
            button.textContent = "Move appointment";
            loadDays();
          } else {
            toast(error.message, "err");
            button.disabled = false;
            button.textContent = "Move appointment";
          }
        }
      });

      async function loadDays() {
        const body = root.querySelector("#rs-body");
        body.innerHTML = `<div class="skeleton" style="height:120px"></div>`;
        try {
          const summary = await availabilitySummary(doctor.id, { days: 21 });
          state.days = summary.days;
          state.date = state.days.find((day) => day.free_slots > 0 && day.date !== dateKey(appointment.starts_at))?.date
            || state.days.find((day) => day.free_slots > 0)?.date
            || null;
          renderDays();
        } catch (error) {
          body.innerHTML = `<div class="error-box">${esc(error.message)}</div>`;
        }
      }

      function renderDays() {
        const body = root.querySelector("#rs-body");
        body.innerHTML = `
          <div class="date-strip">${state.days.slice(0, 14).map((day) => {
            const target = new Date(day.date + "T12:00:00+03:00").toISOString();
            return `<button class="date-chip" type="button" data-rs-date="${day.date}" aria-pressed="${day.date === state.date}" ${day.free_slots === 0 ? "disabled" : ""}>
              <span class="dow">${esc(weekday(target))}</span><span class="dom">${esc(dayOf(target))}</span><span class="free">${day.free_slots === 0 ? "full" : `${day.free_slots} free`}</span></button>`;
          }).join("")}</div>
          <div id="rs-slots" style="margin-top:8px"><div class="skeleton" style="height:60px"></div></div>`;

        body.querySelectorAll("[data-rs-date]").forEach((button) => {
          button.addEventListener("click", () => {
            state.date = button.dataset.rsDate;
            state.slot = null;
            renderDays();
          });
        });
        loadSlots();
      }

      async function loadSlots() {
        const holder = root.querySelector("#rs-slots");
        if (!holder || !state.date) return;
        try {
          const data = await availabilityFor(doctor.id, state.date);
          if (!data.slots.length) {
            holder.innerHTML = `<p class="small muted">No free slots that day.</p>`;
            return;
          }
          holder.innerHTML = `<div class="slot-grid">${data.slots.map((slot) => `<button class="slot" type="button" data-rs-start="${slot.starts_at}" aria-pressed="false">${esc(clock(slot.starts_at))}</button>`).join("")}</div>`;
          holder.querySelectorAll("[data-rs-start]").forEach((button) => {
            button.addEventListener("click", () => {
              state.slot = data.slots.find((slot) => slot.starts_at === button.dataset.rsStart);
              holder.querySelectorAll("[data-rs-start]").forEach((node) => node.setAttribute("aria-pressed", String(node === button)));
              root.querySelector("#confirm-move").disabled = false;
            });
          });
        } catch (error) {
          holder.innerHTML = `<div class="error-box">${esc(error.message)}</div>`;
        }
      }

      loadDays();
    },
  });
  return modal;
}

/* ---------------------------------------------------------------- router */

function fatal(error) {
  console.error(error);
  main.innerHTML = `
    <div class="wrap" style="padding-top:60px">
      <div class="card card-pad" style="max-width:560px;margin:0 auto;text-align:center">
        <h2>Something went wrong</h2>
        <p class="muted" style="margin:10px 0 18px">${esc(error.message || "Unexpected error")}</p>
        <div class="row" style="justify-content:center">
          <button class="btn" onclick="location.reload()">Reload</button>
          <a class="btn btn-primary" href="#/">Back to booking</a>
        </div>
      </div>
    </div>`;
}

function setActiveNav(path) {
  $$("[data-nav]").forEach((link) => {
    const isAppointments = link.dataset.nav === "appointments";
    const active = isAppointments ? path.startsWith("/appointments") : !path.startsWith("/appointments");
    link.toggleAttribute("aria-current", active);
    if (active) link.setAttribute("aria-current", "page");
  });
}

async function route() {
  const path = (location.hash.replace(/^#/, "") || "/").split("?")[0];
  setActiveNav(path);
  window.scrollTo({ top: 0 });

  const bookMatch = path.match(/^\/book\/([0-9a-f-]{36})$/);
  const manageMatch = path.match(/^\/appointment\/([0-9a-f-]{36})$/);

  try {
    if (path === "/" || path === "") return await home();
    if (bookMatch) return await book(bookMatch[1]);
    if (path === "/appointments") return await appointmentsView();
    if (manageMatch) return await manageView(manageMatch[1]);
    return fatal(new Error("That page doesn't exist."));
  } catch (error) {
    fatal(error);
  }
}

/* ------------------------------------------------------------------ boot */

function initTheme() {
  // ?theme=light|dark is handy for screenshots and for sharing a link.
  const forced = new URLSearchParams(location.search).get("theme");
  const stored = forced || localStorage.getItem("clinic.theme");
  const prefersDark = window.matchMedia("(prefers-color-scheme: dark)").matches;
  document.documentElement.dataset.theme = stored || (prefersDark ? "dark" : "light");
  $("#theme-toggle").addEventListener("click", () => {
    const next = document.documentElement.dataset.theme === "dark" ? "light" : "dark";
    document.documentElement.dataset.theme = next;
    localStorage.setItem("clinic.theme", next);
  });
}

window.addEventListener("hashchange", route);
initTheme();
route();
