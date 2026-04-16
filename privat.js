// =============================================================
//  KONFIGURASJON — rediger denne seksjonen
// =============================================================

// Lim inn SHA-256-hashen av passordet ditt her.
// Tomt = oppsettmodus (siden viser deg hvordan du genererer hashen).
const PASSWORD_HASH = "";

// Smarthus-lenker
const SMARTHUS = [
  { label: "Home Assistant", url: "http://homeassistant.local:8123", icon: "🏠" },
  { label: "Kamera",         url: "http://",                         icon: "📷" },
  { label: "Varme",          url: "http://",                         icon: "🌡️" },
  // Legg til flere: { label: "Navn", url: "http://...", icon: "🔌" }
];

// Morgenbrief-lenker
const MORGENBRIEF = [
  { label: "Yr.no",            url: "https://www.yr.no",                  icon: "🌤️" },
  { label: "NRK Nyheter",      url: "https://www.nrk.no/nyheter/",        icon: "📰" },
  { label: "Google Kalender",  url: "https://calendar.google.com",         icon: "📅" },
  { label: "Gmail",            url: "https://mail.google.com",             icon: "✉️" },
  // Legg til flere: { label: "Navn", url: "https://...", icon: "🔗" }
];

// =============================================================
//  AUTENTISERING — ikke rediger under denne linjen
// =============================================================

const SESSION_KEY = "privat_auth";

/** Beregner SHA-256 av en streng og returnerer hex-streng */
async function hashPassword(password) {
  const msgBuffer  = new TextEncoder().encode(password);
  const hashBuffer = await crypto.subtle.digest("SHA-256", msgBuffer);
  return Array.from(new Uint8Array(hashBuffer))
    .map(b => b.toString(16).padStart(2, "0"))
    .join("");
}

/** Bygger et klikkbart lenke-kort */
function buildLinkCard(item) {
  const a = document.createElement("a");
  a.href   = item.url;
  a.target = "_blank";
  a.rel    = "noopener noreferrer";
  a.className = "link-card";
  a.innerHTML = `
    <span class="link-card-icon">${item.icon}</span>
    <span class="link-card-label">${item.label}</span>
  `;
  return a;
}

/** Fyller inn innhold i dashboardet */
function renderDashboard() {
  const smarthusGrid    = document.getElementById("smarthus-grid");
  const morgenbriefGrid = document.getElementById("morgenbrief-grid");

  SMARTHUS.forEach(item => smarthusGrid.appendChild(buildLinkCard(item)));
  MORGENBRIEF.forEach(item => morgenbriefGrid.appendChild(buildLinkCard(item)));
}

/** Viser kun det oppgitte view-elementet */
function showView(id) {
  ["setup-view", "login-view", "dashboard-view"].forEach(v => {
    document.getElementById(v).style.display = v === id ? "" : "none";
  });

  const isLoggedIn = id === "dashboard-view";
  document.getElementById("nav-logout-item").style.display = isLoggedIn ? "" : "none";
}

/** Logg ut */
function logout() {
  sessionStorage.removeItem(SESSION_KEY);
  showView("login-view");
  document.getElementById("login-pw").value = "";
}

// ---------------------------------------------------------------
//  Oppsettmodus — genererer hash og viser instruksjoner
// ---------------------------------------------------------------
function initSetupMode() {
  showView("setup-view");

  document.getElementById("setup-btn").addEventListener("click", async () => {
    const pw = document.getElementById("setup-pw").value;
    if (!pw) return;

    const hash   = await hashPassword(pw);
    const output = document.getElementById("hash-output");
    output.textContent = hash;
    document.getElementById("setup-result").style.display = "";
  });

  document.getElementById("setup-pw").addEventListener("keydown", e => {
    if (e.key === "Enter") document.getElementById("setup-btn").click();
  });
}

// ---------------------------------------------------------------
//  Innloggingsmodus
// ---------------------------------------------------------------
function initLoginMode() {
  if (sessionStorage.getItem(SESSION_KEY) === "ok") {
    renderDashboard();
    showView("dashboard-view");
    return;
  }

  showView("login-view");
  const pwInput  = document.getElementById("login-pw");
  const loginBtn = document.getElementById("login-btn");
  const errorMsg = document.getElementById("login-error");

  async function attemptLogin() {
    const pw   = pwInput.value;
    if (!pw) return;

    loginBtn.disabled = true;
    const hash = await hashPassword(pw);

    if (hash === PASSWORD_HASH) {
      sessionStorage.setItem(SESSION_KEY, "ok");
      errorMsg.classList.remove("visible");
      renderDashboard();
      showView("dashboard-view");
    } else {
      errorMsg.classList.add("visible");
      pwInput.value = "";
      pwInput.focus();
    }

    loginBtn.disabled = false;
  }

  loginBtn.addEventListener("click", attemptLogin);
  pwInput.addEventListener("keydown", e => { if (e.key === "Enter") attemptLogin(); });
}

// ---------------------------------------------------------------
//  Oppstart
// ---------------------------------------------------------------
document.addEventListener("DOMContentLoaded", () => {
  // Koble til logg ut-knapper
  document.getElementById("nav-logout").addEventListener("click", logout);
  document.getElementById("dashboard-logout").addEventListener("click", logout);

  if (!PASSWORD_HASH) {
    initSetupMode();
  } else {
    initLoginMode();
  }
});
