document.addEventListener("click", (event) => {
  const target = event.target;
  if (target instanceof HTMLElement && target.classList.contains("tab")) {
    document.querySelectorAll(".tab").forEach((tab) => {
      tab.classList.remove("active");
    });
    target.classList.add("active");
  }
});
