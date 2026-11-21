// Arhata tracker: everything is stored on this device (localStorage), nothing is sent anywhere.
(function () {
  "use strict";

  var STATUSES = [
    { id: "not_started", label: "Not started", advance: "Documents are ready" },
    { id: "documents_ready", label: "Documents ready", advance: "I have applied" },
    { id: "applied", label: "Applied", advance: "It is under review" },
    { id: "under_review", label: "Under review", advance: "I received it" },
    { id: "received", label: "Received", advance: null },
    { id: "rejected", label: "Rejected", advance: null }
  ];
  var REMIND_AT = [14, 7, 3, 1];

  function read(key, fallback) {
    try { var v = JSON.parse(localStorage.getItem(key)); return v == null ? fallback : v; } catch (e) { return fallback; }
  }
  function write(key, value) {
    try { localStorage.setItem(key, JSON.stringify(value)); } catch (e) {}
  }

  var meta = {};
  try {
    JSON.parse(document.getElementById("schemes-meta").textContent).forEach(function (s) { meta[s.id] = s; });
  } catch (e) {}

  var list = document.querySelector("[data-track-list]");
  var empty = document.querySelector("[data-empty]");
  var tpl = document.getElementById("track-item");
  var urgent = document.querySelector("[data-urgent]");
  var tools = document.querySelector("[data-tools]");

  function daysLeft(iso) {
    if (!iso) return null;
    var today = new Date(); today.setHours(0, 0, 0, 0);
    var d = new Date(iso + "T00:00:00");
    return Math.round((d - today) / 86400000);
  }

  function niceDate(iso) {
    return new Date(iso + "T00:00:00").toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" });
  }

  function docsDone(id) {
    return read("arhata:docs:" + id, []);
  }

  function nextStep(item, m, done) {
    var docs = (m && m.documents) || [];
    switch (item.status) {
      case "not_started":
        var missing = docs.filter(function (d, i) { return done.indexOf(String(i)) === -1; });
        if (missing.length) return "Get your " + missing[0].name.replace(/ \(.*\)$/, "").toLowerCase() + ". " + missing[0].hint + ".";
        return "Your documents are ready. Apply on " + (m ? m.source_name : "the official portal") + ".";
      case "documents_ready": return "Apply on " + (m ? m.source_name : "the official portal") + " before the last date.";
      case "applied": return "Ask your college office to verify and forward your application.";
      case "under_review": return "Check your status on the portal every two weeks.";
      case "received": return "Done. Remember to renew it next year.";
      case "rejected": return "Read the reason on the portal, fix it (often an old certificate or a name mismatch), and ask your college about applying again.";
    }
    return "";
  }

  function render() {
    var items = read("arhata:tracker", []);
    list.innerHTML = "";
    empty.hidden = items.length > 0;
    tools.hidden = items.length === 0;

    // soonest first; finished ones last
    items.sort(function (a, b) {
      var fa = a.status === "received" || a.status === "rejected" ? 1 : 0;
      var fb = b.status === "received" || b.status === "rejected" ? 1 : 0;
      if (fa !== fb) return fa - fb;
      var da = daysLeft((meta[a.id] || a).deadline), db = daysLeft((meta[b.id] || b).deadline);
      return (da == null ? 1e6 : da) - (db == null ? 1e6 : db);
    });

    var soon = [];
    items.forEach(function (item, i) {
      var m = meta[item.id];
      var node = tpl.content.firstElementChild.cloneNode(true);
      var deadline = m ? m.deadline : item.deadline;
      var left = daysLeft(deadline);
      var status = STATUSES.filter(function (s) { return s.id === item.status; })[0] || STATUSES[0];
      var finished = status.id === "received" || status.id === "rejected";
      var done = docsDone(item.id);
      var total = m ? m.documents.length : 0;

      node.style.setProperty("--i", i);
      node.classList.add("status-" + status.id);
      node.querySelector("[data-status-label]").textContent = status.label;
      var link = node.querySelector("[data-link]");
      link.textContent = m ? m.name : item.name;
      link.href = "/scheme/" + item.id;

      var daysEl = node.querySelector("[data-days]");
      var dlEl = node.querySelector("[data-deadline]");
      if (deadline && left != null) {
        if (left < 0) { daysEl.textContent = "Closed"; dlEl.textContent = "Last date was " + niceDate(deadline) + "."; }
        else {
          daysEl.textContent = left === 0 ? "Last day today" : left + " day" + (left === 1 ? "" : "s") + " left";
          dlEl.textContent = "Apply by " + niceDate(deadline) + ".";
          if (left <= 7 && !finished) { node.classList.add("is-urgent"); soon.push({ name: m ? m.name : item.name, left: left }); }
        }
      } else {
        daysEl.textContent = "No fixed date";
        dlEl.textContent = (m && m.deadline_note) || "Apply before your fees are due.";
      }

      node.querySelector("[data-bar]").style.width = (total ? (done.length / total) * 100 : 0) + "%";
      node.querySelector("[data-docs]").textContent = done.length + " of " + total + " documents ready";
      node.querySelector("[data-next]").textContent = nextStep(item, m, done);

      var adv = node.querySelector("[data-advance]");
      if (status.advance) {
        adv.textContent = status.advance;
        adv.addEventListener("click", function () { setStatus(item.id, STATUSES[STATUSES.indexOf(status) + 1].id); });
      } else {
        adv.remove();
      }

      var sel = node.querySelector("[data-status-select]");
      STATUSES.forEach(function (s) {
        var o = document.createElement("option");
        o.value = s.id; o.textContent = s.label; o.selected = s.id === status.id;
        sel.appendChild(o);
      });
      sel.addEventListener("change", function () { setStatus(item.id, sel.value); });

      var ics = node.querySelector("[data-ics]");
      if (deadline && left != null && left >= 0) ics.href = "/api/ics/" + item.id; else ics.remove();

      node.querySelector("[data-remove]").addEventListener("click", function () {
        write("arhata:tracker", read("arhata:tracker", []).filter(function (t) { return t.id !== item.id; }));
        render();
      });

      list.appendChild(node);
    });

    if (soon.length) {
      soon.sort(function (a, b) { return a.left - b.left; });
      urgent.hidden = false;
      urgent.querySelector("[data-urgent-text]").textContent = soon[0].name + " closes " +
        (soon[0].left === 0 ? "today" : "in " + soon[0].left + " day" + (soon[0].left === 1 ? "" : "s")) +
        (soon.length > 1 ? ", and " + (soon.length - 1) + " more within a week." : ".");
    } else {
      urgent.hidden = true;
    }
    var dot = document.querySelector(".nav-dot");
    if (dot) dot.classList.toggle("is-visible", soon.length > 0);
  }

  function setStatus(id, status) {
    var items = read("arhata:tracker", []);
    items.forEach(function (t) { if (t.id === id) { t.status = status; t.updated = new Date().toISOString().slice(0, 10); } });
    write("arhata:tracker", items);
    render();
  }

  // ---------- Reminders: shown when the page is opened, once per threshold ----------
  var notifyBtn = document.querySelector("[data-notify]");
  var notifyNote = document.querySelector("[data-notify-note]");

  function remind() {
    if (!("Notification" in window) || Notification.permission !== "granted") return;
    var sent = read("arhata:reminded", {});
    read("arhata:tracker", []).forEach(function (t) {
      if (t.status === "received" || t.status === "rejected") return;
      var m = meta[t.id];
      var left = daysLeft(m ? m.deadline : t.deadline);
      if (left == null || left < 0) return;
      var due = REMIND_AT.filter(function (n) { return left <= n; });
      if (!due.length) return;
      var key = t.id + ":" + Math.min.apply(null, due);
      if (sent[key]) return;
      sent[key] = new Date().toISOString();
      try {
        new Notification((m ? m.name : t.name), { body: (left === 0 ? "Last day today." : left + " day" + (left === 1 ? "" : "s") + " left to apply.") + " Never pay anyone to apply for you." });
      } catch (e) {}
    });
    write("arhata:reminded", sent);
  }

  function updateNotifyButton() {
    if (!("Notification" in window)) {
      notifyBtn.remove();
      notifyNote.textContent = "This browser can't show reminders. Use the Calendar button on each scheme instead.";
      return;
    }
    if (Notification.permission === "granted") {
      notifyBtn.remove();
      notifyNote.textContent = "Reminders are on: 14, 7, 3 and 1 day before each last date, when you open Arhata. For reminders on your phone even when it's closed, add each one to your calendar.";
    } else if (Notification.permission === "denied") {
      notifyBtn.remove();
      notifyNote.textContent = "Reminders are blocked in this browser. Use the Calendar button on each scheme instead.";
    }
  }

  if (notifyBtn) {
    notifyBtn.addEventListener("click", function () {
      Notification.requestPermission().then(function () { updateNotifyButton(); remind(); });
    });
    updateNotifyButton();
  }

  render();
  remind();
})();
