document.addEventListener('DOMContentLoaded', function () {
    const costCentreDropdown = document.getElementById("costCentreDropdown");
    const addCostCentreForm = document.getElementById("addCostCentreForm");
    const expenditureTable = document.querySelector("#expenditureTable tbody");

    // ✅ Date Range Calculator for Expenditure Modal
    const dateFromInput = document.querySelector('.expenditure-date-from');
    const dateToInput = document.querySelector('.expenditure-date-to');
    const amountInput = document.querySelector('.expenditure-amount');
    const costCentreSelect = document.querySelector('.expenditure-cost-centre');
    const monthsDisplay = document.querySelector('.expenditure-months-display');
    const totalCostDisplay = document.querySelector('.expenditure-total-cost-display');
    const moaAvailableDisplay = document.querySelector('.expenditure-moa-available-display');
    const moaRemainingDisplay = document.querySelector('.expenditure-moa-remaining-display');
    const monthHidden = document.querySelector('.expenditure-month');

    function calculateMonths(dateFrom, dateTo) {
        if (!dateFrom || !dateTo) return 0;
        
        const from = new Date(dateFrom);
        const to = new Date(dateTo);
        
        // Calculate days difference
        const daysCount = Math.floor((to - from) / (1000 * 60 * 60 * 24));
        
        // Convert days to months (using 30 days per month)
        const months = Math.max(1, Math.round(daysCount / 30));
        return months;
    }

    function formatCurrency(value) {
        return 'R ' + parseFloat(value).toLocaleString('en-ZA', {
            minimumFractionDigits: 2,
            maximumFractionDigits: 2
        });
    }

    function updateCalculations() {
        const dateFrom = dateFromInput ? dateFromInput.value : null;
        const dateTo = dateToInput ? dateToInput.value : null;
        const amount = amountInput ? parseFloat(amountInput.value) || 0 : 0;
        const selectedOption = costCentreSelect ? costCentreSelect.options[costCentreSelect.selectedIndex] : null;
        const moaAmount = selectedOption ? parseFloat(selectedOption.dataset.moa) || 0 : 0;

        // Calculate months
        const months = calculateMonths(dateFrom, dateTo);
        if (monthsDisplay) {
            monthsDisplay.textContent = months;
        }

        // Set hidden month field to start date (for backward compatibility)
        if (monthHidden && dateFrom) {
            const dateObj = new Date(dateFrom);
            monthHidden.value = dateObj.toISOString().split('T')[0];
        }

        // Calculate total cost (amount × months)
        const totalCost = amount * months;
        if (totalCostDisplay) {
            totalCostDisplay.textContent = formatCurrency(totalCost);
        }

        // Calculate MOA information
        if (moaAvailableDisplay) {
            moaAvailableDisplay.textContent = formatCurrency(moaAmount);
        }

        // Calculate remaining MOA after deduction
        const moaRemaining = moaAmount - totalCost;
        if (moaRemainingDisplay) {
            moaRemainingDisplay.textContent = formatCurrency(moaRemaining);
            // Change color based on remaining amount
            if (moaRemaining < 0) {
                moaRemainingDisplay.style.color = '#dc3545'; // Red for over budget
                moaRemainingDisplay.innerHTML += ' <span style="font-size: 0.8em;">(Over budget)</span>';
            } else if (moaRemaining < totalCost * 0.2) {
                moaRemainingDisplay.style.color = '#ff6b6b'; // Orange for low budget
            } else {
                moaRemainingDisplay.style.color = '#28a745'; // Green for healthy budget
                moaRemainingDisplay.innerHTML = formatCurrency(moaRemaining);
            }
        }
    }

    // Attach event listeners for date and amount inputs
    if (dateFromInput) {
        dateFromInput.addEventListener('change', updateCalculations);
    }
    if (dateToInput) {
        dateToInput.addEventListener('change', updateCalculations);
    }
    if (amountInput) {
        amountInput.addEventListener('input', updateCalculations);
    }
    if (costCentreSelect) {
        costCentreSelect.addEventListener('change', updateCalculations);
    }

    // ✅ Corrected AJAX Form Submission for Cost Centre
    addCostCentreForm.addEventListener('submit', function (e) {
        e.preventDefault();

        const formData = new FormData(addCostCentreForm);
        const formActionUrl = addCostCentreForm.dataset.url;

        fetch(formActionUrl, {
            method: 'POST',
            headers: {
                'X-CSRFToken': '{{ csrf_token }}'
            },
            body: formData
        })
        .then(response => {
            if (response.ok) {
                const modal = bootstrap.Modal.getInstance(document.getElementById('addCostCentreModal'));
                modal.hide();
                location.reload();
            } else {
                alert('Failed to add cost centre.');
            }
        })
        .catch(error => {
            console.error('Error adding cost centre:', error);
        });
    });

    // ✅ Fetch expenditures for selected cost centre
    if (costCentreDropdown) {
        costCentreDropdown.addEventListener("change", function () {
            const selectedId = this.value;
            if (selectedId) {
                fetch(`/finance/expenditures/${selectedId}/`)
                    .then(response => response.json())
                    .then(data => {
                        populateExpenditureTable(data.expenditures);
                    });
            }
        });
    }

    // ✅ Expenditure Table Loader
    function populateExpenditureTable(expenditures) {
        expenditureTable.innerHTML = "";
        if (expenditures.length === 0) {
            expenditureTable.innerHTML = `<tr><td colspan="13" class="text-center">No expenditures recorded.</td></tr>`;
            return;
        }

        expenditures.forEach(record => {
            const categories = {
                Salary: '', Bursaries: '', Invoices: '', Fitness: '', Equipment: '', Travel: ''
            };
            categories[record.category] = `R ${parseFloat(record.amount).toLocaleString()}`;

            expenditureTable.innerHTML += `
                <tr>
                    <td>${record.month}</td>
                    <td>${record.name}</td>
                    <td>${categories['Salary']}</td>
                    <td>${categories['Bursaries']}</td>
                    <td>${categories['Invoices']}</td>
                    <td>${categories['Fitness']}</td>
                    <td>${categories['Equipment']}</td>
                    <td>${categories['Travel']}</td>
                    <td>R ${parseFloat(record.amount).toLocaleString()}</td>
                    <td>R ${parseFloat(record.opening_balance).toLocaleString()}</td>
                    <td>R ${parseFloat(record.closing_balance).toLocaleString()}</td>
                    <td>R ${parseFloat(record.oracle_balance).toLocaleString()}</td>
                    <td>R ${parseFloat(record.closing_balance).toLocaleString()}</td>
                </tr>
            `;
        });
    }

    // ===========================
    // BUDGET FORECAST CALCULATIONS
    // ===========================
    
    function setupForecastCalculations() {
        console.log('🔧 setupForecastCalculations() called');
        
        const forecastDateFromInput = document.querySelector('.forecast-date-from');
        const forecastDateToInput = document.querySelector('.forecast-date-to');
        const forecastAmountInput = document.querySelector('.forecast-amount');
        const forecastMonthsDisplay = document.querySelector('.forecast-months-display');
        const forecastTotalCostDisplay = document.querySelector('.forecast-total-cost-display');

        if (!forecastDateFromInput || !forecastDateToInput || !forecastAmountInput) {
            console.warn('⚠️ Forecast input elements not found');
            return;
        }

        function calculateMonthsForecast(dateFrom, dateTo) {
            if (!dateFrom || !dateTo) return 0;
            const from = new Date(dateFrom);
            const to = new Date(dateTo);
            const daysCount = Math.floor((to - from) / (1000 * 60 * 60 * 24));
            return Math.max(1, Math.round(daysCount / 30));
        }

        function updateForecastCalculations() {
            const dateFrom = forecastDateFromInput.value;
            const dateTo = forecastDateToInput.value;
            const amount = parseFloat(forecastAmountInput.value) || 0;

            const months = calculateMonthsForecast(dateFrom, dateTo);
            if (forecastMonthsDisplay) {
                forecastMonthsDisplay.textContent = months;
            }

            const totalCost = amount * months;
            if (forecastTotalCostDisplay) {
                forecastTotalCostDisplay.textContent = formatCurrency(totalCost);
            }
        }

        // Attach listeners
        forecastDateFromInput.addEventListener('change', updateForecastCalculations);
        forecastDateFromInput.addEventListener('blur', updateForecastCalculations);
        forecastDateToInput.addEventListener('change', updateForecastCalculations);
        forecastDateToInput.addEventListener('blur', updateForecastCalculations);
        forecastAmountInput.addEventListener('input', updateForecastCalculations);
        forecastAmountInput.addEventListener('change', updateForecastCalculations);

        // Initial update
        updateForecastCalculations();
        console.log('✅ setupForecastCalculations() ready');
    }

    // Setup forecast calculations when modal is shown
    const addForecastModal = document.getElementById('addForecastModal');
    
    if (addForecastModal) {
        addForecastModal.addEventListener('show.bs.modal', function() {
            // Reset form fields to prevent stale data
            const forecastDateFromInput = document.querySelector('.forecast-date-from');
            const forecastDateToInput = document.querySelector('.forecast-date-to');
            const forecastCostCentreInput = document.querySelector('.forecast-cost-centre');
            const forecastNameInput = document.querySelector('[name="name"]');
            const forecastCategoryInput = document.querySelector('[name="category"]');
            const forecastAmountInput = document.querySelector('.forecast-amount');
            
            if (forecastDateFromInput) forecastDateFromInput.value = '';
            if (forecastDateToInput) forecastDateToInput.value = '';
            if (forecastCostCentreInput) forecastCostCentreInput.value = '';
            if (forecastNameInput) forecastNameInput.value = '';
            if (forecastCategoryInput) forecastCategoryInput.value = '';
            if (forecastAmountInput) forecastAmountInput.value = '';
            
            // Reset display values
            const forecastMonthsDisplay = document.querySelector('.forecast-months-display');
            const forecastTotalCostDisplay = document.querySelector('.forecast-total-cost-display');
            if (forecastMonthsDisplay) forecastMonthsDisplay.textContent = '0';
            if (forecastTotalCostDisplay) forecastTotalCostDisplay.textContent = 'R 0.00';
            
            console.log('✨ Form reset for new entry');
            setupForecastCalculations();
        });
    }

    // Log form submission for debugging
    const addBudgetForecastForm = document.getElementById('addBudgetForecastForm');
    if (addBudgetForecastForm) {
        addBudgetForecastForm.addEventListener('submit', function(e) {
            console.log('📤 FORM SUBMITTING - Reading actual form values:');
            
            // Ensure date fields have full yyyy-MM-dd format
            const dateFromInput = document.querySelector('.forecast-date-from');
            const dateToInput = document.querySelector('.forecast-date-to');
            
            let date_from = dateFromInput.value;
            let date_to = dateToInput.value;
            
            // Pad dates with "-01" if they're missing the day (yyyy-MM format)
            if (date_from && date_from.length === 7) {
                date_from += '-01';
                dateFromInput.value = date_from;
                console.log('  📅 Padded date_from:', date_from);
            }
            if (date_to && date_to.length === 7) {
                date_to += '-01';
                dateToInput.value = date_to;
                console.log('  📅 Padded date_to:', date_to);
            }
            
            const cost_centre = document.querySelector('.forecast-cost-centre').value;
            const name = document.querySelector('[name="name"]').value;
            const category = document.querySelector('[name="category"]').value;
            const amount = document.querySelector('.forecast-amount').value;
            
            console.log('  date_from:', date_from);
            console.log('  date_to:', date_to);
            console.log('  cost_centre:', cost_centre);
            console.log('  name:', name);
            console.log('  category:', category);
            console.log('  amount:', amount);
        });
    }

    // ===========================
    // BUDGET FORECAST TABLE LOADER
    // ===========================
    
    const forecastTableBody = document.querySelector('#forecastTableBody');
    const releaseForecastsBtn = document.querySelector('#releaseForecastsBtn');
    const currentCostCentreForForecasts = {};

    if (costCentreDropdown) {
        costCentreDropdown.addEventListener("change", function () {
            const selectedId = this.value;
            currentCostCentreForForecasts.id = selectedId;
            
            if (selectedId) {
                // Load forecasts
                fetch(`/adminpanel/finance/forecasts/${selectedId}/`)
                    .then(response => {
                        if (!response.ok) throw new Error('Failed to load forecasts');
                        return response.json();
                    })
                    .then(data => {
                        if (data.forecasts) {
                            populateForecastTable(data.forecasts);
                        }
                    })
                    .catch(error => {
                        console.error('Error loading forecasts:', error);
                        if (forecastTableBody) {
                            forecastTableBody.innerHTML = '<tr><td colspan="8" class="text-center text-danger">Error loading forecasts</td></tr>';
                        }
                    });
            } else {
                if (forecastTableBody) {
                    forecastTableBody.innerHTML = '<tr><td colspan="8" class="text-center text-muted">Select a cost centre to view forecasts</td></tr>';
                }
                if (releaseForecastsBtn) releaseForecastsBtn.style.display = 'none';
            }
        });
    }

    function populateForecastTable(forecasts) {
        if (!forecastTableBody) return;
        
        forecastTableBody.innerHTML = "";
        
        if (!forecasts || forecasts.length === 0) {
            forecastTableBody.innerHTML = '<tr><td colspan="8" class="text-center text-muted">No forecasts yet</td></tr>';
            if (releaseForecastsBtn) releaseForecastsBtn.style.display = 'none';
            return;
        }

        // Show release button if there are forecasts
        if (releaseForecastsBtn) {
            releaseForecastsBtn.style.display = 'block';
        }

        forecasts.forEach(forecast => {
            const period = forecast.date_from && forecast.date_to 
                ? `${forecast.date_from} to ${forecast.date_to}`
                : forecast.month || 'N/A';
            
            const categoryColors = {
                'Salary': '#ffc107',
                'Bursaries': '#17a2b8',
                'Invoices': '#6c757d',
                'Fitness': '#20c997',
                'Equipment': '#6f42c1',
                'Travel': '#fd7e14'
            };

            const categoryColor = categoryColors[forecast.category] || '#6c757d';

            forecastTableBody.innerHTML += `
                <tr>
                    <td><small>${period}</small></td>
                    <td>${forecast.name}</td>
                    <td><span class="badge" style="background-color: ${categoryColor};">${forecast.category}</span></td>
                    <td>R ${parseFloat(forecast.amount).toLocaleString('en-ZA', {minimumFractionDigits: 2, maximumFractionDigits: 2})}</td>
                    <td><span class="badge bg-info">${forecast.months}</span></td>
                    <td><strong>R ${parseFloat(forecast.total_cost).toLocaleString('en-ZA', {minimumFractionDigits: 2, maximumFractionDigits: 2})}</strong></td>
                    <td><span class="badge bg-warning text-dark">Draft</span></td>
                    <td>
                        <form method="POST" action="/finance/delete-budget-forecast/${forecast.id}/" style="display: inline;">
                            <button type="submit" class="btn btn-sm btn-danger" title="Delete forecast" onclick="return confirm('Delete this forecast?');">🗑️</button>
                        </form>
                    </td>
                </tr>
            `;
        });
    }

    // Release Forecasts Handler (initialize only once)
    if (releaseForecastsBtn) {
        releaseForecastsBtn.addEventListener('click', function (e) {
            e.preventDefault();
            const costCentreId = currentCostCentreForForecasts.id;
            if (!costCentreId) {
                alert('Please select a cost centre first');
                return;
            }

            if (confirm('Release all forecasts to Monthly Expenditure Tracker? This cannot be undone.')) {
                const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]') 
                    ? document.querySelector('[name=csrfmiddlewaretoken]').value 
                    : getCookie('csrftoken');
                
                fetch(`/adminpanel/finance/release-forecasts/${costCentreId}/`, {
                    method: 'POST',
                    headers: {
                        'X-CSRFToken': csrfToken,
                        'Content-Type': 'application/x-www-form-urlencoded'
                    }
                })
                .then(response => {
                    if (response.ok) {
                        alert('Forecasts released successfully!');
                        location.reload();
                    } else {
                        return response.text().then(text => {
                            throw new Error('Error releasing forecasts: ' + text);
                        });
                    }
                })
                .catch(error => {
                    console.error('Error:', error);
                    alert('Error: ' + error.message);
                });
            }
        });
    }

    // Helper function to get CSRF token
    function getCookie(name) {
        let cookieValue = null;
        if (document.cookie && document.cookie !== '') {
            const cookies = document.cookie.split(';');
            for (let i = 0; i < cookies.length; i++) {
                const cookie = cookies[i].trim();
                if (cookie.substring(0, name.length + 1) === (name + '=')) {
                    cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                    break;
                }
            }
        }
        return cookieValue;
    }

    // ===========================
    // BUDGET FORECAST ARCHIVE
    // ===========================
    
    const archiveModal = document.getElementById('archiveForecastsModal');
    const viewArchiveBtn = document.getElementById('viewArchiveBtn');
    const selectAllArchive = document.getElementById('selectAllArchive');
    const releaseSelectedBtn = document.getElementById('releaseSelectedBtn');
    const releaseAllArchiveBtn = document.getElementById('releaseAllArchiveBtn');
    const archiveTableBody = document.getElementById('archiveTableBody');
    const archiveCostCentreFilter = document.getElementById('archiveCostCentreFilter');
    
    let archiveForecasts = [];
    let allArchiveForecasts = [];

    if (viewArchiveBtn && archiveModal) {
        archiveModal.addEventListener('show.bs.modal', function() {
            loadArchiveCostCentres();
            loadAllArchiveForecasts();
        });
    }

    function loadArchiveCostCentres() {
        // Populate the dropdown with cost centres from the main dropdown
        if (costCentreDropdown) {
            const options = costCentreDropdown.querySelectorAll('option');
            archiveCostCentreFilter.innerHTML = '<option value="">All Cost Centres</option>';
            options.forEach(option => {
                if (option.value && option.value !== '') {
                    const newOption = document.createElement('option');
                    newOption.value = option.value;
                    newOption.textContent = option.textContent;
                    archiveCostCentreFilter.appendChild(newOption);
                }
            });
        }
    }

    function loadAllArchiveForecasts() {
        // Load forecasts from the currently selected cost centre OR all if available
        const selectedCostCentreId = archiveCostCentreFilter.value;
        
        if (selectedCostCentreId) {
            // Load for specific cost centre
            fetch(`/adminpanel/finance/forecasts/${selectedCostCentreId}/`)
                .then(response => {
                    if (!response.ok) throw new Error('Failed to load');
                    return response.json();
                })
                .then(data => {
                    allArchiveForecasts = data.forecasts || [];
                    archiveForecasts = allArchiveForecasts;
                    populateArchiveTable(archiveForecasts);
                })
                .catch(error => {
                    console.error('Error loading archive:', error);
                    archiveTableBody.innerHTML = '<tr><td colspan="7" class="text-center text-muted">No forecasts available</td></tr>';
                });
        } else {
            // Load all forecasts from all cost centres
            const costCentreIds = Array.from(costCentreDropdown.querySelectorAll('option'))
                .filter(opt => opt.value && opt.value !== '')
                .map(opt => opt.value);
            
            if (costCentreIds.length === 0) {
                archiveTableBody.innerHTML = '<tr><td colspan="7" class="text-center text-muted">No cost centres available</td></tr>';
                return;
            }

            let allForecasts = [];
            let loaded = 0;
            let errors = 0;

            costCentreIds.forEach(ccId => {
                fetch(`/adminpanel/finance/forecasts/${ccId}/`)
                    .then(response => {
                        loaded++;
                        if (!response.ok) {
                            errors++;
                            console.log(`No forecasts for CC ${ccId} (404)`);
                            return null;
                        }
                        return response.json();
                    })
                    .then(data => {
                        if (data && data.forecasts) {
                            allForecasts = allForecasts.concat(data.forecasts);
                        }
                        if (loaded === costCentreIds.length) {
                            allArchiveForecasts = allForecasts;
                            archiveForecasts = allForecasts;
                            populateArchiveTable(archiveForecasts);
                        }
                    })
                    .catch(error => {
                        loaded++;
                        errors++;
                        console.error('Error loading forecasts for CC', ccId, error);
                        if (loaded === costCentreIds.length) {
                            allArchiveForecasts = allForecasts;
                            archiveForecasts = allForecasts;
                            populateArchiveTable(archiveForecasts);
                        }
                    });
            });
        }
    }

    function loadArchiveForecasts() {
        loadAllArchiveForecasts();
    }

    function populateArchiveTable(forecasts) {
        archiveTableBody.innerHTML = '';
        
        if (!forecasts || forecasts.length === 0) {
            archiveTableBody.innerHTML = '<tr><td colspan="7" class="text-center text-muted">No draft forecasts</td></tr>';
            selectAllArchive.checked = false;
            selectAllArchive.disabled = true;
            return;
        }

        selectAllArchive.disabled = false;

        forecasts.forEach((forecast, idx) => {
            const period = forecast.date_from && forecast.date_to 
                ? `${forecast.date_from} to ${forecast.date_to}`
                : forecast.month || 'N/A';
            
            const categoryColors = {
                'Salary': '#ffc107',
                'Bursaries': '#17a2b8',
                'Invoices': '#6c757d',
                'Fitness': '#20c997',
                'Equipment': '#6f42c1',
                'Travel': '#fd7e14'
            };

            const categoryColor = categoryColors[forecast.category] || '#6c757d';

            archiveTableBody.innerHTML += `
                <tr>
                    <td><input type="checkbox" class="archive-checkbox" data-id="${forecast.id}" data-cost="${forecast.total_cost}" data-cc="${forecast.cost_centre_id}"></td>
                    <td><small>${period}</small></td>
                    <td>${forecast.name}</td>
                    <td><span class="badge" style="background-color: ${categoryColor};">${forecast.category}</span></td>
                    <td>R ${parseFloat(forecast.amount).toLocaleString('en-ZA', {minimumFractionDigits: 2, maximumFractionDigits: 2})}</td>
                    <td><span class="badge bg-info">${forecast.months}</span></td>
                    <td><strong>R ${parseFloat(forecast.total_cost).toLocaleString('en-ZA', {minimumFractionDigits: 2, maximumFractionDigits: 2})}</strong></td>
                </tr>
            `;
        });

        // Add event listeners to checkboxes
        document.querySelectorAll('.archive-checkbox').forEach(checkbox => {
            checkbox.addEventListener('change', updateArchiveSummary);
        });

        selectAllArchive.addEventListener('change', function() {
            document.querySelectorAll('.archive-checkbox').forEach(cb => {
                cb.checked = this.checked;
            });
            updateArchiveSummary();
        });
    }

    function updateArchiveSummary() {
        const selectedCheckboxes = document.querySelectorAll('.archive-checkbox:checked');
        let total = 0;
        selectedCheckboxes.forEach(cb => {
            total += parseFloat(cb.dataset.cost) || 0;
        });

        if (selectedCheckboxes.length > 0) {
            document.getElementById('archiveSummary').style.display = 'block';
            document.getElementById('selectedTotal').textContent = formatCurrency(total);
        } else {
            document.getElementById('archiveSummary').style.display = 'none';
        }
    }

    if (releaseSelectedBtn) {
        releaseSelectedBtn.addEventListener('click', function() {
            const selectedIds = Array.from(document.querySelectorAll('.archive-checkbox:checked'))
                .map(cb => cb.dataset.id);

            if (selectedIds.length === 0) {
                alert('Please select at least one forecast');
                return;
            }

            if (confirm(`Release ${selectedIds.length} forecast(s)? This cannot be undone.`)) {
                releaseForecasts(selectedIds);
            }
        });
    }

    if (archiveCostCentreFilter) {
        archiveCostCentreFilter.addEventListener('change', function() {
            loadAllArchiveForecasts();
        });
    }

    if (releaseAllArchiveBtn) {
        releaseAllArchiveBtn.addEventListener('click', function() {
            const allIds = archiveForecasts.map(f => f.id);

            if (allIds.length === 0) {
                alert('No forecasts to release');
                return;
            }

            if (confirm(`Release all ${allIds.length} forecasts? This cannot be undone.`)) {
                releaseForecasts(allIds);
            }
        });
    }

    function releaseForecasts(forecastIds) {
        const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]') 
            ? document.querySelector('[name=csrfmiddlewaretoken]').value 
            : getCookie('csrftoken');
        
        const selectedCostCentreId = archiveCostCentreFilter ? archiveCostCentreFilter.value : null;
        
        // If releasing from archive with "All Cost Centres" selected, group by cost centre
        if (!selectedCostCentreId && archiveForecasts.length > 0) {
            // Group forecasts by cost centre
            const forecastsByCostCentre = {};
            Array.from(document.querySelectorAll('.archive-checkbox:checked')).forEach(cb => {
                const ccId = cb.dataset.cc;
                const forecastId = cb.dataset.id;
                if (!forecastsByCostCentre[ccId]) {
                    forecastsByCostCentre[ccId] = [];
                }
                forecastsByCostCentre[ccId].push(parseInt(forecastId));
            });

            // Release for each cost centre
            let completedCount = 0;
            const totalRequests = Object.keys(forecastsByCostCentre).length;

            Object.keys(forecastsByCostCentre).forEach(ccId => {
                fetch(`/adminpanel/finance/release-forecasts/${ccId}/`, {
                    method: 'POST',
                    headers: {
                        'X-CSRFToken': csrfToken,
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({ forecast_ids: forecastsByCostCentre[ccId] })
                })
                .then(response => {
                    completedCount++;
                    if (completedCount === totalRequests) {
                        alert('All forecasts released successfully!');
                        loadAllArchiveForecasts();
                    }
                })
                .catch(error => {
                    console.error('Error:', error);
                    alert('Error releasing forecasts: ' + error.message);
                });
            });
        } else if (selectedCostCentreId) {
            // Releasing from archive with specific cost centre selected
            const costCentreId = selectedCostCentreId;
            fetch(`/adminpanel/finance/release-forecasts/${costCentreId}/`, {
                method: 'POST',
                headers: {
                    'X-CSRFToken': csrfToken,
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ forecast_ids: forecastIds })
            })
            .then(response => {
                if (response.ok) {
                    alert('Forecasts released successfully!');
                    loadAllArchiveForecasts();
                } else {
                    return response.text().then(text => {
                        throw new Error('Error releasing forecasts: ' + text);
                    });
                }
            })
            .catch(error => {
                console.error('Error:', error);
                alert('Error: ' + error.message);
            });
        } else {
            // Releasing from main forecast modal - use currentCostCentreForForecasts
            const costCentreId = currentCostCentreForForecasts.id;
            fetch(`/adminpanel/finance/release-forecasts/${costCentreId}/`, {
                method: 'POST',
                headers: {
                    'X-CSRFToken': csrfToken,
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ forecast_ids: forecastIds })
            })
            .then(response => {
                if (response.ok) {
                    alert('Forecasts released successfully!');
                    location.reload();
                } else {
                    return response.text().then(text => {
                        throw new Error('Error releasing forecasts: ' + text);
                    });
                }
            })
            .catch(error => {
                console.error('Error:', error);
                alert('Error: ' + error.message);
            });
        }
    }

    // Show View Archive button when forecasts exist
    if (releaseForecastsBtn && viewArchiveBtn) {
        const originalShowArchiveBtn = function() {
            const hasForecastsValue = releaseForecastsBtn.style.display;
            viewArchiveBtn.style.display = hasForecastsValue;
        };
        // Call when cost centre changes
        if (costCentreDropdown) {
            costCentreDropdown.addEventListener('change', originalShowArchiveBtn);
        }
    }
});
