/**
 * AIC LABORET GIRLS BOARDING PRIMARY School - Main JavaScript File
 * Handles all interactive functionality across the website
 */

document.addEventListener('DOMContentLoaded', function() {
    // ======================
    // Mobile Navigation
    // ======================
    const mobileMenuBtn = document.querySelector('.mobile-menu-btn');
    const mainNav = document.querySelector('.main-nav');
    
    if (mobileMenuBtn && mainNav) {
        mobileMenuBtn.addEventListener('click', function() {
            mainNav.classList.toggle('active');
            this.querySelector('i').classList.toggle('fa-times');
        });
    }

    // ======================
    // Login Page Functionality
    // ======================
    if (document.querySelector('.login-page')) {
        // Toggle password visibility
        document.querySelectorAll('.toggle-password').forEach(button => {
            button.addEventListener('click', function() {
                const passwordInput = this.parentElement.querySelector('input');
                const icon = this.querySelector('i');
                
                if (passwordInput.type === 'password') {
                    passwordInput.type = 'text';
                    icon.classList.replace('fa-eye', 'fa-eye-slash');
                } else {
                    passwordInput.type = 'password';
                    icon.classList.replace('fa-eye-slash', 'fa-eye');
                }
            });
        });

        // Login form submission
        const loginForm = document.getElementById('loginForm');
        if (loginForm) {
            loginForm.addEventListener('submit', function(e) {
                e.preventDefault();
                const username = this.querySelector('[name="username"]').value;
                const password = this.querySelector('[name="password"]').value;
                
                // Basic validation
                if (!username || !password) {
                    showAlert('Please fill in all fields', 'error');
                    return;
                }
                
                // Simulate authentication
                simulateLogin(username, password);
            });
        }
    }

    // ======================
    // Registration Page Functionality
    // ======================
    const registerForm = document.getElementById('registerForm');
    if (registerForm) {
        // Show/hide student ID field based on user type
        document.querySelectorAll('input[name="userType"]').forEach(radio => {
            radio.addEventListener('change', function() {
                const studentFields = document.querySelectorAll('.student-field');
                if (this.value === 'student') {
                    studentFields.forEach(field => field.style.display = 'block');
                } else {
                    studentFields.forEach(field => field.style.display = 'none');
                }
            });
        });

        // Password strength checker
        const passwordInput = document.getElementById('password');
        if (passwordInput) {
            passwordInput.addEventListener('input', function() {
                checkPasswordStrength(this.value);
            });
        }

        // Form submission
        registerForm.addEventListener('submit', function(e) {
            e.preventDefault();
            
            const password = document.getElementById('password')?.value;
            const confirmPassword = document.getElementById('confirmPassword')?.value;
            
            // Validation
            if (password !== confirmPassword) {
                showAlert('Passwords do not match!', 'error');
                return;
            }
            
            if (!this.querySelector('[name="terms"]').checked) {
                showAlert('You must agree to the terms and conditions', 'error');
                return;
            }
            
            // Simulate registration
            simulateRegistration(new FormData(this));
        });
    }

    // ======================
    // Forgot Password Functionality
    // ======================
    const forgotPasswordForm = document.getElementById('forgotPasswordForm');
    if (forgotPasswordForm) {
        forgotPasswordForm.addEventListener('submit', function(e) {
            e.preventDefault();
            
            const email = this.querySelector('[name="email"]').value;
            if (!validateEmail(email)) {
                showAlert('Please enter a valid email address', 'error');
                return;
            }
            
            // Simulate sending reset link
            simulatePasswordReset(email);
        });
    }

    // ======================
    // General Site Functionality
    // ======================
    
    // FAQ Accordion
    document.querySelectorAll('.faq-question').forEach(question => {
        question.addEventListener('click', function() {
            const answer = this.nextElementSibling;
            const icon = this.querySelector('i');
            
            // Toggle answer visibility
            if (answer.style.display === 'block') {
                answer.style.display = 'none';
                icon.style.transform = 'rotate(0deg)';
            } else {
                answer.style.display = 'block';
                icon.style.transform = 'rotate(180deg)';
            }
            
            // Toggle question active state
            this.classList.toggle('active');
        });
    });

    // Event Filtering
    document.querySelectorAll('.filter-btn').forEach(button => {
        button.addEventListener('click', function() {
            // Update active button
            document.querySelectorAll('.filter-btn').forEach(btn => {
                btn.classList.remove('active');
            });
            this.classList.add('active');
            
            const filterValue = this.getAttribute('data-filter');
            const eventCards = document.querySelectorAll('.event-card');
            
            // Filter events
            eventCards.forEach(card => {
                if (filterValue === 'all' || card.getAttribute('data-category') === filterValue) {
                    card.style.display = 'flex';
                } else {
                    card.style.display = 'none';
                }
            });
        });
    });

    // Initialize maps if they exist
    if (document.getElementById('school-map')) {
        initMap();
    }

    // Smooth scrolling for anchor links
    document.querySelectorAll('a[href^="#"]').forEach(anchor => {
        anchor.addEventListener('click', function(e) {
            e.preventDefault();
            const target = document.querySelector(this.getAttribute('href'));
            if (target) {
                target.scrollIntoView({
                    behavior: 'smooth'
                });
            }
        });
    });

    // ======================
    // Grade Level Tabs Functionality
    // ======================
    const tabButtons = document.querySelectorAll('.tab-button');
    const tabContents = document.querySelectorAll('.tab-content');

    tabButtons.forEach(button => {
        button.addEventListener('click', function() {
            const tabId = this.getAttribute('data-tab');

            // Remove active class from all buttons and contents
            tabButtons.forEach(btn => btn.classList.remove('active'));
            tabContents.forEach(content => content.classList.remove('active'));

            // Add active class to the clicked button and corresponding content
            this.classList.add('active');
            document.getElementById(tabId).classList.add('active');
        });
    });
});
/**
 * Check password strength and update UI
 */
function checkPasswordStrength(password) {
    const strengthBar = document.querySelector('.strength-bar');
    if (!strengthBar) return;

    const requirements = {
        length: password.length >= 8,
        uppercase: /[A-Z]/.test(password),
        number: /\d/.test(password),
        special: /[^A-Za-z0-9]/.test(password)
    };

    // Update requirement indicators
    Object.keys(requirements).forEach(key => {
        const element = document.querySelector(`[data-requirement="${key}"]`);
        if (element) {
            if (requirements[key]) {
                element.classList.add('requirement-met');
            } else {
                element.classList.remove('requirement-met');
            }
        }
    });

    // Calculate strength percentage
    const metCount = Object.values(requirements).filter(Boolean).length;
    const strengthPercent = (metCount / Object.keys(requirements).length) * 100;
    
    // Update strength bar
    strengthBar.style.width = `${strengthPercent}%`;
    strengthBar.style.backgroundColor = getStrengthColor(strengthPercent);
}

function getStrengthColor(percent) {
    if (percent < 25) return '#ff4d4d';
    if (percent < 50) return '#ffa64d';
    if (percent < 75) return '#ffcc00';
    return '#2ecc71';
}

/**
 * Validate email format
 */
function validateEmail(email) {
    const re = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    return re.test(email);
}

/**
 * Show alert message
 */
function showAlert(message, type = 'success') {
    // Remove existing alerts
    const existingAlert = document.querySelector('.custom-alert');
    if (existingAlert) {
        existingAlert.remove();
    }

    // Create alert element
    const alert = document.createElement('div');
    alert.className = `custom-alert ${type}`;
    alert.textContent = message;
    
    // Add to page
    document.body.appendChild(alert);
    
    // Auto-remove after 5 seconds
    setTimeout(() => {
        alert.remove();
    }, 5000);
}

/**
 * Initialize map using Leaflet
 */
function initMap() {
    const map = L.map('school-map').setView([51.505, -0.09], 15);
    
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
    }).addTo(map);
    
    L.marker([51.505, -0.09]).addTo(map)
        .bindPopup('Greenwood High School<br>123 Education Blvd')
        .openPopup();
}

// ======================
// Simulation Functions (Replace with real API calls)
// ======================

function simulateLogin(username, password) {
    console.log('Simulating login with:', username, password);
    // In a real app, this would be an API call
    
    // Simulate API delay
    setTimeout(() => {
        // For demo purposes, accept any non-empty password
        if (username && password) {
            showAlert('Login successful! Redirecting...', 'success');
            // window.location.href = 'dashboard.html';
        } else {
            showAlert('Invalid credentials', 'error');
        }
    }, 1000);
}

function simulateRegistration(formData) {
    console.log('Simulating registration with:', Object.fromEntries(formData));
    // In a real app, this would be an API call
    
    // Simulate API delay
    setTimeout(() => {
        showAlert('Registration successful! Please check your email to verify your account.', 'success');
        // window.location.href = 'registration-success.html';
    }, 1500);
}

function simulatePasswordReset(email) {
    console.log('Simulating password reset for:', email);
    // In a real app, this would be an API call
    
    const form = document.getElementById('forgotPasswordForm');
    if (form) {
        form.innerHTML = `
            <div class="reset-success">
                <div class="success-icon">
                    <i class="fas fa-check-circle"></i>
                </div>
                <h3>Reset Link Sent!</h3>
                <p>We've sent an email to <strong>${email}</strong> with instructions to reset your password.</p>
                <p class="check-spam">Didn't receive it? Check your spam folder or <a href="#" id="resend-link">resend the link</a>.</p>
                <a href="login.html" class="btn-login">Return to Login</a>
            </div>
        `;
        
        // Add event listener for resend link
        document.getElementById('resend-link')?.addEventListener('click', function(e) {
            e.preventDefault();
            showAlert('Reset link resent to your email', 'success');
        });
    }
}