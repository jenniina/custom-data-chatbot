// Progressive enhancements only. All workflows also work with JavaScript disabled.
document.querySelectorAll("form[data-busy]").forEach(form => {
  form.addEventListener("submit", event => {
    if (form.dataset.submitting) { event.preventDefault(); return; }
    form.dataset.submitting = "true";
    const status = form.querySelector(".busy-status");
    status.hidden = false;
    status.textContent = form.dataset.busy;
    form.querySelectorAll("button[type=submit], button:not([type])").forEach(button => { button.disabled = true; });
  });
});
const question = document.getElementById("id_question");
question?.addEventListener("keydown", event => {
  if (event.key === "Enter" && !event.shiftKey && !event.isComposing) {
    event.preventDefault();
    const form = question.form;
    if (!form.querySelector("button[type=submit]").disabled) form.requestSubmit();
  }
});
const errors = document.getElementById("form-errors");
if (errors) errors.focus();
else if (location.hash === "#latest-answer") document.getElementById("latest-answer")?.focus();
window.addEventListener("pageshow", event => {
  if (!event.persisted) return;
  document.querySelectorAll("form[data-submitting]").forEach(form => {
    delete form.dataset.submitting;
    form.querySelectorAll("button").forEach(button => { button.disabled = false; });
    form.querySelector(".busy-status").hidden = true;
  });
});
