"use strict";

const $ = (id) => document.getElementById(id);
let offset = 0;
const limit = 50;
let selectedId = null;

function fmtTs(ts) {
  if (!ts) return "";
  const s = String(ts).replace("T", " ");
  return s.length >= 16 ? s.slice(0, 16) : s;
}

function shortId(id) {
  if (!id) return "";
  return id.length > 14 ? id.slice(0, 12) + "…" : id;
}

function statusDotClass(status, trust) {
  if (status === "proposed") return "proposed";
  if (status === "rejected") return "rejected";
  if (status === "reverted") return "reverted";
  if (status === "active" || trust === "verified") return "active";
  return status || "";
}

function makeRow(e, text) {
  const row = document.createElement("div");
  row.className = "row" + (e.id === selectedId ? " is-selected" : "");
  row.setAttribute("role", "listitem");
  row.dataset.id = e.id || "";

  const meta = document.createElement("div");
  meta.className = "row-meta";
  const idEl = document.createElement("span");
  idEl.className = "row-id";
  idEl.textContent = shortId(e.id);
  idEl.title = e.id || "";
  const tsEl = document.createElement("span");
  tsEl.textContent = fmtTs(e.ts || e.timestamp || "");
  meta.appendChild(idEl);
  meta.appendChild(document.createElement("br"));
  meta.appendChild(tsEl);

  const body = document.createElement("div");
  body.className = "row-body";
  const type = document.createElement("p");
  type.className = "row-type";
  type.textContent = e.type || "";
  const snip = document.createElement("p");
  snip.className = "row-snippet";
  snip.textContent = text ?? "";
  const src = document.createElement("p");
  src.className = "row-source";
  const bits = [e.source || e.actor || "", e.subject || "", e.trust || ""].filter(Boolean);
  src.textContent = bits.join(" · ");
  body.appendChild(type);
  body.appendChild(snip);
  body.appendChild(src);

  const side = document.createElement("div");
  side.className = "row-status";
  const dot = document.createElement("span");
  dot.className = "dot " + statusDotClass(e.status, e.trust);
  dot.title = (e.status || "?") + " / " + (e.trust || "?");
  side.appendChild(dot);
  if (e.status === "proposed") {
    const b = document.createElement("button");
    b.type = "button";
    b.className = "approve";
    b.textContent = "Onay";
    b.disabled = true;
    b.title = "Onay yalnızca CLI ile (adım 2).";
    side.appendChild(b);
  }

  row.appendChild(meta);
  row.appendChild(body);
  row.appendChild(side);
  row.addEventListener("click", () => {
    selectedId = e.id;
    document.querySelectorAll(".row.is-selected").forEach((el) => el.classList.remove("is-selected"));
    row.classList.add("is-selected");
  });
  return row;
}

function renderRows(items, textFn) {
  const list = $("list");
  list.replaceChildren();
  items.forEach((e) => list.appendChild(makeRow(e, textFn(e))));
  const empty = !items.length;
  $("empty").hidden = !empty;
  return items.length;
}

async function load() {
  const p = new URLSearchParams({ limit: String(limit), offset: String(offset) });
  if ($("status").value) p.set("status", $("status").value);
  if ($("trust").value) p.set("trust", $("trust").value);
  const d = await (await fetch("/api/events?" + p)).json();
  if (d.error) {
    $("info").textContent = d.error;
    $("list").replaceChildren();
    $("empty").hidden = false;
    return;
  }
  const n = renderRows(d.items || [], (e) => e.text_short);
  $("info").textContent = d.total
    ? `${d.total} kayıt · ${offset + 1}–${offset + n}`
    : "0 kayıt";
  $("prev").disabled = offset === 0;
  $("next").disabled = offset + limit >= d.total;
}

async function search() {
  const q = $("q").value.trim();
  if (!q) return load();
  const d = await (await fetch("/api/search?" + new URLSearchParams({ q }))).json();
  const results = d.results || [];
  renderRows(results, (e) => e.snippet || "");
  $("info").textContent = `${results.length} arama sonucu`;
  $("prev").disabled = true;
  $("next").disabled = true;
}

$("status").onchange = $("trust").onchange = () => {
  offset = 0;
  load();
};
$("go").onclick = search;
$("q").onkeydown = (ev) => {
  if (ev.key === "Enter") search();
};
$("clear").onclick = () => {
  $("q").value = "";
  offset = 0;
  load();
};
$("prev").onclick = () => {
  offset = Math.max(0, offset - limit);
  load();
};
$("next").onclick = () => {
  offset += limit;
  load();
};

load();
