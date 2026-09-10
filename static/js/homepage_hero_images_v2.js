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
        if (!document.body.classList.contains('page-home')) return;

        document.querySelectorAll('.wptb-slider.style3 .swiper-slide').forEach((slide) => {
            const subtitle = slide.querySelector('.wptb-item--subtitle');
            const image = slide.querySelector('.wptb-slider--image');
            if (!subtitle || !image) return;

            const sources = heroMap[subtitle.textContent.trim()];
            if (!sources) return;

            image.style.setProperty('--desktop-image', imageUrl(sources.desktop));
            image.style.setProperty('--mobile-image', imageUrl(sources.mobile));

            const selected = window.matchMedia('(max-width: 767px)').matches
                ? sources.mobile
                : sources.desktop;
            image.style.setProperty('background-image', imageUrl(selected), 'important');
        });
    };

    const refresh = () => {
        applyHeroImages();
        requestAnimationFrame(applyHeroImages);
        window.setTimeout(applyHeroImages, 150);
    };

    refresh();
    window.addEventListener('load', applyHeroImages, { once: true });

    let resizeTimer;
    window.addEventListener('resize', () => {
        clearTimeout(resizeTimer);
        resizeTimer = setTimeout(applyHeroImages, 100);
    });
})();
