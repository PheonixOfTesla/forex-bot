"use strict";
/* ===========================================================================
   SOUND

   Everything is synthesised at runtime. No audio files, so nothing to
   download, nothing to license, and the whole game stays a handful of text
   files on a CDN.

   The bar is Nintendo: every press answers, every phase has a voice, and the
   island is never silent. Ambience is a wave bed with gulls over it; the
   interface speaks in short marimba-ish tones rather than beeps.

   Browsers refuse to start audio until the player touches the page, so
   everything routes through one context that is unlocked on first input.
   =========================================================================== */

const Sound = (() => {

  let ctx = null, master = null, ambientGain = null, uiGain = null;
  let on = true, started = false;
  let waveSource = null, gullTimer = null;
  let lastStep = 0;

  function ensure(){
    if (ctx) return ctx;
    const AC = window.AudioContext || window.webkitAudioContext;
    if (!AC) return null;
    ctx = new AC();
    master = ctx.createGain();
    master.gain.value = 0.8;
    master.connect(ctx.destination);

    ambientGain = ctx.createGain();
    ambientGain.gain.value = 0;          // faded in once the island loads
    ambientGain.connect(master);

    uiGain = ctx.createGain();
    uiGain.gain.value = 0.9;
    uiGain.connect(master);
    return ctx;
  }

  /* A short pitched tone. Triangle and sine read as wooden and warm rather
     than as a computer beep. */
  function tone({ freq = 440, type = "triangle", dur = 0.18, gain = 0.22,
                  delay = 0, sweep = null, dest = null }){
    if (!ensure() || !on) return;
    const t0 = ctx.currentTime + delay;
    const osc = ctx.createOscillator();
    const g = ctx.createGain();
    osc.type = type;
    osc.frequency.setValueAtTime(freq, t0);
    if (sweep) osc.frequency.exponentialRampToValueAtTime(Math.max(1, sweep), t0 + dur);
    // Fast attack, exponential tail: the shape of a struck object.
    g.gain.setValueAtTime(0.0001, t0);
    g.gain.exponentialRampToValueAtTime(gain, t0 + 0.008);
    g.gain.exponentialRampToValueAtTime(0.0001, t0 + dur);
    osc.connect(g).connect(dest || uiGain);
    osc.start(t0); osc.stop(t0 + dur + 0.04);
  }

  /* Filtered noise: footsteps, surf, the pull of water. */
  function noise({ dur = 0.3, gain = 0.2, freq = 1200, q = 1,
                   type = "bandpass", delay = 0, sweep = null, dest = null }){
    if (!ensure() || !on) return;
    const t0 = ctx.currentTime + delay;
    const len = Math.max(1, Math.ceil(ctx.sampleRate * dur));
    const buf = ctx.createBuffer(1, len, ctx.sampleRate);
    const data = buf.getChannelData(0);
    for (let i = 0; i < len; i++) data[i] = (Math.random() * 2 - 1) * (1 - i / len);
    const src = ctx.createBufferSource();
    src.buffer = buf;
    const filter = ctx.createBiquadFilter();
    filter.type = type;
    filter.frequency.setValueAtTime(freq, t0);
    if (sweep) filter.frequency.exponentialRampToValueAtTime(Math.max(40, sweep), t0 + dur);
    filter.Q.value = q;
    const g = ctx.createGain();
    g.gain.setValueAtTime(gain, t0);
    g.gain.exponentialRampToValueAtTime(0.0001, t0 + dur);
    src.connect(filter).connect(g).connect(dest || uiGain);
    src.start(t0);
  }

  /* ---------------------------------------------------------------------
     Island ambience: surf that never quite repeats, and gulls
     --------------------------------------------------------------------- */
  function startAmbient(){
    if (!ensure() || waveSource) return;

    // Two seconds of brown-ish noise, looped through a slow filter sweep, is
    // enough to read as surf without ever sounding like a loop.
    const len = ctx.sampleRate * 2;
    const buf = ctx.createBuffer(1, len, ctx.sampleRate);
    const d = buf.getChannelData(0);
    let last = 0;
    for (let i = 0; i < len; i++){
      const white = Math.random() * 2 - 1;
      last = (last + 0.02 * white) / 1.02;
      d[i] = last * 3.2;
    }
    waveSource = ctx.createBufferSource();
    waveSource.buffer = buf;
    waveSource.loop = true;

    const surf = ctx.createBiquadFilter();
    surf.type = "lowpass";
    surf.frequency.value = 520;
    surf.Q.value = 0.6;

    // The swell: a very slow LFO opening and closing the filter, so waves
    // arrive rather than hum.
    const lfo = ctx.createOscillator();
    lfo.frequency.value = 0.085;
    const lfoGain = ctx.createGain();
    lfoGain.gain.value = 260;
    lfo.connect(lfoGain).connect(surf.frequency);
    lfo.start();

    waveSource.connect(surf).connect(ambientGain);
    waveSource.start();
    ambientGain.gain.linearRampToValueAtTime(0.30, ctx.currentTime + 3);

    scheduleGull();
  }

  function scheduleGull(){
    clearTimeout(gullTimer);
    gullTimer = setTimeout(() => {
      if (on && ctx){
        // Two falling cries, the second quieter, panned off to one side.
        const base = 900 + Math.random() * 500;
        tone({ freq: base, type: "sine", dur: 0.22, gain: 0.05,
               sweep: base * 0.55, dest: ambientGain });
        tone({ freq: base * 0.94, type: "sine", dur: 0.18, gain: 0.032,
               sweep: base * 0.5, delay: 0.26, dest: ambientGain });
      }
      scheduleGull();
    }, 6000 + Math.random() * 12000);
  }

  return {
    unlock(){
      if (!ensure()) return;
      if (ctx.state === "suspended") ctx.resume();
      if (!started){ started = true; startAmbient(); }
    },
    toggle(){
      on = !on;
      if (master) master.gain.linearRampToValueAtTime(on ? 0.8 : 0, ctx.currentTime + 0.25);
      return on;
    },
    get enabled(){ return on; },

    /* --- interface ---------------------------------------------------- */
    tap(){ tone({ freq: 620, dur: 0.07, gain: 0.14 }); },
    confirm(){ tone({ freq: 523, dur: 0.11, gain: 0.2 });
               tone({ freq: 784, dur: 0.16, gain: 0.18, delay: 0.07 }); },
    back(){ tone({ freq: 400, dur: 0.1, gain: 0.14, sweep: 280 }); },
    deny(){ tone({ freq: 180, type: "square", dur: 0.13, gain: 0.1 }); },

    /* --- people ------------------------------------------------------- */
    join(){ tone({ freq: 660, dur: 0.12, gain: 0.16 });
            tone({ freq: 880, dur: 0.18, gain: 0.14, delay: 0.09 }); },
    leave(){ tone({ freq: 520, dur: 0.16, gain: 0.12, sweep: 330 }); },

    /* A soft sandy scuff, alternating pitch so it reads as left then right. */
    /* Footsteps at the pace you are actually going.

       A fixed interval was fine when there was one speed. Now that the walk
       accelerates, a stride that does not keep up with the legs is worse than
       none - so the gap scales with how fast the character is moving, and the
       step lands a little heavier at a run. */
    step(speed){
      const s = Math.max(0.25, Math.min(1, (speed === undefined ? 1 : speed / 6.2)));
      const gap = 400 - s * 150;
      const now = performance.now();
      if (now - lastStep < gap) return;
      lastStep = now;
      noise({ dur: 0.09, gain: 0.035 + s * 0.03, freq: 900 + (Math.random() * 500),
              q: 0.9, type: "bandpass", dest: ambientGain });
    },

    /* --- the game ----------------------------------------------------- */
    nightfall(){
      // Low, wide, and a little uneasy without being a horror sting.
      tone({ freq: 174, type: "sine", dur: 1.9, gain: 0.2 });
      tone({ freq: 261, type: "sine", dur: 1.4, gain: 0.1, delay: 0.05 });
      noise({ dur: 1.6, gain: 0.05, freq: 400, q: 0.7, type: "lowpass", sweep: 160 });
    },
    gathering(){
      // Bright, rising, a bell calling everyone to the square.
      [523, 659, 784].forEach((f, i) =>
        tone({ freq: f, type: "triangle", dur: 1.0, gain: 0.16, delay: i * 0.1 }));
    },
    /* The pull: water dragging down, then it is gone. */
    cut(){
      noise({ dur: 0.85, gain: 0.3, freq: 1800, q: 0.9, type: "lowpass", sweep: 130 });
      tone({ freq: 150, type: "sine", dur: 1.2, gain: 0.32, sweep: 42, delay: 0.05 });
      tone({ freq: 300, type: "sine", dur: 0.5, gain: 0.1, sweep: 90 });
    },
    /* Forty seconds: a heartbeat that tightens as it runs out. */
    heart(fraction){
      tone({ freq: 62, type: "sine", dur: 0.16, gain: 0.34, sweep: 38 });
      tone({ freq: 55, type: "sine", dur: 0.2, gain: 0.22, sweep: 33, delay: 0.17 });
    },
    verdict(){
      noise({ dur: 0.2, gain: 0.24, freq: 300, q: 1.2 });
      tone({ freq: 98, type: "sine", dur: 0.8, gain: 0.24, sweep: 55 });
    },
    vote(){ tone({ freq: 740, dur: 0.09, gain: 0.15 }); },
    win(good){
      const notes = good ? [523, 659, 784, 1047] : [440, 392, 330, 262];
      notes.forEach((f, i) =>
        tone({ freq: f, type: "triangle", dur: 1.1, gain: 0.2, delay: i * 0.14 }));
    },
    /* --- voice -------------------------------------------------------- */
    micOn(){ tone({ freq: 700, dur: 0.09, gain: 0.16 });
             tone({ freq: 1050, dur: 0.12, gain: 0.13, delay: 0.07 }); },
    micOff(){ tone({ freq: 700, dur: 0.09, gain: 0.13, sweep: 420 }); }
  };
})();
