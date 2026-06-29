document.addEventListener('DOMContentLoaded', function() {
    const table = document.getElementById('transactions-table');

    table.addEventListener('click', async function(event) {
        const target = event.target;
        
        if (target.classList.contains('btn-complete') || target.classList.contains('btn-fail')) {
            const txnId = target.getAttribute('data-id');
            const isComplete = target.classList.contains('btn-complete');
            const endpoint = isComplete ? `/api/transactions/${txnId}/complete` : `/api/transactions/${txnId}/fail`;
            
            // Disable buttons while processing
            const row = document.getElementById(`row-${txnId}`);
            const actionCell = row.querySelector('.action-cell');
            actionCell.innerHTML = 'Processing...';

            try {
                const response = await fetch(endpoint, { method: 'POST' });
                const data = await response.json();

                if (data.success) {
                    // Update status cell
                    const statusCell = row.querySelector('.status-cell');
                    statusCell.innerText = data.new_status;
                    statusCell.style.color = data.new_status === 'Success' ? 'green' : 'red';
                    
                    // Remove action buttons
                    actionCell.innerHTML = '-';
                } else {
                    alert('Error: ' + data.message);
                    // Restore buttons on failure
                    actionCell.innerHTML = `
                        <button class="btn-complete" data-id="${txnId}">Complete</button>
                        <button class="btn-fail" data-id="${txnId}">Fail</button>
                    `;
                }
            } catch (error) {
                alert('Network error occurred.');
                actionCell.innerHTML = `
                    <button class="btn-complete" data-id="${txnId}">Complete</button>
                    <button class="btn-fail" data-id="${txnId}">Fail</button>
                `;
            }
        }
    });
});