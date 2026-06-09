document.addEventListener('DOMContentLoaded', function() {
    const copyButtons = document.querySelectorAll('.copy-btn');
    copyButtons.forEach(btn => {
        btn.addEventListener('click', function() {
            const targetId = this.getAttribute('data-target');
            const textToCopy = document.getElementById(targetId).innerText;
            
            navigator.clipboard.writeText(textToCopy).then(() => {
                const originalText = this.innerText;
                this.innerText = 'Copied!';
                setTimeout(() => { this.innerText = originalText; }, 1500);
            }).catch(err => {
                console.error('Failed to copy text: ', err);
            });
        });
    });
});