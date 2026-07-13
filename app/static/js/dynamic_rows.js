/*
 * Generic "+ Add row" / "Remove" behavior for repeatable form sections
 * (currently: salary allowance/deduction rows on the Employee form).
 *
 * Usage: a <template id="X-template"> holding one row's markup, a
 * container <div id="X"> to append clones into, and a button with
 * data-row-adder="X". Each row needs a [data-row-remove] button inside it.
 */
document.addEventListener('DOMContentLoaded', function () {
  document.querySelectorAll('[data-row-adder]').forEach(function (button) {
    var targetId = button.getAttribute('data-row-adder');
    var container = document.getElementById(targetId);
    var template = document.getElementById(targetId + '-template');
    if (!container || !template) return;

    button.addEventListener('click', function () {
      container.appendChild(template.content.cloneNode(true));
    });
  });

  // Delegated on document so it also works on rows added dynamically above.
  document.addEventListener('click', function (event) {
    if (!event.target.matches('[data-row-remove]')) return;
    var row = event.target.closest('.dynamic-row');
    if (row) row.remove();
  });
});
