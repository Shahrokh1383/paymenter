document.addEventListener('DOMContentLoaded', function() {
    const cardInput = document.getElementById('card_number');
    if (cardInput) {
        cardInput.addEventListener('input', function(e) {
            let value = e.target.value.replace(/\s+/g, '').replace(/[^0-9]/gi, '');
            if (value.length > 16) value = value.substring(0, 16);
            e.target.value = value;
        });
    }
    const otpInput = document.getElementById('otp_code');
    if (otpInput) {
        otpInput.addEventListener('input', function(e) {
            let value = e.target.value.replace(/\s+/g, '').replace(/[^0-9]/gi, '');
            if (value.length > 5) value = value.substring(0, 5);
            e.target.value = value;
        });
    }
});