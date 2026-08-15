"use strict";
/* ===========================================================================
   VOICE - browser mic, Discord style

   Click the mic, everyone in the room hears you. No voice server: WebRTC
   carries the audio peer to peer, and the game's existing room socket carries
   the handshake, so this adds nothing to deploy.

   Topology is a full mesh - every player dials every other player. That is the
   right call up to roughly eight people (each client sends its stream 7 times,
   which a phone handles). Beyond that a mesh gets expensive on upload, and the
   answer would be a selective forwarding unit, which *is* a server.

   Connectivity uses public STUN only. Most networks work; the awkward ones -
   symmetric NAT, some mobile carriers, strict school and campus wifi - need a
   TURN relay to get through, and TURN has to be paid for. Players who cannot
   connect fall back to silence rather than breaking the game.
   =========================================================================== */

const Voice = (() => {

  const ICE = {
    iceServers: [
      { urls: ["stun:stun.l.google.com:19302", "stun:stun1.l.google.com:19302"] }
    ]
  };

  let localStream = null;
  let enabled = false;
  let send = null;                 // injected: how to reach the room socket
  let selfPid = null;
  const peers = new Map();         // pid -> { pc, audio, analyser, speaking }
  let onChange = () => {};
  let audioCtx = null;

  /* ---------------------------------------------------------------------
     Mic
     --------------------------------------------------------------------- */
  async function enable(){
    if (enabled) return { ok: true };
    if (!navigator.mediaDevices || !window.RTCPeerConnection){
      return { ok: false, reason: "This browser can't do voice chat." };
    }
    try {
      localStream = await navigator.mediaDevices.getUserMedia({
        audio: {
          echoCancellation: true,     // players are often in the same room
          noiseSuppression: true,
          autoGainControl: true
        },
        video: false
      });
    } catch (err){
      const denied = err && (err.name === "NotAllowedError" || err.name === "SecurityError");
      return {
        ok: false,
        reason: denied
          ? "Mic blocked. Allow the microphone in your browser settings."
          : "No microphone found."
      };
    }
    enabled = true;
    watchSpeaking(selfPid, localStream);
    send && send({ t: "voice", on: true });
    onChange();
    return { ok: true };
  }

  function disable(){
    if (!enabled) return;
    enabled = false;
    if (localStream){
      localStream.getTracks().forEach(t => t.stop());
      localStream = null;
    }
    peers.forEach((_, pid) => drop(pid));
    send && send({ t: "voice", on: false });
    onChange();
  }

  function toggle(){ return enabled ? (disable(), Promise.resolve({ ok: true })) : enable(); }

  /* Mute without dropping the call, the way a mute button should behave. */
  let muted = false;
  function setMuted(v){
    muted = !!v;
    if (localStream) localStream.getAudioTracks().forEach(t => { t.enabled = !muted; });
    onChange();
  }

  /* ---------------------------------------------------------------------
     Peers
     --------------------------------------------------------------------- */
  function makePeer(pid, polite){
    if (peers.has(pid)) return peers.get(pid);

    const pc = new RTCPeerConnection(ICE);
    const audio = document.createElement("audio");
    audio.autoplay = true;
    audio.playsInline = true;
    document.body.appendChild(audio);

    const entry = { pc, audio, speaking: false, level: 0 };
    peers.set(pid, entry);

    if (localStream) localStream.getTracks().forEach(t => pc.addTrack(t, localStream));

    pc.onicecandidate = (e) => {
      if (e.candidate) send({ t: "rtc", to: pid, kind: "ice", data: e.candidate.toJSON() });
    };
    pc.ontrack = (e) => {
      audio.srcObject = e.streams[0];
      // Some browsers refuse autoplay until the page has been interacted with.
      audio.play().catch(() => {});
      watchSpeaking(pid, e.streams[0]);
    };
    pc.onconnectionstatechange = () => {
      if (["failed", "closed"].includes(pc.connectionState)) drop(pid);
      onChange();
    };

    // Only one side offers, decided by comparing ids, so two peers never
    // offer to each other at the same time and collide.
    if (!polite){
      pc.onnegotiationneeded = async () => {
        try {
          await pc.setLocalDescription(await pc.createOffer());
          send({ t: "rtc", to: pid, kind: "offer", data: pc.localDescription.toJSON() });
        } catch (e){ /* renegotiation raced a drop; the next sync re-dials */ }
      };
    }
    return entry;
  }

  function drop(pid){
    const entry = peers.get(pid);
    if (!entry) return;
    try { entry.pc.close(); } catch (e){}
    if (entry.audio && entry.audio.parentNode) entry.audio.parentNode.removeChild(entry.audio);
    peers.delete(pid);
    onChange();
  }

  /* Handshake arriving from another player, relayed by the room socket. */
  async function signal(from, kind, data){
    if (!enabled) return;
    const polite = String(selfPid) > String(from);
    const entry = makePeer(from, polite);
    const pc = entry.pc;
    try {
      if (kind === "offer"){
        await pc.setRemoteDescription(new RTCSessionDescription(data));
        await pc.setLocalDescription(await pc.createAnswer());
        send({ t: "rtc", to: from, kind: "answer", data: pc.localDescription.toJSON() });
      } else if (kind === "answer"){
        if (pc.signalingState !== "stable") await pc.setRemoteDescription(new RTCSessionDescription(data));
      } else if (kind === "ice"){
        await pc.addIceCandidate(new RTCIceCandidate(data));
      }
    } catch (e){ /* a stale candidate after a drop is normal; ignore */ }
  }

  /* Reconcile the mesh against who is actually in the room with a mic on. */
  function sync(players){
    if (!enabled) return;
    const live = new Set(
      players.filter(p => p.voice && p.pid !== selfPid && p.connected).map(p => p.pid));
    live.forEach(pid => { if (!peers.has(pid)) makePeer(pid, String(selfPid) > String(pid)); });
    [...peers.keys()].forEach(pid => { if (!live.has(pid)) drop(pid); });
  }

  /* ---------------------------------------------------------------------
     Who is talking - drives the ring around a speaker's name tag
     --------------------------------------------------------------------- */
  function watchSpeaking(pid, stream){
    try {
      audioCtx = audioCtx || new (window.AudioContext || window.webkitAudioContext)();
      const src = audioCtx.createMediaStreamSource(stream);
      const analyser = audioCtx.createAnalyser();
      analyser.fftSize = 512;
      src.connect(analyser);
      const buf = new Uint8Array(analyser.frequencyBinCount);
      const entry = pid === selfPid ? (selfMeter = { speaking: false }) : peers.get(pid);
      const tick = () => {
        if (!enabled) return;
        analyser.getByteFrequencyData(buf);
        let sum = 0;
        for (let i = 0; i < buf.length; i++) sum += buf[i];
        const level = sum / buf.length / 255;
        const target = pid === selfPid ? selfMeter : peers.get(pid);
        if (target){
          const now = level > 0.045 && !(pid === selfPid && muted);
          if (now !== target.speaking){ target.speaking = now; onChange(); }
        }
        requestAnimationFrame(tick);
      };
      tick();
    } catch (e){ /* metering is decoration; never let it break the call */ }
  }
  let selfMeter = { speaking: false };

  function speakingSet(){
    const out = {};
    if (enabled && selfMeter.speaking) out[selfPid] = true;
    peers.forEach((e, pid) => { if (e.speaking) out[pid] = true; });
    return out;
  }

  return {
    init(opts){ send = opts.send; selfPid = opts.pid; onChange = opts.onChange || (() => {}); },
    setPid(pid){ selfPid = pid; },
    enable, disable, toggle, setMuted, signal, sync, speakingSet,
    get enabled(){ return enabled; },
    get muted(){ return muted; },
    get peerCount(){ return peers.size; }
  };
})();
