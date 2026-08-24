(function () {
  "use strict";
  var input = document.getElementById('glossary-search');
  if (!input) return;

  var items = Array.prototype.slice.call(document.querySelectorAll('#glossary-list .glossary-item'));
  var emptyState = document.getElementById('glossary-empty');
  var emptyQuery = document.getElementById('glossary-empty-query');

  function filter() {
    var query = input.value.trim().toLowerCase();
    var visibleCount = 0;

    items.forEach(function (item) {
      var haystack = (item.getAttribute('data-term') + ' ' + item.textContent).toLowerCase();
      var match = query === '' || haystack.indexOf(query) !== -1;
      item.hidden = !match;
      if (match) visibleCount += 1;
    });

    if (emptyState) {
      emptyState.hidden = visibleCount > 0 || query === '';
      if (emptyQuery) emptyQuery.textContent = input.value.trim();
    }
  }

  input.addEventListener('input', filter);
})();
