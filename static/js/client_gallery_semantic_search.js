(() => {
  document.querySelectorAll("[data-semantic-client-form]").forEach(form => {
    const status=form.parentElement.querySelector("[data-semantic-status]");
    const results=form.parentElement.querySelector("[data-semantic-results]");
    form.addEventListener("submit", async event => {
      event.preventDefault();
      results.replaceChildren();
      status.textContent="Searching…";
      const q=new FormData(form).get("q");
      try {
        const response=await fetch(form.dataset.searchUrl+"?q="+encodeURIComponent(q),{credentials:"same-origin"});
        if(!response.ok) throw new Error("Search is unavailable");
        const payload=await response.json();
        for(const item of payload.results || []){
          const image=document.createElement("img");
          image.src=item.thumbnail_url;
          image.alt="Matching gallery photo";
          image.loading="lazy";
          image.style.cssText="width:140px;height:110px;object-fit:cover;border-radius:8px";
          results.appendChild(image);
        }
        status.textContent=(payload.results || []).length+" matching photos";
      } catch {status.textContent="Search is unavailable. Please try again later.";}
    });
  });
})();