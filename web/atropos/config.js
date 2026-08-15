"use strict";
/* ===========================================================================
   Where the game's backend lives.

   The client is static and can be served from anywhere, but the game itself
   needs a live WebSocket, which serverless hosting cannot hold open. So the
   two halves are split: the page can sit on any static host, while rooms,
   movement and every game action run on the Railway backend.

   Served from Railway, the page talks to itself. Served from anywhere else -
   Vercel, Netlify, a laptop - it points back at Railway.

   To move the backend, change API_ORIGIN and nothing else.
   =========================================================================== */

const API_ORIGIN = "https://web-production-7d1c.up.railway.app";

// Never clobber a value set ahead of this file. That lets a host inject its
// own backend at build time, and lets a test point the client somewhere else,
// without editing this file at all.
if (!window.ATROPOS_API){
  const sameOrigin =
    /(^|\.)railway\.app$/.test(location.hostname) ||
    location.hostname === "localhost" ||
    location.hostname === "127.0.0.1";
  window.ATROPOS_API = sameOrigin ? location.origin : API_ORIGIN;
}
