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
});
