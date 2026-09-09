/* ---------- utils ---------- */
const fmtEUR = n => n.toLocaleString('fr-FR', { style: 'currency', currency: 'EUR' });
const fmtNum = n => n.toLocaleString('fr-FR');
const fmtDate = iso => new Date(iso).toLocaleDateString('fr-FR', { day: '2-digit', month: 'short' });
const fmtDateTime = iso => new Date(iso).toLocaleString('fr-FR', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' });
const uid = () => Math.random().toString(36).slice(2, 9);
const clamp = (n, min, max) => Math.max(min, Math.min(max, n));
const daysAgo = n => { const d = new Date(); d.setDate(d.getDate() - n); return d; };
const isoDaysAgo = n => daysAgo(n).toISOString();

const CHANNEL_META = {
  shopify: { label: 'Shopify', color: 'var(--cat-shopify)', initials: 'Sh' },
  etsy: { label: 'Etsy', color: 'var(--cat-etsy)', initials: 'Et' },
  instagram: { label: 'Instagram Shop', color: 'var(--cat-instagram)', initials: 'Ig' },
  woocommerce: { label: 'WooCommerce', color: 'var(--cat-woocommerce)', initials: 'Wc' },
  tiktok: { label: 'TikTok Shop', color: 'var(--cat-tiktok)', initials: 'Tk' },
  custom: { label: 'Personnalisé', color: 'var(--cat-custom)', initials: '{}' }
};

const FIELD_CATALOG = {
  manual: [
    { key: 'note_interne', label: 'Note interne' },
    { key: 'priorite', label: 'Priorité' },
    { key: 'emballe_par', label: 'Emballé par' },
    { key: 'etiquette', label: 'Étiquette / mention' }
  ],
  shopify: [
    { key: 'tracking_number', label: 'Numéro de suivi' },
    { key: 'shopify_tags', label: 'Tags Shopify' },
    { key: 'fulfillment_status', label: "Statut d'exécution" }
  ],
  etsy: [
    { key: 'etsy_message', label: 'Message acheteur' },
    { key: 'etsy_gift', label: 'Commande cadeau' }
  ],
  instagram: [
    { key: 'insta_handle', label: 'Identifiant Instagram' },
    { key: 'insta_post', label: 'Publication d\'origine' }
  ],
  woocommerce: [
    { key: 'woo_notes', label: 'Notes de commande' },
    { key: 'woo_coupon', label: 'Code promo utilisé' }
  ],
  tiktok: [
    { key: 'tiktok_video_ref', label: 'Vidéo associée' },
    { key: 'tiktok_creator', label: 'Créateur partenaire' }
  ],
  custom: [
    { key: 'ext_ref', label: 'Référence externe' },
    { key: 'ext_status', label: 'Statut plateforme' }
  ]
};

const SAV_FIELD_CATALOG = {
  manual: [
    { key: 'action_decidee', label: 'Action décidée' },
    { key: 'montant_rembourse', label: 'Montant remboursé' },
    { key: 'transporteur_retour', label: 'Transporteur retour' },
    { key: 'num_retour', label: 'Numéro de retour' },
    { key: 'note_sav', label: 'Note interne SAV' }
  ],
  shopify: [
    { key: 'etiquette_retour', label: 'Étiquette de retour' },
    { key: 'statut_remboursement', label: 'Statut du remboursement' }
  ],
  etsy: [
    { key: 'etsy_case', label: 'Litige Etsy ouvert' },
    { key: 'etsy_message_sav', label: 'Dernier message acheteur' }
  ],
  instagram: [
    { key: 'insta_conversation', label: 'Conversation Instagram' }
  ],
  woocommerce: [
    { key: 'woo_refund_id', label: 'Référence remboursement' }
  ],
  tiktok: [
    { key: 'tiktok_case_sav', label: 'Litige TikTok Shop' }
  ],
  custom: [
    { key: 'ext_sav_ref', label: 'Référence SAV externe' },
    { key: 'ext_sav_statut', label: 'Statut SAV plateforme' }
  ]
};

const ACCENTS = {
  teal: {
    label: 'Original (vert)',
    light: { brand: '#146356', bright: '#1F8F79', soft: 'rgba(20, 99, 86, 0.09)' },
    dark: { brand: '#35B597', bright: '#5FD1B4', soft: 'rgba(53, 181, 151, 0.15)' }
  },
  rouge: {
    label: 'Rouge',
    light: { brand: '#B5402A', bright: '#D14E35', soft: 'rgba(181, 64, 42, 0.09)' },
    dark: { brand: '#E2694A', bright: '#EF8563', soft: 'rgba(226, 105, 74, 0.15)' }
  },
  bleu: {
    label: 'Bleu',
    light: { brand: '#1D5FA5', bright: '#2E78C7', soft: 'rgba(29, 95, 165, 0.09)' },
    dark: { brand: '#4FA3E8', bright: '#7CBCF0', soft: 'rgba(79, 163, 232, 0.15)' }
  },
  violet: {
    label: 'Violet',
    light: { brand: '#5B3AA7', bright: '#7452C4', soft: 'rgba(91, 58, 167, 0.09)' },
    dark: { brand: '#9B85E9', bright: '#B3A2F0', soft: 'rgba(155, 133, 233, 0.15)' }
  },
  orange: {
    label: 'Orange',
    light: { brand: '#B5651D', bright: '#D07D2E', soft: 'rgba(181, 101, 29, 0.09)' },
    dark: { brand: '#E8944F', bright: '#F0AC74', soft: 'rgba(232, 148, 79, 0.15)' }
  }
};

const PLAN_META = {
  decouverte: { name: 'Découverte', price: 10, channels: 1, orders: 50 },
  multicanal: { name: 'Multicanal', price: 19, channels: 3, orders: 500 },
  croissance: { name: 'Croissance', price: 49, channels: Infinity, orders: 3000 }
};

/* ---------- seed data ---------- */
function buildCustomerDirectory() {
  return [
    { name: 'M. Dubois', email: 'marie.dubois@orange.fr', phone: '06 41 22 87 30', city: 'Lyon' },
    { name: 'S. Nguyen', email: 'sofia.nguyen@gmail.com', phone: '07 58 14 02 96', city: 'Paris' },
    { name: 'A. Rossi', email: 'a.rossi@libero.it', phone: '+39 340 221 8874', city: 'Turin' },
    { name: 'K. Haddad', email: 'karim.haddad@gmail.com', phone: '06 73 90 41 15', city: 'Marseille' },
    { name: 'L. Girard', email: 'lea.girard@hotmail.fr', phone: '06 12 55 78 03', city: 'Nantes' },
    { name: 'P. Costa', email: 'paulo.costa@sapo.pt', phone: '+351 912 480 337', city: 'Porto' },
    { name: 'N. Benali', email: 'nadia.benali@gmail.com', phone: '07 81 36 60 24', city: 'Toulouse' },
    { name: 'E. Morel', email: 'emma.morel@free.fr', phone: '06 95 07 33 48', city: 'Bordeaux' },
    { name: 'C. Laurent', email: 'c.laurent@outlook.fr', phone: '06 24 81 09 57', city: 'Lille' },
    { name: 'R. Fontaine', email: 'r.fontaine@gmail.com', phone: '07 44 63 18 92', city: 'Rennes' }
  ];
}

function seedData() {
  const connectors = [
    { id: uid(), type: 'shopify', label: 'Shopify', status: 'connected', connectedAt: isoDaysAgo(210), lastSync: isoDaysAgo(0) },
    { id: uid(), type: 'etsy', label: 'Etsy', status: 'connected', connectedAt: isoDaysAgo(140), lastSync: isoDaysAgo(0) },
    { id: uid(), type: 'instagram', label: 'Instagram Shop', status: 'connected', connectedAt: isoDaysAgo(60), lastSync: isoDaysAgo(1) },
    { id: uid(), type: 'custom', label: 'Boutique perso', status: 'connected', connectedAt: isoDaysAgo(30), lastSync: isoDaysAgo(2), apiKey: 'cpt_live_' + uid() + uid() }
  ];
  const byType = t => connectors.find(c => c.type === t);
  const weights = [['shopify', 0.48], ['etsy', 0.27], ['instagram', 0.17], ['custom', 0.08]];
  const customerDirectory = buildCustomerDirectory();
  const customers = customerDirectory.map(c => c.name);
  const productNames = ['Étole en lin écru', 'Bougie Cèdre 220g', 'Sac tissé beige', 'Coussin brodé', 'Carnet ligné kraft', 'Savon artisanal', 'Vase en grès', 'Plaid en laine'];

  function pickChannel() {
    const r = Math.random(); let acc = 0;
    for (const [t, w] of weights) { acc += w; if (r <= acc) return t; }
    return 'shopify';
  }
  function pickStatus() {
    const r = Math.random();
    if (r < 0.78) return 'livree';
    if (r < 0.93) return 'preparation';
    return 'retour';
  }

  const costPrices = [14, 6, 18, 12, 3, 2.5, 9, 22];
  const salePrices = [32, 15, 42, 28, 8, 7, 24, 55];
  const suppliers = ['Atelier Nord', 'Cire & Co', 'Fibres Douces', 'Atelier Nord', 'Papeterie Belloc', 'Savonnerie du Lac', 'Grès & Terre', 'Fibres Douces'];
  const products = productNames.map((name, i) => ({
    id: uid(),
    name,
    stock: [3, 24, 9, 40, 60, 11, 2, 18][i],
    threshold: 12,
    costPrice: costPrices[i],
    salePrice: salePrices[i],
    supplier: suppliers[i],
    custom: {},
    channels: i % 3 === 0 ? ['shopify', 'custom'] : i % 3 === 1 ? ['instagram'] : ['shopify', 'etsy']
  }));

  const orders = [];
  for (let i = 0; i < 260; i++) {
    const daysBack = Math.random() * 89;
    const type = pickChannel();
    const eligible = products.filter(p => p.channels.includes(type));
    const product = (eligible.length ? eligible : products)[Math.floor(Math.random() * (eligible.length ? eligible.length : products.length))];
    orders.push({
      id: uid(),
      orderNumber: 1000 + i,
      channelType: type,
      productId: product.id,
      customer: customers[Math.floor(Math.random() * customers.length)],
      amount: Math.round((18 + Math.random() * 122) * 100) / 100,
      status: pickStatus(),
      date: daysAgo(daysBack).toISOString(),
      custom: {}
    });
  }
  orders.sort((a, b) => new Date(b.date) - new Date(a.date));

  const returnOrders = orders.filter(o => o.status === 'retour').slice(0, 6);
  const savTickets = returnOrders.map((o, i) => ({
    id: uid(),
    orderId: o.id,
    orderNumber: o.orderNumber,
    product: productNames[i % productNames.length],
    channelType: o.channelType,
    reason: ['Taille non conforme', 'Produit endommagé', 'Erreur de commande', 'Changement d\'avis'][i % 4],
    status: i < 2 ? 'resolu' : 'ouvert',
    date: o.date,
    custom: {}
  }));

  return {
    theme: null,
    accent: 'teal',
    range: '30',
    rangeCustom: null,
    overviewGranularity: 'day',
    connectors,
    products,
    orders,
    customers: customerDirectory,
    customFields: [],
    savFields: [],
    savTickets,
    catalogFields: [],
    expenses: [
      { id: uid(), label: 'Abonnement Shopify', amount: 29, date: isoDaysAgo(12) },
      { id: uid(), label: 'Publicité Instagram', amount: 85, date: isoDaysAgo(9) },
      { id: uid(), label: 'Emballages', amount: 42, date: isoDaysAgo(20) }
    ],
    plan: { tier: 'multicanal', renewsAt: isoDaysAgo(-14) },
    billingHistory: [
      { id: uid(), date: isoDaysAgo(16), amount: 19, tier: 'Multicanal' },
      { id: uid(), date: isoDaysAgo(46), amount: 19, tier: 'Multicanal' },
      { id: uid(), date: isoDaysAgo(76), amount: 5, tier: 'Découverte' }
    ]
  };
}

// A real account starts with nothing fabricated — no fake orders, customers or
// pre-connected platforms. seedData() (above) is demo-only content, kept for local/dev
// exploration; every real signup gets this instead (see boot()).
function emptyState() {
  return {
    theme: null,
    accent: 'teal',
    range: '30',
    rangeCustom: null,
    overviewGranularity: 'day',
    connectors: [],
    products: [],
    orders: [],
    customers: [],
    customFields: [],
    savFields: [],
    savTickets: [],
    catalogFields: [],
    expenses: [],
    plan: { tier: 'decouverte', renewsAt: isoDaysAgo(-30) },
    billingHistory: []
  };
}

/* ---------- store ----------
 * Source of truth is the server (GET/PUT /api/state, one JSON document per
 * account — see server.py). localStorage is kept only as an instant local
 * cache: it paints something before the network round-trip resolves in
 * boot(), and it's a fallback if the server is briefly unreachable. */
const STORAGE_KEY = 'comptoir-proto-v1';
function loadLocalCache() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw) return JSON.parse(raw);
  } catch (e) {}
  return null;
}
function migrateState(s) {
  // Defensive: every collection defaults to empty before anything iterates over it — a
  // state blob missing a field (an older shape, a hand-built test payload, a partial PUT)
  // must degrade gracefully here rather than throw and force a fall-back to stale local data.
  s.orders = s.orders || [];
  s.products = s.products || [];
  s.connectors = s.connectors || [];
  s.savTickets = s.savTickets || [];
  s.billingHistory = s.billingHistory || [];
  s.plan = s.plan || { tier: 'decouverte', renewsAt: isoDaysAgo(-30) };
  s.range = s.range || '30';
  s.rangeCustom = s.rangeCustom || null;
  s.overviewGranularity = s.overviewGranularity || 'day';
  s.theme = s.theme ?? null;
  s.customFields = s.customFields || [];
  s.customFields.forEach(f => { f.source = f.source || 'manual'; });
  s.orders.forEach(o => { o.custom = o.custom || {}; });
  s.customers = s.customers || buildCustomerDirectory();
  s.accent = s.accent || 'teal';
  s.savFields = s.savFields || [];
  s.savTickets.forEach(t => { t.custom = t.custom || {}; });
  const defaultCosts = { 'Étole en lin écru': 14, 'Bougie Cèdre 220g': 6, 'Sac tissé beige': 18, 'Coussin brodé': 12, 'Carnet ligné kraft': 3, 'Savon artisanal': 2.5, 'Vase en grès': 9, 'Plaid en laine': 22 };
  s.catalogFields = s.catalogFields || [];
  s.expenses = s.expenses || [];
  s.expenses.forEach(e => { e.label = e.label || ''; e.amount = Number(e.amount) || 0; e.date = e.date || new Date().toISOString(); });
  s.products.forEach(p => {
    if (p.costPrice == null) p.costPrice = defaultCosts[p.name] ?? 0;
    if (p.salePrice == null) p.salePrice = null;
    if (p.supplier == null) p.supplier = '';
    p.custom = p.custom || {};
    p.channels = p.channels || [];
  });
  // Note: orders with no productId are left alone here on purpose. An older version of
  // this migration used to randomly assign one from the catalog — harmless for the
  // fabricated demo data it was written for, but it would fabricate sales history for a
  // real, genuinely-unlinked order (see server.py's ingest auto-create/backfill instead,
  // which is how a real order actually gets its product back).
  s.orders.forEach(o => {
    if (o.productId && !s.products.some(p => p.id === o.productId)) o.productId = null;
  });
  return s;
}
// Placeholder so nothing crashes before boot() resolves the real (server) state.
let state = migrateState(loadLocalCache() || emptyState());
let persistTimer = null;
function persist() {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
  const session = getSession();
  if (!session || !session.token) return;
  clearTimeout(persistTimer);
  persistTimer = setTimeout(() => {
    apiRequest('/api/state', { method: 'PUT', token: session.token, body: { data: JSON.stringify(state) } })
      .catch(() => { toast('Échec de la synchronisation avec le serveur.', true); });
  }, 500);
}
function setState(patch) { Object.assign(state, patch); persist(); render(); }

/* ---------- theme ---------- */
const mq = window.matchMedia('(prefers-color-scheme: dark)');
function resolvedTheme() { return state.theme === 'light' || state.theme === 'dark' ? state.theme : (mq.matches ? 'dark' : 'light'); }
function paintTheme() {
  document.documentElement.setAttribute('data-theme', resolvedTheme());
  applyAccent();
}
function applyAccent() {
  const a = ACCENTS[state.accent] || ACCENTS.teal;
  const vals = a[resolvedTheme()];
  const root = document.documentElement.style;
  root.setProperty('--brand', vals.brand);
  root.setProperty('--brand-bright', vals.bright);
  root.setProperty('--brand-soft', vals.soft);
  // The logo's four-tone palette stays fixed regardless of light/dark theme —
  // it blends both variants for its depth effect, so it only shifts with the accent choice.
  root.setProperty('--logo-deep', a.light.brand);
  root.setProperty('--logo-mid', a.dark.brand);
  root.setProperty('--logo-bright', a.dark.bright);
  root.setProperty('--logo-light', a.light.bright);
}
function toggleTheme() { state.theme = resolvedTheme() === 'dark' ? 'light' : 'dark'; persist(); paintTheme(); render(); }
mq.addEventListener('change', () => { paintTheme(); render(); });

/* ---------- auth ---------- */
const AUTH_KEY = 'comptoir-auth';
function getSession() { try { return JSON.parse(localStorage.getItem(AUTH_KEY)); } catch (e) { return null; } }
function setSession(token, email) { localStorage.setItem(AUTH_KEY, JSON.stringify({ token, email })); }
function clearSession() { localStorage.removeItem(AUTH_KEY); }

async function apiRequest(path, { method = 'GET', body, token } = {}) {
  const headers = { 'Content-Type': 'application/json' };
  if (token) headers.Authorization = `Bearer ${token}`;
  const res = await fetch(path, { method, headers, body: body ? JSON.stringify(body) : undefined });
  let data = {};
  try { data = await res.json(); } catch (e) {}
  if (!res.ok) throw new Error(data.error || `Erreur ${res.status}`);
  return data;
}

const AUTH_MARK = `<svg viewBox="50 50 500 470" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
  <path d="M445 92C386 34 302 0 208 0C93 0 0 93 0 208s93 208 208 208c94 0 178-34 237-92l-65-65c-43 40-102 63-172 63-63 0-114-51-114-114S145 94 208 94c70 0 129 23 172 63z" fill="var(--logo-deep)" transform="translate(75 75)"/>
  <path d="M16 264c31 91 106 152 192 152 71 0 135-27 184-73l-66-65c-31 28-72 44-118 44-44 0-82-24-100-58-17-31-14-56-14-56-21 14-51 37-78 56z" fill="var(--logo-mid)" transform="translate(75 75)"/>
  <g transform="translate(205 210)">
    <path d="M78 0l80 42-80 44L0 42z" fill="var(--logo-bright)"/>
    <path d="M0 42l78 44v88L0 130z" fill="var(--logo-deep)"/>
    <path d="M158 42L78 86v88l80-44z" fill="var(--logo-light)"/>
    <path d="M78 4v82M49 25l79 42" stroke="#fff" stroke-width="9" fill="none"/>
  </g>
</svg>`;

const LOGO_FONT = "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif";

function renderSplash(done) {
  if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return done();
  document.getElementById('appRoot').style.display = 'none';
  document.getElementById('authRoot').innerHTML = `
    <div class="splash" id="splash">
      <svg class="splash-svg logo-anim-svg" viewBox="0 0 2200 650" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
        <g transform="translate(75 75)">
          <path class="s-p s-arc1" d="M445 92C386 34 302 0 208 0C93 0 0 93 0 208s93 208 208 208c94 0 178-34 237-92l-65-65c-43 40-102 63-172 63-63 0-114-51-114-114S145 94 208 94c70 0 129 23 172 63z" fill="var(--logo-deep)"/>
          <path class="s-p s-arc2" d="M16 264c31 91 106 152 192 152 71 0 135-27 184-73l-66-65c-31 28-72 44-118 44-44 0-82-24-100-58-17-31-14-56-14-56-21 14-51 37-78 56z" fill="var(--logo-mid)"/>
          <g transform="translate(130 135)">
            <path class="s-p s-top" d="M78 0l80 42-80 44L0 42z" fill="var(--logo-bright)"/>
            <path class="s-p s-left" d="M0 42l78 44v88L0 130z" fill="var(--logo-deep)"/>
            <path class="s-p s-right" d="M158 42L78 86v88l80-44z" fill="var(--logo-light)"/>
            <path class="s-p s-lines" d="M78 4v82M49 25l79 42" stroke="#fff" stroke-width="9" fill="none"/>
          </g>
        </g>
        <rect class="s-p s-title" x="650" y="155" width="2" height="245" fill="var(--ink)"/>
        <text class="s-p s-title" x="735" y="325" font-family="${LOGO_FONT}" font-size="170" font-weight="700" letter-spacing="-5" fill="var(--ink)">Comptoir</text>
        <text class="s-p s-tag1" x="740" y="430" font-family="${LOGO_FONT}" font-size="48" letter-spacing="1.5" fill="var(--ink)">Vendez partout.</text>
        <text class="s-p s-tag2" x="1112" y="430" font-family="${LOGO_FONT}" font-size="48" letter-spacing="1.5" fill="var(--brand)"> Comptez ici.</text>
      </svg>
    </div>
  `;
  setTimeout(() => {
    const el = document.getElementById('splash');
    if (el) el.classList.add('out');
    setTimeout(done, 320);
  }, 1400);
}

function renderTransition(done) {
  if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return done();
  document.getElementById('appRoot').style.display = 'none';
  document.getElementById('authRoot').innerHTML = `
    <div class="transition-screen" id="transScreen">
      <div class="t-wrap">
        <div class="t-mark-wrap">
          <span class="t-ring"></span>
          <span class="t-ring t-ring-2"></span>
          <svg class="t-mark logo-anim-svg" viewBox="0 0 2200 650" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
            <g transform="translate(75 75)">
              <path class="s-p s-arc1" d="M445 92C386 34 302 0 208 0C93 0 0 93 0 208s93 208 208 208c94 0 178-34 237-92l-65-65c-43 40-102 63-172 63-63 0-114-51-114-114S145 94 208 94c70 0 129 23 172 63z" fill="var(--logo-deep)"/>
              <path class="s-p s-arc2" d="M16 264c31 91 106 152 192 152 71 0 135-27 184-73l-66-65c-31 28-72 44-118 44-44 0-82-24-100-58-17-31-14-56-14-56-21 14-51 37-78 56z" fill="var(--logo-mid)"/>
              <g transform="translate(130 135)">
                <path class="s-p s-top" d="M78 0l80 42-80 44L0 42z" fill="var(--logo-bright)"/>
                <path class="s-p s-left" d="M0 42l78 44v88L0 130z" fill="var(--logo-deep)"/>
                <path class="s-p s-right" d="M158 42L78 86v88l80-44z" fill="var(--logo-light)"/>
                <path class="s-p s-lines" d="M78 4v82M49 25l79 42" stroke="#fff" stroke-width="9" fill="none"/>
              </g>
            </g>
            <rect class="s-p s-title" x="650" y="155" width="2" height="245" fill="var(--ink)"/>
            <text class="s-p s-title" x="735" y="325" font-family="${LOGO_FONT}" font-size="170" font-weight="700" letter-spacing="-5" fill="var(--ink)">Comptoir</text>
            <text class="s-p s-tag1" x="740" y="430" font-family="${LOGO_FONT}" font-size="48" letter-spacing="1.5" fill="var(--ink)">Vendez partout.</text>
            <text class="s-p s-tag2" x="1112" y="430" font-family="${LOGO_FONT}" font-size="48" letter-spacing="1.5" fill="var(--brand)"> Comptez ici.</text>
          </svg>
        </div>
      </div>
      <div class="t-label">Préparation de votre tableau de bord…</div>
    </div>
  `;
  setTimeout(() => {
    const el = document.getElementById('transScreen');
    if (el) el.classList.add('out');
    setTimeout(done, 320);
  }, 1450);
}

/* ---------- landing page ----------
 * Shown to visitors with no session — served by this same app, not a separate
 * marketing site, so its CTAs go straight into the real auth screen below
 * (renderAuth), which already talks to the real API. No separate signup path
 * to keep in sync. */
function renderLanding() {
  document.getElementById('appRoot').style.display = 'none';
  const dark = resolvedTheme() === 'dark';
  document.getElementById('authRoot').innerHTML = `
    <div id="landingRoot">
      <style>
        #landingRoot { background: var(--bg); color: var(--ink); }
        #landingRoot .wrap { max-width: 1080px; margin: 0 auto; padding: 0 24px; }
        #landingRoot section { position: relative; }
        #landingRoot a { color: inherit; }
        #landingRoot img, #landingRoot svg { display: block; max-width: 100%; }

        #landingRoot header.l-nav {
          position: sticky; top: 0; z-index: 20;
          background: color-mix(in srgb, var(--bg) 86%, transparent);
          backdrop-filter: blur(10px);
          border-bottom: 1px solid var(--rule-soft);
        }
        #landingRoot .l-nav-row { display: flex; align-items: center; justify-content: space-between; padding-top: 14px; padding-bottom: 14px; }
        #landingRoot .l-nav-brand { display: flex; align-items: center; gap: 9px; font-weight: 800; font-size: 16px; letter-spacing: -0.02em; }
        #landingRoot .l-nav-brand svg { width: 24px; height: 23px; }
        #landingRoot .l-nav-links { display: flex; align-items: center; gap: 28px; font-size: 13.5px; color: var(--ink-soft); }
        #landingRoot .l-nav-links a:hover { color: var(--ink); }
        #landingRoot .l-nav-right { display: flex; align-items: center; gap: 10px; }
        #landingRoot .l-nav-cta { font-family: var(--font); font-weight: 650; font-size: 13px; background: var(--ink); color: var(--bg); padding: 9px 16px; border-radius: 7px; white-space: nowrap; border: none; cursor: pointer; flex-shrink: 0; }
        #landingRoot .l-nav-cta:hover { background: var(--brand); color: #fff; }
        #landingRoot .l-nav-cta .l-cta-short { display: none; }
        #landingRoot .wrap.l-nav-row { flex-wrap: nowrap; gap: 10px; }
        #landingRoot .l-nav-brand span { white-space: nowrap; }
        @media (max-width: 640px) { #landingRoot .l-nav-links { display: none; } }
        @media (max-width: 480px) {
          #landingRoot .l-nav-cta .l-cta-full { display: none; }
          #landingRoot .l-nav-cta .l-cta-short { display: inline; }
          #landingRoot .l-nav-cta { padding: 8px 12px; font-size: 12.5px; }
          #landingRoot .l-toggle-label { display: none; }
          #landingRoot .theme-toggle { padding: 8px; }
        }

        #landingRoot .l-hero { padding: 88px 0 76px; overflow: hidden; }
        #landingRoot .l-hero-inner { position: relative; z-index: 2; max-width: 640px; }
        #landingRoot .l-eyebrow {
          display: inline-flex; align-items: center; gap: 8px;
          font-family: var(--font-mono); font-size: 11.5px; letter-spacing: 0.04em;
          color: var(--brand); background: var(--brand-soft); padding: 5px 11px 5px 9px; border-radius: 20px;
          margin-bottom: 22px;
        }
        #landingRoot .l-eyebrow .dot { width: 6px; height: 6px; border-radius: 50%; background: var(--brand); }
        #landingRoot h1.l-hero-h { font-size: clamp(38px, 6vw, 60px); line-height: 1.04; font-weight: 800; letter-spacing: -0.03em; margin: 0 0 22px; text-wrap: balance; }
        #landingRoot h1.l-hero-h .accent { color: var(--brand); }
        #landingRoot .l-hero-sub { font-size: 17px; line-height: 1.55; color: var(--ink-soft); max-width: 50ch; margin: 0 0 32px; }
        #landingRoot .l-hero-ctas { display: flex; gap: 10px; flex-wrap: wrap; }
        #landingRoot .l-btn-cta {
          height: 48px; padding: 0 22px; border-radius: 8px; font-weight: 650; font-size: 14.5px;
          cursor: pointer; display: inline-flex; align-items: center; justify-content: center; white-space: nowrap;
          border: 1px solid transparent; font-family: var(--font); text-decoration: none;
        }
        #landingRoot .l-btn-cta.primary { background: var(--brand); color: #fff; }
        #landingRoot .l-btn-cta.primary:hover { background: var(--brand-bright); }
        #landingRoot .l-btn-cta.ghost { background: transparent; border-color: var(--rule); color: var(--ink); }
        #landingRoot .l-btn-cta.ghost:hover { border-color: var(--brand); color: var(--brand); }
        #landingRoot .l-hero-note { font-size: 12.5px; color: var(--ink-faint); margin-top: 14px; }

        #landingRoot .l-hero-chart { position: absolute; right: -6%; top: 6%; width: 62%; height: 74%; z-index: 1; opacity: 0.9; pointer-events: none; }
        @media (max-width: 900px) { #landingRoot .l-hero-chart { opacity: 0.35; width: 100%; right: 0; } }
        #landingRoot .l-hero-chart .line { fill: none; stroke: var(--brand); stroke-width: 2.5; stroke-linecap: round; stroke-linejoin: round; }
        #landingRoot .l-hero-chart .area { fill: url(#landingHeroFill); }
        #landingRoot .l-hero-chart .dot { fill: var(--brand); }

        #landingRoot .l-section-head { max-width: 560px; margin: 0 0 40px; }
        #landingRoot .l-section-eyebrow { font-family: var(--font-mono); font-size: 11.5px; letter-spacing: 0.06em; text-transform: uppercase; color: var(--brand); margin-bottom: 10px; }
        #landingRoot h2.l-section-h { font-size: clamp(24px, 3.4vw, 32px); font-weight: 800; letter-spacing: -0.02em; margin: 0 0 10px; text-wrap: balance; }
        #landingRoot .l-section-sub { font-size: 15.5px; color: var(--ink-soft); line-height: 1.55; }

        #landingRoot .l-problem { padding: 90px 0; background: var(--surface-sunken); border-top: 1px solid var(--rule-soft); border-bottom: 1px solid var(--rule-soft); }
        #landingRoot .l-compare { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
        @media (max-width: 720px) { #landingRoot .l-compare { grid-template-columns: 1fr; } }
        #landingRoot .l-compare-card { background: var(--surface); border: 1px solid var(--rule-soft); border-radius: 12px; padding: 26px 24px; }
        #landingRoot .l-compare-card h3 { font-size: 13px; margin: 0 0 16px; text-transform: uppercase; letter-spacing: 0.04em; color: var(--ink-faint); }
        #landingRoot .l-compare-card.after { border-color: var(--brand); }
        #landingRoot .l-compare-card.after h3 { color: var(--brand); }
        #landingRoot .l-compare-list { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 13px; }
        #landingRoot .l-compare-list li { display: flex; gap: 10px; font-size: 14.5px; line-height: 1.5; color: var(--ink); }
        #landingRoot .l-compare-list .mk { flex: none; width: 16px; height: 16px; margin-top: 2px; }
        #landingRoot .l-compare-card.now .mk { color: var(--ink-faint); }
        #landingRoot .l-compare-card.after .mk { color: var(--brand); }

        #landingRoot .l-features { padding: 90px 0; }
        #landingRoot .l-feature-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 14px; }
        @media (max-width: 900px) { #landingRoot .l-feature-grid { grid-template-columns: repeat(2, 1fr); } }
        @media (max-width: 520px) { #landingRoot .l-feature-grid { grid-template-columns: 1fr; } }
        #landingRoot .l-feature-card { background: var(--surface); border: 1px solid var(--rule-soft); border-radius: 12px; padding: 22px 20px; }
        #landingRoot .l-feature-ico { width: 34px; height: 34px; border-radius: 9px; background: var(--brand-soft); color: var(--brand); display: flex; align-items: center; justify-content: center; margin-bottom: 14px; }
        #landingRoot .l-feature-ico svg { width: 18px; height: 18px; }
        #landingRoot .l-feature-card h3 { font-size: 15px; margin: 0 0 6px; }
        #landingRoot .l-feature-card p { font-size: 13.5px; color: var(--ink-soft); line-height: 1.5; margin: 0; }

        #landingRoot .l-channels { padding: 0 0 90px; }
        #landingRoot .l-channel-row { display: flex; flex-wrap: wrap; gap: 10px; }
        #landingRoot .l-channel-chip { display: flex; align-items: center; gap: 8px; border: 1px solid var(--rule-soft); background: var(--surface); border-radius: 20px; padding: 9px 16px 9px 12px; font-size: 13.5px; }
        #landingRoot .l-channel-chip .sw { width: 8px; height: 8px; border-radius: 50%; }
        #landingRoot .l-channel-chip.plus { border-style: dashed; color: var(--ink-faint); }

        #landingRoot .l-pricing { padding: 90px 0; background: var(--surface-sunken); border-top: 1px solid var(--rule-soft); border-bottom: 1px solid var(--rule-soft); }
        #landingRoot .l-plan-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 14px; }
        @media (max-width: 800px) { #landingRoot .l-plan-grid { grid-template-columns: 1fr; } }
        #landingRoot .l-plan-card { background: var(--surface); border: 1px solid var(--rule-soft); border-radius: 14px; padding: 26px 24px; display: flex; flex-direction: column; gap: 14px; }
        #landingRoot .l-plan-card.feat { border: 2px solid var(--brand); position: relative; }
        #landingRoot .l-plan-tag { position: absolute; top: -12px; left: 20px; background: var(--brand); color: #fff; font-size: 11px; font-weight: 700; padding: 3px 10px; border-radius: 20px; }
        #landingRoot .l-plan-name { font-weight: 700; font-size: 15.5px; }
        #landingRoot .l-plan-price { font-family: var(--font-mono); font-size: 30px; font-weight: 600; font-variant-numeric: tabular-nums; }
        #landingRoot .l-plan-price span { font-size: 12.5px; font-weight: 400; color: var(--ink-faint); }
        #landingRoot .l-plan-list { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 8px; font-size: 13.5px; color: var(--ink-soft); }
        #landingRoot .l-plan-list li::before { content: "+ "; color: var(--brand); font-weight: 700; }
        #landingRoot .l-plan-cta { margin-top: auto; width: 100%; text-align: center; padding: 10px; border-radius: 8px; border: 1px solid var(--rule); background: var(--surface); color: var(--ink); font-size: 13.5px; font-weight: 650; font-family: var(--font); cursor: pointer; }
        #landingRoot .l-plan-card.feat .l-plan-cta { background: var(--brand); border-color: var(--brand); color: #fff; }
        #landingRoot .l-plan-note { font-size: 12px; color: var(--ink-faint); margin-top: 24px; }

        #landingRoot .l-final { padding: 100px 0 110px; text-align: left; }
        #landingRoot .l-final-inner { max-width: 560px; }
        #landingRoot .l-final h2 { font-size: clamp(26px, 4vw, 38px); font-weight: 800; letter-spacing: -0.02em; margin: 0 0 14px; text-wrap: balance; }
        #landingRoot .l-final p { font-size: 15.5px; color: var(--ink-soft); margin: 0 0 30px; }

        #landingRoot footer.l-foot { border-top: 1px solid var(--rule-soft); padding: 28px 0 40px; }
        #landingRoot .l-foot-row { display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 12px; font-size: 12.5px; color: var(--ink-faint); }
        #landingRoot .l-foot-brand { display: flex; align-items: center; gap: 8px; }
        #landingRoot .l-foot-brand svg { width: 18px; height: 17px; }
        #landingRoot .l-foot-links { display: flex; align-items: center; gap: 18px; }
        #landingRoot .l-foot-links a { color: var(--ink-faint); text-decoration: none; }
        #landingRoot .l-foot-links a:hover { color: var(--brand); text-decoration: underline; }
      </style>

      <header class="l-nav">
        <div class="wrap l-nav-row">
          <div class="l-nav-brand">${AUTH_MARK}Comptoir</div>
          <nav class="l-nav-links">
            <a href="#l-fonctionnalites">Fonctionnalités</a>
            <a href="#l-tarifs">Tarifs</a>
          </nav>
          <div class="l-nav-right">
            <button class="theme-toggle" data-action="landingToggleTheme">
              ${dark
                ? `<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.4"><circle cx="8" cy="8" r="3"/><path d="M8 1v1.6M8 13.4V15M2.6 8H1M15 8h-1.6M3.5 3.5l1.1 1.1M11.4 11.4l1.1 1.1M12.5 3.5l-1.1 1.1M4.6 11.4l-1.1 1.1"/></svg>`
                : `<svg viewBox="0 0 16 16" fill="currentColor"><path d="M13.5 9.8A5.8 5.8 0 0 1 6.2 2.5a5.8 5.8 0 1 0 7.3 7.3z"/></svg>`}
              <span class="l-toggle-label">${dark ? 'Sombre' : 'Clair'}</span>
            </button>
            <button class="l-nav-cta" data-action="authSwitch" data-mode="signup" type="button"><span class="l-cta-full">Créer un compte / Se connecter</span><span class="l-cta-short">Connexion</span></button>
          </div>
        </div>
      </header>

      <section class="l-hero">
        <div class="wrap">
          <div class="l-hero-inner">
            <div class="l-eyebrow"><span class="dot"></span>Multicanal · Stock synchronisé · Facturation automatique</div>
            <h1 class="l-hero-h">Vendez partout.<br><span class="accent">Comptez ici.</span></h1>
            <p class="l-hero-sub">Comptoir centralise vos ventes Shopify, Etsy, Instagram et vos plateformes personnalisées dans un seul tableau de bord — stock synchronisé, alertes automatiques, zéro tableur.</p>
            <div class="l-hero-ctas">
              <button class="l-btn-cta primary" data-action="authSwitch" data-mode="signup" type="button">Créer un compte</button>
              <a class="l-btn-cta ghost" href="#l-tarifs">Voir les tarifs</a>
            </div>
            <div class="l-hero-note">Installation en moins de 5 minutes. Sans engagement de durée.</div>
          </div>
        </div>
        <svg class="l-hero-chart" viewBox="0 0 500 340" preserveAspectRatio="xMidYMid meet" aria-hidden="true">
          <defs>
            <linearGradient id="landingHeroFill" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stop-color="var(--brand)" stop-opacity="0.22"/>
              <stop offset="100%" stop-color="var(--brand)" stop-opacity="0"/>
            </linearGradient>
          </defs>
          <polygon class="area" points="0,300 20,285 55,292 90,255 125,268 160,222 195,238 230,190 265,205 300,150 335,168 370,110 405,128 440,70 475,88 500,60 500,340 0,340"/>
          <polyline class="line" points="0,300 20,285 55,292 90,255 125,268 160,222 195,238 230,190 265,205 300,150 335,168 370,110 405,128 440,70 475,88 500,60"/>
          <circle class="dot" cx="500" cy="60" r="5.5"/>
        </svg>
      </section>

      <section class="l-problem">
        <div class="wrap">
          <div class="l-section-head">
            <div class="l-section-eyebrow">Le problème</div>
            <h2 class="l-section-h">Vous vendez déjà sur plusieurs canaux. Vos outils, eux, ne se parlent pas.</h2>
            <p class="l-section-sub">Chaque plateforme a son propre tableau de bord — aucune ne voit ce qui se passe chez les autres.</p>
          </div>
          <div class="l-compare">
            <div class="l-compare-card now">
              <h3>Aujourd'hui</h3>
              <ul class="l-compare-list">
                <li><svg class="mk" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.6"><path d="M4 4l8 8M12 4l-8 8"/></svg>Un onglet par plateforme, ouverts en permanence</li>
                <li><svg class="mk" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.6"><path d="M4 4l8 8M12 4l-8 8"/></svg>Un tableur pour recouper le chiffre d'affaires</li>
                <li><svg class="mk" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.6"><path d="M4 4l8 8M12 4l-8 8"/></svg>Le stock mis à jour à la main, canal par canal</li>
                <li><svg class="mk" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.6"><path d="M4 4l8 8M12 4l-8 8"/></svg>La rupture de stock découverte après-coup</li>
              </ul>
            </div>
            <div class="l-compare-card after">
              <h3>Avec Comptoir</h3>
              <ul class="l-compare-list">
                <li><svg class="mk" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M3 8.5l3 3 7-7"/></svg>Un seul tableau de bord pour tous vos canaux</li>
                <li><svg class="mk" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M3 8.5l3 3 7-7"/></svg>Le chiffre d'affaires consolidé, en temps réel</li>
                <li><svg class="mk" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M3 8.5l3 3 7-7"/></svg>Un stock partagé, décrémenté automatiquement</li>
                <li><svg class="mk" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M3 8.5l3 3 7-7"/></svg>Une alerte avant la rupture, pas après</li>
              </ul>
            </div>
          </div>
        </div>
      </section>

      <section class="l-features" id="l-fonctionnalites">
        <div class="wrap">
          <div class="l-section-head">
            <div class="l-section-eyebrow">Fonctionnalités</div>
            <h2 class="l-section-h">Tout ce qu'il faut, rien de plus</h2>
          </div>
          <div class="l-feature-grid">
            <div class="l-feature-card">
              <div class="l-feature-ico"><svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M2 3l4.5 3-4.5 3M14 3l-4.5 3 4.5 3M6.5 13h3"/></svg></div>
              <h3>Centralisation multicanal</h3>
              <p>Shopify, Etsy, Instagram Shop et vos plateformes personnalisées, réunis dans un seul tableau de bord.</p>
            </div>
            <div class="l-feature-card">
              <div class="l-feature-ico"><svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M2 4l6-3 6 3v8l-6 3-6-3z"/></svg></div>
              <h3>Stock synchronisé</h3>
              <p>Un stock partagé entre canaux, avec une alerte avant la rupture — pas après.</p>
            </div>
            <div class="l-feature-card">
              <div class="l-feature-ico"><svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5"><circle cx="8" cy="8" r="6"/><path d="M8 5v3l2 2"/></svg></div>
              <h3>Connecteurs en libre-service</h3>
              <p>Ajoutez une plateforme vous-même, en quelques minutes — sans ticket support.</p>
            </div>
            <div class="l-feature-card">
              <div class="l-feature-ico"><svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5"><rect x="2" y="4" width="12" height="8" rx="1.2"/><path d="M2 6.5h12"/></svg></div>
              <h3>Facturation automatique</h3>
              <p>Changez de forfait en un clic — débloqué immédiatement, sans attendre personne.</p>
            </div>
          </div>
        </div>
      </section>

      <section class="l-channels">
        <div class="wrap">
          <div class="l-channel-row">
            <div class="l-channel-chip"><span class="sw" style="background:var(--cat-shopify)"></span>Shopify</div>
            <div class="l-channel-chip"><span class="sw" style="background:var(--cat-etsy)"></span>Etsy</div>
            <div class="l-channel-chip"><span class="sw" style="background:var(--cat-instagram)"></span>Instagram Shop</div>
            <div class="l-channel-chip"><span class="sw" style="background:var(--cat-woocommerce)"></span>WooCommerce</div>
            <div class="l-channel-chip plus">+ votre plateforme, via API</div>
          </div>
        </div>
      </section>

      <section class="l-pricing" id="l-tarifs">
        <div class="wrap">
          <div class="l-section-head">
            <div class="l-section-eyebrow">Tarifs</div>
            <h2 class="l-section-h">Un prix d'entrée pensé pour débuter petit</h2>
            <p class="l-section-sub">Vous grandissez, votre forfait grandit avec vous.</p>
          </div>
          <div class="l-plan-grid">
            ${Object.entries(PLAN_META).map(([key, p]) => `
              <div class="l-plan-card ${key === 'multicanal' ? 'feat' : ''}">
                ${key === 'multicanal' ? '<span class="l-plan-tag">Le plus choisi</span>' : ''}
                <div class="l-plan-name">${p.name}</div>
                <div class="l-plan-price">${fmtEUR(p.price)}<span>/mois</span></div>
                <ul class="l-plan-list"><li>${p.channels === Infinity ? 'Canaux illimités' : p.channels + ' canal' + (p.channels > 1 ? 'aux' : '')}</li><li>${fmtNum(p.orders)} commandes / mois</li></ul>
                <button class="l-plan-cta" data-action="authSwitch" data-mode="signup" type="button">Choisir ${p.name}</button>
              </div>
            `).join('')}
          </div>
          <div class="l-plan-note">Résiliable à tout moment, sans engagement de durée.</div>
        </div>
      </section>

      <section class="l-final">
        <div class="wrap l-final-inner">
          <h2>Prêt à centraliser vos ventes ?</h2>
          <p>Créez votre compte et connectez votre première plateforme en quelques minutes.</p>
          <div class="l-hero-ctas">
            <button class="l-btn-cta primary" data-action="authSwitch" data-mode="signup" type="button">Créer un compte</button>
            <a class="l-btn-cta ghost" href="#l-tarifs">Comparer les forfaits</a>
          </div>
        </div>
      </section>

      <footer class="l-foot">
        <div class="wrap l-foot-row">
          <div class="l-foot-brand">${AUTH_MARK}Comptoir</div>
          <div class="l-foot-links">
            <a href="mailto:contact@getcomptoir.fr">contact@getcomptoir.fr</a>
            <span>© 2026 Comptoir. Vendez partout. Comptez ici.</span>
          </div>
        </div>
      </footer>
    </div>
  `;
}

function renderAuth(mode) {
  const isSignup = mode === 'signup';
  document.getElementById('appRoot').style.display = 'none';
  document.getElementById('authRoot').innerHTML = `
    <div class="auth-wrap">
      <div class="auth-card">
        <div class="auth-brand">${AUTH_MARK}<span>Comptoir</span></div>
        <h1>${isSignup ? 'Créer votre compte' : 'Connexion'}</h1>
        <div class="auth-sub">${isSignup ? 'Commencez à centraliser vos ventes en quelques secondes.' : 'Accédez à votre tableau de bord.'}</div>
        <div id="authError"></div>
        <form id="authForm">
          <div class="field"><label>Adresse email</label><input type="email" id="authEmail" placeholder="vous@boutique.fr" required></div>
          <div class="field"><label>Mot de passe</label><input type="password" id="authPassword" placeholder="••••••••" required minlength="8"></div>
          ${isSignup ? `<div class="field"><label>Confirmer le mot de passe</label><input type="password" id="authPassword2" placeholder="••••••••" required minlength="8"></div>` : ''}
          <button type="submit" class="btn primary" id="authSubmitBtn">${isSignup ? 'Créer mon compte' : 'Se connecter'}</button>
        </form>
        <div class="auth-switch">
          ${isSignup
            ? `Déjà un compte ? <button type="button" data-action="authSwitch" data-mode="login">Se connecter</button>`
            : `Pas encore de compte ? <button type="button" data-action="authSwitch" data-mode="signup">Créer un compte</button>`}
        </div>
      </div>
    </div>
  `;
  document.getElementById('authForm').addEventListener('submit', async e => {
    e.preventDefault();
    const email = document.getElementById('authEmail').value.trim();
    const password = document.getElementById('authPassword').value;
    const errBox = document.getElementById('authError');
    const submitBtn = document.getElementById('authSubmitBtn');
    errBox.innerHTML = '';
    if (!email || !password) { errBox.innerHTML = '<div class="auth-error">Merci de renseigner votre email et votre mot de passe.</div>'; return; }
    if (isSignup && password !== document.getElementById('authPassword2').value) {
      errBox.innerHTML = '<div class="auth-error">Les mots de passe ne correspondent pas.</div>';
      return;
    }
    submitBtn.disabled = true;
    submitBtn.textContent = isSignup ? 'Création…' : 'Connexion…';
    try {
      const data = await apiRequest(isSignup ? '/api/signup' : '/api/login', { method: 'POST', body: { email, password } });
      setSession(data.token, data.email);
      renderTransition(boot);
    } catch (err) {
      errBox.innerHTML = `<div class="auth-error">${escapeHTML(err.message)}</div>`;
      submitBtn.disabled = false;
      submitBtn.textContent = isSignup ? 'Créer mon compte' : 'Se connecter';
    }
  });
}

async function boot() {
  const session = getSession();
  if (!session || !session.token) return renderLanding();
  let me;
  try {
    me = await apiRequest('/api/me', { token: session.token });
  } catch (err) {
    clearSession();
    return renderAuth('login');
  }
  try {
    const stateRes = await apiRequest('/api/state', { token: session.token });
    if (stateRes.data) {
      state = migrateState(JSON.parse(stateRes.data));
    } else {
      // Brand-new account: start with nothing fabricated, persisted server-side right away.
      state = migrateState(emptyState());
      await apiRequest('/api/state', { method: 'PUT', token: session.token, body: { data: JSON.stringify(state) } });
    }
    localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
  } catch (err) {
    console.error('Impossible de charger les données depuis le serveur, utilisation du cache local.', err);
    toast('Connexion au serveur impossible, données locales utilisées.', true);
  }
  document.getElementById('authRoot').innerHTML = '';
  document.getElementById('appRoot').style.display = '';
  const label = document.getElementById('userEmailLabel');
  if (label) label.textContent = me.email;
  paintTheme();
  render();
}

/* ---------- toasts ---------- */
function toast(msg, isErr) {
  const stack = document.getElementById('toastStack');
  const el = document.createElement('div');
  el.className = 'toast' + (isErr ? ' err' : '');
  el.textContent = msg;
  stack.appendChild(el);
  setTimeout(() => el.remove(), 3200);
}

/* ---------- modal ---------- */
function openModal(html, onMount) {
  const root = document.getElementById('modalRoot');
  root.innerHTML = `<div class="modal-overlay" id="modalOverlay"><div class="modal" id="modalBody">${html}</div></div>`;
  document.getElementById('modalOverlay').addEventListener('click', e => {
    if (e.target.id === 'modalOverlay') closeModal();
  });
  if (onMount) onMount(root);
}
function closeModal() { document.getElementById('modalRoot').innerHTML = ''; }

/* ---------- router ---------- */
const ROUTES = [
  { path: '', label: "Vue d'ensemble", icon: 'M2 9h3v5H2zM6.5 5h3v9h-3zM11 2h3v12h-3z' },
  { path: 'ventes', label: 'Ventes', icon: null },
  { path: 'stock', label: 'Stock', icon: null },
  { path: 'catalogue', label: 'Mon catalogue', icon: null },
  { path: 'sav', label: 'SAV', icon: null },
  { path: 'connecteurs', label: 'Connecteurs', icon: null },
  { path: 'facturation', label: 'Facturation', icon: null },
  { path: 'comptabilite', label: 'Comptabilité', icon: null },
  { path: 'parametres', label: 'Paramètres', icon: null }
];
function currentPath() { return (location.hash || '#').slice(1); }
window.addEventListener('hashchange', render);

/* ---------- helpers: connectors ---------- */
function connectedTypes() { return state.connectors.filter(c => c.status === 'connected'); }
function connectorLabel(type) {
  const c = state.connectors.find(c => c.type === type);
  return c ? c.label : (CHANNEL_META[type] ? CHANNEL_META[type].label : type);
}
function channelColor(type) { return CHANNEL_META[type] ? CHANNEL_META[type].color : 'var(--ink-faint)'; }

/* ---------- KPI computation ---------- */
// A range is always resolved to explicit {from, to} Date bounds (inclusive) before use —
// this is what lets a preset ('7'/'30'/'90') and a custom date-to-date pick share every
// downstream computation (KPIs, charts, accounting) without those needing to know which
// kind of range produced them.
function getRangeBounds() {
  if (state.range === 'custom' && state.rangeCustom && state.rangeCustom.from && state.rangeCustom.to) {
    const from = new Date(state.rangeCustom.from + 'T00:00:00');
    const to = new Date(state.rangeCustom.to + 'T23:59:59.999');
    if (!isNaN(from) && !isNaN(to) && from <= to) return { from, to };
  }
  const days = Number(state.range) || 30;
  return { from: daysAgo(days), to: new Date() };
}
function rangeDayCount(bounds) {
  return Math.max(1, Math.round((bounds.to.getTime() - bounds.from.getTime()) / 86400000));
}
function rangeLabel(bounds) {
  if (state.range === 'custom') return `du ${fmtDate(bounds.from.toISOString())} au ${fmtDate(bounds.to.toISOString())}`;
  return `${rangeDayCount(bounds)} derniers jours`;
}
function ordersInRange(bounds) {
  const from = bounds.from.getTime(), to = bounds.to.getTime();
  return state.orders.filter(o => { const t = new Date(o.date).getTime(); return t >= from && t <= to; });
}
function computeKPIs(bounds) {
  const cur = ordersInRange(bounds);
  const span = bounds.to.getTime() - bounds.from.getTime();
  const prevFrom = bounds.from.getTime() - span;
  const prevTo = bounds.from.getTime();
  const prev = state.orders.filter(o => { const t = new Date(o.date).getTime(); return t >= prevFrom && t < prevTo; });

  const ca = cur.reduce((s, o) => s + o.amount, 0);
  const caPrev = prev.reduce((s, o) => s + o.amount, 0);
  const count = cur.length;
  const countPrev = prev.length || 1;
  const panier = count ? ca / count : 0;
  const panierPrev = prev.length ? caPrev / prev.length : panier;
  const retours = cur.filter(o => o.status === 'retour').length;
  const tauxRetour = count ? (retours / count) * 100 : 0;
  const retoursPrev = prev.filter(o => o.status === 'retour').length;
  const tauxRetourPrev = prev.length ? (retoursPrev / prev.length) * 100 : tauxRetour;

  const pct = (a, b) => b ? Math.round(((a - b) / b) * 1000) / 10 : 0;

  return {
    ca, caDelta: pct(ca, caPrev),
    count, countDelta: pct(count, countPrev),
    panier, panierDelta: pct(panier, panierPrev),
    tauxRetour, tauxRetourDelta: Math.round((tauxRetour - tauxRetourPrev) * 10) / 10
  };
}
// Buckets a date into a granularity-aligned key: a calendar day, an ISO (Monday-start)
// week, or a calendar month — so "par semaine" / "par mois" reads as real weeks/months,
// not arbitrary N-day slices.
function bucketStart(date, granularity) {
  const d = new Date(date);
  d.setHours(0, 0, 0, 0);
  if (granularity === 'month') { d.setDate(1); return d; }
  if (granularity === 'week') { const dow = (d.getDay() + 6) % 7; d.setDate(d.getDate() - dow); return d; }
  return d;
}
function bucketKey(date, granularity) { return bucketStart(date, granularity).getTime(); }
function stepBucket(d, granularity) {
  const next = new Date(d);
  if (granularity === 'month') next.setMonth(next.getMonth() + 1);
  else if (granularity === 'week') next.setDate(next.getDate() + 7);
  else next.setDate(next.getDate() + 1);
  return next;
}
function bucketLabel(t, granularity) {
  const d = new Date(t);
  if (granularity === 'month') return d.toLocaleDateString('fr-FR', { month: 'short', year: 'numeric' });
  if (granularity === 'week') { const end = new Date(d); end.setDate(d.getDate() + 6); return `Sem. du ${d.toLocaleDateString('fr-FR', { day: '2-digit', month: '2-digit' })}`; }
  return d.toLocaleDateString('fr-FR', { day: '2-digit', month: 'short' });
}
function trendSeries(bounds, granularity) {
  const cur = ordersInRange(bounds);
  const keys = [];
  let cursor = bucketStart(bounds.from, granularity);
  let guard = 0;
  while (cursor.getTime() <= bounds.to.getTime() && guard < 400) {
    keys.push(cursor.getTime());
    cursor = stepBucket(cursor, granularity);
    guard++;
  }
  if (!keys.length) keys.push(bucketStart(bounds.from, granularity).getTime());
  const map = {};
  keys.forEach(t => { map[t] = { t, ca: 0, count: 0 }; });
  cur.forEach(o => {
    const key = bucketKey(new Date(o.date), granularity);
    if (!map[key]) return;
    map[key].ca += o.amount;
    map[key].count += 1;
  });
  return keys.map(t => map[t]);
}
function channelBreakdown(bounds) {
  const cur = ordersInRange(bounds);
  const total = cur.reduce((s, o) => s + o.amount, 0) || 1;
  const byType = {};
  cur.forEach(o => { byType[o.channelType] = (byType[o.channelType] || 0) + o.amount; });
  return Object.entries(byType)
    .map(([type, amount]) => ({ type, amount, pct: Math.round((amount / total) * 100) }))
    .sort((a, b) => b.amount - a.amount);
}
const VAT_RATE = 0.20;
function orderProduct(o) { return state.products.find(p => p.id === o.productId) || null; }
function expensesInRange(bounds) {
  const from = bounds.from.getTime(), to = bounds.to.getTime();
  return state.expenses.filter(e => { const t = new Date(e.date).getTime(); return t >= from && t <= to; }).sort((a, b) => new Date(b.date) - new Date(a.date));
}
function computeAccounting(bounds) {
  const cur = ordersInRange(bounds).filter(o => o.status !== 'retour');
  const refunded = ordersInRange(bounds).filter(o => o.status === 'retour');
  const ttc = cur.reduce((s, o) => s + o.amount, 0);
  const ht = ttc / (1 + VAT_RATE);
  const tva = ttc - ht;
  const cost = cur.reduce((s, o) => { const p = orderProduct(o); return s + (p ? p.costPrice || 0 : 0); }, 0);
  const margin = ht - cost;
  const marginPct = ht ? (margin / ht) * 100 : 0;
  const refundsTotal = refunded.reduce((s, o) => s + o.amount, 0);
  const expenses = expensesInRange(bounds);
  const expensesTotal = expenses.reduce((s, e) => s + e.amount, 0);
  const netProfit = margin - expensesTotal;
  return {
    ttc, ht, tva, cost, margin, marginPct, refundsTotal, refundedCount: refunded.length,
    orders: [...cur, ...refunded].sort((a, b) => new Date(b.date) - new Date(a.date)),
    expenses, expensesTotal, netProfit
  };
}
const DOW_LABELS = ['Dimanche', 'Lundi', 'Mardi', 'Mercredi', 'Jeudi', 'Vendredi', 'Samedi'];
const WEEK_POS_LABELS = ['Semaine 1 (1–7)', 'Semaine 2 (8–14)', 'Semaine 3 (15–21)', 'Semaine 4 (22–31)'];
// Sales-habits indicator: uses the FULL order history (not the Vue d'ensemble range) on
// purpose — a recurring pattern (best weekday, best week-of-month, best month) only gets
// more reliable with more history, so narrowing it to a KPI range would work against it.
function computeSalesHabits() {
  const sold = state.orders.filter(o => o.status !== 'retour');
  if (sold.length < 5) return null;

  const dow = Array.from({ length: 7 }, () => ({ count: 0, revenue: 0 }));
  const weekPos = Array.from({ length: 4 }, () => ({ count: 0, revenue: 0 }));
  const months = {};
  let minT = Infinity, maxT = -Infinity;

  sold.forEach(o => {
    const d = new Date(o.date);
    const t = d.getTime();
    if (t < minT) minT = t;
    if (t > maxT) maxT = t;
    dow[d.getDay()].count++; dow[d.getDay()].revenue += o.amount;
    const wp = Math.min(3, Math.floor((d.getDate() - 1) / 7));
    weekPos[wp].count++; weekPos[wp].revenue += o.amount;
    const mkey = `${d.getFullYear()}-${d.getMonth()}`;
    months[mkey] = months[mkey] || { count: 0, revenue: 0, year: d.getFullYear(), month: d.getMonth() };
    months[mkey].count++; months[mkey].revenue += o.amount;
  });

  const rank = arr => arr.map((s, i) => ({ i, ...s })).sort((a, b) => b.revenue - a.revenue);
  const dowRanked = rank(dow);
  const weekPosRanked = rank(weekPos);
  const monthRanked = Object.values(months).sort((a, b) => b.revenue - a.revenue);
  const spanDays = Math.round((maxT - minT) / 86400000);
  const distinctMonths = Object.keys(months).length;

  const nextOccurrence = targetDow => {
    const d = new Date(); d.setHours(0, 0, 0, 0); d.setDate(d.getDate() + 1);
    for (let i = 0; i < 8; i++) { if (d.getDay() === targetDow) return d; d.setDate(d.getDate() + 1); }
    return null;
  };

  return {
    dowRanked, weekPosRanked, monthRanked, spanDays, distinctMonths,
    totalOrders: sold.length,
    bestDow: dowRanked[0],
    bestWeekPos: weekPosRanked[0],
    nextBestDowDate: nextOccurrence(dowRanked[0].i),
    sparse: spanDays < 30 || sold.length < 20
  };
}
function stockAlerts() {
  return state.products.filter(p => p.stock <= p.threshold).sort((a, b) => a.stock - b.stock);
}
function alertLevel(p) {
  if (p.stock <= p.threshold * 0.3) return 'critical';
  if (p.stock <= p.threshold) return 'warning';
  return 'good';
}

/* ---------- svg chart pieces ---------- */
function sparkline(points, color) {
  const max = Math.max(...points, 1), min = Math.min(...points, 0);
  const w = 160, h = 28;
  const coords = points.map((v, i) => {
    const x = (i / (points.length - 1 || 1)) * w;
    const y = h - 4 - ((v - min) / (max - min || 1)) * (h - 8);
    return `${x},${y}`;
  });
  const last = coords[coords.length - 1].split(',');
  return `<svg class="spark" viewBox="0 0 ${w} ${h}" preserveAspectRatio="none">
    <polyline points="${coords.join(' ')}" fill="none" stroke="${color}" stroke-width="2"/>
    <circle cx="${last[0]}" cy="${last[1]}" r="2.4" fill="${color}"/>
  </svg>`;
}
// "Nice" round ceiling above v (1/2/5 × 10^n) — so the y-axis reads 0/50/100/150 instead
// of the raw data max, matching how the gridlines are labeled.
// Classic "nice numbers" axis algorithm (Heckbert): picks a round step (1/2/5 × 10^n) so
// every tick is a clean number — 0/500/1000/1500 — instead of dividing the max into thirds,
// which produces ugly fractions like 333/667 for any max that isn't itself a multiple of 3.
// Nearest-fit round step (1/2/2.5/5/10 × 10^n). The wider 1/2/5/10 set used earlier could
// jump straight from a step of 2 to a step of 5 for a max just past the cutoff, ceiling the
// axis up to 40-50% above the real peak — the 2.5 in between keeps that padding closer to
// 10-20%, so the plotted line still fills most of the chart height instead of hugging the
// bottom third of it.
function niceNum(x) {
  if (!isFinite(x) || x <= 0) return 1;
  const exp = Math.floor(Math.log10(x));
  const f = x / Math.pow(10, exp);
  const nf = f < 1.5 ? 1 : f < 2.25 ? 2 : f < 3.54 ? 2.5 : f < 7.07 ? 5 : 10;
  return nf * Math.pow(10, exp);
}
function niceAxis(dataMax, targetTicks, minStep) {
  const safeMax = (!isFinite(dataMax) || dataMax <= 0) ? 1 : dataMax;
  let step = niceNum(safeMax / Math.max(1, targetTicks - 1));
  if (minStep) step = Math.max(step, minStep);
  const max = Math.ceil(safeMax / step) * step;
  const ticks = [];
  for (let v = 0; v <= max + step * 1e-6 && ticks.length < 10; v += step) ticks.push(Math.round(v * 1000) / 1000);
  return { max, ticks };
}
function pickTickIndices(n, maxTicks) {
  if (n <= 1) return [0];
  if (n <= maxTicks) return Array.from({ length: n }, (_, i) => i);
  const idx = [];
  for (let i = 0; i < maxTicks; i++) idx.push(Math.round(i * (n - 1) / (maxTicks - 1)));
  return [...new Set(idx)];
}
// Compact axis label (125k € instead of 125 000,00 €) — the full precision belongs in the
// hover tooltip, which has room for it; the gridline label just needs to fit in ~50 SVG
// units without spilling past the card's own padding.
function fmtCompact(v, isCurrency) {
  const abs = Math.abs(v);
  let s;
  if (abs >= 1000000) s = (v / 1000000).toLocaleString('fr-FR', { maximumFractionDigits: 1 }) + 'M';
  else if (abs >= 1000) s = (v / 1000).toLocaleString('fr-FR', { maximumFractionDigits: 1 }) + 'k';
  else s = v.toLocaleString('fr-FR', { maximumFractionDigits: 0 });
  return isCurrency ? s + ' €' : s;
}
function trendChartSVG(series, granularity, idPrefix, valueKey) {
  const values = series.map(p => p[valueKey]);
  const minStep = valueKey === 'count' ? 1 : undefined;
  const { max: niceMaxV, ticks: tickValues } = niceAxis(Math.max(...values, 0), 4, minStep);
  // Axis labels live INSIDE the 0..w viewBox (plotLeft reserves their space) rather than in
  // negative coordinates outside it — a card only has ~20px of padding, far less than labels
  // need, so anything drawn outside the box (even with overflow:visible) spills past the
  // card's edge instead of sitting inside it.
  const w = 640, h = 220, plotLeft = 46, plotTop = 14, plotBottom = 190;
  const plotW = w - plotLeft;
  const coords = series.map((p, i) => {
    const x = plotLeft + (i / (series.length - 1 || 1)) * plotW;
    const y = plotBottom - (p[valueKey] / niceMaxV) * (plotBottom - plotTop);
    return { x, y, v: p[valueKey], t: p.t };
  });
  const line = coords.map(c => `${c.x},${c.y}`).join(' ');
  const area = `${plotLeft},${plotBottom} ${line} ${w},${plotBottom}`;
  const yTicks = tickValues.map(v => ({ y: plotBottom - (v / niceMaxV) * (plotBottom - plotTop), v }));
  const xTickIdx = pickTickIndices(coords.length, 6);
  const formatY = v => fmtCompact(v, valueKey === 'ca');
  return { coords, svg: `
    <svg id="${idPrefix}Svg" viewBox="0 0 ${w} ${h}" preserveAspectRatio="none">
      <defs><linearGradient id="${idPrefix}FillGrad" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0%" stop-color="var(--brand)" stop-opacity="0.22"/>
        <stop offset="100%" stop-color="var(--brand)" stop-opacity="0"/>
      </linearGradient></defs>
      ${yTicks.map(t => `<line x1="${plotLeft}" y1="${t.y}" x2="${w}" y2="${t.y}" stroke="var(--rule-soft)" stroke-width="1"/>`).join('')}
      ${yTicks.map(t => `<text x="${plotLeft - 8}" y="${t.y + 3.5}" text-anchor="end" font-size="10" fill="var(--ink-faint)" font-family="var(--font-mono)">${formatY(t.v)}</text>`).join('')}
      ${xTickIdx.map(i => `<text x="${coords[i].x}" y="${plotBottom + 15}" text-anchor="${i === 0 ? 'start' : i === coords.length - 1 ? 'end' : 'middle'}" font-size="10" fill="var(--ink-faint)" font-family="var(--font-mono)">${escapeHTML(bucketLabel(coords[i].t, granularity))}</text>`).join('')}
      <polygon fill="url(#${idPrefix}FillGrad)" points="${area}"/>
      <polyline fill="none" stroke="var(--brand)" stroke-width="2.5" stroke-linejoin="round" stroke-linecap="round" points="${line}"/>
      <circle id="${idPrefix}HoverDot" r="4" fill="var(--brand)" stroke="var(--surface)" stroke-width="2" style="opacity:0"/>
      <line id="${idPrefix}HoverLine" x1="0" y1="${plotTop}" x2="0" y2="${plotBottom}" stroke="var(--ink-faint)" stroke-width="1" stroke-dasharray="3,3" style="opacity:0"/>
      <rect id="${idPrefix}HoverCatcher" x="${plotLeft}" y="0" width="${plotW}" height="${h}" fill="transparent"/>
    </svg>` };
}
function wireTrendChart(coords, granularity, idPrefix, formatValue) {
  const svg = document.getElementById(`${idPrefix}Svg`);
  if (!svg) return;
  const catcher = document.getElementById(`${idPrefix}HoverCatcher`);
  const dot = document.getElementById(`${idPrefix}HoverDot`);
  const hoverLine = document.getElementById(`${idPrefix}HoverLine`);
  const tooltip = document.getElementById(`${idPrefix}Tooltip`);
  const wrap = document.getElementById(`${idPrefix}Wrap`);
  const w = 640;
  function nearest(xVal) { let best = coords[0]; for (const c of coords) if (Math.abs(c.x - xVal) < Math.abs(best.x - xVal)) best = c; return best; }
  catcher.addEventListener('mousemove', e => {
    const rect = svg.getBoundingClientRect();
    const xVal = ((e.clientX - rect.left) / rect.width) * w;
    const c = nearest(xVal);
    dot.setAttribute('cx', c.x); dot.setAttribute('cy', c.y); dot.style.opacity = 1;
    hoverLine.setAttribute('x1', c.x); hoverLine.setAttribute('x2', c.x); hoverLine.style.opacity = 1;
    const wrapRect = wrap.getBoundingClientRect();
    tooltip.style.left = ((c.x / w) * wrapRect.width) + 'px';
    tooltip.style.top = ((c.y / 220) * wrapRect.height) + 'px';
    tooltip.textContent = bucketLabel(c.t, granularity) + ' — ' + formatValue(c.v);
    tooltip.style.opacity = 1;
  });
  catcher.addEventListener('mouseleave', () => { dot.style.opacity = 0; hoverLine.style.opacity = 0; tooltip.style.opacity = 0; });
}

/* ---------- page: overview ---------- */
function habitBarsHTML(ranked, labelFn) {
  const byIndex = ranked.slice().sort((a, b) => a.i - b.i);
  const max = Math.max(...ranked.map(r => r.revenue), 1);
  const bestRevenue = ranked[0].revenue;
  return byIndex.map(r => {
    const pct = Math.round((r.revenue / max) * 100);
    const isBest = r.revenue === bestRevenue && r.revenue > 0;
    return `<div class="chan-row">
      <div class="top"><span>${labelFn(r.i)}</span><span class="pct">${fmtEUR(r.revenue)}</span></div>
      <div class="chan-bar"><div style="width:${pct}%; background:${isBest ? 'var(--brand)' : 'var(--rule-soft)'}"></div></div>
    </div>`;
  }).join('');
}
function habitMonthsHTML(monthRanked) {
  const top = monthRanked.slice(0, 3);
  const max = Math.max(...top.map(m => m.revenue), 1);
  return top.map((m, idx) => {
    const label = new Date(m.year, m.month, 1).toLocaleDateString('fr-FR', { month: 'long', year: 'numeric' });
    const pct = Math.round((m.revenue / max) * 100);
    return `<div class="chan-row">
      <div class="top"><span>${label}${idx === 0 ? ' — meilleur mois' : ''}</span><span class="pct">${fmtEUR(m.revenue)}</span></div>
      <div class="chan-bar"><div style="width:${pct}%; background:${idx === 0 ? 'var(--brand)' : 'var(--rule-soft)'}"></div></div>
    </div>`;
  }).join('');
}
function habitsInsightText(h) {
  const dowName = DOW_LABELS[h.bestDow.i].toLowerCase();
  const wpName = WEEK_POS_LABELS[h.bestWeekPos.i].toLowerCase();
  let s = `Vos ventes sont historiquement les plus fortes le ${dowName}, en ${wpName} du mois.`;
  if (h.nextBestDowDate) s += ` Le prochain ${dowName} est le ${fmtDate(h.nextBestDowDate.toISOString())} — pensez à renforcer votre communication (pub, posts, relances) dans les jours qui précèdent.`;
  return s;
}
function pageOverview() {
  const bounds = getRangeBounds();
  const granularity = state.overviewGranularity;
  const k = computeKPIs(bounds);
  const series = trendSeries(bounds, granularity);
  const caChart = trendChartSVG(series, granularity, 'ca', 'ca');
  const cntChart = trendChartSVG(series, granularity, 'cnt', 'count');
  const breakdown = channelBreakdown(bounds);
  const habits = computeSalesHabits();
  const alerts = stockAlerts();
  const recent = state.orders.slice(0, 6);
  const todayISO = new Date().toISOString().slice(0, 10);
  const fallbackFrom = daysAgo(29).toISOString().slice(0, 10);
  const custom = state.rangeCustom || {};

  return `
    <div class="topbar">
      <div><h1>Vue d'ensemble</h1><div class="sub">Aperçu de votre activité multicanale</div></div>
      <div class="topbar-actions">
        <div class="range">
          ${['7', '30', '90'].map(d => `<button data-action="setRange" data-range="${d}" class="${state.range === d ? 'active' : ''}">${d} j</button>`).join('')}
          <button data-action="setRange" data-range="custom" class="${state.range === 'custom' ? 'active' : ''}">Personnalisé</button>
        </div>
        ${state.range === 'custom' ? `
        <div style="display:flex; align-items:center; gap:6px;">
          <input type="date" id="rangeFromInput" class="stock-input" style="width:auto;" value="${custom.from || fallbackFrom}" max="${todayISO}">
          <span style="color:var(--ink-faint); font-size:12.5px;">→</span>
          <input type="date" id="rangeToInput" class="stock-input" style="width:auto;" value="${custom.to || todayISO}" max="${todayISO}">
        </div>` : ''}
        <div class="range">
          ${[['day', 'Jour'], ['week', 'Semaine'], ['month', 'Mois']].map(([g, label]) => `<button data-action="setGranularity" data-granularity="${g}" class="${granularity === g ? 'active' : ''}">${label}</button>`).join('')}
        </div>
        ${themeToggleHTML()}
      </div>
    </div>

    <div class="kpis">
      <div class="kpi"><div class="label">Chiffre d'affaires</div><div class="row"><span class="value">${fmtEUR(k.ca)}</span>${deltaHTML(k.caDelta)}</div>${sparkline(series.map(s => s.ca), 'var(--brand)')}</div>
      <div class="kpi"><div class="label">Commandes</div><div class="row"><span class="value">${fmtNum(k.count)}</span>${deltaHTML(k.countDelta)}</div>${sparkline(series.map(s => s.ca), 'var(--brand)')}</div>
      <div class="kpi"><div class="label">Panier moyen</div><div class="row"><span class="value">${fmtEUR(k.panier)}</span>${deltaHTML(k.panierDelta)}</div>${sparkline(series.map(s => s.ca), 'var(--brand)')}</div>
      <div class="kpi"><div class="label">Taux de retour</div><div class="row"><span class="value">${k.tauxRetour.toFixed(1)}%</span>${deltaHTML(-k.tauxRetourDelta, true)}</div>${sparkline(series.map(s => s.ca), k.tauxRetourDelta > 0 ? 'var(--critical)' : 'var(--brand)')}</div>
    </div>

    <div class="grid">
      <div class="card">
        <h2>Chiffre d'affaires — ${rangeLabel(bounds)}</h2>
        <div class="card-sub">Tous canaux confondus</div>
        <div class="chart-wrap" id="caWrap">${caChart.svg}<div class="tooltip" id="caTooltip"></div></div>
      </div>
      <div class="card">
        <h2>Répartition par canal</h2>
        <div class="card-sub">Part du chiffre d'affaires</div>
        ${breakdown.length ? breakdown.map(b => `
          <div class="chan-row">
            <div class="top"><span>${connectorLabel(b.type)}</span><span class="pct">${b.pct}%</span></div>
            <div class="chan-bar"><div style="width:${b.pct}%; background:${channelColor(b.type)}"></div></div>
          </div>`).join('') : `<div class="empty">Aucune vente sur cette période.</div>`}
      </div>
    </div>

    <div class="card" style="margin-bottom:14px;">
      <h2>Nombre de ventes — ${rangeLabel(bounds)}</h2>
      <div class="card-sub">Commandes reçues, tous canaux confondus</div>
      <div class="chart-wrap" id="cntWrap">${cntChart.svg}<div class="tooltip" id="cntTooltip"></div></div>
    </div>

    <div class="card" style="margin-bottom:14px;">
      <h2>Habitudes de vente</h2>
      ${habits ? `
        <div class="card-sub">Basé sur tout votre historique — ${fmtNum(habits.totalOrders)} commande${habits.totalOrders !== 1 ? 's' : ''} sur ${fmtNum(habits.spanDays)} jour${habits.spanDays !== 1 ? 's' : ''}</div>
        ${habits.sparse ? `<div class="callout" style="margin-top:10px;">Encore peu d'historique — ces tendances se préciseront à mesure que vos ventes s'accumulent.</div>` : ''}
        <div style="margin-top:10px; background:var(--brand-soft); color:var(--brand); font-size:13px; padding:10px 13px; border-radius:8px; line-height:1.5;">${habitsInsightText(habits)}</div>
        <div style="display:flex; gap:20px; flex-wrap:wrap; margin-top:14px;">
          <div style="flex:1; min-width:220px;">
            <div class="card-sub" style="margin-bottom:8px;">Par jour de la semaine</div>
            ${habitBarsHTML(habits.dowRanked, i => DOW_LABELS[i])}
          </div>
          <div style="flex:1; min-width:220px;">
            <div class="card-sub" style="margin-bottom:8px;">Par semaine du mois</div>
            ${habitBarsHTML(habits.weekPosRanked, i => WEEK_POS_LABELS[i])}
          </div>
        </div>
        ${habits.distinctMonths >= 2 ? `
        <div style="margin-top:14px;">
          <div class="card-sub" style="margin-bottom:8px;">Meilleurs mois observés</div>
          ${habitMonthsHTML(habits.monthRanked)}
        </div>` : ''}
      ` : `<div class="empty">Pas encore assez de ventes pour dégager des tendances (au moins 5 commandes nécessaires).</div>`}
    </div>

    <div class="grid">
      <div class="card">
        <h2>Commandes récentes</h2>
        <div class="card-sub">Tous canaux</div>
        <table class="data">
          <thead><tr><th>Commande</th><th>Canal</th><th>Cliente</th><th style="text-align:right">Montant</th><th>Statut</th></tr></thead>
          <tbody>${recent.map(o => orderRow(o)).join('')}</tbody>
        </table>
      </div>
      <div class="card">
        <h2>Alertes stock</h2>
        <div class="card-sub">${alerts.length ? `${fmtNum(alerts.length)} produit${alerts.length !== 1 ? 's' : ''} sous le seuil — les plus critiques d'abord` : 'Produits sous le seuil'}</div>
        ${alerts.length ? alerts.slice(0, 6).map(p => `
          <div class="alert-row">
            <div class="product">${escapeHTML(p.name)}<span class="chan">${p.channels.map(connectorLabel).join(' + ')}</span></div>
            <span class="status-chip ${alertLevel(p)}"><span class="dot"></span>${p.stock} restants</span>
          </div>`).join('') : `<div class="empty">Tous les stocks sont au-dessus du seuil.</div>`}
        ${alerts.length > 6 ? `<div class="card-sub" style="margin-top:10px;">${fmtNum(alerts.length - 6)} autre${alerts.length - 6 !== 1 ? 's' : ''} produit${alerts.length - 6 !== 1 ? 's' : ''} concerné${alerts.length - 6 !== 1 ? 's' : ''} — <a href="#stock" style="color:var(--brand)">voir tout le stock →</a></div>` : ''}
      </div>
    </div>
  `;
}
function deltaHTML(delta, isPoint) {
  const pos = delta >= 0;
  const txt = isPoint ? `${pos ? '+' : ''}${(-delta).toFixed(1)}pt` : `${pos ? '+' : ''}${delta}%`;
  return `<span class="delta ${pos ? 'pos' : 'neg'}">${txt}</span>`;
}
function statusMeta(status) {
  const map = { livree: ['good', 'Livrée'], preparation: ['warning', 'En préparation'], retour: ['critical', 'Retour'] };
  return map[status];
}
function orderRow(o, withDate) {
  const [cls, label] = statusMeta(o.status);
  return `<tr>
    <td>#${o.orderNumber}</td>
    <td><span class="chan-dot"><span class="sw" style="background:${channelColor(o.channelType)}"></span>${connectorLabel(o.channelType)}</span></td>
    <td>${o.customer}</td>
    ${withDate ? `<td>${fmtDate(o.date)}</td>` : ''}
    <td class="amount">${fmtEUR(o.amount)}</td>
    <td><span class="status-chip ${cls}"><span class="dot"></span>${label}</span></td>
  </tr>`;
}
function themeToggleHTML() {
  const dark = resolvedTheme() === 'dark';
  return `<button class="theme-toggle" data-action="toggleTheme">
    ${dark
      ? `<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.4"><circle cx="8" cy="8" r="3"/><path d="M8 1v1.6M8 13.4V15M2.6 8H1M15 8h-1.6M3.5 3.5l1.1 1.1M11.4 11.4l1.1 1.1M12.5 3.5l-1.1 1.1M4.6 11.4l-1.1 1.1"/></svg>`
      : `<svg viewBox="0 0 16 16" fill="currentColor"><path d="M13.5 9.8A5.8 5.8 0 0 1 6.2 2.5a5.8 5.8 0 1 0 7.3 7.3z"/></svg>`}
    ${dark ? 'Sombre' : 'Clair'}
  </button>`;
}

/* ---------- page: ventes ---------- */
let salesFilter = { channel: 'all', status: 'all', q: '' };
function pageVentes() {
  let list = [...state.orders];
  if (salesFilter.channel !== 'all') list = list.filter(o => o.channelType === salesFilter.channel);
  if (salesFilter.status !== 'all') list = list.filter(o => o.status === salesFilter.status);
  if (salesFilter.q) {
    const q = salesFilter.q.toLowerCase();
    list = list.filter(o => o.customer.toLowerCase().includes(q) || String(o.orderNumber).includes(q));
  }
  const matchCount = list.length;
  const truncated = matchCount > 120;
  list = list.slice(0, 120);

  return `
    <div class="topbar">
      <div><h1>Ventes</h1><div class="sub">${fmtNum(state.orders.length)} commandes au total</div></div>
      <div class="topbar-actions">${themeToggleHTML()}</div>
    </div>
    <div class="card">
      <div class="filters">
        <input type="text" placeholder="Rechercher une cliente ou un numéro" id="salesSearch" value="${salesFilter.q}">
        <select id="salesChannel">
          <option value="all">Tous les canaux</option>
          ${connectedTypes().map(c => `<option value="${c.type}" ${salesFilter.channel === c.type ? 'selected' : ''}>${c.label}</option>`).join('')}
        </select>
        <select id="salesStatus">
          <option value="all" ${salesFilter.status === 'all' ? 'selected' : ''}>Tous les statuts</option>
          <option value="livree" ${salesFilter.status === 'livree' ? 'selected' : ''}>Livrée</option>
          <option value="preparation" ${salesFilter.status === 'preparation' ? 'selected' : ''}>En préparation</option>
          <option value="retour" ${salesFilter.status === 'retour' ? 'selected' : ''}>Retour</option>
        </select>
        <span class="count">${fmtNum(matchCount)} résultat${matchCount > 1 ? 's' : ''}${truncated ? ' · 120 affichés' : ''}</span>
      </div>
      ${list.length ? `<div class="table-scroll"><table class="data">
        <thead><tr>
          <th>Commande</th><th>Canal</th><th>Cliente</th><th>Date</th><th style="text-align:right">Montant</th><th>Statut</th>
          ${state.customFields.map(f => `<th>${f.label}<span class="field-remove" data-action="removeField" data-id="${f.id}" title="Retirer ce champ">×</span><span class="field-source">${fieldSourceLabel(f)}</span></th>`).join('')}
          <th><button class="btn sm" data-action="openAddField">+ Champ</button></th>
        </tr></thead>
        <tbody>${list.map(o => ventesOrderRow(o)).join('')}</tbody>
      </table></div>` : `<div class="empty">Aucune commande ne correspond à ces filtres.</div>`}
      <div class="card-sub" style="margin-top:10px;">Cliquez sur une commande pour voir le détail et renseigner ses champs de suivi.</div>
    </div>
  `;
}
function ventesOrderRow(o) {
  const [cls, label] = statusMeta(o.status);
  return `<tr data-action="openOrderDetail" data-id="${o.id}" class="row-click" role="button" tabindex="0">
    <td>#${o.orderNumber}</td>
    <td><span class="chan-dot"><span class="sw" style="background:${channelColor(o.channelType)}"></span>${connectorLabel(o.channelType)}</span></td>
    <td>${o.customer}</td>
    <td>${fmtDate(o.date)}</td>
    <td class="amount">${fmtEUR(o.amount)}</td>
    <td><span class="status-chip ${cls}"><span class="dot"></span>${label}</span></td>
    ${state.customFields.map(f => `<td>${o.custom[f.id] ? escapeHTML(o.custom[f.id]) : '<span style="color:var(--ink-faint)">—</span>'}</td>`).join('')}
    <td></td>
  </tr>`;
}
function escapeHTML(s) { return String(s).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c])); }

/* ---------- page: stock ---------- */
function pageStock() {
  const alerts = stockAlerts().length;
  return `
    <div class="topbar">
      <div><h1>Stock</h1><div class="sub">${state.products.length} produits · ${alerts} sous le seuil</div></div>
      <div class="topbar-actions">
        ${themeToggleHTML()}
      </div>
    </div>
    <div class="card">
      <table class="data">
        <thead><tr><th>Produit</th><th>Canaux</th><th>Seuil</th><th>Stock</th><th>Statut</th></tr></thead>
        <tbody>
          ${state.products.map(p => `
            <tr>
              <td>${escapeHTML(p.name)}</td>
              <td>${p.channels.length ? p.channels.map(connectorLabel).join(' + ') : '<span style="color:var(--ink-faint)">—</span>'}</td>
              <td class="amount">${p.threshold}</td>
              <td class="amount"><input class="stock-input" type="number" min="0" value="${p.stock}" data-stock-id="${p.id}"></td>
              <td><span class="status-chip ${alertLevel(p)}"><span class="dot"></span>${alertLevel(p) === 'good' ? 'OK' : alertLevel(p) === 'warning' ? 'Vigilance' : 'Critique'}</span></td>
            </tr>`).join('')}
        </tbody>
      </table>
      <div class="card-sub" style="margin-top:10px;">Le stock se déduit automatiquement à chaque vente reçue (et se recrédite en cas de retour) — modifiez-le ici uniquement pour un réassort ou une correction. Prix d'achat et fournisseur se gèrent dans <a href="#catalogue" style="color:var(--brand)">Mon catalogue</a>.</div>
    </div>
  `;
}

/* ---------- page: mon catalogue ---------- */
const CATALOG_TARGET_FIELDS = [
  { key: 'name', label: 'Nom du produit', required: true },
  { key: 'costPrice', label: "Prix d'achat (HT)" },
  { key: 'salePrice', label: 'Prix de revente (HT)' },
  { key: 'supplier', label: 'Fournisseur' },
  { key: 'stock', label: 'Stock' },
  { key: 'threshold', label: "Seuil d'alerte" },
];
let catalogFilterIncomplete = false;
function exportCatalogCSV() {
  const header = ['Nom du produit', "Prix d'achat (HT)", 'Prix de revente (HT)', 'Fournisseur', 'Stock', "Seuil d'alerte", ...state.catalogFields.map(f => f.label)];
  const rows = state.products.map(p => [
    p.name,
    p.costPrice != null ? String(p.costPrice) : '',
    p.salePrice != null ? String(p.salePrice) : '',
    p.supplier || '',
    String(p.stock ?? 0),
    String(p.threshold ?? 0),
    ...state.catalogFields.map(f => p.custom[f.id] || '')
  ]);
  const csvEscape = v => /[";\n]/.test(v) ? `"${String(v).replace(/"/g, '""')}"` : v;
  const csv = [header, ...rows].map(r => r.map(csvEscape).join(';')).join('\r\n');
  const blob = new Blob(['﻿' + csv], { type: 'text/csv;charset=utf-8;' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `comptoir-catalogue-${new Date().toISOString().slice(0, 10)}.csv`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}
function productSalesStats(productId) {
  const orders = state.orders.filter(o => o.productId === productId);
  const sold = orders.filter(o => o.status !== 'retour');
  const revenue = sold.reduce((sum, o) => sum + o.amount, 0);
  // Most recent real sale amount for this product — used to suggest a resale price
  // instead of asking for one Comptoir already knows from the order history. Orders
  // store the amount actually charged (TTC); Prix de revente is HT (see CATALOG_TARGET_FIELDS),
  // so the suggestion is converted HT here rather than handed over as-is.
  const lastSale = sold.length ? sold.reduce((latest, o) => new Date(o.date) > new Date(latest.date) ? o : latest) : null;
  return {
    count: sold.length, revenue, returns: orders.length - sold.length,
    lastSaleTTC: lastSale ? lastSale.amount : null,
    lastSaleHT: lastSale ? Math.round((lastSale.amount / (1 + VAT_RATE)) * 100) / 100 : null
  };
}
function pageCatalogue() {
  const missingCost = state.products.filter(p => !p.costPrice).length;
  const incomplete = state.products.filter(p => !p.costPrice || !p.supplier);
  const shown = catalogFilterIncomplete ? incomplete : state.products;
  const orphanOrders = state.orders.filter(o => !o.productId);
  return `
    <div class="topbar">
      <div><h1>Mon catalogue</h1><div class="sub">${fmtNum(state.products.length)} produit${state.products.length !== 1 ? 's' : ''}${missingCost ? ` · ${missingCost} sans prix d'achat` : ''}</div></div>
      <div class="topbar-actions">
        <button class="btn" data-action="importFromSite">Importer du site</button>
        <button class="btn" data-action="exportCatalog">Exporter en CSV</button>
        <button class="btn" data-action="openImportCatalog">Importer un CSV</button>
        <button class="btn" data-action="openAddCatalogField">+ Colonne</button>
        <button class="btn primary" data-action="openAddProduct">+ Ajouter un produit</button>
        ${themeToggleHTML()}
      </div>
    </div>
    ${catalogFilterIncomplete ? `<div class="callout" style="margin-bottom:14px;">Affichage filtré : ${fmtNum(incomplete.length)} produit${incomplete.length !== 1 ? 's' : ''} sans prix d'achat ou sans fournisseur. <span class="copy" data-action="clearCatalogFilter">Voir tout le catalogue</span></div>` : ''}
    ${orphanOrders.length ? `<div class="callout" style="margin-bottom:14px;">${fmtNum(orphanOrders.length)} commande${orphanOrders.length !== 1 ? 's' : ''} sans produit rattaché — envoyée${orphanOrders.length !== 1 ? 's' : ''} avant la mise à jour du connecteur. Redemandez à votre développeur de les renvoyer (même <code>externalId</code>) : elles se rattacheront automatiquement au produit dès qu'il enverra le nom du produit avec.</div>` : ''}
    <div class="card">
      ${shown.length ? `<div class="table-scroll"><table class="data">
        <thead><tr>
          <th>Produit</th><th>Fournisseur</th><th>Prix d'achat (HT)</th><th>Prix de revente (HT)</th><th>Marge</th><th>Vendu</th><th>CA généré</th>
          ${state.catalogFields.map(f => `<th>${escapeHTML(f.label)}<span class="field-remove" data-action="removeCatalogField" data-id="${f.id}" title="Retirer cette colonne">×</span></th>`).join('')}
        </tr></thead>
        <tbody>
          ${shown.map(p => {
            const hasMargin = p.salePrice != null && p.salePrice > 0 && p.costPrice != null;
            const margin = hasMargin ? p.salePrice - p.costPrice : null;
            const marginPct = hasMargin ? (margin / p.salePrice * 100) : null;
            const stats = productSalesStats(p.id);
            // Highlight whenever cost price is unfilled — it defaults to 0 rather than null
            // for new products, so a bare `!= null` check would miss it; treat 0 as unset.
            // Cost price alone drives this: it's what feeds the margin calc in Comptabilité,
            // so a row missing it is worth flagging even if a resale price is already set.
            const missingCostPrice = !p.costPrice;
            return `
            <tr class="${missingCostPrice ? 'row-incomplete' : ''}">
              <td>${escapeHTML(p.name)}</td>
              <td><input class="stock-input" type="text" value="${escapeHTML(p.supplier || '')}" data-supplier-id="${p.id}" placeholder="—"></td>
              <td class="amount"><input class="stock-input" type="number" min="0" step="0.01" value="${p.costPrice ?? 0}" data-cost-id="${p.id}"></td>
              <td class="amount">
                <input class="stock-input" type="number" min="0" step="0.01" value="${p.salePrice ?? ''}" data-sale-price-id="${p.id}" placeholder="—">
                ${p.salePrice == null && stats.lastSaleHT != null ? `<div class="suggest-chip" data-action="useSuggestedSalePrice" data-id="${p.id}" data-price="${stats.lastSaleHT}" title="Dernière vente réelle : ${fmtEUR(stats.lastSaleTTC)} TTC">Sugg. ${fmtEUR(stats.lastSaleHT)}</div>` : ''}
              </td>
              <td class="amount">${hasMargin ? `${fmtEUR(margin)}<span style="color:var(--ink-faint); font-size:11.5px;"> (${marginPct.toFixed(0)}%)</span>` : '<span style="color:var(--ink-faint)">—</span>'}</td>
              <td class="amount">${fmtNum(stats.count)}${stats.returns ? `<span style="color:var(--critical); font-size:11.5px;"> (${stats.returns} retour${stats.returns !== 1 ? 's' : ''})</span>` : ''}</td>
              <td class="amount">${fmtEUR(stats.revenue)}</td>
              ${state.catalogFields.map(f => `<td><input class="stock-input" type="text" value="${escapeHTML(p.custom[f.id] || '')}" data-catalog-custom-id="${p.id}" data-field-id="${f.id}"></td>`).join('')}
            </tr>`;
          }).join('')}
        </tbody>
      </table></div>` : `<div class="empty">${catalogFilterIncomplete ? 'Tout est déjà complet — aucun produit ne manque de prix d\'achat ou de fournisseur.' : 'Aucun produit — ajoutez-le manuellement, importez un fichier CSV, ou cliquez « Importer du site » si des ventes sont déjà arrivées.'}</div>`}
      <div class="card-sub" style="margin-top:10px;">Prix d'achat et prix de revente s'entendent hors taxes (HT) — c'est aussi la base utilisée pour le calcul de marge dans Comptabilité. Quand un produit n'a pas encore de prix de revente, Comptoir suggère le montant de sa dernière vente réelle. « Vendu » et « CA généré » comptent vos commandes déjà reçues (hors retours) pour ce produit. « Importer du site » synchronise depuis les ventes déjà reçues par Comptoir — ce n'est pas une lecture en direct de votre site, seules les commandes déjà transmises via le connecteur y figurent. Ajoutez vos propres colonnes (référence, poids, couleur…) ou importez un fichier CSV pour remplir tout le catalogue d'un coup. Vous pouvez aussi cliquer « Exporter en CSV », compléter les prix dans Excel, puis « Importer un CSV » pour renvoyer le fichier — les produits déjà présents (même nom) seront mis à jour, pas dupliqués.</div>
    </div>
  `;
}

function csvParse(text) {
  if (text.charCodeAt(0) === 0xFEFF) text = text.slice(1);
  const sample = text.slice(0, 2000);
  const delim = (sample.match(/;/g) || []).length > (sample.match(/,/g) || []).length ? ';' : ',';
  const rows = [];
  let row = [], field = '', inQuotes = false;
  for (let i = 0; i < text.length; i++) {
    const c = text[i];
    if (inQuotes) {
      if (c === '"') { if (text[i + 1] === '"') { field += '"'; i++; } else inQuotes = false; }
      else field += c;
    } else if (c === '"') inQuotes = true;
    else if (c === delim) { row.push(field); field = ''; }
    else if (c === '\n' || c === '\r') {
      if (c === '\r' && text[i + 1] === '\n') i++;
      row.push(field); field = '';
      if (row.length > 1 || row[0] !== '') rows.push(row);
      row = [];
    } else field += c;
  }
  if (field !== '' || row.length) { row.push(field); rows.push(row); }
  if (!rows.length) return { headers: [], rows: [] };
  return { headers: rows[0].map(h => h.trim()), rows: rows.slice(1).filter(r => r.some(c => c.trim() !== '')) };
}

function guessCatalogMapping(header) {
  const norm = header.trim().toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, '');
  if (/(^|\W)(nom|produit|article|name|title|designation)(\W|$)/.test(norm)) return 'name';
  if (/(prix.*achat|cout.*achat|^cout$|^cost$|\bpa\b)/.test(norm)) return 'costPrice';
  if (/(prix.*vente|prix.*revente|\bpv\b|sale.*price|selling.*price)/.test(norm)) return 'salePrice';
  if (/(fournisseur|supplier|vendor)/.test(norm)) return 'supplier';
  if (/(seuil|threshold|alerte)/.test(norm)) return 'threshold';
  if (/(stock|quantite|qty|quantity)/.test(norm)) return 'stock';
  return null;
}

let pendingCatalogImport = null;

function openImportCatalogModal() {
  openModal(`
    <h3>Importer un catalogue</h3>
    <div class="modal-sub">Fichier CSV — si vous avez un Excel, enregistrez-le d'abord au format .csv (Fichier → Enregistrer sous → CSV).</div>
    <div class="field"><input type="file" id="catalogCsvFile" accept=".csv,text/csv"></div>
    <div class="actions"><button class="btn" data-action="closeModal">Annuler</button></div>
  `);
  document.getElementById('catalogCsvFile').addEventListener('change', async e => {
    const file = e.target.files[0];
    if (!file) return;
    const text = await file.text();
    const parsed = csvParse(text);
    if (!parsed.headers.length || !parsed.rows.length) { toast('Fichier CSV vide ou illisible.', true); return; }
    pendingCatalogImport = parsed;
    openCatalogMappingModal(parsed);
  });
}

function openCatalogMappingModal(parsed) {
  const { headers, rows } = parsed;
  const guesses = headers.map(guessCatalogMapping);
  openModal(`
    <h3>Faire correspondre les colonnes</h3>
    <div class="modal-sub">${fmtNum(rows.length)} ligne${rows.length !== 1 ? 's' : ''} détectée${rows.length !== 1 ? 's' : ''}. Un produit déjà présent (même nom) sera mis à jour ; sinon il sera créé.</div>
    <div style="max-height:360px; overflow-y:auto; margin-bottom:14px;">
      ${headers.map((h, i) => `
        <div class="field" style="display:flex; align-items:flex-end; gap:10px; margin-bottom:12px;">
          <div style="flex:1; min-width:0;">
            <label style="margin-bottom:2px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">${escapeHTML(h)}</label>
            <div style="font-size:11.5px; color:var(--ink-faint); white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">Ex. « ${escapeHTML(rows[0][i] ?? '')} »</div>
          </div>
          <select data-map-col="${i}" style="flex:1;">
            <option value="">Ignorer cette colonne</option>
            ${CATALOG_TARGET_FIELDS.map(f => `<option value="field:${f.key}" ${guesses[i] === f.key ? 'selected' : ''}>${f.label}${f.required ? ' (requis)' : ''}</option>`).join('')}
            ${state.catalogFields.map(f => `<option value="custom:${f.id}">${escapeHTML(f.label)} (colonne existante)</option>`).join('')}
            <option value="new" ${guesses[i] === null ? 'selected' : ''}>+ Nouvelle colonne « ${escapeHTML(h)} »</option>
          </select>
        </div>
      `).join('')}
    </div>
    <div class="actions"><button class="btn" data-action="closeModal">Annuler</button><button class="btn primary" data-action="submitCatalogImport">Importer ${fmtNum(rows.length)} produit${rows.length !== 1 ? 's' : ''}</button></div>
  `);
}

function openAddCatalogFieldModal() {
  openModal(`
    <h3>Ajouter une colonne</h3>
    <div class="modal-sub">Ex. Référence fournisseur, Poids, Couleur…</div>
    <div class="field"><label>Nom de la colonne</label><input type="text" id="catalogFieldLabel" placeholder="Ex. Référence fournisseur"></div>
    <div class="actions"><button class="btn" data-action="closeModal">Annuler</button><button class="btn primary" data-action="submitAddCatalogField">Ajouter</button></div>
  `);
}
function openAddExpenseModal() {
  const todayISO = new Date().toISOString().slice(0, 10);
  openModal(`
    <h3>Ajouter une charge</h3>
    <div class="modal-sub">Ex. Abonnement Shopify, Publicité Instagram, Emballages…</div>
    <div class="field"><label>Intitulé</label><input type="text" id="expenseLabel" placeholder="Ex. Abonnement Shopify"></div>
    <div class="field"><label>Montant (€)</label><input type="number" id="expenseAmount" min="0" step="0.01" value="0"></div>
    <div class="field"><label>Date</label><input type="date" id="expenseDate" value="${todayISO}" max="${todayISO}"></div>
    <div class="actions"><button class="btn" data-action="closeModal">Annuler</button><button class="btn primary" data-action="submitAddExpense">Ajouter</button></div>
  `, () => document.getElementById('expenseLabel')?.focus());
}

/* ---------- page: sav ---------- */
function savTableHead() {
  return `<tr>
    <th>Commande</th><th>Canal</th><th>Produit</th><th>Motif</th><th>Date</th><th>Statut</th>
    ${state.savFields.map(f => `<th>${f.label}<span class="field-remove" data-action="removeSavField" data-id="${f.id}" title="Retirer ce champ">×</span><span class="field-source">${fieldSourceLabel(f)}</span></th>`).join('')}
    <th></th>
  </tr>`;
}
function pageSAV() {
  const open = state.savTickets.filter(t => t.status === 'ouvert');
  const resolved = state.savTickets.filter(t => t.status === 'resolu');
  const renderTicket = t => `
    <tr data-action="openTicketDetail" data-id="${t.id}" class="row-click">
      <td>#${state.orders.find(o => o.id === t.orderId)?.orderNumber ?? t.orderNumber}</td>
      <td><span class="chan-dot"><span class="sw" style="background:${channelColor(t.channelType)}"></span>${connectorLabel(t.channelType)}</span></td>
      <td>${t.product}</td>
      <td>${t.reason}</td>
      <td>${fmtDate(t.date)}</td>
      <td><span class="status-chip ${t.status === 'ouvert' ? 'warning' : 'good'}"><span class="dot"></span>${t.status === 'ouvert' ? 'Ouvert' : 'Résolu'}</span></td>
      ${state.savFields.map(f => `<td>${t.custom[f.id] ? escapeHTML(t.custom[f.id]) : '<span style="color:var(--ink-faint)">—</span>'}</td>`).join('')}
      <td><button class="btn sm" data-action="toggleTicket" data-id="${t.id}">${t.status === 'ouvert' ? 'Marquer résolu' : 'Rouvrir'}</button></td>
    </tr>`;
  return `
    <div class="topbar">
      <div><h1>SAV</h1><div class="sub">${open.length} ticket${open.length !== 1 ? 's' : ''} ouvert${open.length !== 1 ? 's' : ''}</div></div>
      <div class="topbar-actions"><button class="btn primary" data-action="openAddSavField">+ Ajouter un champ</button>${themeToggleHTML()}</div>
    </div>
    <div class="card">
      <h2>À traiter</h2>
      <div class="card-sub">Retours et réclamations en attente</div>
      ${open.length ? `<div class="table-scroll"><table class="data"><thead>${savTableHead()}</thead><tbody>${open.map(renderTicket).join('')}</tbody></table></div>` : `<div class="empty">Aucun ticket ouvert — tout est traité.</div>`}
    </div>
    ${resolved.length ? `<div class="card" style="margin-top:14px;">
      <h2>Résolus récemment</h2>
      <div class="table-scroll"><table class="data"><thead>${savTableHead()}</thead><tbody>${resolved.map(renderTicket).join('')}</tbody></table></div>
    </div>` : ''}
    <div class="card-sub" style="margin-top:10px;">Cliquez sur un ticket pour voir le détail et renseigner ses champs de suivi.</div>
  `;
}

/* ---------- page: connecteurs ---------- */
const AVAILABLE_TYPES = ['shopify', 'etsy', 'instagram', 'woocommerce', 'tiktok'];
const CUSTOM_CONNECTOR_GUIDE_URL = '/guide-connecteur.html';
function pageConnecteurs() {
  const connected = state.connectors;
  const notConnected = AVAILABLE_TYPES.filter(t => !connected.some(c => c.type === t));
  return `
    <div class="topbar">
      <div><h1>Connecteurs</h1><div class="sub">${connected.length} plateforme${connected.length !== 1 ? 's' : ''} connectée${connected.length !== 1 ? 's' : ''}</div></div>
      <div class="topbar-actions">
        <button class="btn primary" data-action="openAddCustom">+ Connecteur personnalisé</button>
        <button class="btn icon" data-action="openGuide" title="Guide d'intégration du connecteur personnalisé" aria-label="Guide d'intégration">i</button>
        ${themeToggleHTML()}
      </div>
    </div>

    <h2 style="font-size:14px; margin:0 0 12px;">Connectées</h2>
    <div class="conn-grid">
      ${connected.map(c => `
        <div class="conn-card">
          <div class="head">
            <div class="ico" style="background:${channelColor(c.type)}">${CHANNEL_META[c.type]?.initials ?? '?'}</div>
            <div><div class="name">${c.label}</div><div class="meta">Connecté le ${fmtDate(c.connectedAt)}</div></div>
          </div>
          <div class="meta">Dernière synchro : ${fmtDateTime(c.lastSync)}</div>
          ${c.apiKey ? `<div class="api-box"><div class="line"><span>${c.apiKey.slice(0, 22)}…</span><span><span class="copy" data-action="copyKey" data-key="${c.apiKey}">Copier</span> · <span class="copy" data-action="openGuide" title="Guide d'intégration">ⓘ</span></span></div></div>` : ''}
          <div class="actions">
            <button class="btn sm" data-action="resync" data-id="${c.id}">Resynchroniser</button>
            <button class="btn sm danger" data-action="disconnect" data-id="${c.id}">Déconnecter</button>
          </div>
        </div>`).join('')}
    </div>

    ${notConnected.length ? `<h2 style="font-size:14px; margin:0 0 12px;">Disponibles</h2>
    <div class="conn-grid">
      ${notConnected.map(t => `
        <div class="conn-card">
          <div class="head">
            <div class="ico" style="background:var(--ink-faint)">${CHANNEL_META[t].initials}</div>
            <div><div class="name">${CHANNEL_META[t].label}</div><div class="meta">Non connecté</div></div>
          </div>
          <div class="actions"><button class="btn primary sm" data-action="openConnect" data-type="${t}">Connecter</button></div>
        </div>`).join('')}
    </div>` : ''}
  `;
}

/* ---------- page: facturation ---------- */
function pageFacturation() {
  const tier = state.plan.tier;
  const meta = PLAN_META[tier];
  return `
    <div class="topbar">
      <div><h1>Facturation</h1><div class="sub">Forfait actuel : ${meta.name}</div></div>
      <div class="topbar-actions">${themeToggleHTML()}</div>
    </div>

    <div class="card" style="margin-bottom:18px;">
      <div class="card-head">
        <div>
          <h2>Forfait ${meta.name}</h2>
          <div class="card-sub">Renouvellement le ${fmtDate(state.plan.renewsAt)}</div>
        </div>
        <span class="badge-current">Actif</span>
      </div>
      <div style="font-family:var(--font-mono); font-size:13px; color:var(--ink-soft);">
        ${meta.channels === Infinity ? 'Canaux illimités' : meta.channels + ' canaux max'} · jusqu'à ${fmtNum(meta.orders)} commandes/mois
      </div>
    </div>

    <div class="plan-grid">
      ${Object.entries(PLAN_META).map(([key, p]) => `
        <div class="plan-card ${key === tier ? 'current' : ''}">
          ${key === tier ? '<span class="badge-current">Forfait actuel</span>' : ''}
          <div class="tier-name">${p.name}</div>
          <div class="price">${p.price === 0 ? 'Gratuit' : fmtEUR(p.price)}${p.price ? '<span>/mois</span>' : ''}</div>
          <ul>
            <li>${p.channels === Infinity ? 'Canaux illimités' : p.channels + ' canaux'}</li>
            <li>${fmtNum(p.orders)} commandes/mois</li>
          </ul>
          ${key === tier ? `<button class="btn" disabled>Forfait actuel</button>` : `<button class="btn primary" data-action="openCheckout" data-tier="${key}">Choisir ce forfait</button>`}
        </div>
      `).join('')}
    </div>

    <div class="card">
      <h2>Historique de facturation</h2>
      <div class="card-sub">Factures et paiements passés</div>
      <table class="data">
        <thead><tr><th>Date</th><th>Forfait</th><th style="text-align:right">Montant</th></tr></thead>
        <tbody>${state.billingHistory.map(h => `<tr><td>${fmtDate(h.date)}</td><td>${h.tier}</td><td class="amount">${h.amount === 0 ? '—' : fmtEUR(h.amount)}</td></tr>`).join('')}</tbody>
      </table>
    </div>
  `;
}

/* ---------- page: paramètres ---------- */
function pageComptabilite() {
  const bounds = getRangeBounds();
  const a = computeAccounting(bounds);
  const missingCost = state.products.filter(p => !p.costPrice).length;
  const todayISO = new Date().toISOString().slice(0, 10);
  const fallbackFrom = daysAgo(29).toISOString().slice(0, 10);
  const custom = state.rangeCustom || {};
  return `
    <div class="topbar">
      <div><h1>Comptabilité</h1><div class="sub">Résumé simplifié — ne remplace pas votre comptable</div></div>
      <div class="topbar-actions">
        <div class="range">
          ${['7', '30', '90'].map(d => `<button data-action="setRange" data-range="${d}" class="${state.range === d ? 'active' : ''}">${d} j</button>`).join('')}
          <button data-action="setRange" data-range="custom" class="${state.range === 'custom' ? 'active' : ''}">Personnalisé</button>
        </div>
        ${state.range === 'custom' ? `
        <div style="display:flex; align-items:center; gap:6px;">
          <input type="date" id="rangeFromInput" class="stock-input" style="width:auto;" value="${custom.from || fallbackFrom}" max="${todayISO}">
          <span style="color:var(--ink-faint); font-size:12.5px;">→</span>
          <input type="date" id="rangeToInput" class="stock-input" style="width:auto;" value="${custom.to || todayISO}" max="${todayISO}">
        </div>` : ''}
        ${themeToggleHTML()}
      </div>
    </div>

    <div class="kpis">
      <div class="kpi"><div class="label">Chiffre d'affaires TTC</div><div class="row"><span class="value">${fmtEUR(a.ttc)}</span></div></div>
      <div class="kpi"><div class="label">Chiffre d'affaires HT</div><div class="row"><span class="value">${fmtEUR(a.ht)}</span></div></div>
      <div class="kpi"><div class="label">TVA collectée (estimée, ${Math.round(VAT_RATE * 100)}%)</div><div class="row"><span class="value">${fmtEUR(a.tva)}</span></div></div>
      <div class="kpi"><div class="label">Remboursements</div><div class="row"><span class="value" style="color:var(--critical)">${fmtEUR(a.refundsTotal)}</span><span class="delta warning">${a.refundedCount} commande${a.refundedCount !== 1 ? 's' : ''}</span></div></div>
    </div>

    <div class="grid">
      <div class="card">
        <h2>Marge brute</h2>
        <div class="card-sub">Chiffre d'affaires HT moins coût d'achat (HT) des produits vendus</div>
        <div style="display:flex; align-items:baseline; gap:14px; margin:10px 0 4px;">
          <span style="font-family:var(--font-mono); font-size:32px; font-weight:600; font-variant-numeric:tabular-nums;">${fmtEUR(a.margin)}</span>
          <span class="status-chip ${a.marginPct >= 40 ? 'good' : a.marginPct >= 20 ? 'warning' : 'critical'}"><span class="dot"></span>${a.marginPct.toFixed(1)}% de marge</span>
        </div>
        <div class="card-sub">Coût d'achat (HT) total sur la période : ${fmtEUR(a.cost)}</div>
        ${missingCost ? `<div class="callout" style="margin-top:14px;">${missingCost} produit${missingCost !== 1 ? 's' : ''} sans coût d'achat renseigné — la marge les compte à 0 €. <a href="#catalogue" style="color:var(--brand)">Compléter dans Mon catalogue →</a></div>` : ''}
      </div>
      <div class="card">
        <h2>Bénéfice net</h2>
        <div class="card-sub">Marge brute moins vos charges sur la période</div>
        <div style="display:flex; align-items:baseline; gap:14px; margin:10px 0 4px;">
          <span style="font-family:var(--font-mono); font-size:32px; font-weight:600; font-variant-numeric:tabular-nums; color:${a.netProfit >= 0 ? 'inherit' : 'var(--critical)'};">${fmtEUR(a.netProfit)}</span>
        </div>
        <div class="card-sub">${fmtEUR(a.margin)} de marge − ${fmtEUR(a.expensesTotal)} de charges</div>
      </div>
    </div>

    <div class="card" style="margin-bottom:14px;">
      <div class="card-head">
        <div><h2>Charges</h2><div class="card-sub">Vos frais fixes ou ponctuels (abonnements, pub, emballages, livraison…) sur la période</div></div>
        <button class="btn" data-action="openAddExpense">+ Ajouter une charge</button>
      </div>
      ${a.expenses.length ? `<div class="table-scroll"><table class="data">
        <thead><tr><th>Charge</th><th>Date</th><th style="text-align:right">Montant</th><th></th></tr></thead>
        <tbody>
          ${a.expenses.map(e => `
            <tr>
              <td>${escapeHTML(e.label)}</td>
              <td>${fmtDate(e.date)}</td>
              <td class="amount">${fmtEUR(e.amount)}</td>
              <td><span class="field-remove" data-action="removeExpense" data-id="${e.id}" title="Supprimer cette charge">×</span></td>
            </tr>`).join('')}
        </tbody>
      </table></div>
      <div class="card-sub" style="margin-top:10px;">Total : ${fmtEUR(a.expensesTotal)} sur ${fmtNum(a.expenses.length)} charge${a.expenses.length !== 1 ? 's' : ''}</div>` : `<div class="empty">Aucune charge enregistrée sur cette période.</div>`}
    </div>

    <div class="grid">
      <div class="card">
        <h2>Export comptable</h2>
        <div class="card-sub">Un fichier CSV prêt pour votre comptable ou votre logiciel de compta.</div>
        <ul class="plain" style="margin-top:6px;">
          <li>Une ligne par commande, avec montant TTC, HT, TVA, coût et marge</li>
          <li>Période sélectionnée : ${rangeLabel(bounds)} (${a.orders.length} commandes)</li>
        </ul>
        <button class="btn primary" data-action="exportAccounting" style="margin-top:8px;">Télécharger l'export (CSV)</button>
      </div>
    </div>
  `;
}

function exportAccountingCSV() {
  const bounds = getRangeBounds();
  const a = computeAccounting(bounds);
  const header = ['Date', 'Commande', 'Canal', 'Cliente', 'Statut', 'Montant TTC', 'Montant HT', 'TVA', "Coût d'achat (HT)", 'Marge'];
  const rows = a.orders.map(o => {
    const p = orderProduct(o);
    const isRefund = o.status === 'retour';
    const ht = isRefund ? 0 : o.amount / (1 + VAT_RATE);
    const tva = isRefund ? 0 : o.amount - ht;
    const cost = isRefund ? 0 : (p ? p.costPrice || 0 : 0);
    const margin = isRefund ? -o.amount : ht - cost;
    return [
      new Date(o.date).toLocaleDateString('fr-FR'),
      `#${o.orderNumber}`,
      connectorLabel(o.channelType),
      o.customer,
      isRefund ? 'Retour' : 'Vente',
      o.amount.toFixed(2),
      ht.toFixed(2),
      tva.toFixed(2),
      cost.toFixed(2),
      margin.toFixed(2)
    ];
  });
  const csvEscape = v => /[";\n]/.test(v) ? `"${String(v).replace(/"/g, '""')}"` : v;
  const summaryRows = [
    [],
    ['Charges'],
    ...a.expenses.map(e => [new Date(e.date).toLocaleDateString('fr-FR'), e.label, '', '', '', '', '', '', '', (-e.amount).toFixed(2)]),
    [],
    ['', '', '', '', '', '', '', '', 'Marge brute', a.margin.toFixed(2)],
    ['', '', '', '', '', '', '', '', 'Total charges', (-a.expensesTotal).toFixed(2)],
    ['', '', '', '', '', '', '', '', 'Bénéfice net', a.netProfit.toFixed(2)]
  ];
  const csv = [header, ...rows, ...summaryRows].map(r => r.map(csvEscape).join(';')).join('\r\n');
  const blob = new Blob(['﻿' + csv], { type: 'text/csv;charset=utf-8;' });
  const url = URL.createObjectURL(blob);
  const a2 = document.createElement('a');
  a2.href = url;
  const rangeTag = state.range === 'custom' ? `${(state.rangeCustom && state.rangeCustom.from) || 'debut'}_${(state.rangeCustom && state.rangeCustom.to) || 'fin'}` : `${rangeDayCount(bounds)}j`;
  a2.download = `comptoir-export-comptable-${rangeTag}-${new Date().toISOString().slice(0, 10)}.csv`;
  document.body.appendChild(a2);
  a2.click();
  a2.remove();
  URL.revokeObjectURL(url);
}

function pageParametres() {
  return `
    <div class="topbar">
      <div><h1>Paramètres</h1><div class="sub">Personnalisez votre espace</div></div>
      <div class="topbar-actions">${themeToggleHTML()}</div>
    </div>
    <div class="card">
      <h2>Couleur d'accent</h2>
      <div class="card-sub">S'applique aux boutons, liens et graphiques dans toute l'application.</div>
      <div class="accent-grid">
        ${Object.entries(ACCENTS).map(([key, a]) => `
          <button class="accent-swatch ${state.accent === key ? 'active' : ''}" data-action="setAccent" data-accent="${key}" type="button">
            <span class="accent-dot" style="background:${a.light.brand}"></span>
            <span>${a.label}</span>
            ${state.accent === key ? '<svg class="accent-check" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M3 8.5l3 3 7-7"/></svg>' : ''}
          </button>
        `).join('')}
      </div>
    </div>
    <div class="card" style="margin-top:14px;">
      <h2>Thème</h2>
      <div class="card-sub">Bascule manuelle entre clair et sombre — le bouton reste aussi accessible en haut de chaque page.</div>
      ${themeToggleHTML()}
    </div>
  `;
}

/* ---------- render root ---------- */
function renderNav() {
  const path = currentPath();
  const iconPaths = {
    '': '<path d="M2 9h3v5H2zM6.5 5h3v9h-3zM11 2h3v12h-3z"/>',
    'ventes': '<circle cx="5" cy="13" r="1.4"/><circle cx="12" cy="13" r="1.4"/><path d="M1 1h2l1.6 8.2a1.5 1.5 0 0 0 1.48 1.3h6.1a1.5 1.5 0 0 0 1.46-1.16L15 4H3.6" fill="none" stroke="currentColor" stroke-width="1.3"/>',
    'stock': '<path d="M2 4l6-3 6 3v8l-6 3-6-3z" fill="none" stroke="currentColor" stroke-width="1.3"/>',
    'catalogue': '<path d="M8.5 2H3a1 1 0 0 0-1 1v5.5a1 1 0 0 0 .3.7l6 6a1 1 0 0 0 1.4 0l4.5-4.5a1 1 0 0 0 0-1.4l-6-6a1 1 0 0 0-.7-.3z" fill="none" stroke="currentColor" stroke-width="1.3"/><circle cx="5" cy="5" r="1" fill="currentColor"/>',
    'sav': '<path d="M2 3h12v8H5l-3 3z" fill="none" stroke="currentColor" stroke-width="1.3"/>',
    'connecteurs': '<circle cx="8" cy="8" r="6" fill="none" stroke="currentColor" stroke-width="1.3"/><path d="M8 5v3l2 2" fill="none" stroke="currentColor" stroke-width="1.3"/>',
    'facturation': '<rect x="2" y="4" width="12" height="8" rx="1.2" fill="none" stroke="currentColor" stroke-width="1.3"/><path d="M2 6.5h12" stroke="currentColor" stroke-width="1.3"/>',
    'comptabilite': '<path d="M3 2h10v12H3z" fill="none" stroke="currentColor" stroke-width="1.3"/><path d="M5.5 5h5M5.5 8h5M5.5 11h3" stroke="currentColor" stroke-width="1.3"/>',
    'parametres': '<circle cx="8" cy="8" r="2.2" fill="none" stroke="currentColor" stroke-width="1.3"/><path d="M8 1.6v1.6M8 12.8v1.6M14.4 8h-1.6M3.2 8H1.6M12.4 3.6l-1.1 1.1M4.7 11.3l-1.1 1.1M12.4 12.4l-1.1-1.1M4.7 4.7l-1.1-1.1" stroke="currentColor" stroke-width="1.3"/>'
  };
  document.getElementById('nav').innerHTML = ROUTES.map(r => `
    <a href="#${r.path}" class="${path === r.path ? 'active' : ''}"><svg viewBox="0 0 16 16" fill="currentColor">${iconPaths[r.path]}</svg>${r.label}</a>
  `).join('');

  const connected = connectedTypes().length;
  const cs = document.getElementById('connectorStatus');
  cs.className = 'connector-status' + (connected ? '' : ' off');
  cs.innerHTML = `<span class="dot"></span>${connected} connecteur${connected !== 1 ? 's' : ''} actif${connected !== 1 ? 's' : ''}`;
  document.getElementById('planChipLabel').textContent = PLAN_META[state.plan.tier].name;
}

function render() {
  paintTheme();
  renderNav();
  const main = document.getElementById('main');
  const path = currentPath();
  const pages = { '': pageOverview, 'ventes': pageVentes, 'stock': pageStock, 'catalogue': pageCatalogue, 'sav': pageSAV, 'connecteurs': pageConnecteurs, 'facturation': pageFacturation, 'comptabilite': pageComptabilite, 'parametres': pageParametres };
  main.innerHTML = (pages[path] || pageOverview)();
  if (path === '') {
    const bounds = getRangeBounds();
    const granularity = state.overviewGranularity;
    const series = trendSeries(bounds, granularity);
    wireTrendChart(trendChartSVG(series, granularity, 'ca', 'ca').coords, granularity, 'ca', fmtEUR);
    wireTrendChart(trendChartSVG(series, granularity, 'cnt', 'count').coords, granularity, 'cnt', v => `${fmtNum(v)} vente${v !== 1 ? 's' : ''}`);
  }
}

/* ---------- actions ---------- */
function openAddProductModal() {
  // The catalog is already kept in sync with sales history (every product seen in an
  // order lands here automatically) — so it's already "the list of unique products from
  // history." Offered as suggestions so a product already tracked gets picked instead of
  // retyped (and risk a near-duplicate spelling that would fragment its stock).
  const suggestions = state.products.map(p => p.name).sort((a, b) => a.localeCompare(b, 'fr'));
  openModal(`
    <h3>Ajouter un produit</h3>
    <div class="modal-sub">Il apparaîtra dans le suivi de stock. ${suggestions.length ? 'Sélectionnez un produit déjà vu dans vos ventes, ou tapez un nouveau nom.' : ''}</div>
    <div class="field"><label>Nom du produit</label><input type="text" id="pName" list="pNameHistory" placeholder="Ex. Écharpe en laine">
      <datalist id="pNameHistory">${suggestions.map(n => `<option value="${escapeHTML(n)}">`).join('')}</datalist>
    </div>
    <div class="row2">
      <div class="field"><label>Stock initial</label><input type="number" id="pStock" min="0" value="20"></div>
      <div class="field"><label>Seuil d'alerte</label><input type="number" id="pThreshold" min="0" value="10"></div>
    </div>
    <div class="field"><label>Coût d'achat (HT, par unité)</label><input type="number" id="pCost" min="0" step="0.01" value="0"></div>
    <div class="field"><label>Canal</label><select id="pChannel">${connectedTypes().map(c => `<option value="${c.type}">${c.label}</option>`).join('')}</select></div>
    <div class="actions"><button class="btn" data-action="closeModal">Annuler</button><button class="btn primary" data-action="submitAddProduct">Ajouter</button></div>
  `);
}
function openAddCustomModal() {
  openModal(`
    <h3>Connecteur personnalisé</h3>
    <div class="modal-sub">Pour une plateforme maison — génère une clé API à transmettre à votre développeur. <span class="copy" data-action="openGuide" title="Guide d'intégration">Guide complet ⓘ</span></div>
    <div class="field"><label>Nom de la plateforme</label><input type="text" id="cName" placeholder="Ex. Boutique WordPress"></div>
    <div class="actions"><button class="btn" data-action="closeModal">Annuler</button><button class="btn primary" data-action="submitAddCustom">Générer la clé</button></div>
  `);
}
function findStockConflict(channelType) {
  return state.products.find(p =>
    p.channels.includes(channelType) && p.channels.length > 1 && p.stock <= 2
  ) || null;
}
function openStockConflictModal(product, connector) {
  const otherChannel = product.channels.find(ch => ch !== connector.type) || product.channels[0];
  openModal(`
    <h3>⚠️ Conflit de stock détecté</h3>
    <div class="modal-sub">Pendant la synchronisation de ${connector.label}</div>
    <div class="auth-error" style="background:var(--warning-soft); color:var(--warning);">
      « ${product.name} » a reçu des commandes quasi simultanées sur <b>${connectorLabel(connector.type)}</b> et <b>${connectorLabel(otherChannel)}</b>, alors qu'il ne restait que <b>${product.stock}</b> en stock.
    </div>
    <div class="modal-sub" style="margin-bottom:0;">Une des deux commandes ne pourra pas être honorée. Comptoir ne rembourse jamais automatiquement — à vous de décider.</div>
    <div class="actions" style="margin-top:18px;">
      <button class="btn" data-action="dismissConflict">Traiter plus tard</button>
      <button class="btn primary" data-action="resolveConflict" data-product-id="${product.id}" data-channel-type="${connector.type}">Créer un ticket SAV</button>
    </div>
  `);
}
function openConnectModal(type) {
  const meta = CHANNEL_META[type];
  openModal(`
    <h3>Connecter ${meta.label}</h3>
    <div class="modal-sub">Simulation de l'autorisation OAuth — aucune vraie connexion n'est établie.</div>
    <div id="connectBody" style="text-align:center; padding:20px 0;">
      <button class="btn primary" data-action="doConnect" data-type="${type}" style="width:100%; justify-content:center;">Autoriser l'accès à ${meta.label}</button>
    </div>
  `);
}
function openCheckoutModal(tier) {
  const p = PLAN_META[tier];
  openModal(`
    <h3>Passer au forfait ${p.name}</h3>
    <div class="modal-sub">${p.price === 0 ? 'Aucun paiement requis.' : fmtEUR(p.price) + ' / mois, résiliable à tout moment.'}</div>
    <div id="checkoutBody">
      ${p.price > 0 ? `
      <div class="field"><label>Numéro de carte</label><input type="text" placeholder="4242 4242 4242 4242" id="ccNum"></div>
      <div class="row2">
        <div class="field"><label>Expiration</label><input type="text" placeholder="12/28" id="ccExp"></div>
        <div class="field"><label>CVC</label><input type="text" placeholder="123" id="ccCvc"></div>
      </div>` : ''}
      <div class="actions"><button class="btn" data-action="closeModal">Annuler</button><button class="btn primary" data-action="doCheckout" data-tier="${tier}">${p.price === 0 ? 'Confirmer' : 'Payer et activer'}</button></div>
    </div>
  `);
}
function availableFieldOptions(catalog, existingFields) {
  const used = new Set(existingFields.map(f => `${f.source}::${f.key}`));
  const groups = [];
  groups.push({ label: 'Saisie manuelle', options: catalog.manual.filter(f => !used.has(`manual::${f.key}`)).map(f => ({ value: `manual::${f.key}`, text: f.label })) });
  connectedTypes().forEach(c => {
    const fields = catalog[c.type] || [];
    groups.push({ label: c.label, options: fields.filter(f => !used.has(`${c.id}::${f.key}`)).map(f => ({ value: `${c.id}::${f.key}`, text: f.label })) });
  });
  return groups.filter(g => g.options.length);
}
function openFieldPickerModal(catalog, existingFields, submitAction) {
  const groups = availableFieldOptions(catalog, existingFields);
  if (!groups.length) {
    openModal(`
      <h3>Ajouter un champ de suivi</h3>
      <div class="modal-sub">Tous les champs disponibles en base sont déjà ajoutés pour vos sources connectées.</div>
      <div class="actions"><button class="btn primary" data-action="closeModal">Fermer</button></div>
    `);
    return;
  }
  openModal(`
    <h3>Ajouter un champ de suivi</h3>
    <div class="modal-sub">Uniquement les champs disponibles dans les données de vos plateformes connectées — pas de champ libre.</div>
    <div class="field">
      <label>Champ</label>
      <select id="fieldPick">
        ${groups.map(g => `<optgroup label="${g.label}">${g.options.map(o => `<option value="${o.value}">${o.text}</option>`).join('')}</optgroup>`).join('')}
      </select>
    </div>
    <div class="actions"><button class="btn" data-action="closeModal">Annuler</button><button class="btn primary" data-action="${submitAction}">Ajouter</button></div>
  `);
}
function openAddFieldModal() { openFieldPickerModal(FIELD_CATALOG, state.customFields, 'submitAddField'); }
function openAddSavFieldModal() { openFieldPickerModal(SAV_FIELD_CATALOG, state.savFields, 'submitAddSavField'); }
function fieldSourceLabel(f) {
  if (f.source === 'manual') return 'Saisie manuelle';
  const c = state.connectors.find(c => c.id === f.source);
  return c ? `Synchronisé · ${c.label}` : 'Source inconnue';
}
function openOrderDetailModal(orderId) {
  const o = state.orders.find(o => o.id === orderId);
  if (!o) return;
  const [cls, label] = statusMeta(o.status);
  openModal(`
    <h3>Commande #${o.orderNumber}</h3>
    <div class="modal-sub">${connectorLabel(o.channelType)} · ${fmtDateTime(o.date)}</div>
    <div class="detail-grid">
      <div class="item"><div class="k">Cliente</div><div class="v">${o.customer}</div></div>
      <div class="item"><div class="k">Montant</div><div class="v">${fmtEUR(o.amount)}</div></div>
      <div class="item"><div class="k">Canal</div><div class="v"><span class="chan-dot"><span class="sw" style="background:${channelColor(o.channelType)}"></span>${connectorLabel(o.channelType)}</span></div></div>
      <div class="item"><div class="k">Statut</div><div class="v"><span class="status-chip ${cls}"><span class="dot"></span>${label}</span></div></div>
    </div>
    <div style="border-top:1px solid var(--rule-soft); padding-top:14px;">
      <div style="font-size:12.5px; color:var(--ink-faint); margin-bottom:12px;">Champs de suivi</div>
      ${state.customFields.length ? state.customFields.map(f => {
        const synced = f.source !== 'manual';
        const val = o.custom[f.id] ? escapeHTML(o.custom[f.id]) : '';
        return `
        <div class="custom-field-row">
          <label>${f.label}<span class="field-source-tag">${fieldSourceLabel(f)}</span></label>
          <input type="text" data-field-id="${f.id}" value="${val}" ${synced ? 'disabled placeholder="Rempli automatiquement à la prochaine synchro"' : ''}>
        </div>`;
      }).join('') : `<div class="card-sub" style="margin-bottom:12px;">Aucun champ pour l'instant.</div>`}
      <button class="btn sm" data-action="openAddField">+ Ajouter un champ</button>
    </div>
    <div class="actions"><button class="btn" data-action="closeModal">Fermer</button><button class="btn primary" data-action="saveOrderDetail" data-id="${o.id}">Enregistrer</button></div>
  `);
}
function openTicketDetailModal(ticketId) {
  const t = state.savTickets.find(t => t.id === ticketId);
  if (!t) return;
  const order = state.orders.find(o => o.id === t.orderId);
  const customerName = order ? order.customer : null;
  const contact = customerName ? state.customers.find(c => c.name === customerName) : null;
  const isOpen = t.status === 'ouvert';
  openModal(`
    <h3>Ticket — commande #${t.orderNumber}</h3>
    <div class="modal-sub">${connectorLabel(t.channelType)} · ${fmtDateTime(t.date)}</div>

    <div class="detail-section-label">Coordonnées de la cliente</div>
    <div class="detail-grid">
      <div class="item"><div class="k">Nom</div><div class="v">${contact ? contact.name : (customerName || '—')}</div></div>
      <div class="item"><div class="k">Ville</div><div class="v">${contact ? contact.city : '—'}</div></div>
      <div class="item"><div class="k">Email</div><div class="v">${contact ? `<a href="mailto:${contact.email}" style="color:var(--brand)">${contact.email}</a>` : '—'}</div></div>
      <div class="item"><div class="k">Téléphone</div><div class="v">${contact ? contact.phone : '—'}</div></div>
    </div>

    <div class="detail-section-label">Détails</div>
    <div class="detail-grid">
      <div class="item"><div class="k">Produit</div><div class="v">${t.product}</div></div>
      <div class="item"><div class="k">Motif</div><div class="v">${t.reason}</div></div>
      <div class="item"><div class="k">Canal</div><div class="v"><span class="chan-dot"><span class="sw" style="background:${channelColor(t.channelType)}"></span>${connectorLabel(t.channelType)}</span></div></div>
      <div class="item"><div class="k">Statut</div><div class="v"><span class="status-chip ${isOpen ? 'warning' : 'good'}"><span class="dot"></span>${isOpen ? 'Ouvert' : 'Résolu'}</span></div></div>
      ${order ? `<div class="item"><div class="k">Montant commande</div><div class="v">${fmtEUR(order.amount)}</div></div>` : ''}
    </div>

    <div style="border-top:1px solid var(--rule-soft); padding-top:14px;">
      <div style="font-size:12.5px; color:var(--ink-faint); margin-bottom:12px;">Champs de suivi SAV</div>
      ${state.savFields.length ? state.savFields.map(f => {
        const synced = f.source !== 'manual';
        const val = t.custom[f.id] ? escapeHTML(t.custom[f.id]) : '';
        return `
        <div class="custom-field-row">
          <label>${f.label}<span class="field-source-tag">${fieldSourceLabel(f)}</span><span class="field-remove" data-action="removeSavField" data-id="${f.id}" title="Retirer ce champ">×</span></label>
          <input type="text" data-sav-field-id="${f.id}" value="${val}" ${synced ? 'disabled placeholder="Rempli automatiquement à la prochaine synchro"' : ''}>
        </div>`;
      }).join('') : `<div class="card-sub" style="margin-bottom:12px;">Aucun champ pour l'instant — ajoutez ceux dont vous avez besoin.</div>`}
      <button class="btn sm" data-action="openAddSavField">+ Ajouter un champ</button>
    </div>
    <div class="actions">
      <button class="btn ${isOpen ? '' : 'sm'}" data-action="toggleTicket" data-id="${t.id}" data-then-close="1">${isOpen ? 'Marquer résolu' : 'Rouvrir'}</button>
      <button class="btn" data-action="closeModal">Fermer</button>
      <button class="btn primary" data-action="saveTicketDetail" data-id="${t.id}">Enregistrer</button>
    </div>
  `);
}

document.addEventListener('click', e => {
  const el = e.target.closest('[data-action]');
  if (!el) return;
  const action = el.dataset.action;

  if (action === 'toggleTheme') return toggleTheme();
  if (action === 'landingToggleTheme') {
    state.theme = resolvedTheme() === 'dark' ? 'light' : 'dark';
    paintTheme();
    renderLanding();
    return;
  }
  if (action === 'setAccent') {
    state.accent = el.dataset.accent;
    persist(); applyAccent(); render();
    toast(`Couleur d'accent : ${ACCENTS[state.accent].label}.`);
    return;
  }
  if (action === 'setRange') {
    if (el.dataset.range === 'custom' && (!state.rangeCustom || !state.rangeCustom.from || !state.rangeCustom.to)) {
      const todayISO = new Date().toISOString().slice(0, 10);
      state.rangeCustom = { from: (state.rangeCustom && state.rangeCustom.from) || daysAgo(29).toISOString().slice(0, 10), to: (state.rangeCustom && state.rangeCustom.to) || todayISO };
    }
    setState({ range: el.dataset.range });
    return;
  }
  if (action === 'setGranularity') { setState({ overviewGranularity: el.dataset.granularity }); return; }
  if (action === 'exportAccounting') {
    exportAccountingCSV();
    toast('Export téléchargé.');
    return;
  }
  if (action === 'closeModal') return closeModal();

  if (action === 'authSwitch') return renderAuth(el.dataset.mode);
  if (action === 'logout') {
    const session = getSession();
    if (session && session.token) apiRequest('/api/logout', { method: 'POST', token: session.token }).catch(() => {});
    clearSession();
    localStorage.removeItem(STORAGE_KEY); // don't leave this account's business data cached on a shared machine
    location.hash = '';
    renderAuth('login');
    toast('Vous avez été déconnecté.');
    return;
  }

  if (action === 'openOrderDetail') return openOrderDetailModal(el.dataset.id);
  if (action === 'saveOrderDetail') {
    const o = state.orders.find(o => o.id === el.dataset.id);
    if (o) {
      document.querySelectorAll('[data-field-id]:not(:disabled)').forEach(inp => {
        o.custom[inp.dataset.fieldId] = inp.value.trim();
      });
      persist();
    }
    closeModal(); render(); toast('Commande mise à jour.');
    return;
  }
  if (action === 'openAddField') return openAddFieldModal();
  if (action === 'submitAddField') {
    const sel = document.getElementById('fieldPick');
    if (!sel) return closeModal();
    const [source, key] = sel.value.split('::');
    const label = sel.options[sel.selectedIndex].textContent;
    state.customFields.push({ id: uid(), key, label, source });
    persist(); closeModal(); render(); toast(`Champ « ${label} » ajouté.`);
    return;
  }
  if (action === 'removeField') {
    const f = state.customFields.find(f => f.id === el.dataset.id);
    state.customFields = state.customFields.filter(f => f.id !== el.dataset.id);
    persist(); render(); toast(`Champ « ${f?.label ?? ''} » retiré.`);
    return;
  }

  if (action === 'openAddProduct') return openAddProductModal();
  if (action === 'submitAddProduct') {
    const name = document.getElementById('pName').value.trim();
    if (!name) return toast('Le nom du produit est requis.', true);
    const existing = state.products.find(p => p.name.trim().toLowerCase() === name.toLowerCase());
    if (existing) {
      closeModal();
      toast(`« ${existing.name} » existe déjà dans votre catalogue — pas de doublon créé.`, true);
      return;
    }
    const stock = Number(document.getElementById('pStock').value) || 0;
    const threshold = Number(document.getElementById('pThreshold').value) || 0;
    const costPrice = Math.max(0, Number(document.getElementById('pCost').value) || 0);
    const channel = document.getElementById('pChannel').value;
    state.products.unshift({ id: uid(), name, stock, threshold, costPrice, salePrice: null, supplier: '', custom: {}, channels: channel ? [channel] : [] });
    persist(); closeModal(); render(); toast(`« ${name} » ajouté au suivi de stock.`);
    return;
  }

  if (action === 'importFromSite') {
    const known = new Set(state.products.map(p => p.id));
    const orphanOrders = state.orders.filter(o => !o.productId || !known.has(o.productId));
    const incomplete = state.products.filter(p => !p.costPrice || !p.supplier).length;
    catalogFilterIncomplete = incomplete > 0;
    render();
    if (state.products.length === 0 && orphanOrders.length === 0) {
      toast('Aucune vente enregistrée pour l\'instant — le catalogue se remplira automatiquement dès les premières commandes.', true);
    } else {
      let msg = `${fmtNum(state.products.length)} produit${state.products.length !== 1 ? 's' : ''} distinct${state.products.length !== 1 ? 's' : ''} depuis vos ventes`;
      msg += incomplete > 0 ? ` — ${incomplete} à compléter (prix d'achat / fournisseur).` : ', tous déjà complets.';
      if (orphanOrders.length) msg += ` ${orphanOrders.length} commande${orphanOrders.length !== 1 ? 's' : ''} sans produit rattaché (voir ci-dessous).`;
      toast(msg, orphanOrders.length > 0);
    }
    return;
  }
  if (action === 'clearCatalogFilter') { catalogFilterIncomplete = false; render(); return; }
  if (action === 'useSuggestedSalePrice') {
    const p = state.products.find(p => p.id === el.dataset.id);
    if (p) { p.salePrice = Number(el.dataset.price) || 0; persist(); render(); toast('Prix de revente renseigné depuis la dernière vente.'); }
    return;
  }
  if (action === 'exportCatalog') { exportCatalogCSV(); return; }

  if (action === 'openImportCatalog') return openImportCatalogModal();
  if (action === 'submitCatalogImport') {
    if (!pendingCatalogImport) return;
    const { headers, rows } = pendingCatalogImport;
    const mapping = {};
    document.querySelectorAll('[data-map-col]').forEach(sel => {
      const idx = Number(sel.dataset.mapCol);
      const val = sel.value;
      if (!val) return;
      if (val.startsWith('field:')) mapping[idx] = { type: 'field', key: val.slice(6) };
      else if (val.startsWith('custom:')) mapping[idx] = { type: 'custom', id: val.slice(7) };
      else if (val === 'new') mapping[idx] = { type: 'new', label: headers[idx] };
    });
    const nameEntry = Object.entries(mapping).find(([, m]) => m.type === 'field' && m.key === 'name');
    if (!nameEntry) return toast('Associez au moins une colonne au « Nom du produit ».', true);
    const nameIdx = Number(nameEntry[0]);

    const newFieldIds = {};
    Object.entries(mapping).forEach(([idx, m]) => {
      if (m.type === 'new') {
        const fid = uid();
        state.catalogFields.push({ id: fid, label: m.label });
        newFieldIds[idx] = fid;
      }
    });

    let created = 0, updated = 0;
    rows.forEach(row => {
      const name = (row[nameIdx] || '').trim();
      if (!name) return;
      let p = state.products.find(p => p.name.trim().toLowerCase() === name.toLowerCase());
      if (!p) {
        p = { id: uid(), name, stock: 0, threshold: 10, costPrice: 0, salePrice: null, supplier: '', custom: {}, channels: [] };
        state.products.push(p);
        created++;
      } else updated++;
      Object.entries(mapping).forEach(([idx, m]) => {
        const raw = (row[idx] || '').trim();
        if (m.type === 'field') {
          if (m.key === 'name' || !raw) return;
          if (['costPrice', 'salePrice', 'stock', 'threshold'].includes(m.key)) {
            const num = parseFloat(raw.replace(',', '.').replace(/[^\d.\-]/g, ''));
            if (!isNaN(num)) p[m.key] = num;
          } else {
            p[m.key] = raw;
          }
        } else if (m.type === 'custom' && raw) {
          p.custom[m.id] = raw;
        } else if (m.type === 'new' && raw) {
          p.custom[newFieldIds[idx]] = raw;
        }
      });
    });

    pendingCatalogImport = null;
    persist(); closeModal(); render();
    toast(`Import terminé : ${created} produit${created !== 1 ? 's' : ''} créé${created !== 1 ? 's' : ''}, ${updated} mis à jour.`);
    return;
  }

  if (action === 'openAddCatalogField') return openAddCatalogFieldModal();
  if (action === 'submitAddCatalogField') {
    const label = document.getElementById('catalogFieldLabel').value.trim();
    if (!label) return toast('Le nom de la colonne est requis.', true);
    state.catalogFields.push({ id: uid(), label });
    persist(); closeModal(); render();
    toast(`Colonne « ${label} » ajoutée.`);
    return;
  }
  if (action === 'removeCatalogField') {
    const fieldId = el.dataset.id;
    state.catalogFields = state.catalogFields.filter(f => f.id !== fieldId);
    state.products.forEach(p => { delete p.custom[fieldId]; });
    persist(); render();
    return;
  }

  if (action === 'openAddExpense') return openAddExpenseModal();
  if (action === 'submitAddExpense') {
    const label = document.getElementById('expenseLabel').value.trim();
    const amount = Math.max(0, Number(document.getElementById('expenseAmount').value) || 0);
    const dateInput = document.getElementById('expenseDate').value;
    if (!label) return toast('L\'intitulé de la charge est requis.', true);
    const date = dateInput ? new Date(dateInput + 'T12:00:00').toISOString() : new Date().toISOString();
    state.expenses.push({ id: uid(), label, amount, date });
    persist(); closeModal(); render();
    toast(`Charge « ${label} » ajoutée.`);
    return;
  }
  if (action === 'removeExpense') {
    state.expenses = state.expenses.filter(e => e.id !== el.dataset.id);
    persist(); render();
    return;
  }

  if (action === 'openAddCustom') return openAddCustomModal();
  if (action === 'submitAddCustom') {
    const name = document.getElementById('cName').value.trim();
    if (!name) return toast('Le nom de la plateforme est requis.', true);
    const session = getSession();
    const submitBtn = el;
    submitBtn.disabled = true;
    submitBtn.textContent = 'Génération…';
    apiRequest('/api/connectors/custom', { method: 'POST', token: session.token, body: { label: name } })
      .then(({ connectorId, apiKey }) => {
        const conn = { id: connectorId, type: 'custom', label: name, status: 'connected', connectedAt: new Date().toISOString(), lastSync: new Date().toISOString(), apiKey };
        state.connectors.push(conn); persist();
        const endpoint = `${location.origin}/api/ingest/orders`;
        const curlExample = `curl -X POST ${endpoint} \\\n  -H "Authorization: Bearer ${apiKey}" \\\n  -H "Content-Type: application/json" \\\n  -d '{"externalId":"CMD-1234","amount":42.90,"status":"livree","customerName":"Jeanne Dupont","productName":"Étole en lin écru"}'`;
        document.getElementById('modalBody').innerHTML = `
          <h3>${escapeHTML(name)} connecté</h3>
          <div class="modal-sub">Transmettez ces informations à votre développeur — chaque nouvelle commande sur ${escapeHTML(name)} doit déclencher cet appel. <span class="copy" data-action="openGuide" title="Guide d'intégration">Guide complet ⓘ</span></div>
          <div class="api-box">
            <div class="line"><span>Clé API</span><span class="copy" data-action="copyKey" data-key="${apiKey}">Copier</span></div>
            <div style="word-break:break-all; margin-bottom:8px;">${apiKey}</div>
            <div class="line"><span>Endpoint commandes</span></div>
            <div>POST ${endpoint}</div>
          </div>
          <div class="modal-sub" style="margin-top:14px;">Exemple d'appel :</div>
          <div class="api-box"><pre style="white-space:pre-wrap; word-break:break-all; margin:0; font-family:var(--font-mono); font-size:12px;">${escapeHTML(curlExample)}</pre></div>
          <div class="modal-sub" style="margin-top:14px;">Seul le montant est obligatoire. Les noms de champs sont reconnus automatiquement : <code>amount</code>/<code>total</code>/<code>montant</code>/<code>price</code>, <code>status</code>/<code>statut</code>/<code>state</code> (accepte aussi delivered/shipped/pending/refunded...), <code>customerName</code>/<code>client</code>/ou un objet <code>customer: {name}</code>, <code>productName</code>/<code>product</code>/ou un tableau <code>items</code>. Pas besoin de reformater exactement — envoyez ce que renvoie déjà le site. <code>externalId</code> évite les doublons si l'appel est renvoyé deux fois.</div>
          <div class="actions"><button class="btn primary" data-action="closeModal">Terminé</button></div>
        `;
        render(); toast(`Connecteur « ${name} » créé.`);
      })
      .catch(err => {
        submitBtn.disabled = false;
        submitBtn.textContent = 'Générer la clé';
        toast(err.message, true);
      });
    return;
  }
  if (action === 'openGuide') {
    window.open(CUSTOM_CONNECTOR_GUIDE_URL, '_blank', 'noopener');
    return;
  }
  if (action === 'copyKey') {
    navigator.clipboard?.writeText(el.dataset.key).then(() => toast('Clé copiée.'));
    return;
  }

  if (action === 'openConnect') return openConnectModal(el.dataset.type);
  if (action === 'doConnect') {
    const type = el.dataset.type;
    document.getElementById('connectBody').innerHTML = `<span class="spinner" style="border-top-color:var(--brand); border-color:var(--rule-soft);"></span> Connexion à ${CHANNEL_META[type].label}…`;
    setTimeout(() => {
      state.connectors.push({ id: uid(), type, label: CHANNEL_META[type].label, status: 'connected', connectedAt: new Date().toISOString(), lastSync: new Date().toISOString() });
      persist(); closeModal(); render(); toast(`${CHANNEL_META[type].label} connecté.`);
    }, 1100);
    return;
  }
  if (action === 'resync') {
    const c = state.connectors.find(c => c.id === el.dataset.id);
    if (!c) return;
    c.lastSync = new Date().toISOString();
    persist(); render();
    const conflict = findStockConflict(c.type);
    if (conflict) { openStockConflictModal(conflict, c); return; }
    toast(`${c.label} resynchronisé.`);
    return;
  }
  if (action === 'resolveConflict') {
    const p = state.products.find(p => p.id === el.dataset.productId);
    const cType = el.dataset.channelType;
    if (p) {
      const otherChannel = p.channels.find(ch => ch !== cType) || p.channels[0];
      state.savTickets.unshift({
        id: uid(), orderId: null, orderNumber: '—', product: p.name,
        channelType: otherChannel, reason: 'Conflit de stock — rupture après synchronisation multicanal',
        status: 'ouvert', date: new Date().toISOString(), custom: {}
      });
      persist();
    }
    closeModal(); render(); toast('Ticket SAV créé pour gérer le conflit.');
    return;
  }
  if (action === 'dismissConflict') { closeModal(); toast('Conflit ignoré pour l\'instant.'); return; }
  if (action === 'disconnect') {
    const c = state.connectors.find(c => c.id === el.dataset.id);
    state.connectors = state.connectors.filter(c => c.id !== el.dataset.id);
    persist(); render(); toast(`${c?.label ?? 'Connecteur'} déconnecté.`);
    if (c?.type === 'custom') {
      const session = getSession();
      if (session && session.token) {
        apiRequest(`/api/connectors/${c.id}`, { method: 'DELETE', token: session.token })
          .catch(() => { toast('La clé API n\'a pas pu être révoquée côté serveur.', true); });
      }
    }
    return;
  }

  if (action === 'openCheckout') return openCheckoutModal(el.dataset.tier);
  if (action === 'doCheckout') {
    const tier = el.dataset.tier;
    const p = PLAN_META[tier];
    const body = document.getElementById('checkoutBody');
    body.innerHTML = `<div style="text-align:center; padding:24px 0;"><span class="spinner" style="border-top-color:var(--brand); border-color:var(--rule-soft);"></span><div style="margin-top:10px; font-size:13px; color:var(--ink-soft);">Traitement du paiement…</div></div>`;
    setTimeout(() => {
      state.plan = { tier, renewsAt: isoDaysAgo(-30) };
      if (p.price > 0) state.billingHistory.unshift({ id: uid(), date: new Date().toISOString(), amount: p.price, tier: p.name });
      persist(); closeModal(); render(); toast(`Forfait ${p.name} activé automatiquement.`);
    }, 1300);
    return;
  }

  if (action === 'toggleTicket') {
    const t = state.savTickets.find(t => t.id === el.dataset.id);
    if (t) {
      t.status = t.status === 'ouvert' ? 'resolu' : 'ouvert';
      persist();
      if (el.dataset.thenClose) closeModal();
      render();
      toast(t.status === 'resolu' ? 'Ticket marqué résolu.' : 'Ticket rouvert.');
    }
    return;
  }

  if (action === 'openTicketDetail') return openTicketDetailModal(el.dataset.id);
  if (action === 'saveTicketDetail') {
    const t = state.savTickets.find(t => t.id === el.dataset.id);
    if (t) {
      document.querySelectorAll('[data-sav-field-id]:not(:disabled)').forEach(inp => {
        t.custom[inp.dataset.savFieldId] = inp.value.trim();
      });
      persist();
    }
    closeModal(); render(); toast('Ticket mis à jour.');
    return;
  }
  if (action === 'openAddSavField') return openAddSavFieldModal();
  if (action === 'submitAddSavField') {
    const sel = document.getElementById('fieldPick');
    if (!sel) return closeModal();
    const [source, key] = sel.value.split('::');
    const label = sel.options[sel.selectedIndex].textContent;
    state.savFields.push({ id: uid(), key, label, source });
    persist(); closeModal(); render(); toast(`Champ « ${label} » ajouté aux tickets SAV.`);
    return;
  }
  if (action === 'removeSavField') {
    const f = state.savFields.find(f => f.id === el.dataset.id);
    state.savFields = state.savFields.filter(f => f.id !== el.dataset.id);
    persist(); closeModal(); render(); toast(`Champ « ${f?.label ?? ''} » retiré.`);
    return;
  }
});

document.addEventListener('keydown', e => {
  if ((e.key === 'Enter' || e.key === ' ') && e.target.matches('[role="button"][data-action]')) {
    e.preventDefault();
    e.target.click();
  }
});

document.addEventListener('input', e => {
  if (e.target.matches('[data-stock-id]')) {
    const p = state.products.find(p => p.id === e.target.dataset.stockId);
    if (p) { p.stock = clamp(Number(e.target.value) || 0, 0, 99999); persist(); }
    const row = e.target.closest('tr');
    if (row) row.querySelector('.status-chip').outerHTML = `<span class="status-chip ${alertLevel(p)}"><span class="dot"></span>${alertLevel(p) === 'good' ? 'OK' : alertLevel(p) === 'warning' ? 'Vigilance' : 'Critique'}</span>`;
  }
  if (e.target.matches('[data-cost-id]')) {
    const p = state.products.find(p => p.id === e.target.dataset.costId);
    if (p) { p.costPrice = Math.max(0, Number(e.target.value) || 0); persist(); }
  }
  if (e.target.matches('[data-supplier-id]')) {
    const p = state.products.find(p => p.id === e.target.dataset.supplierId);
    if (p) { p.supplier = e.target.value; persist(); }
  }
  if (e.target.matches('[data-sale-price-id]')) {
    const p = state.products.find(p => p.id === e.target.dataset.salePriceId);
    if (p) { p.salePrice = e.target.value === '' ? null : Math.max(0, Number(e.target.value) || 0); persist(); }
  }
  if (e.target.matches('[data-catalog-custom-id]')) {
    const p = state.products.find(p => p.id === e.target.dataset.catalogCustomId);
    if (p) { p.custom[e.target.dataset.fieldId] = e.target.value; persist(); }
  }
  if (e.target.id === 'salesSearch') { salesFilter.q = e.target.value; renderKeepFocus('salesSearch'); }
});
document.addEventListener('change', e => {
  if (e.target.id === 'salesChannel') { salesFilter.channel = e.target.value; render(); }
  if (e.target.id === 'salesStatus') { salesFilter.status = e.target.value; render(); }
  if (e.target.id === 'rangeFromInput') { state.rangeCustom = { ...(state.rangeCustom || {}), from: e.target.value }; setState({ range: 'custom' }); }
  if (e.target.id === 'rangeToInput') { state.rangeCustom = { ...(state.rangeCustom || {}), to: e.target.value }; setState({ range: 'custom' }); }
});
function renderKeepFocus(id) {
  const pos = document.getElementById(id)?.selectionStart;
  render();
  const el = document.getElementById(id);
  if (el) { el.focus(); el.setSelectionRange(pos, pos); }
}

/* ---------- init ---------- */
paintTheme();
renderSplash(boot);

if ('serviceWorker' in navigator) {
  window.addEventListener('load', () => navigator.serviceWorker.register('/sw.js').catch(() => {}));
}
