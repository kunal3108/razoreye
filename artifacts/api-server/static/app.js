const modal = document.querySelector("#add-modal");
document.querySelectorAll("[data-open-modal]").forEach((button) => {
  button.addEventListener("click", () => modal?.showModal());
});
document.querySelectorAll("[data-close-modal]").forEach((button) => {
  button.addEventListener("click", () => modal?.close());
});
modal?.addEventListener("click", (event) => {
  if (event.target === modal) modal.close();
});
document.querySelectorAll(".toast").forEach((toast) => {
  window.setTimeout(() => toast.remove(), 4500);
});