"use strict";
/* ===========================================================================
   Where the game's backend lives.

   The client is static and can be served from anywhere, but the game itself
   needs a live WebSocket, which serverless hosting cannot hold open. So the
   two halves are split: the page can sit on any static host, while rooms,
   movement and every game action run on a small always-on backend.

   Served from the backend's own host, the page talks to itself. Served from
   anywhere else - Vercel, Netlify, a laptop - it points back at API_ORIGIN.

   Resolution order, first match wins:

     1. window.MOLUA_API set before this file  - a host injecting at build time
     2. ?api=https://...  in the URL           - point the live page anywhere
     3. the last ?api= used, remembered        - survives the hop to /CODE
     4. same origin, if this looks like the backend host
     5. API_ORIGIN below

   Rule 2 is what makes a new backend testable without redeploying the site:
   deploy it, then open the live page with ?api= pointing at it. The browser's
   CSP still has to allow the host, so this is not a way to reach anywhere -
   see connect-src in the site's vercel.json.
   =========================================================================== */

// Change this one line to point the game at its backend.
const API_ORIGIN = "https://molua-backend.up.railway.app";

(function resolveBackend(){
  // Never clobber a value set ahead of this file.
  if (window.MOLUA_API) return;

  const REMEMBER = "molua:api";
  let override = null;

  try {
    const q = new URLSearchParams(location.search).get("api");
    if (q){
      const u = new URL(q, location.href);
      // https only, except on a laptop where there is no certificate to have.
      const localish = u.hostname === "localhost" || u.hostname === "127.0.0.1";
      if (u.protocol === "https:" || (localish && u.protocol === "http:")){
        override = u.origin;
        try { localStorage.setItem(REMEMBER, override); } catch(e){}
      }
    } else {
      // Opening a shared room link drops the query string, so the choice has
      // to outlive the first page.
      override = localStorage.getItem(REMEMBER) || null;
    }
  } catch(e){ /* a hostile query string is not worth a broken page */ }

  if (override){
    window.MOLUA_API = override;
    window.MOLUA_API_CUSTOM = true;   // the page says so out loud
    return;
  }

  const sameOrigin =
    /(^|\.)railway\.app$/.test(location.hostname) ||
    /(^|\.)fly\.dev$/.test(location.hostname) ||
    /(^|\.)onrender\.com$/.test(location.hostname) ||
    location.hostname === "localhost" ||
    location.hostname === "127.0.0.1";
  window.MOLUA_API = sameOrigin ? location.origin : API_ORIGIN;
})();
