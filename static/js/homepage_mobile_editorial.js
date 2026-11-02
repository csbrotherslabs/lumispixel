document.addEventListener('DOMContentLoaded', function () {
  document.querySelectorAll('.lp-mobile-home [data-lpm-rail]').forEach(function (rail) {
    var controls = rail.nextElementSibling;
    if (!controls || !controls.classList.contains('lpm-rail-controls')) return;
    var prev = controls.querySelector('[data-lpm-prev]');
    var next = controls.querySelector('[data-lpm-next]');
    var cards = Array.from(rail.children);
    if (!prev || !next || !cards.length) return;
    function currentIndex() {
      var x = rail.getBoundingClientRect().left;
      var best = 0, distance = Infinity;
      cards.forEach(function (card, i) {
        var d = Math.abs(card.getBoundingClientRect().left - x);
        if (d < distance) { distance = d; best = i; }
      });
      return best;
    }
    function update() { var i = currentIndex(); prev.disabled = i === 0; next.disabled = i === cards.length - 1; }
    function move(delta) {
      var index = Math.max(0, Math.min(cards.length - 1, currentIndex() + delta));
      cards[index].scrollIntoView({behavior:window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth', block:'nearest', inline:'start'});
    }
    prev.addEventListener('click', function () { move(-1); });
    next.addEventListener('click', function () { move(1); });
    rail.addEventListener('scroll', update, {passive:true});
    window.addEventListener('resize', update);
    update();
  });
});