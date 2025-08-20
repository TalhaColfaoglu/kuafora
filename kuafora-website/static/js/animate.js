// Kuafora Animation & Interaction Scripts

document.addEventListener('DOMContentLoaded', function() {
  // Initialize all animations and interactions
  initScrollAnimations();
  initSmoothScroll();
  initAccordions();
  initNavbarAnimation();
});

// Scroll-based animations using IntersectionObserver
function initScrollAnimations() {
  // Check for reduced motion preference
  const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  
  if (prefersReducedMotion) {
    // If user prefers reduced motion, make all animated elements visible immediately
    document.querySelectorAll('[data-animate], [data-reveal]').forEach(el => {
      el.style.opacity = '1';
      el.style.transform = 'none';
    });
    return;
  }

  // Set up intersection observer for scroll animations
  const observerOptions = {
    threshold: 0.1,
    rootMargin: '0px 0px -50px 0px'
  };

  const observer = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        const element = entry.target;
        
        // Add appropriate animation class
        if (element.hasAttribute('data-animate')) {
          element.classList.add('animate-fade-in', 'visible');
        } else if (element.hasAttribute('data-reveal')) {
          element.classList.add('animate-fade-in', 'visible');
        }
        
        // Stagger animations for multiple elements
        const delay = Array.from(element.parentNode.children).indexOf(element) * 100;
        element.style.animationDelay = `${delay}ms`;
        
        observer.unobserve(element);
      }
    });
  }, observerOptions);

  // Observe all elements with animation attributes
  document.querySelectorAll('[data-animate], [data-reveal]').forEach(el => {
    // Set initial state
    el.classList.add('animate-fade-in');
    observer.observe(el);
  });
}

// Smooth scrolling for navigation links
function initSmoothScroll() {
  // Handle navbar links
  document.querySelectorAll('a[href^="#"]').forEach(link => {
    link.addEventListener('click', function(e) {
      const href = this.getAttribute('href');
      
      // Skip if it's just a hash
      if (href === '#') return;
      
      const targetId = href.substring(1);
      const targetElement = document.getElementById(targetId);
      
      if (targetElement) {
        e.preventDefault();
        
        // Calculate offset for fixed header
        const headerHeight = document.querySelector('[data-header]')?.offsetHeight || 80;
        const targetPosition = targetElement.offsetTop - headerHeight;
        
        window.scrollTo({
          top: targetPosition,
          behavior: 'smooth'
        });
        
        // Update URL without jumping
        history.pushState(null, null, href);
      }
    });
  });

  // Handle "Kuafora Partner" link in navbar to scroll to partner-teaser
  document.querySelectorAll('a[href*="partner"]').forEach(link => {
    // Only apply to internal links that should scroll to partner section
    if (link.textContent.includes('Partner') && link.hostname === window.location.hostname) {
      link.addEventListener('click', function(e) {
        const partnerSection = document.getElementById('partner-teaser');
        if (partnerSection && window.location.pathname === '/') {
          e.preventDefault();
          
          const headerHeight = document.querySelector('[data-header]')?.offsetHeight || 80;
          const targetPosition = partnerSection.offsetTop - headerHeight;
          
          window.scrollTo({
            top: targetPosition,
            behavior: 'smooth'
          });
        }
      });
    }
  });
}

// Accordion functionality for FAQ sections
function initAccordions() {
  document.querySelectorAll('[aria-expanded]').forEach(trigger => {
    trigger.addEventListener('click', function() {
      const isExpanded = this.getAttribute('aria-expanded') === 'true';
      const targetId = this.getAttribute('aria-controls');
      const content = document.getElementById(targetId);
      const chevron = this.querySelector('.accordion-chevron, [class*="rotate"]');
      
      if (content) {
        if (isExpanded) {
          // Close
          this.setAttribute('aria-expanded', 'false');
          content.classList.remove('expanded');
          if (chevron) chevron.classList.remove('rotated');
        } else {
          // Close all other accordions in the same container
          const container = this.closest('section') || document;
          container.querySelectorAll('[aria-expanded="true"]').forEach(otherTrigger => {
            if (otherTrigger !== this) {
              const otherTargetId = otherTrigger.getAttribute('aria-controls');
              const otherContent = document.getElementById(otherTargetId);
              const otherChevron = otherTrigger.querySelector('.accordion-chevron, [class*="rotate"]');
              
              otherTrigger.setAttribute('aria-expanded', 'false');
              if (otherContent) otherContent.classList.remove('expanded');
              if (otherChevron) otherChevron.classList.remove('rotated');
            }
          });
          
          // Open this one
          this.setAttribute('aria-expanded', 'true');
          content.classList.add('expanded');
          if (chevron) chevron.classList.add('rotated');
        }
      }
    });
  });
}

// Enhanced navbar island animation
function initNavbarAnimation() {
  const header = document.querySelector('[data-header]');
  const nav = document.querySelector('[data-nav]');
  
  if (!header || !nav) return;
  
  const baseClasses = nav.className;
  const islandClasses = 'mx-auto mt-3 max-w-7xl w-full rounded-full border border-emerald-900/10 bg-[#F3FAF2]/90 shadow-lg backdrop-blur px-6 sm:px-8 py-3 transition-all duration-300 ease-out translate-y-2';
  
  let isScrolled = false;
  let ticking = false;
  
  function updateNavbar() {
    const scrollY = window.scrollY;
    const shouldBeScrolled = scrollY > 120;
    
    if (shouldBeScrolled !== isScrolled) {
      isScrolled = shouldBeScrolled;
      
      if (isScrolled) {
        nav.className = islandClasses;
        header.style.background = 'transparent';
      } else {
        nav.className = baseClasses;
        header.style.background = '';
      }
    }
    
    ticking = false;
  }
  
  function onScroll() {
    if (!ticking) {
      requestAnimationFrame(updateNavbar);
      ticking = true;
    }
  }
  
  // Initial check
  updateNavbar();
  
  // Listen to scroll events
  window.addEventListener('scroll', onScroll, { passive: true });
  
  // Handle resize events
  window.addEventListener('resize', updateNavbar, { passive: true });
}

// Active link highlighting
function updateActiveLinks() {
  const sections = document.querySelectorAll('section[id]');
  const navLinks = document.querySelectorAll('nav a[href^="#"]');
  
  if (sections.length === 0 || navLinks.length === 0) return;
  
  let current = '';
  const scrollY = window.scrollY;
  const headerHeight = document.querySelector('[data-header]')?.offsetHeight || 80;
  
  sections.forEach(section => {
    const sectionTop = section.offsetTop - headerHeight - 100;
    const sectionHeight = section.offsetHeight;
    
    if (scrollY >= sectionTop && scrollY < sectionTop + sectionHeight) {
      current = section.getAttribute('id');
    }
  });
  
  navLinks.forEach(link => {
    const href = link.getAttribute('href');
    if (href === `#${current}`) {
      link.classList.add('text-[#4F7942]', 'font-medium');
    } else {
      link.classList.remove('text-[#4F7942]', 'font-medium');
    }
  });
}

// Throttled scroll handler for active links
let activeLinksThrottle = false;
window.addEventListener('scroll', () => {
  if (!activeLinksThrottle) {
    requestAnimationFrame(() => {
      updateActiveLinks();
      activeLinksThrottle = false;
    });
    activeLinksThrottle = true;
  }
}, { passive: true });

// Initialize active links on load
document.addEventListener('DOMContentLoaded', updateActiveLinks);

// Handle hash changes
window.addEventListener('hashchange', updateActiveLinks);

// Utility function to add stagger delays to elements
function addStaggerDelay(elements, baseDelay = 100) {
  elements.forEach((element, index) => {
    element.style.animationDelay = `${index * baseDelay}ms`;
  });
}

// Export functions for use in other scripts if needed
window.KuaforaAnimations = {
  initScrollAnimations,
  initSmoothScroll,
  initAccordions,
  initNavbarAnimation,
  updateActiveLinks,
  addStaggerDelay
};
