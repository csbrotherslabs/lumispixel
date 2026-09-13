(() => {
    const body = document.body;
    const sidebar = document.getElementById('internalSidebar');
    if (!sidebar) return;

    const desktopQuery = window.matchMedia('(min-width: 901px)');
    const toggles = [...document.querySelectorAll('[data-sidebar-toggle]')];
    const closers = [...document.querySelectorAll('[data-sidebar-close]')];
    const nav = sidebar.querySelector('[data-sidebar-nav]');
    const storageKey = 'lumispixel.internal.sidebar.collapsed';

    const setExpandedState = (expanded) => {
        toggles.forEach((button) => button.setAttribute('aria-expanded', expanded ? 'true' : 'false'));
    };

    const applyDesktopPreference = () => {
        if (!desktopQuery.matches) return;
        const collapsed = window.localStorage.getItem(storageKey) === 'true';
        body.classList.toggle('is-sidebar-collapsed', collapsed);
        body.classList.remove('is-mobile-nav-open');
        setExpandedState(!collapsed);
    };

    const closeMobile = () => {
        body.classList.remove('is-mobile-nav-open');
        if (!desktopQuery.matches) setExpandedState(false);
    };

    const toggleSidebar = () => {
        if (desktopQuery.matches) {
            const collapsed = !body.classList.contains('is-sidebar-collapsed');
            body.classList.toggle('is-sidebar-collapsed', collapsed);
            window.localStorage.setItem(storageKey, collapsed ? 'true' : 'false');
            setExpandedState(!collapsed);
            return;
        }
        const open = !body.classList.contains('is-mobile-nav-open');
        body.classList.toggle('is-mobile-nav-open', open);
        setExpandedState(open);
    };

    toggles.forEach((button) => button.addEventListener('click', toggleSidebar));
    closers.forEach((button) => button.addEventListener('click', closeMobile));

    nav?.addEventListener('click', (event) => {
        if (!desktopQuery.matches && event.target.closest('a')) closeMobile();
    });

    document.addEventListener('keydown', (event) => {
        if (event.key === 'Escape' && body.classList.contains('is-mobile-nav-open')) closeMobile();
    });

    const handleBreakpointChange = () => {
        if (desktopQuery.matches) {
            applyDesktopPreference();
        } else {
            body.classList.remove('is-sidebar-collapsed', 'is-mobile-nav-open');
            setExpandedState(false);
        }
    };

    if (desktopQuery.addEventListener) desktopQuery.addEventListener('change', handleBreakpointChange);
    else desktopQuery.addListener(handleBreakpointChange);

    handleBreakpointChange();
})();
