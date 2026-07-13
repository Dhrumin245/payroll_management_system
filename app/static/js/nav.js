document.addEventListener('DOMContentLoaded', function () {
  var toggle = document.querySelector('.app-navbar__toggle');
  var links = document.querySelector('.app-navbar__links');
  if (!toggle || !links) return;

  toggle.addEventListener('click', function () {
    var isOpen = links.classList.toggle('is-open');
    toggle.setAttribute('aria-expanded', isOpen ? 'true' : 'false');
  });
});
