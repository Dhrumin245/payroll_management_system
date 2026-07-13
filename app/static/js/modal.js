/*
 * Open/close helpers for the confirmation modal partial
 * (app/templates/partials/confirm_modal.html). Not wired to any live
 * trigger yet — Phase 4a's deactivate/reactivate buttons are the first
 * real callers, per App Flow §3.11.
 */
function openModal(modalId) {
  document.getElementById(modalId).hidden = false;
  document.getElementById(modalId + '-backdrop').hidden = false;
}

function closeModal(modalId) {
  document.getElementById(modalId).hidden = true;
  document.getElementById(modalId + '-backdrop').hidden = true;
}

document.addEventListener('keydown', function (event) {
  if (event.key !== 'Escape') return;
  document.querySelectorAll('.app-modal:not([hidden])').forEach(function (modal) {
    closeModal(modal.id);
  });
});
