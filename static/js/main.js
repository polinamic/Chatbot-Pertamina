// Dark Mode Toggle
document.addEventListener('DOMContentLoaded', function() {
  const theme = localStorage.getItem('theme') || 'light';
  const themeToggle = document.getElementById('theme-toggle');
  
  // Apply saved theme
  if (theme === 'dark') {
    document.documentElement.classList.add('dark-mode');
    document.body.classList.add('dark-mode');
    if (themeToggle) themeToggle.checked = true;
  }
  
  // Theme toggle listener - properly attach to checkbox
  if (themeToggle) {
    themeToggle.addEventListener('change', function(e) {
      const isDark = e.target.checked;
      if (isDark) {
        document.documentElement.classList.add('dark-mode');
        document.body.classList.add('dark-mode');
      } else {
        document.documentElement.classList.remove('dark-mode');
        document.body.classList.remove('dark-mode');
      }
      localStorage.setItem('theme', isDark ? 'dark' : 'light');
    });
  }
});

function toggleTheme() {
  const themeToggle = document.getElementById('theme-toggle');
  if (themeToggle) {
    themeToggle.checked = !themeToggle.checked;
    themeToggle.dispatchEvent(new Event('change'));
  }
}

function updateThemeToggle(isDark) {
  const toggle = document.getElementById('theme-toggle');
  if (toggle) {
    toggle.checked = isDark;
  }
}

// Mobile Menu Toggle
function toggleMobileMenu() {
  const menu = document.getElementById('mobile-menu');
  if (menu) {
    menu.classList.toggle('hidden');
  }
}

// Form Validation
function validateForm(formId) {
  const form = document.getElementById(formId);
  if (!form) return false;
  
  const inputs = form.querySelectorAll('input[required], textarea[required], select[required]');
  let isValid = true;
  
  inputs.forEach(input => {
    if (!input.value.trim()) {
      addError(input, 'Field ini harus diisi');
      isValid = false;
    } else {
      removeError(input);
    }
    
    // Email validation
    if (input.type === 'email' && input.value.trim()) {
      const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
      if (!emailRegex.test(input.value)) {
        addError(input, 'Email tidak valid');
        isValid = false;
      }
    }
    
    // Password match validation
    if (input.name === 'confirm_password') {
      const password = form.querySelector('input[name="password"]');
      if (password && input.value !== password.value) {
        addError(input, 'Password tidak cocok');
        isValid = false;
      }
    }
  });
  
  return isValid;
}

function addError(input, message) {
  input.classList.add('error');
  let errorDiv = input.nextElementSibling;
  if (!errorDiv || !errorDiv.classList.contains('error-message')) {
    errorDiv = document.createElement('div');
    errorDiv.className = 'error-message';
    input.parentNode.insertBefore(errorDiv, input.nextSibling);
  }
  errorDiv.textContent = message;
  errorDiv.style.color = '#ef4444';
  errorDiv.style.fontSize = '0.875rem';
  errorDiv.style.marginTop = '0.25rem';
}

function removeError(input) {
  input.classList.remove('error');
  let errorDiv = input.nextElementSibling;
  if (errorDiv && errorDiv.classList.contains('error-message')) {
    errorDiv.remove();
  }
}

function getCurrentTime() {
  const now = new Date();
  return now.toLocaleTimeString('id-ID', { hour: '2-digit', minute: '2-digit' });
}

function escapeHtml(text) {
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}

// Image Upload Preview
function previewImage(inputId, previewId) {
  const input = document.getElementById(inputId);
  const preview = document.getElementById(previewId);
  
  if (input && preview) {
    input.addEventListener('change', function(e) {
      const file = e.target.files[0];
      if (file) {
        const reader = new FileReader();
        reader.onload = function(event) {
          preview.src = event.target.result;
          preview.style.display = 'block';
        };
        reader.readAsDataURL(file);
      }
    });
  }
}

// Animations
function fadeIn(element, duration = 300) {
  element.style.opacity = '0';
  element.style.display = 'block';
  setTimeout(() => {
    element.style.transition = `opacity ${duration}ms ease-in`;
    element.style.opacity = '1';
  }, 10);
}

function fadeOut(element, duration = 300) {
  element.style.transition = `opacity ${duration}ms ease-out`;
  element.style.opacity = '0';
  setTimeout(() => {
    element.style.display = 'none';
  }, duration);
}
