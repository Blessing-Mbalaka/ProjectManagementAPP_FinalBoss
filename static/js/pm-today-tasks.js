(() => {
  'use strict';
  const root = document.getElementById('dashboard-personal-tasks');
  if (!root) return;
  const form = document.getElementById('dashboard-task-form');
  const list = document.getElementById('tasks-list');
  const feedback = document.getElementById('dashboard-task-feedback');
  const url = root.dataset.listUrl;
  const token = () => document.cookie.split('; ').find(v => v.startsWith('csrftoken='))?.split('=')[1] || '';
  async function request(target, payload) {
    const response = await fetch(target, payload === undefined ? {} : {method: 'POST', headers: {'Content-Type': 'application/json', 'X-CSRFToken': token()}, body: JSON.stringify(payload)});
    let data;
    try { data = await response.json(); } catch (_) { throw new Error('Unable to save. Please reload and try again.'); }
    if (!response.ok || !data.success) throw new Error(data.error || 'Unable to save this task.');
    return data;
  }
  function status(message, failed = false) {
    feedback.textContent = message;
    feedback.className = failed ? 'text-danger' : 'text-success';
  }
  async function load() {
    const data = await request(url);
    list.replaceChildren();
    if (!data.tasks.length) list.textContent = 'No tasks for today yet.';
    data.tasks.forEach(task => {
      const row = document.createElement('div'); row.className = 'task-item'; row.dataset.id = task.id;
      const title = document.createElement('span'); title.textContent = task.title;
      if (task.completed) { title.style.textDecoration = 'line-through'; title.style.opacity = '.6'; }
      const controls = document.createElement('div'); controls.className = 'task-actions';
      [['complete', task.completed ? 'Reopen task' : 'Mark as done', task.completed ? 'bi-arrow-counterclockwise' : 'bi-check-circle'], ['delete', 'Delete task', 'bi-trash']].forEach(([action, label, icon]) => {
        const button = document.createElement('button'); button.type = 'button'; button.className = 'btn btn-sm btn-link'; button.setAttribute('aria-label', label); button.title = label;
        const image = document.createElement('i'); image.className = 'bi ' + icon; button.append(image);
        button.addEventListener('click', async () => {
          button.disabled = true;
          try { await request(url + task.id + '/', {action: action === 'complete' && task.completed ? 'reopen' : action}); await load(); status(action === 'delete' ? 'Task deleted.' : 'Task updated.'); }
          catch (error) { status(error.message, true); button.disabled = false; }
        });
        controls.append(button);
      });
      row.append(title, controls); list.append(row);
    });
  }
  form.addEventListener('submit', async event => {
    event.preventDefault();
    const button = form.querySelector('button'); if (button.disabled) return;
    button.disabled = true;
    try { await request(url, {title: form.elements.title.value}); form.reset(); await load(); status('Task saved.'); }
    catch (error) { status(error.message, true); }
    finally { button.disabled = false; }
  });
  // Legacy lists were shared by every account on this browser. Import only
  // after the current user reviews and confirms ownership of the displayed list.
  const importButton = document.getElementById('import-legacy-tasks');
  let legacy = [];
  try { const stored = JSON.parse(localStorage.getItem('dashboard-tasks') || '[]'); if (Array.isArray(stored)) legacy = stored; } catch (_) {}
  if (legacy.length && importButton) {
    importButton.hidden = false;
    importButton.addEventListener('click', async () => {
      if (!window.confirm('Import these old browser tasks into ' + root.dataset.account + '? Only continue if they belong to you. They will be removed from the old browser list after saving.\n\n' + legacy.map(item => item.text).join('\n'))) return;
      importButton.disabled = true;
      try { await request(url, {import_tasks: legacy}); localStorage.removeItem('dashboard-tasks'); importButton.hidden = true; await load(); status('Previous tasks saved to your account.'); }
      catch (error) { status(error.message, true); importButton.disabled = false; }
    });
  }
  load().catch(error => { list.textContent = 'Tasks could not be loaded.'; status(error.message, true); });
})();
