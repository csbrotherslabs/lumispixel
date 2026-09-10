(() => {
    'use strict';

    const STATIC_ROOT = '/static/img/landing/gallery/';

    const heroMap = {
        'AI Photography Platform': {
            desktop: 'hero-ai-photography-platform.webp',
            mobile: 'hero-ai-photography-platform-mobile.webp',
        },
        'FOR CLIENTS': {
            desktop: 'hero-client-photo-discovery.webp',
            mobile: 'hero-client-photo-discovery-mobile.webp',
        },
        'FOR PHOTOGRAPHERS': {
            desktop: 'hero-photographer-workspace.webp',
            mobile: 'hero-photographer-workspace-mobile.webp',
        },
        'PHOTOGRAPHER MARKETPLACE': {
            desktop: 'hero-photographer-marketplace.webp',
            mobile: 'hero-photographer-marketplace-mobile.webp',
        },
    };

    const imageUrl = (filename) => `url("${STATIC_ROOT}${filename}")`;

    const applyHeroImages = () => {
        if (!document.body.classList.contains('page-home')) {
            return;
        }

        document.querySelectorAll('.wptb-slider.style3 .swiper-slide').forEach((slide) => {
            const subtitle = slide.querySelector('.wptb-item--subtitle');
            const image = slide.querySelector('.wptb-slider--image');

            if (!subtitle || !image) {
                return;
            }

            const key = subtitle.textContent.trim();
            const sources = heroMap[key];

            if (!sources) {
                return;
            }

            image.style.setProperty('--desktop-image', imageUrl(sources.desktop));
            image.style.setProperty('--mobile-image', imageUrl(sources.mobile));

            // Desktop fallback: ensure the actual background is populated even if
            // a theme stylesheet does not resolve the CSS custom property as expected.
            if (!window.matchMedia('(max-width: 767px)').matches) {
                image.style.setProperty('background-image', imageUrl(sources.desktop), 'important');
            }
        });
    };

    const applyAndRefresh = () => {
        applyHeroImages();
        requestAnimationFrame(applyHeroImages);
        window.setTimeout(applyHeroImages, 150);
    };

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', applyAndRefresh, { once: true });
    } else {
        applyAndRefresh();
    }

    window.addEventListener('load', applyHeroImages, { once: true });

    let resizeTimer;
    window.addEventListener('resize', () => {
        window.clearTimeout(resizeTimer);
        resizeTimer = window.setTimeout(applyHeroImages, 100);
    });
})();
