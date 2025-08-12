document.addEventListener("DOMContentLoaded", function () {
  const statusSel = document.getElementById("statusFilter");
  const userSel = document.getElementById("userFilter");

  function filterProjects() {
    const status = statusSel.value; // 'all' or e.g. 'in-progress'
    const user = userSel.value;     // 'all' or username

    document.querySelectorAll("#projectTableBody tr").forEach(row => {
      const rowStatus = row.dataset.status; // e.g. 'in-progress'
      const rowUser = row.dataset.user;

      const matchStatus = (status === "all") || (rowStatus === status);
      const matchUser   = (user === "all")   || (rowUser === user);

      row.style.display = (matchStatus && matchUser) ? "" : "none";
    });
  }

  statusSel.addEventListener("change", filterProjects);
  userSel.addEventListener("change", filterProjects);

  // Gantt modal (also clear previous content before append)
  document.querySelectorAll('.view-gantt-btn').forEach(btn => {
    btn.addEventListener('click', function () {
      const projectName = this.getAttribute('data-project-name');
      const progress = this.getAttribute('data-progress');
      const tasks = JSON.parse(this.getAttribute('data-tasks') || '[]');

      document.getElementById('ganttModalLabel').textContent = `Gantt Chart: ${projectName}`;
      document.getElementById('ganttProjectTitle').innerHTML = `<strong>Project:</strong> ${projectName}`;
      const bar = document.getElementById('ganttProgressBar');
      bar.style.width = `${progress}%`;
      bar.textContent = `${progress}%`;

      const pct = document.getElementById('ganttProgressPercent');
      pct.innerHTML = `<strong>Progress:</strong> ${progress}% Completed`;

      let taskHtml = '';
      tasks.forEach(t => {
        const due = t.due || '—';
        const pct = Number.isFinite(t.progress) ? t.progress : 0;
        taskHtml += `
          <div class="mt-3">
            <strong>${t.title}</strong> (Due: ${due})<br>
            <div class="progress mt-1" style="height: 12px;">
              <div class="progress-bar bg-info" style="width: ${pct}%;">
                ${pct}%
              </div>
            </div>
          </div>`;
      });
      document.getElementById('ganttProjectTitle').insertAdjacentHTML('beforeend', taskHtml);

      new bootstrap.Modal(document.getElementById('ganttModal')).show();
    });
  });
});

