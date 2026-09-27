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
        document.dispatchEvent(new CustomEvent('lumispixel:favorite-changed', {detail: {photo: photo, favorited: data.favorited}}));
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
          const authorName = data.comment.author || 'Guest';
          const article = document.createElement('article');
          article.className = 'sf-comment';

          const avatar = document.createElement('div');
          avatar.className = 'sf-comment__avatar';
          avatar.setAttribute('aria-hidden', 'true');
          avatar.textContent = authorName.charAt(0).toUpperCase();

          const content = document.createElement('div');
          content.className = 'sf-comment__content';
          const meta = document.createElement('div');
          meta.className = 'sf-comment__meta';
          const author = document.createElement('strong');
          author.textContent = authorName;
          const time = document.createElement('time');
          time.textContent = 'just now';
          const body = document.createElement('p');
          body.textContent = data.comment.body;

          meta.append(author, time);
          content.append(meta, body);
          article.append(avatar, content);
          thread.appendChild(article);
          thread.scrollTop = thread.scrollHeight;
        }
        textarea.value = '';
        updateCount(count, data.comment_count);
        updateCount(panel?.querySelector('[data-thread-count]'), data.comment_count);
        document.dispatchEvent(new CustomEvent('lumispixel:comment-submitted', {detail: {photo: photo, panel: panel}}));
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