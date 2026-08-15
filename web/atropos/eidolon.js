"use strict";
/* ===========================================================================
   EIDOLON - turning a photo into a character

   Greek "eidolon": a likeness, an image of a person. You give it a photo and
   it gives you back a cartoon of yourself - a cel-shaded face plus the three
   colours that dress the rest of the body.

   Everything happens on the player's own device. No upload, no server, no
   model: the photo never leaves the phone, only the small stylised thumbnail
   the other players need in order to recognise you does.
   =========================================================================== */

const Eidolon = (() => {

  const FACE_SIZE = 128;      // what everyone else receives
  const WORK_SIZE = 256;      // what we style at, before downscaling

  /* ---------------------------------------------------------------------
     Colour helpers
     --------------------------------------------------------------------- */
  const clamp255 = (v) => v < 0 ? 0 : v > 255 ? 255 : v;
  const hex = (r, g, b) =>
    "#" + [r, g, b].map(v => clamp255(Math.round(v)).toString(16).padStart(2, "0")).join("");

  function rgbToHsl(r, g, b){
    r /= 255; g /= 255; b /= 255;
    const max = Math.max(r, g, b), min = Math.min(r, g, b);
    let h = 0, s = 0;
    const l = (max + min) / 2;
    const d = max - min;
    if (d){
      s = l > 0.5 ? d / (2 - max - min) : d / (max + min);
      if (max === r)      h = ((g - b) / d + (g < b ? 6 : 0)) / 6;
      else if (max === g) h = ((b - r) / d + 2) / 6;
      else                h = ((r - g) / d + 4) / 6;
    }
    return [h, s, l];
  }

  function hslToRgb(h, s, l){
    if (!s) { const v = l * 255; return [v, v, v]; }
    const q = l < 0.5 ? l * (1 + s) : l + s - l * s;
    const p = 2 * l - q;
    const f = (t) => {
      if (t < 0) t += 1;
      if (t > 1) t -= 1;
      if (t < 1/6) return p + (q - p) * 6 * t;
      if (t < 1/2) return q;
      if (t < 2/3) return p + (q - p) * (2/3 - t) * 6;
      return p;
    };
    return [f(h + 1/3) * 255, f(h) * 255, f(h - 1/3) * 255];
  }

  /* ---------------------------------------------------------------------
     The cartoon pass

     Three things together sell "drawn" rather than "photo pasted on a head":
     saturation lifted, luminance quantised into a few flat bands, and a dark
     line laid in wherever the image changes fast.
     --------------------------------------------------------------------- */
  function stylise(ctx, size, strength){
    const img = ctx.getImageData(0, 0, size, size);
    const d = img.data;
    const bands = strength >= 2 ? 4 : 6;          // fewer bands = flatter, more graphic
    const boost = strength >= 2 ? 1.55 : 1.32;

    // Luminance copy first, so edge detection is not affected by our own edits.
    const lum = new Float32Array(size * size);
    for (let i = 0, p = 0; i < d.length; i += 4, p++){
      lum[p] = (d[i] * 0.299 + d[i+1] * 0.587 + d[i+2] * 0.114) / 255;
    }

    for (let i = 0, p = 0; i < d.length; i += 4, p++){
      let [h, s, l] = rgbToHsl(d[i], d[i+1], d[i+2]);

      s = Math.min(1, s * boost);
      l = Math.round(l * bands) / bands;          // flat bands of tone
      l = 0.10 + l * 0.86;                        // keep it off pure black and white

      let [r, g, b] = hslToRgb(h, s, l);

      // Sobel-lite: compare against the pixel right and below for a cheap edge.
      const x = p % size, y = (p / size) | 0;
      if (x < size - 1 && y < size - 1){
        const gx = Math.abs(lum[p] - lum[p + 1]);
        const gy = Math.abs(lum[p] - lum[p + size]);
        const edge = Math.min(1, (gx + gy) * 3.2);
        if (edge > 0.35){
          const ink = 1 - edge * 0.75;
          r *= ink; g *= ink; b *= ink;
        }
      }

      d[i] = clamp255(r); d[i+1] = clamp255(g); d[i+2] = clamp255(b);
    }
    ctx.putImageData(img, 0, 0);
  }

  /* Average a region, ignoring pixels outside the circular face crop. */
  function sample(ctx, size, x0, y0, x1, y1){
    const w = Math.max(1, Math.round(x1 - x0));
    const h = Math.max(1, Math.round(y1 - y0));
    const d = ctx.getImageData(Math.round(x0), Math.round(y0), w, h).data;
    let r = 0, g = 0, b = 0, n = 0;
    for (let i = 0; i < d.length; i += 4){
      if (d[i+3] < 128) continue;                 // transparent corner, skip
      r += d[i]; g += d[i+1]; b += d[i+2]; n++;
    }
    if (!n) return [200, 170, 150];
    return [r/n, g/n, b/n];
  }

  /* ---------------------------------------------------------------------
     Build the face texture and pull the body colours out of it
     --------------------------------------------------------------------- */
  function render(image, opts){
    const { zoom = 1, offsetX = 0, offsetY = 0, strength = 2 } = opts || {};

    const work = document.createElement("canvas");
    work.width = work.height = WORK_SIZE;
    const ctx = work.getContext("2d", { willReadFrequently: true });

    // Cover-fit the photo into the square, then apply the player's framing.
    const scale = (WORK_SIZE / Math.min(image.width, image.height)) * zoom;
    const dw = image.width * scale;
    const dh = image.height * scale;
    const dx = (WORK_SIZE - dw) / 2 + offsetX * WORK_SIZE;
    const dy = (WORK_SIZE - dh) / 2 + offsetY * WORK_SIZE;

    ctx.fillStyle = "#f2e9dc";
    ctx.fillRect(0, 0, WORK_SIZE, WORK_SIZE);
    ctx.drawImage(image, dx, dy, dw, dh);

    stylise(ctx, WORK_SIZE, strength);

    // Colours are read before the circular mask, from where each thing lives:
    // cheeks for skin, the top strip for hair, the bottom strip for clothing.
    const S = WORK_SIZE;
    const skinPx  = sample(ctx, S, S*0.30, S*0.52, S*0.70, S*0.68);
    const hairPx  = sample(ctx, S, S*0.28, S*0.04, S*0.72, S*0.20);
    const shirtPx = sample(ctx, S, S*0.18, S*0.88, S*0.82, S*1.00);

    // Nudge each toward something a cartoon would actually use.
    const skin  = punch(skinPx,  0.30, 0.62);
    const hair  = punch(hairPx,  0.45, 0.28);
    const shirt = punch(shirtPx, 0.62, 0.55);

    // Circular crop with a soft edge, so the face sits on the head cleanly.
    const out = document.createElement("canvas");
    out.width = out.height = FACE_SIZE;
    const octx = out.getContext("2d");
    octx.save();
    octx.beginPath();
    octx.arc(FACE_SIZE/2, FACE_SIZE/2, FACE_SIZE/2 - 1, 0, Math.PI*2);
    octx.closePath();
    octx.clip();
    octx.drawImage(work, 0, 0, FACE_SIZE, FACE_SIZE);
    octx.restore();

    return {
      canvas: out,
      face: out.toDataURL("image/jpeg", 0.72),
      colors: { skin, hair, shirt }
    };
  }

  /* Push a sampled colour toward a usable cartoon version of itself. */
  function punch(rgb, minSat, targetLum){
    let [h, s, l] = rgbToHsl(rgb[0], rgb[1], rgb[2]);
    s = Math.max(minSat, Math.min(0.85, s * 1.35));
    l = l * 0.45 + targetLum * 0.55;
    const [r, g, b] = hslToRgb(h, s, Math.max(0.12, Math.min(0.88, l)));
    return hex(r, g, b);
  }

  /* ---------------------------------------------------------------------
     For players who would rather not use a photo at all
     --------------------------------------------------------------------- */
  const PRESET_SKIN  = ["#F2C9A0","#E0AC7E","#C68642","#8D5524","#5C3317","#FFDCB8"];
  const PRESET_HAIR  = ["#2B1B12","#5A3825","#A65E2E","#D9A441","#B33A3A","#3B5BA5","#2E7D5B","#8E5FA8"];
  const PRESET_SHIRT = ["#E05B4B","#3B82C4","#4CAF6E","#E8A33D","#8E5FA8","#E86FA8","#38B2AC","#F2F0E6"];

  function drawn(seedText, choice){
    const c = document.createElement("canvas");
    c.width = c.height = FACE_SIZE;
    const g = c.getContext("2d");
    const skin = choice.skin, hair = choice.hair;

    g.save();
    g.beginPath();
    g.arc(64, 64, 63, 0, Math.PI*2);
    g.closePath();
    g.clip();

    g.fillStyle = skin; g.fillRect(0, 0, 128, 128);

    // Hair as a cap across the top of the head.
    g.fillStyle = hair;
    g.beginPath();
    g.ellipse(64, 44, 52, 40, 0, 0, Math.PI*2);
    g.fill();
    g.beginPath();
    g.rect(12, 8, 104, 30);
    g.fill();

    // Eyes.
    g.fillStyle = "#2B2438";
    [46, 82].forEach(x => {
      g.beginPath(); g.ellipse(x, 70, 6, 7.5, 0, 0, Math.PI*2); g.fill();
    });
    g.fillStyle = "#FFFFFF";
    [46, 82].forEach(x => {
      g.beginPath(); g.ellipse(x + 2, 67, 2.2, 2.6, 0, 0, Math.PI*2); g.fill();
    });

    // Smile.
    g.strokeStyle = "#8A4A3A"; g.lineWidth = 4; g.lineCap = "round";
    g.beginPath(); g.arc(64, 88, 16, 0.22 * Math.PI, 0.78 * Math.PI); g.stroke();

    // Cheeks.
    g.fillStyle = "rgba(230,120,110,0.34)";
    [36, 92].forEach(x => { g.beginPath(); g.ellipse(x, 84, 9, 6, 0, 0, Math.PI*2); g.fill(); });

    g.restore();
    return {
      canvas: c,
      face: c.toDataURL("image/jpeg", 0.8),
      colors: { skin, hair, shirt: choice.shirt }
    };
  }

  function randomChoice(){
    const pick = (a) => a[Math.floor(Math.random() * a.length)];
    return { skin: pick(PRESET_SKIN), hair: pick(PRESET_HAIR), shirt: pick(PRESET_SHIRT) };
  }

  /* Read a File into an <img>, honouring orientation where the browser can. */
  function load(file){
    return new Promise((resolve, reject) => {
      if (!file || !/^image\//.test(file.type)) return reject(new Error("Not an image"));
      const url = URL.createObjectURL(file);
      const img = new Image();
      img.onload = () => { URL.revokeObjectURL(url); resolve(img); };
      img.onerror = () => { URL.revokeObjectURL(url); reject(new Error("Could not read that photo")); };
      img.src = url;
    });
  }

  return { render, drawn, randomChoice, load, PRESET_SKIN, PRESET_HAIR, PRESET_SHIRT, FACE_SIZE };
})();
