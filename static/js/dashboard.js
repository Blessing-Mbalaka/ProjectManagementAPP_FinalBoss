// Sidebar Toggle Functionality
const toggleBtn = document.getElementById('toggleBtn');
const sidebar = document.getElementById('sidebar');
const mainContent = document.getElementById('mainContent');
const mobileMenuBtn = document.getElementById('mobileMenuBtn');

// Only attach event listeners if elements exist
if (toggleBtn && sidebar && mainContent) {
    toggleBtn.addEventListener('click', function () {
        sidebar.classList.toggle('collapsed');
        mainContent.classList.toggle('expanded');

        // Change the icon based on state
        const icon = toggleBtn.querySelector('i');
        if (sidebar.classList.contains('collapsed')) {
            icon.classList.remove('bi-chevron-left');
            icon.classList.add('bi-chevron-right');
        } else {
            icon.classList.remove('bi-chevron-right');
            icon.classList.add('bi-chevron-left');
        }
    });
}

// Mobile Menu Toggle
if (mobileMenuBtn && sidebar) {
    mobileMenuBtn.addEventListener('click', function () {
        sidebar.classList.toggle('show');
    });
}

// Close sidebar when clicking outside on mobile
document.addEventListener('click', function (event) {
    if (sidebar && window.innerWidth <= 768 && !sidebar.contains(event.target) && event.target !== mobileMenuBtn) {
        sidebar.classList.remove('show');
    }
});

// File Upload Management
const fileUploadEl = document.getElementById('file-upload');
if (fileUploadEl) {
    fileUploadEl.addEventListener('change', function (e) {
        const fileName = e.target.files[0]?.name || 'No file selected';
        const selectedFile = document.getElementById('selected-file-name');
        if (selectedFile) {
            selectedFile.textContent = `Selected: ${fileName}`;
        }
    });
}

const confirmUploadBtn = document.getElementById('confirm-upload');
if (confirmUploadBtn) {
    confirmUploadBtn.addEventListener('click', function () {
        const fileNameInput = document.getElementById('file-name');
        const fileUpload = document.getElementById('file-upload');
        if (fileNameInput && fileUpload) {
            const fileName = fileNameInput.value.trim() || fileUpload.files[0]?.name || 'Untitled';

            if (fileUpload.files.length > 0) {
                const fileId = 'file-' + Date.now();
                const uploadItem = document.createElement('div');
                uploadItem.className = 'upload-item';
                uploadItem.id = fileId;
                uploadItem.innerHTML = `
                    <span>${fileName}</span>
                    <div class="upload-actions">
                        <i class="bi-pencil text-primary" title="Rename" onclick="renameFile('${fileId}')"></i>
                        <i class="bi-trash text-danger" title="Delete" onclick="removeFile('${fileId}')"></i>
                    </div>
                `;
                const uploadsList = document.getElementById('uploads-list');
                if (uploadsList) {
                    uploadsList.appendChild(uploadItem);
                }

                // Reset form
                fileNameInput.value = '';
                fileUpload.value = '';
                const selectedFile = document.getElementById('selected-file-name');
                if (selectedFile) selectedFile.textContent = '';

                // Close modal
                const uploadModal = document.getElementById('uploadModal');
                if (uploadModal) {
                    try {
                        const modal = bootstrap.Modal.getInstance(uploadModal);
                        if (modal) modal.hide();
                    } catch (e) {
                        console.warn('Modal error:', e);
                    }
                }

                saveUploads();
            } else {
                alert('Please select a file to upload');
            }
        }
    });
}

// Rename file
function renameFile(fileId) {
    const fileItem = document.getElementById(fileId);
    const currentName = fileItem.querySelector('span').textContent;
    const newName = prompt('Enter new file name:', currentName);

    if (newName && newName !== currentName) {
        fileItem.querySelector('span').textContent = newName;
        saveUploads();
    }
}

// Remove file
function removeFile(fileId) {
    if (confirm('Are you sure you want to delete this file?')) {
        document.getElementById(fileId).remove();
        saveUploads();
    }
}

// Save uploads to localStorage
function saveUploads() {
    const uploads = [];
    document.querySelectorAll('#uploads-list .upload-item').forEach(upload => {
        uploads.push({
            name: upload.querySelector('span').textContent
        });
    });
    localStorage.setItem('dashboard-uploads', JSON.stringify(uploads));
}

// Load uploads from localStorage
function loadUploads() {
    const savedUploads = JSON.parse(localStorage.getItem('dashboard-uploads')) || [];
    const uploadsList = document.getElementById('uploads-list');
    if (!uploadsList) return;
    uploadsList.innerHTML = '';

    savedUploads.forEach(upload => {
        const fileId = 'file-' + Date.now();
        const uploadItem = document.createElement('div');
        uploadItem.className = 'upload-item';
        uploadItem.id = fileId;
        uploadItem.innerHTML = `
            <span>${upload.name}</span>
            <div class="upload-actions">
                <i class="bi-pencil text-primary" title="Rename" onclick="renameFile('${fileId}')"></i>
                <i class="bi-trash text-danger" title="Delete" onclick="removeFile('${fileId}')"></i>
            </div>
        `;
        uploadsList.appendChild(uploadItem);
    });
}

// Confetti animation
function createConfetti() {
    const colors = ['#e74c3c', '#3498db', '#2ecc71', '#f1c40f', '#9b59b6', '#1abc9c'];

    for (let i = 0; i < 50; i++) {
        const confetti = document.createElement('div');
        confetti.className = 'confetti';
        confetti.style.backgroundColor = colors[Math.floor(Math.random() * colors.length)];
        confetti.style.left = Math.random() * 100 + 'vw';
        confetti.style.top = '100vh';
        confetti.style.width = Math.random() * 10 + 5 + 'px';
        confetti.style.height = Math.random() * 10 + 5 + 'px';
        confetti.style.animationDuration = Math.random() * 1 + 0.5 + 's';
        document.body.appendChild(confetti);

        // Remove confetti after animation
        setTimeout(() => {
            confetti.remove();
        }, 1000);
    }
}

// Initialize on load
window.addEventListener('load', function () {
    loadUploads();

    // Initialize sidebar state based on screen size
    if (sidebar && mainContent && window.innerWidth <= 768) {
        sidebar.classList.remove('collapsed');
        sidebar.classList.remove('show');
        mainContent.classList.remove('expanded');
    }
});

// Handle window resize
window.addEventListener('resize', function () {
    if (sidebar && window.innerWidth > 768) {
        sidebar.classList.remove('show');
    }
});
