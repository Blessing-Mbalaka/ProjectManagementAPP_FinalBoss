(function () {
  'use strict';

  const SAVE_WORDS = /\b(save|update|create|add|upload|assign|submit|record|send|confirm)\b/i;
  let activeNotice = null;
  let activeTimers = [];

  function clearTimers() {
    activeTimers.forEach(window.clearTimeout);
    activeTimers = [];
  }

  function clearNotice() {
    clearTimers();
    if (activeNotice) activeNotice.remove();
    activeNotice = null;
    document.querySelectorAll('[data-save-feedback-active]').forEach(button => {
      button.style.removeProperty('pointer-events');
      button.style.removeProperty('opacity');
      button.removeAttribute('aria-disabled');
      button.removeAttribute('data-save-feedback-active');
    });
  }

  function ensureStyles() {
    if (document.getElementById('global-save-feedback-styles')) return;
    const style = document.createElement('style');
    style.id = 'global-save-feedback-styles';
    style.textContent = '.global-save-feedback{position:fixed;top:18px;left:50%;transform:translateX(-50%);z-index:3000;width:min(560px,calc(100vw - 28px));padding:14px 18px;border-radius:14px;background:#5f1765;color:#fff;box-shadow:0 14px 38px rgba(0,0,0,.25);font:600 14px/1.45 system-ui,sans-serif}.global-save-feedback.is-delayed{background:#8a4b08}.global-save-feedback.is-error{background:#b02a37}';
    document.head.appendChild(style);
  }

  function showNotice(submitter) {
    clearNotice();
    ensureStyles();
    activeNotice = document.createElement('div');
    activeNotice.className = 'global-save-feedback';
    activeNotice.setAttribute('role', 'status');
    activeNotice.setAttribute('aria-live', 'polite');
    activeNotice.textContent = 'Saving your update. Please stay online while the system finishes.';
    document.body.appendChild(activeNotice);

    if (submitter) {
      submitter.dataset.saveFeedbackActive = 'true';
      submitter.setAttribute('aria-disabled', 'true');
      submitter.style.pointerEvents = 'none';
      submitter.style.opacity = '.72';
    }

    activeTimers.push(window.setTimeout(() => {
      if (activeNotice) activeNotice.textContent = 'The system is still updating. Thank you for your patience—please stay online.';
    }, 10000));
    activeTimers.push(window.setTimeout(() => {
      if (!activeNotice) return;
      activeNotice.classList.add('is-delayed');
      activeNotice.textContent = 'Sorry this is taking longer than usual. Please stay online; we are still saving your update.';
    }, 20000));
    activeTimers.push(window.setTimeout(() => {
      if (!activeNotice) return;
      activeNotice.classList.remove('is-delayed');
      activeNotice.classList.add('is-error');
      activeNotice.textContent = 'The request is taking too long. The controls have been restored; please check your connection before trying again.';
      if (submitter) {
        submitter.style.removeProperty('pointer-events');
        submitter.style.removeProperty('opacity');
        submitter.removeAttribute('aria-disabled');
        submitter.removeAttribute('data-save-feedback-active');
      }
    }, 60000));
  }

  document.addEventListener('submit', function (event) {
    if (event.defaultPrevented) return;
    const form = event.target;
    if (!(form instanceof HTMLFormElement) || form.dataset.noSaveFeedback !== undefined) return;
    if ((form.method || 'get').toLowerCase() === 'get') return;
    if (form.classList.contains('kanban-edit-form') || form.classList.contains('staff-kanban-edit-form')) return;

    const submitter = event.submitter || form.querySelector('[type="submit"]');
    const label = [
      submitter ? submitter.textContent : '',
      submitter ? submitter.value : '',
      form.dataset.saveFeedback || '',
    ].join(' ');
    if (!SAVE_WORDS.test(label)) return;
    showNotice(submitter);
  });

  window.addEventListener('pageshow', clearNotice);
})();
