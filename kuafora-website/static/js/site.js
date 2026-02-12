// Kuafora Site JavaScript - Modern Animations & Interactions
(function() {
  'use strict';

  // ===== Preloader / Açılış Animasyonu =====
  function initPreloader() {
    const preloader = document.getElementById('preloader');
    if (!preloader) return;

    // Sayfa yüklendiğinde preloader'ı kaldır
    window.addEventListener('load', function() {
      setTimeout(() => {
        preloader.style.opacity = '0';
        preloader.style.transform = 'scale(1.1)';
        setTimeout(() => {
          preloader.style.display = 'none';
        }, 500);
      }, 500); // Reduced from 800ms to 500ms for faster loading
    });
  }

  // ===== Smooth Scroll Animations =====
  function initScrollAnimations() {
    const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    
    if (prefersReducedMotion) {
      document.querySelectorAll('[data-reveal]').forEach(el => {
        el.style.opacity = '1';
        el.style.transform = 'none';
      });
      return;
    }

    // Intersection Observer for reveal animations
    const revealObserver = new IntersectionObserver((entries) => {
      entries.forEach((entry, index) => {
        if (entry.isIntersecting) {
          const delay = Math.min(index * 50, 300);
          setTimeout(() => {
            entry.target.classList.add('revealed');
            revealObserver.unobserve(entry.target);
          }, delay);
        }
      });
    }, {
      threshold: 0.1,
      rootMargin: '0px 0px -100px 0px'
    });

    // Initialize reveal elements
    document.querySelectorAll('[data-reveal]').forEach(el => {
      el.classList.add('reveal-ready');
      revealObserver.observe(el);
    });

    // Parallax effect disabled - hero stays fixed
    // const hero = document.querySelector('.hero-parallax');
    // if (hero) {
    //   window.addEventListener('scroll', () => {
    //     const scrolled = window.pageYOffset;
    //     const rate = scrolled * 0.5;
    //     hero.style.transform = `translateY(${rate}px)`;
    //   });
    // }
  }

  // ===== Floating Animation =====
  function initFloatingAnimations() {
    const floatElements = document.querySelectorAll('.animate-float');
    floatElements.forEach((el, index) => {
      const delay = parseFloat(el.getAttribute('data-delay')) || index * 0.2;
      el.style.animationDelay = `${delay}s`;
    });
  }

  // ===== Gradient Text Animation =====
  function initGradientAnimation() {
    const gradientTexts = document.querySelectorAll('.gradient-text');
    gradientTexts.forEach(text => {
      text.addEventListener('mouseenter', function() {
        this.style.backgroundPosition = '100% 50%';
      });
      text.addEventListener('mouseleave', function() {
        this.style.backgroundPosition = '0% 50%';
      });
    });
  }

  // ===== Cursor Effect (Optional) =====
  function initCursorEffect() {
    if (window.innerWidth < 768) return; // Sadece desktop'ta
    
    const cursor = document.createElement('div');
    cursor.className = 'custom-cursor';
    document.body.appendChild(cursor);

    let mouseX = 0, mouseY = 0;
    let cursorX = 0, cursorY = 0;

    document.addEventListener('mousemove', (e) => {
      mouseX = e.clientX;
      mouseY = e.clientY;
    });

    function animateCursor() {
      cursorX += (mouseX - cursorX) * 0.1;
      cursorY += (mouseY - cursorY) * 0.1;
      cursor.style.left = cursorX + 'px';
      cursor.style.top = cursorY + 'px';
      requestAnimationFrame(animateCursor);
    }
    animateCursor();

    // Hover effects
    document.querySelectorAll('a, button, [role="button"]').forEach(el => {
      el.addEventListener('mouseenter', () => cursor.classList.add('cursor-hover'));
      el.addEventListener('mouseleave', () => cursor.classList.remove('cursor-hover'));
    });
  }

  // ===== Smooth Anchor Scrolling =====
  function initSmoothScrolling() {
    document.addEventListener('click', function(e) {
      const link = e.target.closest('a');
      if (!link) return;
      
      const href = link.getAttribute('href') || '';
      if (!href.startsWith('#')) return;
      
      const target = document.querySelector(href);
      if (!target) return;
      
      e.preventDefault();
      const offset = 100;
      const targetPosition = target.getBoundingClientRect().top + window.pageYOffset - offset;
      
      window.scrollTo({
        top: targetPosition,
        behavior: 'smooth'
      });
    });
  }

  // ===== Image Loading Handler =====
  function initImageLoading() {
    const images = document.querySelectorAll('img[src*="/static/img/"], img[src*="img/screens/"]');
    
    images.forEach(function(img) {
      // Set loading state
      img.style.opacity = '0';
      img.style.transition = 'opacity 0.3s ease';
      
      // Error handler - silently handle missing images
      img.addEventListener('error', function() {
        // Only log in development
        if (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1') {
          console.warn('Görsel yüklenemedi:', this.src);
        }
        this.style.display = 'none';
        this.style.opacity = '0';
        const fallback = this.nextElementSibling;
        if (fallback && (fallback.classList.contains('hidden') || fallback.style.display === 'none')) {
          fallback.classList.remove('hidden');
          fallback.style.display = 'flex';
          fallback.style.opacity = '1';
        }
      });
      
      // Load handler
      img.addEventListener('load', function() {
        this.classList.add('loaded');
        this.style.opacity = '1';
        const fallback = this.nextElementSibling;
        if (fallback && !fallback.classList.contains('hidden')) {
          fallback.classList.add('hidden');
          fallback.style.display = 'none';
        }
      });
      
      // Check if already loaded
      if (img.complete && img.naturalHeight !== 0) {
        img.classList.add('loaded');
        img.style.opacity = '1';
        const fallback = img.nextElementSibling;
        if (fallback && !fallback.classList.contains('hidden')) {
          fallback.classList.add('hidden');
          fallback.style.display = 'none';
        }
      } else {
        // Force load attempt
        const src = img.src;
        if (src) {
          const testImg = new Image();
          testImg.onload = function() {
            img.style.opacity = '1';
            img.classList.add('loaded');
          };
          testImg.onerror = function() {
            img.style.display = 'none';
            img.style.opacity = '0';
          };
          testImg.src = src;
        }
      }
    });
  }

  // ===== Navbar Scroll Effect =====
  function initNavbarScroll() {
    const navbar = document.querySelector('.dynamic-nav');
    if (!navbar) return;

    let lastScroll = 0;
    window.addEventListener('scroll', () => {
      const currentScroll = window.pageYOffset;
      
      if (currentScroll > 100) {
        navbar.classList.add('nav-scrolled');
      } else {
        navbar.classList.remove('nav-scrolled');
      }

      lastScroll = currentScroll;
    });
  }

  // ===== Counter Animation =====
  function initCounters() {
    const counters = document.querySelectorAll('[data-count]');
    
    counters.forEach(counter => {
      const target = parseInt(counter.getAttribute('data-count'));
      const duration = 2000;
      const increment = target / (duration / 16);
      let current = 0;

      const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
          if (entry.isIntersecting) {
            const timer = setInterval(() => {
              current += increment;
              if (current >= target) {
                counter.textContent = target;
                clearInterval(timer);
              } else {
                counter.textContent = Math.floor(current);
              }
            }, 16);
            observer.unobserve(entry.target);
          }
        });
      });

      observer.observe(counter);
    });
  }

  // ===== Initialize Everything =====
  function init() {
    initPreloader();
    initScrollAnimations();
    initFloatingAnimations();
    initGradientAnimation();
    initSmoothScrolling();
    initImageLoading();
    initNavbarScroll();
    // initCursorEffect(); // Optional - uncomment if needed
    initCounters();
  }

  // Run on DOM ready
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
