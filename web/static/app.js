document.addEventListener("click", (event) => {
  const target = event.target;
  if (target instanceof HTMLElement && target.classList.contains("tab")) {
    document.querySelectorAll(".tab").forEach((tab) => {
      tab.classList.remove("active");
    });
    target.classList.add("active");
  }
});
    target.classList.add("active");
  }
});

console.log('=== HTMX Debug ===');
console.log('HTMX available:', typeof window.htmx !== 'undefined');
console.log('HTMX version:', window.htmx?.version);

document.body.addEventListener('htmx:afterRequest', (e) => {
  console.log('HTMX afterRequest:', e.detail.successful ? 'SUCCESS' : 'FAILED');
});

document.body.addEventListener('htmx:sendError', (e) => {
  console.log('HTMX send error:', e.detail);
});

document.body.addEventListener('htmx:responseError', (e) => {
  console.log('HTMX response error:', e.detail);
});

document.body.addEventEventListener('htmx:beforeRequest', (e) => {
  console.log('HTMX beforeRequest:', e.detail);
});
