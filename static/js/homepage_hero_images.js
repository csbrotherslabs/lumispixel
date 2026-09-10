(() => {
    'use strict';

    if (!document.body.classList.contains('page-home')) {
        return;
    }

    const staticPath = (filename) => `/static/img/landing/gallery/${filename}`;
    const heroImages = [
        ['hero-ai-photography-platform.webp', 'hero-ai-photography-platform-mobile.webp'],
        ['hero-client-photo-discovery.webp', 'hero-client-photo-discovery-mobile.webp'],
        ['hero-photographer-workspace.webp', 'hero-photographer-workspace-mobile.webp'],
        ['hero-photographer-marketplace.webp', 'hero-photographer-marketplace-mobile.webp'],
    ];

    document.querySelectorAll('.wptb-slider.style3 .swiper-wrapper > .swiper-slide').forEach((slide, index) => {
        const image = slide.querySelector('.wptb-slider--image');
        const sources = heroImages[index];

        if (!image || !sources) {
            return;
        }

        image.style.setProperty('--desktop-image', `url("${staticPath(sources[0])}")`);
        image.style.setProperty('--mobile-image', `url("${staticPath(sources[1])}")`);
    });
})();
