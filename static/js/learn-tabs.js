(function () {
  "use strict";

  var buttons = Array.prototype.slice.call(document.querySelectorAll('.tab-btn[data-tab]'));
  if (!buttons.length) return;

  function activate(tabName, updateUrl) {
    buttons.forEach(function (btn) {
      var isActive = btn.getAttribute('data-tab') === tabName;
      btn.setAttribute('aria-selected', String(isActive));
    });
    document.querySelectorAll('.tab-panel').forEach(function (panel) {
      panel.classList.toggle('active', panel.id === 'tab-panel-' + tabName);
    });
    if (updateUrl && window.history && window.history.replaceState) {
      var url = new URL(window.location.href);
      url.searchParams.set('tab', tabName);
      window.history.replaceState({}, '', url);
    }
  }

  buttons.forEach(function (btn) {
    btn.addEventListener('click', function () {
      activate(btn.getAttribute('data-tab'), true);
    });
  });
})();
