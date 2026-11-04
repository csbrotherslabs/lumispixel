/* Mobile marketing preview only. No photos are uploaded or AI models invoked. */
(function(){
  function init(){
    document.querySelectorAll('[data-lpm-ai-demo]').forEach(function(root){
      var tabs=Array.prototype.slice.call(root.querySelectorAll('[data-lpm-ai-tab]'));
      var panels=Array.prototype.slice.call(root.querySelectorAll('[data-lpm-ai-panel]'));
      function select(tab,focus){
        var key=tab.getAttribute('data-lpm-ai-tab');
        tabs.forEach(function(t){var active=t===tab;t.setAttribute('aria-selected',String(active));t.tabIndex=active?0:-1;});
        panels.forEach(function(p){p.hidden=p.getAttribute('data-lpm-ai-panel')!==key;});
        if(focus)tab.focus();
      }
      tabs.forEach(function(tab,index){
        tab.addEventListener('click',function(){select(tab,false);});
        tab.addEventListener('keydown',function(e){
          var next=index;
          if(e.key==='ArrowRight')next=(index+1)%tabs.length;
          else if(e.key==='ArrowLeft')next=(index+tabs.length-1)%tabs.length;
          else if(e.key==='Home')next=0;
          else if(e.key==='End')next=tabs.length-1;
          else return;
          e.preventDefault();select(tabs[next],true);
        });
      });
      var range=root.querySelector('.lpm-ai-compare-range');
      if(range){
        function update(){range.parentElement.style.setProperty('--split',range.value+'%');}
        range.addEventListener('input',update);update();
      }
    });
  }
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init);else init();
})();
