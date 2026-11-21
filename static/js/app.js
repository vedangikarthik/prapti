// Hakku client scripts: rotating examples, voice input, edit panel, checklist, tracker.
(function () {
  "use strict";

  function store(key, value) {
    try {
      if (value === undefined) return JSON.parse(localStorage.getItem(key) || "null");
      localStorage.setItem(key, JSON.stringify(value));
    } catch (e) {
      return null;
    }
  }

  // ---------- Toast ----------
  var toastTimer;
  function toast(msg) {
    var el = document.querySelector(".toast");
    if (!el) return;
    el.textContent = msg;
    el.hidden = false;
    requestAnimationFrame(function () { el.classList.add("is-visible"); });
    clearTimeout(toastTimer);
    toastTimer = setTimeout(function () {
      el.classList.remove("is-visible");
      setTimeout(function () { el.hidden = true; }, 300);
    }, 3000);
  }

  // Links for screens that arrive in later steps.
  document.querySelectorAll("[data-soon]").forEach(function (a) {
    a.addEventListener("click", function (e) {
      e.preventDefault();
      toast("Coming soon");
    });
  });

  // ---------- Home: rotating placeholder ----------
  var textarea = document.querySelector("textarea[data-examples]");
  if (textarea) {
    var examples = [];
    try { examples = JSON.parse(textarea.dataset.examples); } catch (e) {}
    var idx = 0;
    var reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (examples.length > 1 && !reduce) {
      setInterval(function () {
        if (textarea.value || document.activeElement === textarea) return;
        textarea.classList.add("is-swapping");
        setTimeout(function () {
          idx = (idx + 1) % examples.length;
          textarea.placeholder = examples[idx];
          textarea.classList.remove("is-swapping");
        }, 250);
      }, 4000);
    }

    // ---------- Voice input (Web Speech API) ----------
    var SR = window.SpeechRecognition || window.webkitSpeechRecognition;
    var micRow = document.querySelector("[data-mic-row]");
    var mic = document.querySelector("[data-mic]");
    var micLabel = document.querySelector("[data-mic-label]");
    if (SR && micRow && mic) {
      micRow.hidden = false;
      var rec = null;
      var base = "";
      var lang = document.documentElement.lang === "te" ? "te-IN" : document.documentElement.lang === "hi" ? "hi-IN" : "en-IN";
      mic.addEventListener("click", function () {
        if (rec) { rec.stop(); return; }
        rec = new SR();
        rec.lang = lang;
        rec.interimResults = true;
        rec.continuous = true;
        base = textarea.value ? textarea.value.trim() + " " : "";
        rec.onresult = function (ev) {
          var text = "";
          for (var i = 0; i < ev.results.length; i++) text += ev.results[i][0].transcript;
          textarea.value = base + text;
        };
        rec.onend = function () {
          rec = null;
          mic.setAttribute("aria-pressed", "false");
          micLabel.textContent = "Tap and speak";
        };
        rec.onerror = function () {
          toast("Couldn't hear you. Check microphone permission and try again.");
        };
        rec.start();
        mic.setAttribute("aria-pressed", "true");
        micLabel.textContent = "Listening… tap to stop";
      });
    }
  }

  // ---------- Results: edit panel ----------
  var editToggle = document.querySelector("[data-edit-toggle]");
  var editPanel = document.getElementById("edit-panel");
  if (editToggle && editPanel) {
    editToggle.addEventListener("click", function () {
      var open = editPanel.hidden;
      editPanel.hidden = !open;
      editToggle.setAttribute("aria-expanded", String(open));
      if (open) editPanel.querySelector("input").focus({ preventScroll: true });
    });
    if (location.hash === "#edit-panel") {
      editPanel.hidden = false;
      editToggle.setAttribute("aria-expanded", "true");
    }
  }

  // ---------- Scheme detail: checklist ----------
  var list = document.querySelector("[data-checklist]");
  if (list) {
    var key = "hakku:docs:" + list.dataset.checklist;
    var saved = store(key) || [];
    var boxes = list.querySelectorAll("input[type=checkbox]");
    var progressText = document.querySelector("[data-doc-progress]");
    var bar = document.querySelector("[data-doc-bar]");
    function update() {
      var done = [];
      boxes.forEach(function (b) {
        b.closest(".check-item").classList.toggle("is-done", b.checked);
        if (b.checked) done.push(b.value);
      });
      store(key, done);
      if (progressText) progressText.textContent = done.length + " of " + boxes.length + " ready";
      if (bar) bar.style.width = (boxes.length ? (done.length / boxes.length) * 100 : 0) + "%";
    }
    boxes.forEach(function (b) {
      b.checked = saved.indexOf(b.value) !== -1;
      b.addEventListener("change", update);
    });
    update();
  }

  // ---------- Scheme detail: add to tracker ----------
  var trackBtn = document.querySelector("[data-track]");
  var head = document.querySelector("[data-scheme-id]");
  if (trackBtn && head) {
    var tracked = store("hakku:tracker") || [];
    var id = head.dataset.schemeId;
    function setTracked(isTracked) {
      trackBtn.disabled = isTracked;
      trackBtn.lastChild.textContent = isTracked ? "In your tracker" : "Add to my tracker";
    }
    setTracked(tracked.some(function (t) { return t.id === id; }));
    trackBtn.addEventListener("click", function () {
      tracked = store("hakku:tracker") || [];
      if (!tracked.some(function (t) { return t.id === id; })) {
        tracked.push({ id: id, name: head.dataset.schemeName, deadline: head.dataset.deadline || null,
                       status: "not_started", added: new Date().toISOString().slice(0, 10) });
        store("hakku:tracker", tracked);
      }
      setTracked(true);
      toast("Added to your tracker");
    });
  }

  // ---------- Nav dot: any tracked deadline within 7 days ----------
  var dot = document.querySelector(".nav-dot");
  var all = store("hakku:tracker") || [];
  var soon = all.some(function (t) {
    if (!t.deadline || t.status === "received") return false;
    var days = (new Date(t.deadline) - new Date()) / 86400000;
    return days >= -1 && days <= 7;
  });
  if (dot && soon) dot.classList.add("is-visible");
})();
