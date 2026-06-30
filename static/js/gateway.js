document.addEventListener('DOMContentLoaded', function() {
    const cardInput = document.getElementById('card_number');
    const otpInput = document.getElementById('otp_code');
    const btnRequestOtp = document.getElementById('btn-request-otp');
    const btnPay = document.getElementById('btn-pay');
    const otpHint = document.getElementById('otp-hint');
    const otpTimer = document.getElementById('otp-timer');
    const token = document.querySelector('input[name="token"]').value;
    
    let countdownInterval = null;

    if (cardInput) {
        cardInput.addEventListener('input', function(e) {
            let value = e.target.value.replace(/\s+/g, '').replace(/[^0-9]/gi, '');
            if (value.length > 16) value = value.substring(0, 16);
            e.target.value = value;
            
            // Enable Request button only if 16 digits are entered
            if (btnRequestOtp) {
                btnRequestOtp.disabled = value.length !== 16;
            }
        });
    }

    if (otpInput) {
        otpInput.addEventListener('input', function(e) {
            let value = e.target.value.replace(/\s+/g, '').replace(/[^0-9]/gi, '');
            if (value.length > 5) value = value.substring(0, 5);
            e.target.value = value;
            
            // Enable Pay button if OTP is 5 digits and timer is active
            if (btnPay && countdownInterval) {
                btnPay.disabled = value.length !== 5;
            }
        });
    }

    if (btnRequestOtp) {
        btnRequestOtp.addEventListener('click', async function() {
            const cardNumber = cardInput.value;
            btnRequestOtp.disabled = true;
            btnRequestOtp.innerText = 'Sending...';

            try {
                const response = await fetch('/gateway/request-otp', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ token: token, card_number: cardNumber })
                });

                const data = await response.json();

                if (response.ok) {
                    otpInput.disabled = false;
                    otpInput.value = ''; // Clear previous OTP if resending
                    otpInput.focus();
                    otpHint.style.display = 'none';
                    startCountdown(data.expires_in);
                    btnRequestOtp.innerText = 'Resend OTP';
                    btnRequestOtp.disabled = false; // Allow resending if needed (will reset timer)
                } else {
                    alert(data.error || 'Failed to send OTP');
                    btnRequestOtp.disabled = false;
                    btnRequestOtp.innerText = 'Request OTP';
                }
            } catch (error) {
                alert('Network error. Please try again.');
                btnRequestOtp.disabled = false;
                btnRequestOtp.innerText = 'Request OTP';
            }
        });
    }

    function startCountdown(seconds) {
        if (countdownInterval) clearInterval(countdownInterval);
        
        let timeLeft = seconds;
        otpTimer.style.display = 'block';
        btnPay.disabled = true; // Disable pay until OTP is fully entered

        countdownInterval = setInterval(() => {
            const mins = Math.floor(timeLeft / 60);
            const secs = timeLeft % 60;
            otpTimer.innerText = `Time remaining: ${mins}:${secs < 10 ? '0' : ''}${secs}`;

            if (timeLeft <= 0) {
                clearInterval(countdownInterval);
                countdownInterval = null;
                otpTimer.innerText = 'OTP Expired. Please request a new one.';
                otpTimer.style.color = 'red';
                otpInput.value = '';
                otpInput.disabled = true;
                btnPay.disabled = true;
                if(btnRequestOtp) {
                    btnRequestOtp.innerText = 'Request OTP';
                    // Re-enable if card is still 16 digits
                    btnRequestOtp.disabled = cardInput.value.length !== 16;
                }
            }
            timeLeft--;
        }, 1000);
    }
});