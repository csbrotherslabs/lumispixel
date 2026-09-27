(() => {
    'use strict';

    if (!document.body.classList.contains('page-home')) {
        return;
    }

    const staticPath = (filename) => `/static/img/landing/gallery/${filename}`;

    const setImageSource = (selector, filename) => {
        const image = document.querySelector(selector);
        if (image) {
            image.src = staticPath(filename);
        }
    };

    const photoMatchImages = [
        'photo-match-event-result-01.webp',
        'photo-match-event-result-02.webp',
        'photo-match-event-result-03.webp',
    ];

    document.querySelectorAll('.lumis-photo-match__grid img').forEach((image, index) => {
        if (photoMatchImages[index]) {
            image.src = staticPath(photoMatchImages[index]);
        }
    });

    const workflowImages = [
        'workflow-ai-culling.webp',
        'workflow-ai-editing.webp',
        'workflow-client-gallery.webp',
        'workflow-face-recognition.webp',
        'workflow-online-photo-sales.webp',
        'workflow-business-dashboard.webp',
    ];

    document.querySelectorAll('.lumis-photographer-workflow__carousel .swiper-wrapper > .swiper-slide').forEach((slide, index) => {
        const image = slide.querySelector('.wptb-item--image > img');
        if (image && workflowImages[index]) {
            image.src = staticPath(workflowImages[index]);
        }
    });

    const audienceImages = [
        'audience-photographers.webp',
        'audience-clients.webp',
        'audience-hire-photographer.webp',
    ];

    document.querySelectorAll('.lumis-audiences__grid .lumis-audience-card').forEach((card, index) => {
        const image = card.querySelector('.lumis-audience-card__image img');
        if (image && audienceImages[index]) {
            image.src = staticPath(audienceImages[index]);
        }
    });

    const howItWorksImages = {
        '#lumis-workflow-upload > img': 'destination-tropical-islands.webp',
        '#lumis-workflow-organize > img': 'destination-coastal-fishing-village.webp',
        '#lumis-workflow-refine > img': 'destination-northern-lights.webp',
        '#lumis-workflow-deliver > img': 'destination-geyser-sunrise.webp',
        '#lumis-workflow-sell-share > img': 'destination-canyon-sunset.webp',
    };

    Object.entries(howItWorksImages).forEach(([selector, filename]) => {
        setImageSource(selector, filename);
    });

    setImageSource('.lumis-pricing-visual__primary img', 'executive-portrait.webp');
    setImageSource('.lumis-pricing-visual__secondary img', 'creative-rainbow-portrait.webp');
    setImageSource('.lumis-final-cta__media img', 'professional-portrait-collection.webp');
})();
