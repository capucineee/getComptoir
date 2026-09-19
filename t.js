/* Comptoir — visitor counter. No cookie, no stored identifier, honours Do Not Track. */
(function () {
  var s = document.currentScript;
  var site = s && s.getAttribute('data-site');
  if (!site || navigator.doNotTrack === '1' || window.doNotTrack === '1') return;
  var api = s.src.replace(/\/t\.js.*$/, '') + '/api/track';
  var last = '';
  function send() {
    var path = location.pathname + location.search;
    if (path === last) return;
    last = path;
    var tz = '';
    try { tz = Intl.DateTimeFormat().resolvedOptions().timeZone || ''; } catch (e) {}
    var body = JSON.stringify({ site: site, url: location.href, ref: document.referrer, tz: tz, lang: navigator.language || '' });
    try {
      if (navigator.sendBeacon) navigator.sendBeacon(api, new Blob([body], { type: 'text/plain' }));
      else fetch(api, { method: 'POST', body: body, keepalive: true, headers: { 'Content-Type': 'text/plain' } });
    } catch (e) {}
  }
  var ps = history.pushState;
  if (ps) history.pushState = function () { ps.apply(this, arguments); setTimeout(send, 0); };
  window.addEventListener('popstate', send);
  send();
})();
