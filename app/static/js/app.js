document.addEventListener("click", async (event) => {
  const button = event.target.closest("[data-copy-target]");
  if (!button) return;

  const target = document.getElementById(button.dataset.copyTarget);
  if (!target) return;

  await navigator.clipboard.writeText(target.innerText);
  const original = button.innerText;
  button.innerText = "Copied";
  window.setTimeout(() => {
    button.innerText = original;
  }, 1400);
});
