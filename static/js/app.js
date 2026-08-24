(function () {
  "use strict";

  var root = document.documentElement;

  /* ---- Theme ---- */
  function setTheme(theme) {
    root.setAttribute('data-theme', theme);
    try { localStorage.setItem('sb-theme', theme); } catch (e) {}
    document.querySelectorAll('[data-theme-btn]').forEach(function (btn) {
      btn.setAttribute('aria-pressed', String(btn.getAttribute('data-theme-btn') === theme));
    });
  }

  document.querySelectorAll('[data-theme-btn]').forEach(function (btn) {
    btn.addEventListener('click', function () {
      setTheme(btn.getAttribute('data-theme-btn'));
    });
  });

  /* ---- Font size ---- */
  function setFontSize(size) {
    root.setAttribute('data-font-size', size);
    try { localStorage.setItem('sb-font-size', size); } catch (e) {}
    document.querySelectorAll('[data-font]').forEach(function (btn) {
      btn.setAttribute('aria-pressed', String(btn.getAttribute('data-font') === size));
    });
  }

  document.querySelectorAll('[data-font]').forEach(function (btn) {
    btn.addEventListener('click', function () {
      setFontSize(btn.getAttribute('data-font'));
    });
  });

  /* Sync control button states with whatever was applied pre-paint */
  setTheme(root.getAttribute('data-theme') || 'dark');
  setFontSize(root.getAttribute('data-font-size') || 'medium');

  /* ---- Active nav state ---- */
  var path = window.location.pathname;
  document.querySelectorAll('.nav-link').forEach(function (link) {
    var href = link.getAttribute('href');
    var isActive = href === path || (href !== '/' && path.indexOf(href) === 0);
    if (href === '/' && path !== '/') isActive = false;
    if (isActive) link.setAttribute('aria-current', 'page');
  });

  /* ---- Mobile nav ---- */
  var sidebar = document.getElementById('sidebar');
  var toggle = document.getElementById('navToggle');
  var scrim = document.getElementById('navScrim');

  function closeNav() {
    sidebar.classList.remove('open');
    toggle.setAttribute('aria-expanded', 'false');
    scrim.hidden = true;
  }
  function openNav() {
    sidebar.classList.add('open');
    toggle.setAttribute('aria-expanded', 'true');
    scrim.hidden = false;
  }
  if (toggle) {
    toggle.addEventListener('click', function () {
      var expanded = toggle.getAttribute('aria-expanded') === 'true';
      if (expanded) { closeNav(); } else { openNav(); }
    });
  }
  if (scrim) scrim.addEventListener('click', closeNav);
  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape') closeNav();
  });
})();

/* ==========================================================================
   Edge meter rendering — shared across Overview, Analyze, Decide, Simulator.
   Renders a track from 0-1 with a marker for market probability and one
   for model probability, highlighting the gap between them as the edge.
   ========================================================================== */
function renderEdgeMeter(container, marketProb, modelProb) {
  if (!container) return;
  var clamp = function (v) { return Math.max(0, Math.min(1, v)); };
  var m = clamp(marketProb);
  var p = clamp(modelProb);
  var positive = p >= m;
  var lo = Math.min(m, p) * 100;
  var hi = Math.max(m, p) * 100;

  container.innerHTML =
    '<div class="edge-meter-labels">' +
      '<span>0%</span><span>50%</span><span>100%</span>' +
    '</div>' +
    '<div class="edge-meter-track" role="img" aria-label="Market probability ' +
      Math.round(m * 100) + ' percent, model probability ' + Math.round(p * 100) +
      ' percent, edge ' + (positive ? '+' : '') + Math.round((p - m) * 100) + ' percent">' +
      '<div class="edge-meter-range ' + (positive ? 'positive' : 'negative') + '" style="left:' + lo + '%; width:' + (hi - lo) + '%;"></div>' +
      '<div class="edge-meter-marker market" style="left:' + (m * 100) + '%;"></div>' +
      '<div class="edge-meter-marker model ' + (positive ? 'positive' : 'negative') + '" style="left:' + (p * 100) + '%;"></div>' +
    '</div>' +
    '<div class="edge-meter-legend">' +
      '<span><span class="legend-dot market"></span>Market ' + (m * 100).toFixed(1) + '%</span>' +
      '<span><span class="legend-dot model"></span>Model ' + (p * 100).toFixed(1) + '%</span>' +
    '</div>';
}
