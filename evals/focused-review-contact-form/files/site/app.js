let slide = 0;
const slides = document.querySelectorAll('.slide');
function showSlide(i) {
  slides.forEach((s, n) => s.classList.toggle('active', n === i));
}
function nextSlide() { slide = (slide + 1) % slides.length; showSlide(slide); }
function prevSlide() { slide = (slide - 1 + slides.length) % slides.length; showSlide(slide); }
if (slides.length) setInterval(nextSlide, 3000);

function toggleMenu() { document.getElementById('menu').classList.toggle('open'); }

function closeModal() { document.getElementById('cookie-modal').classList.remove('open'); }
window.addEventListener('load', () => {
  const m = document.getElementById('cookie-modal');
  if (m && !localStorage.getItem('cookies-ok')) m.classList.add('open');
});

function subscribe(e) {
  e.preventDefault();
  const email = document.getElementById('nl-email');
  const result = document.getElementById('nl-result');
  if (!email.value.includes('@')) {
    email.classList.add('invalid');
    return false;
  }
  result.textContent = 'Bedankt, je bent aangemeld.';
  return false;
}

function toggleAgree() { document.getElementById('agree').classList.toggle('checked'); }

function submitContact() {
  const required = ['name', 'email', 'message'];
  let ok = true;
  required.forEach((id) => {
    const el = document.getElementById(id);
    const bad = !el.value.trim();
    el.classList.toggle('invalid', bad);
    if (bad) ok = false;
  });
  const result = document.getElementById('form-result');
  if (!ok) { result.textContent = ''; return; }
  result.textContent = 'Uw bericht is verzonden.';
  setTimeout(() => { result.textContent = ''; }, 2000);
}
