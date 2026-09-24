(function () {
  'use strict';

  function updateCount(node, value) {
    if (!node) return;
    node.textContent = String(value);
    node.classList.toggle('is-empty', !value);
  }

  document.querySelectorAll('[data-favorite-form]').forEach(function (form) {
    form.addEventListener('submit', async function (event) {
      event.preventDefault();
      const photo = form.closest('[data-client-photo]');
      const button = form.querySelector('button[type="submit"]');
      const count = form.querySelector('[data-favorite-count]');
      try {
        const response = await fetch(form.action, {
          method: 'POST',
          body: new FormData(form),
          headers: {'X-Requested-With': 'XMLHttpRequest'}
        });
        if (!response.ok) throw new Error('Favorite failed');
        const data = await response.json();
        if (photo) {
          photo.dataset.favorite = data.favorited ? 'true' : 'false';
          photo.classList.toggle('is-favorite', data.favorited);
        }
        if (button) {
          button.setAttribute('aria-label', data.favorited ? 'Remove favorite' : 'Favorite photo');
          button.setAttribute('aria-pressed', data.favorited ? 'true' : 'false');
          button.querySelector('[data-favorite-icon]')?.classList.toggle('is-filled', data.favorited);
        }
        updateCount(count, data.favorite_count);
        document.dispatchEvent(new CustomEvent('lumispixel:favorite-changed'));
      } catch (error) {
        form.submit();
      }
    });
  });

  document.querySelectorAll('[data-comment-form]').forEach(function (form) {
    form.addEventListener('submit', async function (event) {
      event.preventDefault();
      const photo = form.closest('[data-client-photo]');
      const textarea = form.querySelector('textarea[name="comment"]');
      const panel = form.closest('[data-comment-panel]');
      const count = photo?.querySelector('[data-comment-count]');
      if (!textarea || !textarea.value.trim()) return;
      try {
        const response = await fetch(form.action, {
          method: 'POST',
          body: new FormData(form),
          headers: {'X-Requested-With': 'XMLHttpRequest'}
        });
        if (!response.ok) throw new Error('Comment failed');
        const data = await response.json();
        const thread = panel?.querySelector('[data-comment-thread]');
        thread?.querySelector('[data-comments-empty]')?.remove();
        if (thread) {
          const article = document.createElement('article');
          article.className = 'lp-client-comment';
          const author = document.createElement('strong');
          author.textContent = data.comment.author || 'Guest';
          const body = document.createElement('p');
          body.textContent = data.comment.body;
          article.append(author, body);
          thread.appendChild(article);
        }
        textarea.value = '';
        updateCount(count, data.comment_count);
        updateCount(panel?.querySelector('[data-thread-count]'), data.comment_count);
      } catch (error) {
        form.submit();
      }
    });
  });

  document.querySelectorAll('[data-photo-download]').forEach(function (link) {
    link.addEventListener('click', function () {
      const photo = link.closest('[data-client-photo]');
      const badges = photo?.querySelectorAll('[data-download-count]') || [];
      if (!badges.length) return;
      const next = (parseInt(badges[0].textContent || '0', 10) || 0) + 1;
      badges.forEach(function (badge) { updateCount(badge, next); });
    });
  });
})();
