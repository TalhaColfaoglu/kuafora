// Kuafora Animation Utilities
// Simple, performant animations for reveal-on-scroll effects

(function() {
  'use strict';

  // Check for reduced motion preference
  const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  
  if (prefersReducedMotion) {
    // If user prefers reduced motion, make all elements visible immediately
    document.querySelectorAll('[data-reveal]').forEach(el => {
      el.style.opacity = '1';
      el.style.transform = 'none';
    });
    return;
  }

  // Reveal on scroll using Intersection Observer
  const revealObserver = new IntersectionObserver((entries) => {
    entries.forEach((entry, index) => {
      if (entry.isIntersecting) {
        // Add stagger delay based on order
        const delay = index * 100;
        entry.target.style.transitionDelay = `${delay}ms`;
        entry.target.classList.add('revealed');
        revealObserver.unobserve(entry.target);
      }
    });
  }, {
    threshold: 0.1,
    rootMargin: '0px 0px -50px 0px'
  });

  // Initialize reveal elements
  function initReveal() {
    document.querySelectorAll('[data-reveal]').forEach(el => {
      el.classList.add('reveal-ready');
      revealObserver.observe(el);
    });
  }

  // Add CSS for reveal animations
  const style = document.createElement('style');
  style.textContent = `
    .reveal-ready {
      opacity: 0;
      transform: translateY(20px);
      transition: opacity 0.6s cubic-bezier(0.16, 1, 0.3, 1), 
                  transform 0.6s cubic-bezier(0.16, 1, 0.3, 1);
    }
    
    .reveal-ready.revealed {
      opacity: 1;
      transform: translateY(0);
    }
    
    @media (prefers-reduced-motion: reduce) {
      .reveal-ready {
        opacity: 1;
        transform: none;
        transition: none;
      }
    }
  `;
  document.head.appendChild(style);

  // Run on DOM ready
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initReveal);
  } else {
    initReveal();
  }
})();
