"use strict";
/* ===========================================================================
   THE VILLAGE - a sunlit Greek island you can walk around

   Everything here is generated at runtime: no models, no textures, no assets
   to download. Characters are built from spheres and cylinders in a toon
   material, the island is scattered procedurally from a seeded shuffle so
   every player sees the same village, and shadows are cheap painted blobs
   rather than real shadow maps.
   =========================================================================== */

const Village = (() => {

  const SKY_TOP   = 0x5FA8DC;
  const SKY_BOT   = 0xA6CFE6;
  const SEA       = 0x3F7FA8;
  const SAND      = 0xD9C88C;
  const GRASS     = 0x9FAA5C;
  // Knocked down from 0xC9BE92. Warm pale stone under a midday sun is a warm
  // pale stone; under a low orange one it goes to near-white and the square
  // becomes the brightest thing on the island, which is not where anyone is
  // meant to be looking.
  const PLAZA     = 0xA1977A;
  const WHITEWASH = 0xE8E0CE;
  const DOME      = 0x2E6FA8;
  const TERRA     = 0xCF6A47;
  const TRUNK     = 0x7A5636;
  const LEAF      = 0x5E8442;
  const GOLD      = 0xE8A33D;

  /* Three places to play, and no daylight in any of them.

     A social deduction game is about a village after dark. Noon lighting was
     fighting the premise: flat overhead sun, no shadows worth the name, and
     nothing on the island that could be described as atmosphere. Each map is
     now a different hour of the evening, which also does the job the three
     maps were supposed to do - they no longer look like the same island with
     the trees moved around.

         village  sunset      low orange sun, shadows raked across the square
         grove    twilight    blue hour under the canopy, lanterns and fireflies
         bay      night       moon over the water, stars, no sun at all

     Same rules everywhere; only the scenery and the light change. Each is
     seeded, so every device builds the identical world. */
  const MAPS = {
    village: {
      name: "Molua Village",
      hour: "sunset",
      sky:  [0x27407A, 0xF2874A],        // deep blue overhead, fire at the horizon
      glow: [0xFFC070, 1.0],             // bloom around the sun's bearing
      stars: 0.0,
      cloud: 0xFFC38A,                   // clouds catch the low sun, not white
      fog:  [0x8A6A72, 30, 104],
      // Low and warm. y well under x/z is what rakes the shadows out sideways.
      // Low enough that the shadows rake right across the square. Elevation
      // is about ten degrees; any higher and it is just a warm afternoon.
      sun:  [0xFF9440, 1.45, [26, 13, 15]],
      sky_light: [0x4C5A9C, 0x3A2A22, 0.26],
      rim:  [0xFF8A4A, 0.42],
      water: 0x6E5262,
      // Exposure is the whole difference between an evening and a bright
      // day with orange fog. ACES rolls the highlights off, so pulling it
      // down darkens the ground without flattening the sky.
      exposure: 0.78,
      lamp: 0.9,                        // how lit the windows and lanterns are
      fireflies: 0,
      ground: "grass", ring: "dirt", relief: 1.0,
      houses: 14, trees: 26, palms: 0, rocks: 4, ferns: 0
    },
    grove: {
      name: "Kanu Grove",
      hour: "twilight",
      sky:  [0x141C46, 0x4A4E86],
      glow: [0x8E7ACC, 0.55],
      stars: 0.35,
      cloud: 0x6E6AA0,
      fog:  [0x2E3358, 18, 70],          // closer fog: you cannot see far in a grove
      sun:  [0x8FA4E0, 0.40, [12, 14, -22]],
      sky_light: [0x2E3A72, 0x16121E, 0.26],
      rim:  [0x8CA8E8, 0.34],
      water: 0x232C50,
      exposure: 0.62,
      lamp: 1.15,
      fireflies: 90,
      ground: "grass", ring: "dirt", relief: 1.35,
      houses: 4, trees: 60, palms: 6, rocks: 12, ferns: 40
    },
    bay: {
      name: "Halehua Bay",
      hour: "night",
      sky:  [0x070C24, 0x1B2E52],
      glow: [0xBFD4F2, 0.85],            // the moon, not the sun
      stars: 1.0,
      cloud: 0x35496E,
      fog:  [0x0E182F, 32, 104],         // open water, but the dark eats it
      sun:  [0xAFC6F0, 0.38, [22, 24, 20]],
      sky_light: [0x1C2A55, 0x090C18, 0.24],
      rim:  [0xBCD2F6, 0.40],
      water: 0x10203E,
      exposure: 0.54,
      lamp: 1.2,
      fireflies: 0,
      ground: "sand", ring: "sand", relief: 0.55,
      houses: 8, trees: 6, palms: 22, rocks: 8, ferns: 0
    }
  };
  let MAP = MAPS.village;

  const ISLAND_RADIUS  = 30;
  const VILLAGE_RADIUS = 26;

  let renderer, scene, camera, sun, hemi, rim;
  let toonGradient = null;
  let avatars = new Map();       // pid -> rig
  let clock = 0;
  let quality = 1, fpsAvg = 60, lastFrame = performance.now();
  /* Third person, Fortnite shape: close behind the shoulder rather than a
     drone eleven metres up. The old framing put the character small and
     central in a wide establishing shot - fine for looking at an island,
     wrong for being a person standing on one. Close in, pitch almost level,
     and the body offset off-centre so the view ahead stays clear. */
  /* Distance is arithmetic, not taste. An Islander is about 2.8 units tall
     and the lens is 58 degrees vertical, so the visible height at distance D
     is 2*D*tan(29deg) = 1.109*D. For a character to fill the ~30% of a
     portrait screen a third-person mobile game gives it:

         2.8 / (1.109 * D) = 0.30   ->   D = 8.4

     Five was a face full of the back of your own head; eleven was a drone
     shot. Aiming a little above centre pushes the body down the frame and
     leaves the ground ahead visible, which is what you actually steer by. */
  /* A Sims angle at a playable distance.

     The tilted-down orbit is right - this is a game about watching a room
     full of people, not about aiming at something. The distance was not.
     Fourteen units put an Islander at 19% of screen height, which is a wide
     establishing shot of an island with a person somewhere in it, and the
     first thing anybody said about it was that they could not find
     themselves.

     Distance is arithmetic. An Islander is 2.95 units tall and the lens is 58
     degrees vertical, so the visible height at distance D is
     2*D*tan(29 deg) = 1.109*D:

         9.0  ->  character 30% of screen height   (third-person standard)
         14.0 ->  19%                              (what it was)

     Thirty per cent is where Fortnite, Fall Guys and every other third-person
     game of this shape sit, and it still shows the whole square. Zooming out
     to the old framing is one scroll away; the default should not need one.

     The aim point matters as much as the distance. lookAt puts the target
     dead centre, so aiming at 1.45 - half of 2.95 - centres the body rather
     than the feet. And the shoulder offset stays at zero: off-centring the
     subject is how you leave room for what a character is aiming at, and this
     character is not aiming at anything. */
  /* Pitch came down with the distance. At 0.52 the camera is looking at the
     ground: the frame is nine parts paving to one part anything else, and on
     an island whose whole point is now the colour of its sky, none of that
     sky was ever on screen. 0.44 still reads as looking down on a square and
     puts the horizon in the top third where it belongs. */
  let camYaw = 0, camPitch = 0.44, camDist = 9.0;
  const SHOULDER = 0.0;
  const ISLANDER_H = 2.95;
  const EYE_HEIGHT = ISLANDER_H * 0.49;   // mid-body, so the figure sits centred
  let followPid = null;
  let shakeAmount = 0, flashAmount = 0;
  let flashColor = { r: 1, g: 0.3, b: 0.25 };
  const flashOverlay = { mesh: null };

  /* A deterministic shuffle so every device builds the identical island. */
  function seeded(seed){
    let s = seed >>> 0;
    return () => {
      s = (s * 1664525 + 1013904223) >>> 0;
      return s / 4294967296;
    };
  }

  /* ------------------------------------------------------------------
     Textures

     The single biggest thing separating a low-poly toy from Hyrule Field is
     that the console textured everything. These are drawn on canvases at 64px
     and tiled hard, then point-sampled up close and mipmapped in the distance,
     which is exactly what the hardware did.
     ------------------------------------------------------------------ */
  const texCache = {};
  let maxAniso = 4;

  /* A height field read off the drawn canvas, turned into a tangent-space
     normal map. This is what was missing: every ground surface was drawn as
     flat colour, so the sun could not catch anything and grass, sand and
     stone all lit identically no matter what was painted on them. Deriving
     the relief from the same canvas costs one pass at load and means a
     texture only has to be drawn once to get both its colour and its bumps. */
  function normalFrom(canvas, strength){
    const S = canvas.width;
    const src = canvas.getContext("2d").getImageData(0, 0, S, S).data;
    const h = new Float32Array(S * S);
    for (let i = 0; i < S * S; i++){
      h[i] = (src[i*4] * 0.299 + src[i*4+1] * 0.587 + src[i*4+2] * 0.114) / 255;
    }
    // Wrapped sampling, so the relief tiles as seamlessly as the colour does.
    const at = (x, y) => h[((y % S) + S) % S * S + (((x % S) + S) % S)];
    const out = new Uint8Array(S * S * 3);
    for (let y = 0; y < S; y++){
      for (let x = 0; x < S; x++){
        const dx = (at(x + 1, y) - at(x - 1, y)) * strength;
        const dy = (at(x, y + 1) - at(x, y - 1)) * strength;
        const len = Math.sqrt(dx*dx + dy*dy + 1);
        const i = (y * S + x) * 3;
        out[i]     = (-dx / len * 0.5 + 0.5) * 255;
        out[i + 1] = ( dy / len * 0.5 + 0.5) * 255;
        out[i + 2] = (  1 / len * 0.5 + 0.5) * 255;
      }
    }
    const t = new THREE.DataTexture(out, S, S, THREE.RGBFormat);
    t.wrapS = t.wrapT = THREE.RepeatWrapping;
    t.magFilter = THREE.LinearFilter;
    t.minFilter = THREE.LinearMipmapLinearFilter;
    t.generateMipmaps = true;
    t.needsUpdate = true;
    return t;
  }

  function makeTex(key, draw, repeat, bump){
    if (texCache[key]) return texCache[key];
    // 512, not 256. Measured budget was 31k triangles and 18 textures for a
    // whole village, so the resolution was a habit rather than a limit.
    const size = 512;
    const c = document.createElement("canvas");
    c.width = c.height = size;
    draw(c.getContext("2d"), size);
    const t = new THREE.CanvasTexture(c);
    t.encoding = THREE.sRGBEncoding;     // colour, not data
    t.wrapS = t.wrapT = THREE.RepeatWrapping;
    // Smooth filtering both ways, and anisotropy so ground textures stay
    // legible at a grazing angle instead of smearing into mush.
    t.magFilter = THREE.LinearFilter;
    t.minFilter = THREE.LinearMipmapLinearFilter;
    t.anisotropy = maxAniso;
    t.repeat.set(repeat || 1, repeat || 1);
    if (bump){
      const n = normalFrom(c, bump);
      n.anisotropy = maxAniso;
      n.repeat.copy(t.repeat);
      // three r128's Texture has no userData of its own, so make one.
      t.userData = t.userData || {};
      t.userData.normal = n;
    }
    texCache[key] = t;
    return t;
  }

  /* Fine grain. Still useful as a top layer, but on its own it is coloured
     static - it was doing the whole job for grass, sand, dirt, stone and
     plaster alike, which is why they all read as the same surface in
     different colours. */
  function grain(g, S, spots, density){
    for (let i = 0; i < density; i++){
      g.fillStyle = spots[(Math.random() * spots.length) | 0];
      g.fillRect(Math.random() * S, Math.random() * S,
                 1 + Math.random() * 3, 1 + Math.random() * 2);
    }
  }

  /* No macro blotches anywhere any more, and the helper that drew them is
     gone with them. It was meant to break up a repeating tile at a scale
     larger than the eye can pair up, and it did the opposite everywhere it
     was used: at the repeat counts a ground texture actually needs, four or
     five soft clouds per tile land every metre or two and become the
     pattern. Variation has to be finer than the repeat, not coarser. */

  const TEX = {
    /* Blades, not noise. Short tapered strokes at varying angles, in tufts. */
    grass: () => makeTex("grass", (g, S) => {
      g.fillStyle = "#6E8F3C"; g.fillRect(0, 0, S, S);
      /* No macro patches, and this is the same lesson the plaza already
         taught. Seven soft blotches across a tile look like natural variation
         in the tile and like a repeating pattern in the field, because at
         twenty-four repeats they land every two and a half metres. Under a
         low sun the normal map made of those blotches lit one side of each
         and shaded the other, and the lawn came out as a diamond
         checkerboard. Variation has to come from something too small to pair
         up across a repeat - which is what the blades are for. */
      g.lineCap = "round";
      for (let i = 0; i < 2600; i++){
        const x = Math.random() * S, y = Math.random() * S;
        const a = -Math.PI/2 + (Math.random() - 0.5) * 1.5;
        const len = 2 + Math.random() * 6;
        g.strokeStyle = ["#7FA349","#8CB254","#5D7B33","#4F6B2C","#93B85E",
                         "#6B8F3E","#A0C46A"][(Math.random()*7)|0];
        g.lineWidth = 0.8 + Math.random() * 1.2;
        g.beginPath();
        g.moveTo(x, y);
        g.lineTo(x + Math.cos(a) * len, y + Math.sin(a) * len);
        g.stroke();
      }
      // Clumps: a handful of tighter tufts, small enough that the eye cannot
      // match one against its neighbour a tile away.
      for (let i = 0; i < 90; i++){
        const cx = Math.random() * S, cy = Math.random() * S;
        const tone = ["#88B054","#587A32"][(Math.random()*2)|0];
        for (let k = 0; k < 14; k++){
          const a = -Math.PI/2 + (Math.random() - 0.5) * 1.9;
          const len = 3 + Math.random() * 5;
          const x = cx + (Math.random()-0.5) * 11, y = cy + (Math.random()-0.5) * 11;
          g.strokeStyle = tone; g.lineWidth = 1.0;
          g.beginPath(); g.moveTo(x, y);
          g.lineTo(x + Math.cos(a) * len, y + Math.sin(a) * len); g.stroke();
        }
      }
      // Bump kept low for the same reason. Relief off a blade drawing is
      // fine; relief off a cloud is a hillside that is not there.
    }, 24, 0.85),

    /* Trodden earth: compacted patches, loose clods, small stones. */
    dirt: () => makeTex("dirt", (g, S) => {
      g.fillStyle = "#B39B63"; g.fillRect(0, 0, S, S);
      // No macro blotches. Same story as the grass and the plaza: at ten
      // repeats four soft clouds stop being variation and start being the
      // pattern. Clods and stones carry it instead.
      for (let i = 0; i < 320; i++){
        const x = Math.random() * S, y = Math.random() * S;
        const r = 1.5 + Math.random() * 4;
        g.fillStyle = ["#9C8452","#8E7848","#CBB682"][(Math.random()*3)|0];
        g.beginPath(); g.ellipse(x, y, r, r * 0.7, Math.random() * 3, 0, Math.PI*2); g.fill();
      }
      grain(g, S, ["#C4AC73","#9C8452"], 1200);
    }, 10, 2.0),

    /* Wind ripples are what makes sand read as sand rather than as beige
       noise - the grain alone could be any powder. */
    sand: () => makeTex("sand", (g, S) => {
      g.fillStyle = "#D9C88C"; g.fillRect(0, 0, S, S);
      // The ripples are the variation. Blotches on top of them repeated every
      // metre and a half across the whole bay.
      g.lineWidth = 2.2; g.lineCap = "round";
      for (let y = 0; y < S; y += 9){
        g.strokeStyle = (y / 9) % 2 ? "rgba(196,176,120,.42)" : "rgba(236,224,180,.40)";
        g.beginPath();
        for (let x = 0; x <= S; x += 8){
          const yy = y + Math.sin((x / S) * Math.PI * 4 + y * 0.11) * 3.2;
          x === 0 ? g.moveTo(x, yy) : g.lineTo(x, yy);
        }
        g.stroke();
      }
      grain(g, S, ["#EBDCA8","#C8B478"], 2400);
    }, 20, 1.6),

    /* Flagstones with mortar between them, which is a pattern the eye can
       actually latch onto at ground level. */
    stone: () => makeTex("stone", (g, S) => {
      g.fillStyle = "#B0A992"; g.fillRect(0, 0, S, S);       // mortar
      const N = 5, cell = S / N;
      for (let ry = 0; ry < N; ry++){
        for (let rx = 0; rx < N; rx++){
          const off = (ry % 2) * cell * 0.5;                  // running bond
          const x = rx * cell + off, y = ry * cell;
          const pad = 2 + Math.random();
          // Stones close in tone on purpose. Wide per-stone variance looked
          // richer in a single tile and made the tiling obvious the moment it
          // repeated: the eye cannot see a grid, but it will happily match a
          // memorable arrangement of light and dark blocks across a plaza.
          g.fillStyle = ["#C8C1AE","#CCC5B2","#C2BBA8","#CEC7B5"][(Math.random()*4)|0];
          const w = cell - pad * 2, h = cell - pad * 2;
          for (const ox of [0, S]){
            g.beginPath();
            g.roundRect ? g.roundRect(x + pad - ox, y + pad, w, h, 3)
                        : g.rect(x + pad - ox, y + pad, w, h);
            g.fill();
          }
        }
      }
      // No macro patches here. They break up a tile that repeats a handful of
      // times; at the seven repeats a plaza needs, four big blobs *become* the
      // pattern - the plaza came out as a giant light-and-dark checkerboard,
      // which is the exact artefact patches exist to prevent.
      grain(g, S, ["#D2CCBC","#B8B0A0"], 1300);
    }, 7, 1.5),

    /* Lime render on a wall.

       The old one opened with five blotches four-tenths of a tile wide and
       then took a normal map off them, at a repeat of two. On a three-metre
       wall that is two grey clouds and a relief map of two grey clouds, which
       is why the houses read as damp concrete rather than as painted plaster.

       What a rendered wall actually looks like at six metres is almost flat -
       an even tone, a fine tooth you can only see in raking light, and the
       occasional trowel edge. The interest belongs in the shapes and the
       trim, not in the paint. */
    plaster: () => makeTex("plaster", (g, S) => {
      g.fillStyle = "#EDE4D0"; g.fillRect(0, 0, S, S);
      // Trowel sweeps: long, shallow arcs a shade off the base, not clouds.
      g.lineCap = "round";
      for (let i = 0; i < 26; i++){
        const y = Math.random() * S;
        const sweep = 90 + Math.random() * 200;
        g.strokeStyle = Math.random() > 0.5 ? "rgba(228,217,196,.5)" : "rgba(246,240,226,.5)";
        g.lineWidth = 5 + Math.random() * 9;
        g.beginPath();
        g.moveTo(-20, y);
        g.quadraticCurveTo(sweep, y + (Math.random()-0.5) * 26, S + 20, y + (Math.random()-0.5) * 16);
        g.stroke();
      }
      // The tooth. Small, dense, low contrast: it is what the normal map
      // wants, and at this scale it never resolves into a pattern.
      for (let i = 0; i < 5200; i++){
        g.fillStyle = Math.random() > 0.5 ? "rgba(255,252,244,.42)" : "rgba(206,196,176,.34)";
        g.beginPath();
        g.arc(Math.random()*S, Math.random()*S, 0.6 + Math.random()*1.5, 0, Math.PI*2);
        g.fill();
      }
      // A handful of chips where the render has come away, warm underneath.
      for (let i = 0; i < 7; i++){
        g.fillStyle = "rgba(198,176,150,.30)";
        g.beginPath();
        g.ellipse(Math.random()*S, Math.random()*S, 4 + Math.random()*11,
                  3 + Math.random()*7, Math.random()*3, 0, Math.PI*2);
        g.fill();
      }
    }, 2, 0.45),

    /* Pantiles: half-round, laid in courses, each course lapping the one
       below. The lap line and the shadow under it are the whole read - flat
       rectangles in rows were giving a roof made of brick. */
    roof: () => makeTex("roof", (g,S)=>{
      g.fillStyle = "#8E3F2A"; g.fillRect(0,0,S,S);
      const course = 62, w = 44;
      for (let y = -course; y < S + course; y += course){
        for (let x = -w; x < S + w; x += w){
          const off = ((y / course) | 0) % 2 ? w * 0.5 : 0;
          const px = x + off;
          // The barrel of the tile, lit along its crown and shaded in the
          // valley between it and its neighbour.
          const grd = g.createLinearGradient(px, 0, px + w, 0);
          grd.addColorStop(0.00, "#8A3E29");
          grd.addColorStop(0.30, "#D0704F");
          grd.addColorStop(0.55, "#E08A62");
          grd.addColorStop(1.00, "#93452D");
          g.fillStyle = grd;
          g.beginPath();
          g.moveTo(px, y + course);
          g.lineTo(px, y + 16);
          g.quadraticCurveTo(px + w * 0.5, y - 8, px + w, y + 16);
          g.lineTo(px + w, y + course);
          g.closePath();
          g.fill();
        }
        // Shadow cast by the course above onto the head of this one.
        const sh = g.createLinearGradient(0, y, 0, y + 18);
        sh.addColorStop(0, "rgba(60,18,10,.55)");
        sh.addColorStop(1, "rgba(60,18,10,0)");
        g.fillStyle = sh; g.fillRect(0, y, S, 18);
      }
      // Weathering, so the courses do not read as printed.
      for (let i = 0; i < 900; i++){
        g.fillStyle = Math.random() > 0.5 ? "rgba(230,180,140,.18)" : "rgba(70,30,18,.16)";
        g.fillRect(Math.random()*S, Math.random()*S, 1 + Math.random()*4, 1 + Math.random()*3);
      }
    }, 3, 1.4),

    /* Bark, which is ridges and the shadows between them. Full-height stripes
       of flat colour gave a trunk that looked like a painted dowel. */
    bark: () => makeTex("bark", (g,S)=>{
      g.fillStyle = "#4A3320"; g.fillRect(0,0,S,S);          // the dark between
      // Ridges: tall tapered slabs that wander, each lit on one edge.
      for (let i = 0; i < 46; i++){
        const x = Math.random() * S;
        const w = 6 + Math.random() * 20;
        const light = ["#8A6742","#7A5A38","#96734C","#6B4E30"][(Math.random()*4)|0];
        g.beginPath();
        g.moveTo(x, -10);
        let cx = x;
        for (let y = -10; y < S + 10; y += 40){
          cx += (Math.random() - 0.5) * 9;
          g.lineTo(cx, y);
        }
        for (let y = S + 10; y > -10; y -= 40){
          cx += (Math.random() - 0.5) * 5;
          g.lineTo(cx + w, y);
        }
        g.closePath();
        g.fillStyle = light; g.fill();
        // A highlight down one side of the ridge and nothing down the other:
        // that asymmetry is what makes it read as round.
        g.strokeStyle = "rgba(190,158,116,.34)"; g.lineWidth = 1.6; g.stroke();
      }
      // Horizontal lenticels - the short pale dashes real bark has.
      for (let i = 0; i < 120; i++){
        g.fillStyle = "rgba(178,150,112,.30)";
        g.fillRect(Math.random()*S, Math.random()*S, 3 + Math.random()*10, 1.4);
      }
    }, 2, 1.5),

    /* Leaves, not green static.

       A speckle is the same at every scale, so a canopy made of it is a
       coloured ball however close you stand. Actual leaf shapes with sky
       showing through the gaps is the difference between a tree and a
       lollipop. */
    leaf: () => makeTex("leaf", (g,S)=>{
      g.fillStyle = "#2F4C1E"; g.fillRect(0,0,S,S);          // shade beneath
      const TONES = ["#6FA047","#5C8B39","#7DB152","#4C7A2E","#8CC061"];
      // Three passes dark to light. Later leaves sit on top of earlier ones,
      // which is how depth appears in a flat drawing.
      for (let pass = 0; pass < 3; pass++){
        const n = 340 - pass * 70;
        for (let i = 0; i < n; i++){
          const x = Math.random() * S, y = Math.random() * S;
          const a = Math.random() * Math.PI * 2;
          const L = (9 + Math.random() * 13) * (0.8 + pass * 0.14);
          g.save();
          g.translate(x, y); g.rotate(a);
          g.fillStyle = TONES[(Math.random() * TONES.length) | 0];
          g.globalAlpha = 0.72 + pass * 0.09;
          // A pointed oval: two arcs meeting at the tip and the stem.
          g.beginPath();
          g.moveTo(0, -L * 0.5);
          g.quadraticCurveTo(L * 0.34, 0, 0, L * 0.5);
          g.quadraticCurveTo(-L * 0.34, 0, 0, -L * 0.5);
          g.fill();
          // Midrib, one shade down. Tiny, but it stops the leaf reading as a
          // blob of paint when the camera comes close.
          g.globalAlpha *= 0.5;
          g.strokeStyle = "#385A24"; g.lineWidth = 0.9;
          g.beginPath(); g.moveTo(0, -L*0.44); g.lineTo(0, L*0.44); g.stroke();
          g.restore();
        }
      }
    }, 3, 1.0),
    water: () => makeTex("water", (g,S)=>{
      g.fillStyle = "#3F7FA8"; g.fillRect(0,0,S,S);
      for (let y = 0; y < S; y += 18){
        g.fillStyle = (y/18) % 2 ? "#4E8FB8" : "#356E93";
        g.fillRect(0, y, S, 7);
      }
    }, 40)
  };

  /* ------------------------------------------------------------------
     Materials
     ------------------------------------------------------------------ */
  function gradientMap(){
    if (toonGradient) return toonGradient;
    // Three flat steps of light: the whole cartoon look rests on this.
    const data = new Uint8Array([90, 90, 90, 175, 175, 175, 255, 255, 255]);
    const tex = new THREE.DataTexture(data, 3, 1, THREE.RGBFormat);
    tex.minFilter = tex.magFilter = THREE.NearestFilter;
    tex.generateMipmaps = false;
    tex.needsUpdate = true;
    toonGradient = tex;
    return tex;
  }

  /* N64 hardware did per-vertex Gouraud lighting with no specular, which is
     exactly what Lambert gives - and it has no flatShading option because
     per-vertex is already the model. The toon ramp read as modern cel
     shading; this reads as 1998. */
  /* Both of these are memoised, and that is not a micro-optimisation.

     Every call used to hand back a brand new material, so fourteen houses
     built fourteen separate copies of the same plaster and the batcher - which
     groups by material - found nothing in the world to group. Identical
     arguments now give back the identical material, which is both the correct
     thing and the thing that lets the whole village collapse into a handful
     of draw calls. Anything that wants to differ has to say so in the
     arguments rather than by editing the material afterwards. */
  const matCache = new Map();

  function toon(color, opts){
    const key = "t|" + color + "|" + (opts ? JSON.stringify(opts) : "");
    let m = matCache.get(key);
    if (!m){
      m = new THREE.MeshStandardMaterial(
        Object.assign({ color, roughness: 0.94, metalness: 0.0 }, opts || {}));
      matCache.set(key, m);
    }
    return m;
  }

  /* Textured surface. The colour still tints it, so one texture serves several
     materials without redrawing the canvas. */
  function surf(texFn, tint, bumpScale, opts){
    const key = "s|" + (texFn.name || texFn) + "|" + (tint || 0) + "|" + bumpScale +
                "|" + (opts ? JSON.stringify(opts) : "");
    let cached = matCache.get(key);
    if (cached) return cached;
    const map = texFn();
    const mat = new THREE.MeshStandardMaterial(
      Object.assign({ map, color: tint || 0xffffff, roughness: 0.95, metalness: 0.0 },
                    opts || {}));
    // The relief that came off the same canvas. Kept well under 1 - at full
    // strength procedural bumps read as crumpled foil rather than ground.
    if (map.userData && map.userData.normal){
      mat.normalMap = map.userData.normal;
      const k = bumpScale === undefined ? 0.55 : bumpScale;
      mat.normalScale = new THREE.Vector2(k, k);
    }
    matCache.set(key, mat);
    return mat;
  }

  /* ------------------------------------------------------------------
     Island
     ------------------------------------------------------------------ */
  /* Swap the world. Everything scenic lives in worldGroup so a map change is
     a clear-and-rebuild rather than a page reload, and players keep their
     socket, their Islander and their place in the lobby. */
  function applyMap(id){
    const next = MAPS[id] || MAPS.village;
    if (MAP === next && worldGroup.children.length) return;
    MAP = next;

    while (worldGroup.children.length){
      const child = worldGroup.children.pop();
      child.traverse(o => {
        if (o.geometry) o.geometry.dispose();
      });
      worldGroup.remove(child);
    }

    scene.fog = new THREE.Fog(MAP.fog[0], MAP.fog[1], MAP.fog[2]);
    renderer.setClearColor(MAP.fog[0], 1);
    hemi.color.setHex(MAP.sky_light[0]);
    hemi.groundColor.setHex(MAP.sky_light[1]);
    hemi.intensity = MAP.sky_light[2];
    sun.color.setHex(MAP.sun[0]);
    sun.intensity = MAP.sun[1];
    sun.position.set(MAP.sun[2][0], MAP.sun[2][1], MAP.sun[2][2]);
    rim.color.setHex(MAP.rim[0]);
    rim.intensity = MAP.rim[1];
    // A low sun rakes long shadows, and the default frustum clipped them off
    // partway across the square. Depth along the light's own axis is what
    // needs the room, so it scales with how shallow the light is.
    const sl = Math.hypot(MAP.sun[2][0], MAP.sun[2][1], MAP.sun[2][2]);
    sun.shadow.camera.far = sl + 80;
    sun.shadow.camera.updateProjectionMatrix();
    // ACES holds midtones down, which is right at noon and too dark at
    // midnight, so each hour carries its own exposure.
    renderer.toneMappingExposure = MAP.exposure || 1.15;
    fireflyPts = null;
    lanternBulbs.length = 0;
    blockers.length = 0;
    retintEnvironment();

    buildSky();
    buildIsland();
    scatter();
    buildMonument();
    buildHorizon();
    buildNightLights();
    bakeScenery();
  }

  function currentMap(){ return MAP.name; }

  /* The soft sheen along an arm or a cheek comes from a tiny generated
     environment, and that environment was hard-coded to a blue midday sky.
     Under a sunset it read as a cold light source nobody could see, and the
     characters looked cut out and dropped in. Rebuild it from the map's own
     sky and ground colours, then push it onto everything already built -
     materials captured the old texture, they do not follow a variable. */
  const ENV_RAMPS = {
    sunset:   ["#5A6FB4", "#C87A62", "#E0885A", "#5A4038"],
    twilight: ["#2E3C74", "#4A4E86", "#3A3450", "#1E1A28"],
    night:    ["#16243F", "#24365E", "#1E2A44", "#0E1220"]
  };
  function retintEnvironment(){
    if (!(window.Avatar && Avatar.environment)) return;
    const env = Avatar.environment(renderer, ENV_RAMPS[MAP.hour] || null);
    scene.traverse(o => {
      if (!o.isMesh) return;
      const mats = Array.isArray(o.material) ? o.material : [o.material];
      mats.forEach(m => {
        if (m && "envMap" in m && m.envMap){ m.envMap = env; m.needsUpdate = true; }
      });
    });
  }

  /* ------------------------------------------------------------------
     Terrain

     The island was a flat disc, and no amount of texture fixes that: Hyrule
     Field reads the way it does because the ground has shape, and shape is
     what gives you something to walk over, behind, and out of sight of.

     One pure function of x and z, with fixed constants, so every device
     raises the same hills without the server ever mentioning height. Ground
     mesh, props, players and camera all sample this and nothing else.

     Dead flat inside the plaza on purpose. The Gathering is an argument
     between people looking at each other, and it should not matter that one
     of them happens to be standing in a dip.
     ------------------------------------------------------------------ */
  const FLAT_TO   = 12.5;                 // the square, and a margin
  const COAST_AT  = ISLAND_RADIUS + 2;

  function terrainH(x, z){
    const d = Math.sqrt(x * x + z * z);
    const t = Math.max(0, Math.min(1, (d - FLAT_TO) / (COAST_AT - FLAT_TO)));
    // Zero at the plaza edge, zero again at the water: hills in between and
    // no cliff where the grass meets the sand.
    const ease = Math.sin(Math.PI * t);
    const h = Math.sin(x * 0.17 + 1.3) * Math.cos(z * 0.14 - 0.7) * 1.50
            + Math.sin(x * 0.31 - 2.1) * Math.cos(z * 0.29 + 1.9) * 0.60
            + Math.sin((x + z) * 0.085) * 0.85;
    // Biased so the field only ever rises. Centred on zero it cut troughs
    // three units deep, which is below the sea plane - the island filled with
    // water in every dip and you could see straight through the grass to it.
    return (h * 0.5 + 1.5) * ease * (MAP.relief === undefined ? 1 : MAP.relief);
  }

  /* A disc whose vertices follow the height field.

     RingGeometry rather than CircleGeometry: a circle is a triangle fan with
     a single ring of rim vertices, so there is nothing in between to lift.
     A ring takes a radial subdivision count, and its UVs are planar, so the
     textures tile exactly as they did on the flat version. */
  function groundDisc(radius, mat, baseY, rings){
    const geo = new THREE.RingGeometry(0.02, radius, 72, rings || 26);
    const pos = geo.attributes.position;
    for (let i = 0; i < pos.count; i++){
      // The mesh gets rotated -90 about X, which sends local (x,y,z) to world
      // (x, z, -y). So world z is -local y, and local z is the height.
      pos.setZ(i, terrainH(pos.getX(i), -pos.getY(i)));
    }
    pos.needsUpdate = true;
    geo.computeVertexNormals();          // or the hills light as if still flat
    const m = new THREE.Mesh(geo, mat);
    m.rotation.x = -Math.PI / 2;
    m.position.y = baseY;
    m.receiveShadow = true;
    return m;
  }

  /* The sky was drawing from two module constants and ignoring MAP.sky, which
     is why every island had the same blue overhead no matter which one you
     picked. It reads the map now, and carries the three things an evening sky
     needs that a noon one does not: a bloom around the sun's own bearing, the
     clouds tinted by that light instead of white, and stars. */
  function buildSky(){
    const geo = new THREE.SphereGeometry(180, 24, 16);
    const sd = new THREE.Vector3(MAP.sun[2][0], MAP.sun[2][1], MAP.sun[2][2]).normalize();
    const mat = new THREE.ShaderMaterial({
      side: THREE.BackSide, depthWrite: false, fog: false,
      uniforms: {
        top:    { value: new THREE.Color(MAP.sky[0]) },
        bottom: { value: new THREE.Color(MAP.sky[1]) },
        glow:   { value: new THREE.Color(MAP.glow[0]) },
        glowK:  { value: MAP.glow[1] },
        starK:  { value: MAP.stars },
        cloudC: { value: new THREE.Color(MAP.cloud) },
        sunDir: { value: sd }
      },
      vertexShader: `
        varying float vH;
        varying vec3 vDir;
        void main(){
          vec4 w = modelMatrix * vec4(position, 1.0);
          vDir = normalize(w.xyz);
          vH = vDir.y;
          gl_Position = projectionMatrix * viewMatrix * w;
        }`,
      fragmentShader: `
        varying float vH;
        varying vec3 vDir;
        uniform vec3 top; uniform vec3 bottom; uniform vec3 glow; uniform vec3 cloudC;
        uniform float glowK; uniform float starK; uniform vec3 sunDir;
        // Cheap value noise, enough for soft cloud banding.
        float hash(vec2 p){ return fract(sin(dot(p, vec2(41.3, 289.1))) * 43758.5453); }
        float hash3(vec3 p){ return fract(sin(dot(p, vec3(12.99, 78.23, 37.72))) * 43758.5453); }
        float noise(vec2 p){
          vec2 i = floor(p), f = fract(p);
          f = f * f * (3.0 - 2.0 * f);
          return mix(mix(hash(i), hash(i + vec2(1,0)), f.x),
                     mix(hash(i + vec2(0,1)), hash(i + vec2(1,1)), f.x), f.y);
        }
        void main(){
          // A wider gradient than the daylight one. At sunset the transition
          // from fire to deep blue is most of the sky, not a strip at the
          // bottom of it.
          float t = smoothstep(-0.06, 0.55, vH);
          vec3 sky = mix(bottom, top, t);
          vec3 d = normalize(vDir);

          // Stars first, so everything else lays over them. Quantising the
          // direction gives an even scatter that does not clump at the poles
          // the way a lat/long grid does.
          if (starK > 0.001){
            float s = hash3(floor(d * 240.0));
            float star = smoothstep(0.9971, 0.9998, s);
            // Only above the horizon, and dimmer where the sky is bright.
            sky += vec3(0.86, 0.90, 1.0) * star * starK
                 * smoothstep(0.0, 0.35, vH) * (1.0 - t * 0.25);
          }

          // The sun or moon, as a bloom around its own bearing. Two lobes: a
          // tight disc and a wide haze, which is what stops it reading as a
          // sticker pasted on the gradient.
          float sd = max(0.0, dot(d, normalize(sunDir)));
          sky += glow * glowK * (pow(sd, 220.0) * 0.9 + pow(sd, 9.0) * 0.42 + pow(sd, 2.0) * 0.14);

          // Clouds sit in a band above the horizon and fade out overhead, and
          // they are lit by whatever is in the sky rather than being white.
          vec2 uv = d.xz / max(0.18, d.y + 0.35) * 1.4;
          float n = noise(uv * 1.4) * 0.6 + noise(uv * 3.1) * 0.3 + noise(uv * 6.3) * 0.1;
          float cloud = smoothstep(0.50, 0.80, n) * smoothstep(0.01, 0.28, vH) * (1.0 - t * 0.40);
          // Underlit: the edge nearest the sun keeps its colour, the rest goes
          // to shadow. That contrast is the whole look of a sunset sky.
          vec3 lit = mix(cloudC * 0.42, cloudC, pow(sd, 1.6));
          gl_FragColor = vec4(mix(sky, lit, cloud * 0.8), 1.0);
        }`
    });
    worldGroup.add(new THREE.Mesh(geo, mat));
  }

  function buildIsland(){
    // Sea, out to the horizon.
    // Unlit on purpose - water wants to be its own colour rather than take a
    // shading pass - which means the map has to tint it by hand, or the sea
    // stays midday blue while the sky above it burns orange.
    const sea = new THREE.Mesh(
      new THREE.CircleGeometry(170, 48),
      new THREE.MeshBasicMaterial({ map: TEX.water(), color: MAP.water })
    );
    sea.rotation.x = -Math.PI/2;
    sea.position.y = -0.85;
    worldGroup.add(sea);

    // Beach, then grass, then the paved square in the middle. The first two
    // follow the height field; the square stays flat because the field is
    // flat under it.
    worldGroup.add(groundDisc(ISLAND_RADIUS + 3.5, surf(TEX.sand), -0.34, 22));
    // MAP.ground, not a hardcoded grass. Every map has declared its own ground
    // material since the maps were written and nothing ever read it, so
    // Halehua Bay - a bay - has been a green field with palm trees on it.
    const groundTex = TEX[MAP.ground] || TEX.grass;
    worldGroup.add(groundDisc(ISLAND_RADIUS - 1.5, surf(groundTex), -0.12, 30));

    // Paving. Dirt put its clod-and-pebble blotches right where everyone
    // stands and argues, and at plaza scale they read as mud.
    const plaza = new THREE.Mesh(new THREE.CircleGeometry(11, 40), surf(TEX.stone, PLAZA));
    plaza.receiveShadow = true;
    plaza.rotation.x = -Math.PI/2;
    plaza.position.y = -0.05;
    worldGroup.add(plaza);

    // A ring of paving detail so the square does not read as a flat disc.
    for (let i = 0; i < 3; i++){
      const r = 4.5 + i * 3.0;
      const ring = new THREE.Mesh(
        new THREE.RingGeometry(r, r + 0.16, 48),
        // Unlit like the sea, so it needs the same hand-tinting - left at the
        // daylight value these three lines were the brightest thing on a
        // night island, three glowing hoops around the square.
        new THREE.MeshStandardMaterial({ color: 0xD9C79B, roughness: 0.9,
                                         transparent: true, opacity: 0.75 })
      );
      ring.rotation.x = -Math.PI/2;
      ring.position.y = -0.04;
      worldGroup.add(ring);
    }
  }

  function buildHouse(rand, x, z){
    const g = new THREE.Group();
    const w = 2.6 + rand() * 1.8;
    const h = 2.4 + rand() * 1.7;
    const d = 2.6 + rand() * 1.6;

    const body = new THREE.Mesh(new THREE.BoxGeometry(w, h, d), surf(TEX.plaster));
    body.position.y = h/2;
    body.castShadow = true; body.receiveShadow = true;
    g.add(body);

    // Half the houses get the blue dome, the rest a terracotta roof.
    if (rand() > 0.5){
      /* The dome used to sit straight on the open top of the box, and from
         anywhere above eye level that is what it looked like: a crate with a
         ball in it. A flat roof is not the absence of a roof - it is a slab,
         a parapet round the edge, and a drum under the dome to lift it clear
         of both. */
      const slab = new THREE.Mesh(new THREE.BoxGeometry(w + 0.26, 0.16, d + 0.26),
                                  surf(TEX.plaster, 0xD8CFB8));
      slab.position.y = h + 0.08;
      slab.castShadow = true; slab.receiveShadow = true;
      g.add(slab);
      // Parapet: four low walls round the edge of the slab. The shadow it
      // throws inward is most of what says "roof" from above.
      const PAR = 0.30;
      for (const [sx, sz, bw, bd] of [[0, 1, w + 0.26, 0.13], [0, -1, w + 0.26, 0.13],
                                      [1, 0, 0.13, d + 0.26], [-1, 0, 0.13, d + 0.26]]){
        const wall = new THREE.Mesh(new THREE.BoxGeometry(bw, PAR, bd),
                                    surf(TEX.plaster, 0xE6DDC6));
        wall.position.set(sx * (w + 0.13) / 2, h + 0.16 + PAR/2, sz * (d + 0.13) / 2);
        wall.castShadow = true; wall.receiveShadow = true;
        g.add(wall);
      }
      const drum = new THREE.Mesh(new THREE.CylinderGeometry(w * 0.34, w * 0.36, 0.42, 16),
                                  surf(TEX.plaster, 0xEDE4D0));
      drum.position.y = h + 0.37;
      drum.castShadow = true;
      g.add(drum);
      const dome = new THREE.Mesh(
        new THREE.SphereGeometry(w * 0.36, 18, 11, 0, Math.PI*2, 0, Math.PI/2), toon(DOME));
      dome.position.y = h + 0.58;
      dome.castShadow = true;
      g.add(dome);
      // Finial, so the dome ends in something rather than just stopping.
      const knob = new THREE.Mesh(new THREE.SphereGeometry(0.09, 10, 8), toon(GOLD));
      knob.position.y = h + 0.58 + w * 0.36 + 0.05;
      g.add(knob);
    } else {
      const roof = new THREE.Mesh(new THREE.ConeGeometry(w * 0.92, 1.25, 4), surf(TEX.roof));
      roof.position.y = h + 0.58;
      roof.rotation.y = Math.PI/4;
      roof.castShadow = true;
      g.add(roof);
      // The overhang is the point: it throws a shadow line along the top of
      // the wall, which is most of what tells you a roof is a roof.
      const eave = new THREE.Mesh(new THREE.BoxGeometry(w + 0.34, 0.12, d + 0.34),
                                  toon(0x8E4B33));
      eave.position.y = h + 0.03;
      eave.castShadow = true;
      g.add(eave);
    }

    /* Openings with depth. A door painted on a wall as a flat plane is a
       sticker: at any angle other than straight on it has no thickness, no
       shadow, and the wall reads as a box again. A recess set back into the
       surface catches the sun on one jamb and not the other, which is what
       makes a building look built. */
    const opening = (ow, oh, ox, oy, glass) => {
      const frame = new THREE.Mesh(new THREE.BoxGeometry(ow + 0.16, oh + 0.16, 0.10),
                                   toon(0xEFE7D6));
      frame.position.set(ox, oy, d/2 + 0.02);
      frame.castShadow = true;
      g.add(frame);
      // After dark a window is either lit from inside or it is a black hole in
      // a wall, and both are worth having - a village where every window burns
      // reads as a stage set. Emissive rather than a light: the glow is what
      // sells it, and twenty point lights would not survive a phone.
      const lit = glass && MAP.lamp > 0 && rand() > 0.32;
      const hole = new THREE.Mesh(new THREE.BoxGeometry(ow, oh, 0.30),
                                  toon(glass ? (lit ? 0xFFD79A : 0x2B3348) : 0x21283A,
                                       lit ? { emissive: 0xFFB25E, emissiveIntensity: 2.4 * MAP.lamp }
                                           : null));
      hole.position.set(ox, oy, d/2 - 0.15);      // set back into the wall
      g.add(hole);
      if (glass){
        const bar = new THREE.Mesh(new THREE.BoxGeometry(ow + 0.02, 0.05, 0.12),
                                   toon(0xEFE7D6));
        bar.position.set(ox, oy, d/2 + 0.03);
        g.add(bar);
      }
    };
    opening(0.62, 1.20, 0, 0.60, false);
    opening(0.52, 0.52, w * 0.30, h * 0.64, true);
    if (w > 3.4) opening(0.52, 0.52, -w * 0.30, h * 0.64, true);

    /* Trim.

       A plastered box with holes in it is a shape, not a building. What makes
       the difference at this distance is timber: posts at the corners, a beam
       along the top of the wall, a lintel over the door. All of it is boxes -
       the cost is nothing - and it gives the flat render something to break
       against, which is the job the texture was failing to do on its own. */
    const TIMBER = 0x6B4A32;
    for (const sx of [-1, 1]){
      for (const sz of [-1, 1]){
        const post = new THREE.Mesh(new THREE.BoxGeometry(0.17, h, 0.17), toon(TIMBER));
        post.position.set(sx * (w/2 - 0.06), h/2, sz * (d/2 - 0.06));
        post.castShadow = true;
        g.add(post);
      }
    }
    // The wall plate: one beam right round, sitting just under the roof.
    const plate = new THREE.Mesh(new THREE.BoxGeometry(w + 0.10, 0.18, d + 0.10), toon(TIMBER));
    plate.position.y = h - 0.09;
    plate.castShadow = true;
    g.add(plate);

    // A shallow porch hood over the door, on two brackets.
    const hood = new THREE.Mesh(new THREE.BoxGeometry(1.34, 0.11, 0.60), toon(0x7A5439));
    hood.position.set(0, 1.44, d/2 + 0.26);
    hood.rotation.x = -0.16;
    hood.castShadow = true;
    g.add(hood);
    for (const sx of [-1, 1]){
      const brace = new THREE.Mesh(new THREE.BoxGeometry(0.09, 0.44, 0.09), toon(TIMBER));
      brace.position.set(sx * 0.52, 1.20, d/2 + 0.10);
      brace.rotation.x = 0.5;
      g.add(brace);
    }

    // Shutters, thrown open, on the upper windows. Only ever one pair of
    // colours per house, or a street of them looks like a paint chart.
    const shutter = [0x4E7A8C, 0x8C5B4A, 0x5E7A50][(rand() * 3) | 0];
    const pair = (ox, oy) => {
      for (const sx of [-1, 1]){
        const s = new THREE.Mesh(new THREE.BoxGeometry(0.20, 0.56, 0.05), toon(shutter));
        s.position.set(ox + sx * 0.42, oy, d/2 + 0.06);
        s.rotation.y = sx * 0.42;
        s.castShadow = true;
        g.add(s);
      }
    };
    pair(w * 0.30, h * 0.64);
    if (w > 3.4) pair(-w * 0.30, h * 0.64);

    // Light from inside, on the ground outside the door. Cheap, unlit, and it
    // is the single thing that makes a house read as occupied after dark.
    if (MAP.lamp > 0){
      const spill = new THREE.Mesh(
        new THREE.PlaneGeometry(1.15, 1.5),
        new THREE.MeshBasicMaterial({ map: blobShadow(), color: 0xFFC078,
                                      transparent: true, opacity: 0.42 * MAP.lamp,
                                      blending: THREE.AdditiveBlending,
                                      depthWrite: false })
      );
      spill.rotation.x = -Math.PI/2;
      spill.position.set(0, 0.02, d/2 + 0.66);
      g.add(spill);
    }

    // A step at the door and a base course, so the house meets the ground
    // instead of being dropped onto it.
    const step = new THREE.Mesh(new THREE.BoxGeometry(1.10, 0.14, 0.55), toon(0xCFC6B0));
    step.position.set(0, 0.07, d/2 + 0.24);
    step.receiveShadow = true;
    g.add(step);
    const plinth = new THREE.Mesh(new THREE.BoxGeometry(w + 0.14, 0.28, d + 0.14),
                                  surf(TEX.stone));
    plinth.position.y = 0.14;
    plinth.castShadow = true; plinth.receiveShadow = true;
    g.add(plinth);

    g.position.set(x, terrainH(x, z), z);
    g.rotation.y = rand() * Math.PI * 2;
    worldGroup.add(g);
    // Half the diagonal plus the eaves: near enough for a camera test, and
    // erring wide is the safe direction - it pulls in a fraction early
    // rather than leaving the player behind a wall.
    blocker(x, z, Math.hypot(w, d) * 0.5 + 0.15, h + 1.2);
  }

  /* A tree.

     Three smooth spheres on a dowel is a lollipop, and no texture rescues a
     silhouette. What reads as a tree from across a square is: a trunk that
     flares where it meets the ground, branches going somewhere, and a canopy
     with a broken edge and two tones in it - lit on the sun's side, shaded
     underneath.

     Flat shading on a jittered icosahedron does the last part for nothing.
     Every face takes one normal, so a low-poly lump lights as a cluster of
     facets, which is exactly how a mass of leaves catches light. */
  function leafCluster(rand, r, tone){
    const geo = new THREE.IcosahedronGeometry(r, 1);
    const p = geo.attributes.position;
    // Push each vertex in or out a little. Deterministic per tree, so the
    // island is identical on every device.
    for (let i = 0; i < p.count; i++){
      const k = 0.82 + rand() * 0.36;
      p.setXYZ(i, p.getX(i) * k, p.getY(i) * k * 0.88, p.getZ(i) * k);
    }
    p.needsUpdate = true;
    geo.computeVertexNormals();
    const m = new THREE.Mesh(geo, tone);
    m.castShadow = true; m.receiveShadow = true;
    return m;
  }

  // Same texture, three tints, asked for by argument rather than patched in
  // afterwards - so the cache hands the same three materials to every tree and
  // sixty trees are still three batches.
  function leafTones(){
    return {
      lit:  surf(TEX.leaf, 0xC6E39A, undefined, { flatShading: true }),
      mid:  surf(TEX.leaf, 0x9DC46F, undefined, { flatShading: true }),
      dark: surf(TEX.leaf, 0x6E9450, undefined, { flatShading: true })
    };
  }

  function buildTree(rand, x, z){
    const g = new THREE.Group();
    const th = 1.9 + rand() * 1.3;
    const tone = leafTones();

    const trunk = new THREE.Mesh(new THREE.CylinderGeometry(0.15, 0.26, th, 9), surf(TEX.bark));
    trunk.position.y = th/2;
    trunk.castShadow = true; trunk.receiveShadow = true;
    g.add(trunk);

    // Root flare. A cylinder meeting flat ground looks pushed into it; a
    // wider, shorter cone at the base looks grown out of it.
    const flare = new THREE.Mesh(new THREE.CylinderGeometry(0.27, 0.46, 0.34, 9),
                                 surf(TEX.bark));
    flare.position.y = 0.17;
    flare.receiveShadow = true;
    g.add(flare);

    // Two or three limbs leaving the trunk at an angle, each carrying its own
    // small cluster. This is most of what stops a tree reading as a ball on a
    // stick from the side.
    const limbs = 2 + ((rand() * 2) | 0);
    for (let i = 0; i < limbs; i++){
      const a = (i / limbs) * Math.PI * 2 + rand();
      const len = 0.75 + rand() * 0.5;
      const limb = new THREE.Mesh(new THREE.CylinderGeometry(0.06, 0.11, len, 6),
                                  surf(TEX.bark));
      limb.position.set(Math.cos(a) * len * 0.30, th * 0.80 + rand() * 0.2,
                        Math.sin(a) * len * 0.30);
      limb.rotation.z = -Math.cos(a) * 0.75;
      limb.rotation.x =  Math.sin(a) * 0.75;
      limb.castShadow = true;
      g.add(limb);
      const tip = leafCluster(rand, 0.52 + rand() * 0.22, rand() > 0.5 ? tone.mid : tone.dark);
      tip.position.set(Math.cos(a) * len * 0.85, th * 0.86 + len * 0.4,
                       Math.sin(a) * len * 0.85);
      g.add(tip);
    }

    // The crown: a dark underside, a mid mass, and a smaller lit cap on top.
    // Three tones stacked is the cheapest thing that reads as volume.
    const R = 1.00 + rand() * 0.42;
    const under = leafCluster(rand, R, tone.dark);
    under.position.y = th + R * 0.42;
    g.add(under);
    const mass = leafCluster(rand, R * 0.94, tone.mid);
    mass.position.set((rand()-0.5) * 0.3, th + R * 0.74, (rand()-0.5) * 0.3);
    g.add(mass);
    const cap = leafCluster(rand, R * 0.66, tone.lit);
    cap.position.set((rand()-0.5) * 0.36, th + R * 1.10, (rand()-0.5) * 0.36);
    g.add(cap);

    g.position.set(x, terrainH(x, z), z);
    g.rotation.y = rand() * Math.PI * 2;
    const s = 0.86 + rand() * 0.42;
    g.scale.set(s, s, s);
    worldGroup.add(g);
    // The trunk only. A canopy is not something to be shoved out from behind -
    // you can see through the gaps in it, and being pushed forward every time
    // a branch clips the view would make the camera feel broken.
    blocker(x, z, 0.34 * s, th * s);
  }

  /* The nightfall monument in the middle of the square - the game's namesake,
     and the thing everyone gathers around to vote. */
  /* A ring of hills well beyond the island. They sit inside the fog, so they
     read as distance rather than as geometry, which is the trick the console
     used to make a small world feel like a big one. */
  const HILL_MATS = [];
  function hillMat(step){
    if (!HILL_MATS[step]){
      HILL_MATS[step] = new THREE.MeshStandardMaterial({
        color: new THREE.Color(0x6E8F3C).lerp(new THREE.Color(0x8FA5A0), 0.22 + step * 0.05),
        roughness: 1.0, flatShading: true });
    }
    return HILL_MATS[step];
  }

  function buildHorizon(){
    const rand = seeded(90210);
    // A single cone per bearing is a cardboard triangle. Ridges are two or
    // three peaks of different heights overlapping, and it is the overlap -
    // one shoulder crossing behind another - that reads as land rather than
    // as a cut-out standing on the water.
    for (let i = 0; i < 20; i++){
      const a = (i / 20) * Math.PI * 2 + rand() * 0.2;
      const dist = 76 + rand() * 30;
      const peaks = 2 + ((rand() * 2) | 0);
      for (let k = 0; k < peaks; k++){
        const off = (k - (peaks - 1) / 2) * (12 + rand() * 9);
        const h = (k === 0 ? 13 : 8) + rand() * 14;
        const rr = 10 + rand() * 12;
        // Haze comes from the map's fog, so the rock keeps its own colour and
        // gets greyed by distance instead of being painted pale up front.
        // Four steps of haze rather than a continuous ramp. A fresh material
        // per cone gave sixty materials for the horizon alone and nothing the
        // batcher could group; the difference between step and ramp is not
        // visible at seventy metres through fog.
        const step = (rand() * 4) | 0;
        const hill = new THREE.Mesh(
          new THREE.ConeGeometry(rr, h, 10),
          hillMat(step)
        );
        hill.position.set(Math.cos(a) * dist - Math.sin(a) * off,
                          h * 0.5 - 3.5,
                          Math.sin(a) * dist + Math.cos(a) * off);
        hill.rotation.y = rand() * Math.PI;
        hill.scale.set(1, 1, 0.8 + rand() * 0.5);
        worldGroup.add(hill);
      }
    }
  }

  /* A palm: a leaning trunk with fronds fanned off the top. */
  function buildPalm(rand, x, z){
    const g = new THREE.Group();
    const h = 3.4 + rand() * 2.4;
    const trunk = new THREE.Mesh(new THREE.CylinderGeometry(0.13, 0.22, h, 9), surf(TEX.bark));
    trunk.position.y = h/2;
    trunk.rotation.z = (rand() - 0.5) * 0.34;
    trunk.castShadow = true;
    g.add(trunk);
    for (let i = 0; i < 7; i++){
      const a = (i/7) * Math.PI * 2;
      const frond = new THREE.Mesh(new THREE.ConeGeometry(0.42, 2.5, 4), surf(TEX.leaf));
      frond.position.set(Math.cos(a) * 1.0, h - 0.2 - Math.abs(Math.sin(a)) * 0.25, Math.sin(a) * 1.0);
      frond.rotation.z = Math.cos(a) * 1.25;
      frond.rotation.x = -Math.sin(a) * 1.25;
      frond.castShadow = true;
      g.add(frond);
    }
    g.position.set(x, terrainH(x, z), z);
    worldGroup.add(g);
    blocker(x, z, 0.30, h);
  }

  function buildRock(rand, x, z){
    const r = 0.5 + rand() * 1.2;
    const rock = new THREE.Mesh(new THREE.DodecahedronGeometry(r, 0), surf(TEX.stone));
    rock.position.set(x, r * 0.45, z);
    rock.rotation.set(rand() * 3, rand() * 3, rand() * 3);
    rock.scale.y = 0.7 + rand() * 0.4;
    rock.castShadow = true; rock.receiveShadow = true;
    worldGroup.add(rock);
  }

  function buildFern(rand, x, z){
    const g = new THREE.Group();
    for (let i = 0; i < 5; i++){
      const a = (i/5) * Math.PI * 2;
      const blade = new THREE.Mesh(new THREE.ConeGeometry(0.16, 0.9 + rand()*0.5, 4), surf(TEX.leaf));
      blade.position.set(Math.cos(a) * 0.16, 0.45, Math.sin(a) * 0.16);
      blade.rotation.z = Math.cos(a) * 0.5;
      blade.rotation.x = -Math.sin(a) * 0.5;
      g.add(blade);
    }
    g.position.set(x, terrainH(x, z), z);
    worldGroup.add(g);
  }

  function buildMonument(){
    const g = new THREE.Group();
    const base = new THREE.Mesh(new THREE.CylinderGeometry(2.0, 2.4, 0.5, 24), surf(TEX.stone));
    base.position.y = 0.25;
    g.add(base);
    const step = new THREE.Mesh(new THREE.CylinderGeometry(1.5, 1.7, 0.4, 24), surf(TEX.stone));
    step.position.y = 0.68;
    g.add(step);

    const column = new THREE.Mesh(new THREE.CylinderGeometry(0.42, 0.5, 3.4, 18), surf(TEX.stone));
    column.position.y = 2.55;
    column.castShadow = true;
    g.add(column);
    blocker(0, 0, 0.75, 4.6, 0);

    // Flutes down the column.
    for (let i = 0; i < 10; i++){
      const a = (i/10) * Math.PI * 2;
      const flute = new THREE.Mesh(new THREE.BoxGeometry(0.07, 3.3, 0.07), toon(0xE6DDCB));
      flute.position.set(Math.cos(a) * 0.44, 2.55, Math.sin(a) * 0.44);
      g.add(flute);
    }

    const cap = new THREE.Mesh(new THREE.CylinderGeometry(0.62, 0.5, 0.28, 18), toon(0xF4EEE0));
    cap.position.y = 4.35;
    g.add(cap);

    // The one thing on the island that is meant to be looked at, so after
    // dark it is the one thing that lights itself. It is also the landmark
    // players navigate by, and a landmark you cannot see at night is not one.
    const spindle = new THREE.Mesh(new THREE.SphereGeometry(0.46, 18, 14),
      toon(GOLD, { emissive: 0xFFC24E, emissiveIntensity: 1.2 }));
    spindle.position.y = 4.95;
    g.add(spindle);
    monumentSpindle = spindle;

    const beacon = new THREE.PointLight(0xFFC98A, 2.2 * (MAP.lamp || 0.6), 11, 2);
    beacon.position.y = 4.95;
    g.add(beacon);

    worldGroup.add(g);
  }
  let monumentSpindle = null;

  /* ------------------------------------------------------------------
     After dark

     Turning the sun off is the easy half. What actually makes a night scene
     legible is having somewhere for the light to come from: pools you walk
     through, and points of light at a distance that give the dark depth.

     Point lights are the expensive kind, so there is a hard cap and the rest
     of the lanterns are bulbs only - an unlit lantern with a glowing bulb
     reads correctly from six metres away, which is where most of them are.
     ------------------------------------------------------------------ */
  // Every point light is another loop in the fragment shader for every lit
  // material in the scene, and a phone feels each one. Three round the square,
  // plus the monument's and the one that follows you, is five - which is a
  // budget rather than an accident.
  const MAX_LAMP_LIGHTS = 3;
  let lanternBulbs = [];
  let fireflyPts = null;

  function buildLantern(x, z, withLight){
    const g = new THREE.Group();
    const post = new THREE.Mesh(new THREE.CylinderGeometry(0.07, 0.10, 2.5, 8), toon(0x4A3A2E));
    post.position.y = 1.25; post.castShadow = true;
    g.add(post);
    const arm = new THREE.Mesh(new THREE.BoxGeometry(0.42, 0.08, 0.08), toon(0x4A3A2E));
    arm.position.set(0.18, 2.46, 0);
    g.add(arm);
    // Unlit material, so the bulb stays the same brightness whatever the sky
    // is doing. A bulb that dims with the scene is not a bulb.
    const bulb = new THREE.Mesh(new THREE.SphereGeometry(0.17, 12, 9),
      new THREE.MeshBasicMaterial({ color: 0xFFD9A0 }));
    bulb.position.set(0.36, 2.34, 0);
    g.add(bulb);
    const shade = new THREE.Mesh(
      new THREE.ConeGeometry(0.26, 0.24, 10), toon(0x3A2E24));
    shade.position.set(0.36, 2.56, 0);
    g.add(shade);
    if (withLight){
      // Short reach on purpose. At fifteen units three lanterns lit the
      // whole beach and night went back to looking like an overcast day; the
      // point of a lamp is the dark it leaves around itself.
      const l = new THREE.PointLight(0xFFC489, 2.6 * MAP.lamp, 8.5, 2);
      l.position.set(0.36, 2.30, 0);
      g.add(l);
    }
    g.position.set(x, terrainH(x, z), z);
    g.rotation.y = Math.atan2(-x, -z);          // arm points into the square
    worldGroup.add(g);
    lanternBulbs.push(bulb);
  }

  /* Points, not meshes: ninety fireflies in one draw call. Additive blending
     so they brighten whatever they drift over rather than punching holes. */
  function buildFireflies(n){
    const c = document.createElement("canvas");
    c.width = c.height = 32;
    const ctx = c.getContext("2d");
    const grd = ctx.createRadialGradient(16, 16, 0, 16, 16, 16);
    grd.addColorStop(0, "rgba(220,255,170,1)");
    grd.addColorStop(0.35, "rgba(160,230,90,0.55)");
    grd.addColorStop(1, "rgba(120,200,60,0)");
    ctx.fillStyle = grd; ctx.fillRect(0, 0, 32, 32);

    const pos = new Float32Array(n * 3);
    const seed = new Float32Array(n * 3);          // home x, home z, phase
    const rand = seeded(7717);
    for (let i = 0; i < n; i++){
      const a = rand() * Math.PI * 2, r = 9 + rand() * 20;
      const x = Math.cos(a) * r, z = Math.sin(a) * r;
      seed[i*3] = x; seed[i*3+1] = z; seed[i*3+2] = rand() * Math.PI * 2;
      pos[i*3] = x; pos[i*3+1] = terrainH(x, z) + 0.7 + rand() * 1.8; pos[i*3+2] = z;
    }
    const geo = new THREE.BufferGeometry();
    geo.setAttribute("position", new THREE.BufferAttribute(pos, 3));
    const pts = new THREE.Points(geo, new THREE.PointsMaterial({
      size: 0.38, map: new THREE.CanvasTexture(c), transparent: true,
      blending: THREE.AdditiveBlending, depthWrite: false, sizeAttenuation: true
    }));
    pts.userData.seed = seed;
    worldGroup.add(pts);
    fireflyPts = pts;
  }

  /* Bake the scenery.

     A village of fourteen houses with posts, shutters, a porch and a parapet,
     and twenty-six trees with limbs and a three-tone crown, came to 412 draw
     calls. The triangle count was never the problem - 66k is nothing - but
     every call is a state change and a phone feels four hundred of them.

     Nothing in the scenery moves, and almost all of it shares a handful of
     materials, so the whole lot collapses into one mesh per material. The
     transform each part already has is baked into its vertices on the way in,
     which is why this runs after the world is built rather than during.

     Left out: anything that animates (the spindle, the lantern bulbs, the
     fireflies), anything unique enough that merging saves nothing (the sky,
     the sea, the ground discs), and anything transparent, whose draw order
     depends on staying separate. */
  /* Concatenate geometries that all carry position, normal and uv.

     three ships a mergeBufferGeometries, but in examples/ rather than in the
     core build this vendors, so THREE.BufferGeometryUtils is not there at
     runtime. The general version handles morph targets, groups and mismatched
     attribute sets; none of that appears in a village, and the part that does
     is thirty lines. */
  function mergeGeos(geos){
    let verts = 0, idx = 0;
    const indexed = !!geos[0].index;
    for (const g of geos){
      if (!!g.index !== indexed) return null;      // cannot mix the two
      verts += g.attributes.position.count;
      idx += indexed ? g.index.count : 0;
    }
    // Indices are 16-bit until they cannot be. A village of 60k vertices needs
    // 32, and getting this wrong wraps the geometry into confetti.
    const IndexArray = verts > 65535 ? Uint32Array : Uint16Array;
    const pos = new Float32Array(verts * 3);
    const nor = new Float32Array(verts * 3);
    const uv  = new Float32Array(verts * 2);
    const ind = indexed ? new IndexArray(idx) : null;

    let vo = 0, io = 0;
    for (const g of geos){
      const p = g.attributes.position, n = g.attributes.normal, u = g.attributes.uv;
      pos.set(p.array.subarray(0, p.count * 3), vo * 3);
      nor.set(n.array.subarray(0, n.count * 3), vo * 3);
      uv.set(u.array.subarray(0, u.count * 2), vo * 2);
      if (indexed){
        const src = g.index.array;
        for (let i = 0; i < src.length; i++) ind[io + i] = src[i] + vo;
        io += src.length;
      }
      vo += p.count;
    }
    const out = new THREE.BufferGeometry();
    out.setAttribute("position", new THREE.BufferAttribute(pos, 3));
    out.setAttribute("normal", new THREE.BufferAttribute(nor, 3));
    out.setAttribute("uv", new THREE.BufferAttribute(uv, 2));
    if (indexed) out.setIndex(new THREE.BufferAttribute(ind, 1));
    out.computeBoundingSphere();
    return out;
  }

  function bakeScenery(){
    const keep = new Set([monumentSpindle, fireflyPts].concat(lanternBulbs).filter(Boolean));
    const groups = new Map();
    const originals = [];

    worldGroup.updateMatrixWorld(true);
    worldGroup.traverse(o => {
      if (!o.isMesh || keep.has(o)) return;
      const m = o.material;
      if (!m || Array.isArray(m) || m.transparent || m.isShaderMaterial) return;
      const g = o.geometry;
      if (!g || !g.attributes.position || !g.attributes.normal || !g.attributes.uv) return;
      // Indexed and non-indexed geometry cannot merge with each other, and a
      // mismatch makes mergeBufferGeometries return null rather than throw -
      // which would silently empty the island. Keyed apart instead.
      const key = m.uuid + "|" + (g.index ? "i" : "n");
      let bucket = groups.get(key);
      if (!bucket) groups.set(key, bucket = { mat: m, cast: false, recv: false, geos: [] });
      const clone = g.clone().applyMatrix4(o.matrixWorld);
      // Merging needs the same attribute set on every input; drop the extras
      // some primitives carry so one odd geometry cannot fail the batch.
      for (const name of Object.keys(clone.attributes)){
        if (name !== "position" && name !== "normal" && name !== "uv") clone.deleteAttribute(name);
      }
      bucket.geos.push(clone);
      bucket.cast = bucket.cast || o.castShadow;
      bucket.recv = bucket.recv || o.receiveShadow;
      originals.push(o);
    });

    let merged = 0;
    groups.forEach(bucket => {
      if (bucket.geos.length < 2){ bucket.geos.forEach(g => g.dispose()); return; }
      const geo = mergeGeos(bucket.geos);
      bucket.geos.forEach(g => g.dispose());
      if (!geo) return;
      const mesh = new THREE.Mesh(geo, bucket.mat);
      mesh.castShadow = bucket.cast;
      mesh.receiveShadow = bucket.recv;
      mesh.userData.baked = true;
      worldGroup.add(mesh);
      merged++;
      bucket.done = true;
    });

    // Only remove the originals whose batch actually formed, or a failed
    // merge would delete part of the island rather than leaving it unbatched.
    const survived = new Set();
    groups.forEach((b, key) => { if (b.done) survived.add(key); });
    originals.forEach(o => {
      const key = o.material.uuid + "|" + (o.geometry.index ? "i" : "n");
      if (!survived.has(key)) return;
      o.geometry.dispose();
      if (o.parent) o.parent.remove(o);
    });
    return merged;
  }

  function buildNightLights(){
    lanternBulbs = [];
    if (!MAP.lamp) return;
    // Ringing the square, offset from the benches so they do not share a spot.
    const N = 8;
    for (let i = 0; i < N; i++){
      const a = (i / N) * Math.PI * 2;
      buildLantern(Math.cos(a) * 11.2, Math.sin(a) * 11.2, i % 2 === 0 && i / 2 < MAX_LAMP_LIGHTS);
    }
    if (MAP.fireflies) buildFireflies(MAP.fireflies);
  }

  function scatter(){
    const rand = seeded(20250815);
    for (let i = 0; i < MAP.houses; i++){
      const a = (i / Math.max(1, MAP.houses)) * Math.PI * 2 + rand() * 0.2;
      const r = 15 + rand() * 8;
      buildHouse(rand, Math.cos(a) * r, Math.sin(a) * r);
    }
    for (let i = 0; i < MAP.trees; i++){
      const a = rand() * Math.PI * 2, r = 12.5 + rand() * 15;
      buildTree(rand, Math.cos(a) * r, Math.sin(a) * r);
    }
    for (let i = 0; i < MAP.palms; i++){
      const a = rand() * Math.PI * 2, r = 13 + rand() * 16;
      buildPalm(rand, Math.cos(a) * r, Math.sin(a) * r);
    }
    for (let i = 0; i < MAP.rocks; i++){
      const a = rand() * Math.PI * 2, r = 12 + rand() * 17;
      buildRock(rand, Math.cos(a) * r, Math.sin(a) * r);
    }
    for (let i = 0; i < MAP.ferns; i++){
      const a = rand() * Math.PI * 2, r = 12 + rand() * 17;
      buildFern(rand, Math.cos(a) * r, Math.sin(a) * r);
    }
    // Benches around the plaza edge to make it feel inhabited.
    for (let i = 0; i < 6; i++){
      const a = (i / 6) * Math.PI * 2 + 0.5;
      const bench = new THREE.Mesh(new THREE.BoxGeometry(1.7, 0.24, 0.5), toon(0xB07A4E));
      bench.position.set(Math.cos(a) * 9.6, 0.42, Math.sin(a) * 9.6);
      bench.rotation.y = -a;
      worldGroup.add(bench);
      const legs = new THREE.Mesh(new THREE.BoxGeometry(1.5, 0.4, 0.32), toon(0x9A683F));
      legs.position.set(Math.cos(a) * 9.6, 0.2, Math.sin(a) * 9.6);
      legs.rotation.y = -a;
      worldGroup.add(legs);
    }
  }

  /* ------------------------------------------------------------------
     Characters
     ------------------------------------------------------------------ */
  let blobShadowTex = null;
  function blobShadow(){
    if (blobShadowTex) return blobShadowTex;
    const c = document.createElement("canvas");
    c.width = c.height = 64;
    const g = c.getContext("2d");
    const grd = g.createRadialGradient(32, 32, 0, 32, 32, 32);
    grd.addColorStop(0,   "rgba(40,30,20,0.42)");
    grd.addColorStop(0.6, "rgba(40,30,20,0.18)");
    grd.addColorStop(1,   "rgba(40,30,20,0)");
    g.fillStyle = grd; g.fillRect(0, 0, 64, 64);
    blobShadowTex = new THREE.CanvasTexture(c);
    return blobShadowTex;
  }

  /* ------------------------------------------------------------------
     Speech bubbles

     The Wizard101 / Free Realms arrangement: what you say floats over your
     own head, your name sits under it, and a transcript runs in the corner
     for anything missed. Saying something is an act your character performs
     in the world, not a line in a panel somewhere else.
     ------------------------------------------------------------------ */
  function bubbleTexture(text, spirit){
    const PAD = 26, LINE = 46, MAXW = 620;
    const measure = document.createElement("canvas").getContext("2d");
    const font = "600 38px ui-rounded, -apple-system, 'Segoe UI', system-ui, sans-serif";
    measure.font = font;

    // Wrap on words, then hard-break anything that still will not fit.
    const words = String(text).split(/\s+/);
    const lines = [];
    let line = "";
    words.forEach(w => {
      const test = line ? line + " " + w : w;
      if (measure.measureText(test).width > MAXW - PAD*2 && line){ lines.push(line); line = w; }
      else line = test;
    });
    if (line) lines.push(line);
    while (lines.length > 3){ lines.pop(); }
    if (lines.length === 3 && words.length > lines.join(" ").split(/\s+/).length){
      lines[2] = lines[2].slice(0, 22) + "\u2026";
    }

    const w = Math.min(MAXW, Math.max(160,
      Math.max.apply(null, lines.map(l => measure.measureText(l).width)) + PAD*2));
    const h = lines.length * LINE + PAD*2 + 22;   // 22 for the tail

    const c = document.createElement("canvas");
    c.width = w; c.height = h;
    const g = c.getContext("2d");
    g.font = font;
    g.textAlign = "center";
    g.textBaseline = "middle";

    const bodyH = h - 22;
    const r = 22;
    g.fillStyle = spirit ? "rgba(226,214,246,0.96)" : "rgba(255,252,244,0.97)";
    g.strokeStyle = spirit ? "#7A5CC4" : "#C9A05A";
    g.lineWidth = 4;
    g.beginPath();
    g.moveTo(r, 0);
    g.arcTo(w, 0, w, bodyH, r);
    g.arcTo(w, bodyH, 0, bodyH, r);
    // tail, pointing down at the speaker
    g.lineTo(w/2 + 16, bodyH);
    g.lineTo(w/2, h);
    g.lineTo(w/2 - 16, bodyH);
    g.arcTo(0, bodyH, 0, 0, r);
    g.arcTo(0, 0, w, 0, r);
    g.closePath();
    g.fill(); g.stroke();

    g.fillStyle = spirit ? "#4A2F73" : "#2B2438";
    lines.forEach((l, i) => g.fillText(l, w/2, PAD + LINE*i + LINE/2));

    const tex = new THREE.CanvasTexture(c);
    tex.minFilter = THREE.LinearFilter;
    return { tex, w, h };
  }

  /* Show a line over a player. Replaces whatever they were saying. */
  function say(pid, text, spirit){
    const rig = avatars.get(pid);
    if (!rig || !text) return;
    if (rig.bubble){ rig.group.remove(rig.bubble); rig.bubble.material.map.dispose(); }
    const { tex, w, h } = bubbleTexture(text, spirit);
    const sprite = new THREE.Sprite(new THREE.SpriteMaterial({
      map: tex, transparent: true, depthWrite: false, depthTest: false
    }));
    const scale = 2.4;                     // world units across the widest bubble
    sprite.scale.set(scale * (w / 620), scale * (h / 620), 1);
    /* Clear of everything else over a head, and stepped per seat so two people
       talking at once do not stack their bubbles on each other.

       The stack, from the shoulders up: head 2.95, name tag 3.32, the
       plumbob through about 4.35, and the bubble from here. At 3.78 the
       bubble sat exactly where the diamond is and cut it in half. A bubble is
       transient and grows upward anyway, so it is the one that moves. */
    sprite.position.y = 4.58 + ((rig.seat || 0) % 3) * 0.42;
    sprite.center.set(0.5, 0);             // grow upward from the head
    rig.group.add(sprite);
    rig.bubble = sprite;
    rig.bubbleAt = clock;
  }

  function nameTag(name, tint){
    const c = document.createElement("canvas");
    c.width = 320; c.height = 80;
    const g = c.getContext("2d");
    g.clearRect(0, 0, 320, 80);
    const text = (name || "").slice(0, 14);
    g.font = "700 40px ui-rounded, -apple-system, 'Segoe UI', system-ui, sans-serif";
    g.textAlign = "center"; g.textBaseline = "middle";
    const w = Math.min(300, g.measureText(text).width + 40);

    // Rounded pill behind the name so it reads against sky, sea or grass.
    g.fillStyle = tint || "rgba(43,36,56,0.82)";
    const x = (320 - w) / 2, y = 14, h = 52, r = 26;
    g.beginPath();
    g.moveTo(x + r, y);
    g.arcTo(x + w, y, x + w, y + h, r);
    g.arcTo(x + w, y + h, x, y + h, r);
    g.arcTo(x, y + h, x, y, r);
    g.arcTo(x, y, x + w, y, r);
    g.closePath(); g.fill();

    g.fillStyle = "#FFFFFF";
    g.fillText(text, 160, 41);
    const tex = new THREE.CanvasTexture(c);
    tex.minFilter = THREE.LinearFilter;
    return tex;
  }

  /* One Islander in the world: the shared avatar rig, plus the things only the
     island needs - a painted shadow, a name tag and a vote marker. */
  function buildRig(player, islander){
    const cfg = Object.assign(Avatar.defaults(), islander || {});
    cfg.hat = cfg.hat !== false;

    const a = Avatar.build(cfg);
    const rig = a.root;

    const shadow = new THREE.Mesh(
      new THREE.PlaneGeometry(1.5, 1.5),
      new THREE.MeshBasicMaterial({ map: blobShadow(), transparent: true, depthWrite: false })
    );
    shadow.rotation.x = -Math.PI/2;
    shadow.position.y = 0.02;
    shadow.visible = false;   // real shadows do this job now
    rig.add(shadow);

    const tag = new THREE.Sprite(new THREE.SpriteMaterial({
      map: nameTag(player.name), transparent: true, depthWrite: false, depthTest: false
    }));
    tag.scale.set(1.7, 0.43, 1);
    // Staggered per player so tags on bunched-up characters do not overlap.
    tag.position.y = 3.32 + ((player.seat || 0) % 4) * 0.32;
    rig.add(tag);

    const marker = new THREE.Mesh(
      new THREE.RingGeometry(0.52, 0.68, 24),
      new THREE.MeshBasicMaterial({ color: 0xE04B3C, transparent: true, opacity: 0,
                                    side: THREE.DoubleSide })
    );
    marker.rotation.x = -Math.PI/2;
    marker.position.y = 0.03;
    rig.add(marker);

    rig.traverse(o => { if (o.isMesh) o.castShadow = true; });
    scene.add(rig);
    return {
      // `torso` and `body` are the same object under both names: the emote
      // code reaches for rig.torso and the walk cycle for rig.body, and when
      // only one of them existed every emote that leaned - bow, laugh, sleep,
      // wiggle - threw on the first frame and stopped the render loop.
      group: rig, avatar: a, head: a.head, body: a.body, torso: a.body,
      headY: a.headY, tag, marker, shadow,
      seat: player.seat || 0,
      armL: a.armL, armR: a.armR, legL: a.legL, legR: a.legR,
      pid: player.pid,
      // Interpolation targets, fed by the movement frame.
      x: player.x || 0, z: player.z || 0, angle: 0,
      tx: player.x || 0, tz: player.z || 0, ta: 0,
      moving: false, alive: true, phase: Math.random() * 10,
      emote: "", emoteT: 0, ghost: false
    };
  }

  /* ------------------------------------------------------------------
     Public surface
     ------------------------------------------------------------------ */
  let worldGroup = null;

  function init(canvas, mapId){
    // Sharp. The look we want from Ocarina is its art direction - green
    // fields, blue sky, warm low-poly shapes - not the console's resolution.
    // Rendering through a small buffer reproduced the blur, which is the one
    // part of 1998 nobody misses.
    renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: false });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));

    /* Colour, which is most of why this looked like a WebGL demo rather than
       a game.

       Lighting maths is linear; a screen is not. Without sRGB output every
       shaded value is written straight to an sRGB display, so midtones come
       out pale and washed and nothing has any depth to it. And with no tone
       mapping, bright surfaces clip flat to white instead of rolling off.

       ACES is the filmic curve film and every modern engine use: highlights
       roll off, saturation holds up under a strong sun, and shadows keep
       colour instead of going grey. It costs nothing - it is a curve applied
       in the shader that was already running.

       Any texture used as COLOUR has to be tagged sRGB to match, or it gets
       decoded twice and goes washed out the other way. Data textures - normal
       maps - must stay linear. */
    renderer.outputEncoding = THREE.sRGBEncoding;
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    renderer.toneMappingExposure = 1.15;   // ACES darkens midtones; take it back
    // Deliberately not innerWidth/innerHeight - see resize(). The camera does
    // not exist yet at this point, so this only sizes the buffer; resize()
    // runs again once the camera is built and sets the aspect with it.
    {
      const w = canvas.clientWidth || innerWidth, h = canvas.clientHeight || innerHeight;
      renderer.setSize(w, h, false);
    }
    // Dusk, not daylight, for the frame or two before applyMap runs - a white
    // flash before a night scene is the most visible thing on the page.
    renderer.setClearColor(0x8A6A72, 1);

    maxAniso = renderer.capabilities.getMaxAnisotropy();
    // Characters need this before any of them are built.
    if (window.Avatar && Avatar.environment) Avatar.environment(renderer);

    scene = new THREE.Scene();
    scene.fog = new THREE.Fog(0x8A6A72, 30, 104);
    camera = new THREE.PerspectiveCamera(58, innerWidth/innerHeight, 0.1, 400);

    // Placeholders. applyMap sets all three from the map's own hour.
    hemi = new THREE.HemisphereLight(0x6C7FBE, 0x4E3A32, 0.62);
    scene.add(hemi);
    sun = new THREE.DirectionalLight(0xFFAE64, 1.55);
    sun.position.set(30, 11, 17);

    // Real shadows. The reference has them, and without them everything looks
    // like it is hovering. Kept to a modest map with a tight frustum around
    // the play area so it stays cheap on a phone.
    renderer.shadowMap.enabled = true;
    renderer.shadowMap.type = THREE.PCFSoftShadowMap;
    sun.castShadow = true;
    sun.shadow.mapSize.set(1024, 1024);
    const cam = sun.shadow.camera;
    cam.left = -34; cam.right = 34; cam.top = 34; cam.bottom = -34;
    cam.near = 1; cam.far = 90;
    // A low sun grazes every surface, and at a grazing angle the depth
    // written into the shadow map is nearly parallel to the surface it came
    // from - which is where acne comes from. normalBias offsets along the
    // surface normal instead of along the light, so it holds up at sunset
    // where a plain depth bias just erases the shadow it was meant to fix.
    sun.shadow.bias = -0.0006;
    sun.shadow.normalBias = 0.075;
    scene.add(sun);
    scene.add(sun.target);

    // A dim, cool light from behind picks out the edge of a character against
    // the sky. It is what stops a figure sinking into the background.
    rim = new THREE.DirectionalLight(0xFF9C5C, 0.55);
    rim.position.set(-12, 9, -14);
    scene.add(rim);

    worldGroup = new THREE.Group();
    scene.add(worldGroup);
    applyMap(mapId || "village");

    // One authoritative pass now that both the renderer and the camera exist.
    resize();
    addEventListener("resize", resize, { passive: true });
    addEventListener("orientationchange", resize, { passive: true });
    // iOS moves the visual viewport without ever firing a window resize - the
    // URL bar collapsing on scroll, the keyboard opening under the say bar.
    if (window.visualViewport){
      visualViewport.addEventListener("resize", resize, { passive: true });
    }
    // And a last resort for the cases none of those cover: if the canvas box
    // ever stops matching the buffer, notice within a frame rather than
    // leaving the picture the wrong size until something else happens.
    if (window.ResizeObserver){
      new ResizeObserver(resize).observe(canvas);
    }
    renderer.setAnimationLoop(frame);
  }

  /* Size from the canvas, not from the window.

     innerWidth and innerHeight describe the window; what the picture has to
     match is the box the canvas is actually laid out in, and on a phone those
     are not the same thing - browser chrome, safe-area insets and a visual
     viewport that moves when the keyboard opens all sit between them. Reading
     the element's own client box makes the render buffer and the display box
     the same by construction, whatever CSS decides.

     updateStyle stays false because the stylesheet owns the layout. That is
     only safe now that the stylesheet actually sets a width and a height; it
     was not before, and the picture was drawn at twice the size of the window
     on every device with a retina screen. */
  function resize(){
    if (!renderer) return;
    const el = renderer.domElement;
    const w = el.clientWidth || innerWidth;
    const h = el.clientHeight || innerHeight;
    if (!w || !h) return;
    camera.aspect = w / h;
    camera.updateProjectionMatrix();
    renderer.setSize(w, h, false);
  }

  /* Rebuild the cast when the roster or somebody's Islander changes. */
  function sync(players, islanderMap){
    const seen = new Set();
    players.forEach(p => {
      seen.add(p.pid);
      let rig = avatars.get(p.pid);
      const raw = islanderMap && islanderMap[p.pid];
      // Include the colours, not just the face: changing only a shirt would
      // otherwise leave the old rig standing.
      const stamp = raw ? JSON.stringify(raw) : "none";
      if (rig && rig.stamp !== stamp){
        scene.remove(rig.group);
        avatars.delete(p.pid);
        rig = null;
      }
      if (!rig){
        rig = buildRig(p, raw ? {
          colors: raw,                                  // skin/hair/shirt live on the record
          faceTexture: raw.faceTexture || null
        } : null);
        rig.stamp = stamp;
        avatars.set(p.pid, rig);
      }
      rig.alive = p.alive;
    });
    // Anyone who left the room leaves the island.
    [...avatars.keys()].forEach(pid => {
      if (!seen.has(pid)){
        scene.remove(avatars.get(pid).group);
        avatars.delete(pid);
      }
    });
  }

  /* The movement frame: [pid, x, z, angle, moving, alive, emote] */
  let adoptedSpawn = false;
  let onSpawn = null;

  function applyPositions(rows, selfPid){
    rows.forEach(([pid, x, z, a, m, alive, emote]) => {
      const rig = avatars.get(pid);
      if (!rig) return;
      if (pid === selfPid){
        // Take the server's spawn once, before this player has moved. Without
        // it the local position stays at the origin no matter where the room
        // put you, because self position is otherwise never read back.
        if (!adoptedSpawn && (x || z)){
          adoptedSpawn = true;
          rig.x = rig.tx = x; rig.z = rig.tz = z;
          rig.angle = rig.ta = a;
          if (onSpawn) onSpawn(x, z, a);
        }
        // Your own position stays local, because waiting on a round trip to
        // move is what makes a game feel like a website. The emote does not:
        // the server owns it, and skipping the whole row meant everybody
        // could see your dance except you - the one person who chose it.
        rig.alive = !!alive;
        if (emote && emote !== rig.emote){ rig.emote = emote; rig.emoteT = 0; }
        if (!emote) rig.emote = "";
        return;
      }
      rig.tx = x; rig.tz = z; rig.ta = a;
      rig.moving = !!m;
      rig.alive = !!alive;
      if (emote && emote !== rig.emote){ rig.emote = emote; rig.emoteT = 0; }
      if (!emote) rig.emote = "";
    });
  }

  /* Where the local player is, kept whether or not a rig exists for them yet.

     This used to bail out when the rig was missing, and the camera's only
     other option was to orbit the origin - which is where the monument
     stands. So a player who arrived a frame before their own avatar was built
     got a slow pan around a stone column and no character anywhere on screen.
     The position is always known; the model is what lags. */
  let selfAt = null;

  function setSelf(pid, x, z, angle, moving){
    selfAt = { x, z, angle };
    const rig = avatars.get(pid);
    if (!rig) return;
    rig.x = rig.tx = x; rig.z = rig.tz = z;
    rig.angle = rig.ta = angle;
    rig.moving = moving;
  }

  function setFollow(pid){ followPid = pid; }
  function selfRig(){ return avatars.get(followPid); }

  /* How far the local player has to be pushed to stop standing inside anyone.
     Returns a small nudge rather than hard collision, so crowds stay soft. */
  function separation(pid, x, z){
    let px = 0, pz = 0;
    // Heads are wide, so this has to be comfortably bigger than a body radius
    // or a crowd still reads as one pile with overlapping name tags.
    const MIN = 1.9;
    avatars.forEach((rig, other) => {
      if (other === pid) return;
      const dx = x - rig.x, dz = z - rig.z;
      const d = Math.hypot(dx, dz);
      if (d > 0.0001 && d < MIN){
        const push = (MIN - d) / MIN;
        px += (dx/d) * push;
        pz += (dz/d) * push;
      }
    });
    return [px, pz];
  }

  /* A green ring under whoever is talking. In a deduction game, knowing who
     is speaking matters as much as hearing them. */
  function setSpeaking(map){
    avatars.forEach((rig, pid) => {
      const on = map && map[pid];
      if (!rig.voiceRing){
        const ring = new THREE.Mesh(
          new THREE.RingGeometry(0.72, 0.92, 26),
          new THREE.MeshBasicMaterial({ color: 0x7ED37E, transparent: true, opacity: 0,
                                        side: THREE.DoubleSide })
        );
        ring.rotation.x = -Math.PI/2;
        ring.position.y = 0.05;
        rig.group.add(ring);
        rig.voiceRing = ring;
      }
      const want = on ? 0.9 : 0;
      rig.voiceRing.material.opacity += (want - rig.voiceRing.material.opacity) * 0.25;
      if (on) rig.voiceRing.scale.setScalar(1 + Math.sin(clock * 9) * 0.06);
    });
  }

  function setMarkers(map){
    avatars.forEach((rig, pid) => {
      const on = map && map[pid];
      rig.marker.material.opacity += ((on ? 0.85 : 0) - rig.marker.material.opacity) * 0.25;
    });
  }

  function faceTextureFor(dataUrl){
    return new Promise(resolve => {
      const img = new Image();
      img.onload = () => {
        const tex = new THREE.CanvasTexture(img);
        tex.minFilter = THREE.LinearFilter;
        tex.needsUpdate = true;
        resolve(tex);
      };
      img.onerror = () => resolve(null);
      img.src = dataUrl;
    });
  }

  function flash(hexColor, amount){
    const c = new THREE.Color(hexColor);
    flashColor = { r: c.r, g: c.g, b: c.b };
    flashAmount = amount;
    shakeAmount = Math.min(1, amount);
  }

  function orbit(dx, dy){
    camYaw -= dx * 0.005;
    camPitch = Math.max(0.06, Math.min(1.05, camPitch + dy * 0.004));
  }
  // Down to a shoulder shot, out to the old establishing framing. The default
  // sits near the bottom of that range now, so zoom mostly means "show me
  // more of the square" rather than "let me find my character".
  function zoom(delta){ camDist = Math.max(5.0, Math.min(26, camDist + delta)); }
  function heading(){ return camYaw; }

  /* ------------------------------------------------------------------
     Animation
     ------------------------------------------------------------------ */
  function animateRig(rig, dt){
    // Ease toward the networked position so 7 frames a second look smooth.
    const k = 1 - Math.pow(0.0001, dt);
    rig.x += (rig.tx - rig.x) * k;
    rig.z += (rig.tz - rig.z) * k;
    let da = ((rig.ta - rig.angle + Math.PI * 3) % (Math.PI * 2)) - Math.PI;
    rig.angle += da * Math.min(1, dt * 12);

    rig.group.position.set(rig.x, terrainH(rig.x, rig.z), rig.z);
    rig.group.rotation.y = rig.angle;

    const speed = rig.moving ? 1 : 0;
    rig.phase += dt * (rig.moving ? 9.5 : 2.2);
    const swing = Math.sin(rig.phase);

    // Walk cycle: opposite arm to leg, plus a bob and a slight forward lean.
    rig.legL.rotation.x =  swing * 0.85 * speed;
    rig.legR.rotation.x = -swing * 0.85 * speed;
    rig.armL.rotation.x = -swing * 0.7 * speed;
    rig.armR.rotation.x =  swing * 0.7 * speed;
    // The walk bob rides on top of the ground height, not instead of it.
    rig.group.position.y = terrainH(rig.x, rig.z)
                         + Math.abs(Math.sin(rig.phase)) * 0.07 * speed;
    rig.body.rotation.x = speed * 0.09;

    // Idle: gentle breathing and a slow head sway.
    if (!rig.moving){
      const idle = Math.sin(rig.phase * 0.6);
      rig.body.scale.y = 1 + idle * 0.022;
      // Off the avatar's own head height, not a number typed in when the
      // proportions were different - that hard-coded 1.90 was sinking every
      // idle character's head into its shoulders.
      rig.head.position.y = rig.headY + idle * 0.02;
      rig.head.rotation.z = idle * 0.05;
      rig.armL.rotation.x = idle * 0.1;
      rig.armR.rotation.x = -idle * 0.1;
    } else {
      rig.body.scale.y = 1;
      rig.head.position.y = rig.headY;
      rig.head.rotation.z = 0;
    }

    /* Emotes. Each drives the limbs directly for a few seconds, so they read
       clearly from across a plaza at phone size - big arcs, whole-body motion,
       nothing subtle enough to be lost at that scale. */
    if (rig.emote){
      rig.emoteT += dt;
      const e = rig.emoteT;
      const E = rig.emote;
      const kneeL = rig.legL.userData.knee, kneeR = rig.legR.userData.knee;
      const elbowL = rig.armL.userData.knee, elbowR = rig.armR.userData.knee;

      if (E === "wave"){
        rig.armR.rotation.x = -2.5;
        rig.armR.rotation.z = Math.sin(e * 11) * 0.55 - 0.3;
        rig.head.rotation.z = Math.sin(e * 11) * 0.06;
      }
      else if (E === "cheer"){
        rig.armL.rotation.x = rig.armR.rotation.x = -2.85;
        rig.armL.rotation.z = 0.25; rig.armR.rotation.z = -0.25;
        rig.group.position.y += Math.abs(Math.sin(e * 7)) * 0.34;
      }
      else if (E === "dance"){
        // Hips one way, arms the other, head bobbing on the beat.
        rig.group.rotation.y += Math.sin(e * 6) * 0.55;
        rig.group.position.y += Math.abs(Math.sin(e * 9)) * 0.24;
        rig.armL.rotation.x = -1.7 + Math.sin(e * 9) * 0.95;
        rig.armR.rotation.x = -1.7 - Math.sin(e * 9) * 0.95;
        rig.legL.rotation.x = Math.sin(e * 9) * 0.35;
        rig.legR.rotation.x = -Math.sin(e * 9) * 0.35;
        rig.head.rotation.z = Math.sin(e * 9) * 0.14;
      }
      else if (E === "spin"){
        rig.group.rotation.y += e * 7;
        rig.armL.rotation.z = 1.35; rig.armR.rotation.z = -1.35;
        rig.armL.rotation.x = rig.armR.rotation.x = -0.15;
        rig.group.position.y += Math.abs(Math.sin(e * 5)) * 0.16;
      }
      else if (E === "clap"){
        const swing = Math.abs(Math.sin(e * 10));
        rig.armL.rotation.x = rig.armR.rotation.x = -1.45;
        rig.armL.rotation.z = 0.15 + swing * 0.55;
        rig.armR.rotation.z = -0.15 - swing * 0.55;
        rig.head.rotation.x = -0.08;
      }
      else if (E === "point"){
        rig.armR.rotation.x = -1.55;
        rig.armR.rotation.z = -0.12 + Math.sin(e * 5) * 0.05;
        rig.head.rotation.y = -0.2;
      }
      else if (E === "bow"){
        const hold = e > 1.8 ? Math.max(0, 1 - (e - 1.8) * 2) : Math.min(1, e * 2.2);
        rig.torso.rotation.x = hold * 1.0;
        rig.head.rotation.x = hold * 0.35;
        rig.armL.rotation.x = rig.armR.rotation.x = hold * 0.9;
        rig.group.position.y -= hold * 0.12;
      }
      else if (E === "flex"){
        rig.armL.rotation.z = 1.45; rig.armR.rotation.z = -1.45;
        rig.armL.rotation.x = rig.armR.rotation.x = -0.5;
        const pump = Math.abs(Math.sin(e * 5));
        elbowL.rotation.x = -2.1 - pump * 0.4;
        elbowR.rotation.x = -2.1 - pump * 0.4;
        rig.head.rotation.y = Math.sin(e * 2.5) * 0.28;
      }
      else if (E === "laugh"){
        rig.torso.rotation.x = -0.3 + Math.sin(e * 12) * 0.1;
        rig.head.rotation.x = -0.42 + Math.sin(e * 12) * 0.1;
        rig.armL.rotation.x = rig.armR.rotation.x = -0.9;
        rig.armL.rotation.z = 0.5; rig.armR.rotation.z = -0.5;
        rig.group.position.y += Math.abs(Math.sin(e * 12)) * 0.07;
      }
      else if (E === "think"){
        rig.armR.rotation.x = -2.25;
        rig.armR.rotation.z = -0.62;
        elbowR.rotation.x = -1.2;
        rig.head.rotation.z = 0.2;
        rig.head.rotation.x = 0.12 + Math.sin(e * 1.6) * 0.05;
      }
      else if (E === "sit"){
        rig.group.position.y -= 0.5;
        rig.legL.rotation.x = rig.legR.rotation.x = -1.5;
        kneeL.rotation.x = 1.5; kneeR.rotation.x = 1.5;
        rig.armL.rotation.x = rig.armR.rotation.x = -0.25;
      }
      else if (E === "sleep"){
        rig.group.position.y -= 0.5;
        rig.legL.rotation.x = rig.legR.rotation.x = -1.5;
        kneeL.rotation.x = 1.5; kneeR.rotation.x = 1.5;
        rig.head.rotation.z = 0.55;
        rig.head.rotation.x = 0.25;
        rig.torso.rotation.x = 0.18 + Math.sin(e * 1.4) * 0.05;   // slow breathing
      }
      else if (E === "robot"){
        // Deliberately stepped rather than smooth: it should look mechanical.
        const step = Math.floor(e * 5) % 2;
        rig.armL.rotation.x = step ? -1.6 : -0.2;
        rig.armR.rotation.x = step ? -0.2 : -1.6;
        elbowL.rotation.x = -1.5; elbowR.rotation.x = -1.5;
        rig.head.rotation.y = (step ? 1 : -1) * 0.32;
      }
      else if (E === "wiggle"){
        rig.group.rotation.y += Math.sin(e * 12) * 0.22;
        rig.torso.rotation.z = Math.sin(e * 12) * 0.18;
        rig.armL.rotation.z = 0.9 + Math.sin(e * 12) * 0.3;
        rig.armR.rotation.z = -0.9 + Math.sin(e * 12) * 0.3;
        rig.head.rotation.z = -Math.sin(e * 12) * 0.16;
      }
      else if (E === "shrug"){
        rig.armL.rotation.z = 0.95; rig.armR.rotation.z = -0.95;
        rig.armL.rotation.x = rig.armR.rotation.x = -0.55;
        rig.head.rotation.z = Math.sin(e * 2) * 0.1;
      }

      if (e > 3.4){
        rig.emote = "";
        // Put back anything an emote bent, or the pose sticks.
        rig.torso.rotation.set(0, 0, 0);
        rig.head.rotation.set(0, 0, 0);
        kneeL.rotation.x = kneeR.rotation.x = 0;
        elbowL.rotation.x = elbowR.rotation.x = 0;
      }
    } else {
      rig.armL.rotation.z = rig.armR.rotation.z = 0;
    }

    // The dead drift as translucent spirits, and stop casting a shadow.
    const wantGhost = !rig.alive;
    if (wantGhost !== rig.ghost){
      rig.ghost = wantGhost;
      rig.group.traverse(o => {
        if (o.material && o.material !== rig.tag.material){
          o.material.transparent = true;
          o.material.opacity = wantGhost ? 0.42 : 1;
        }
      });
      rig.shadow.visible = !wantGhost;
    }
    if (wantGhost) rig.group.position.y += 0.35 + Math.sin(clock * 1.6 + rig.phase) * 0.12;
  }

  /* Emote showcase.

     Buying a dance you never see is pointless, which is why every game with
     emotes swings the camera round for them. Behind-the-shoulder is right for
     walking and wrong for dancing: the emote plays into the back of your own
     head.

     While the followed player is emoting the camera eases in and round to a
     three-quarter front view, then eases back. camYaw itself is never touched
     - the offset is applied on top - so the shot the player set up by dragging
     is exactly the shot they get back when the emote ends. */
  // Closer for an emote. Diving in used to fill the screen with the top of a
  // cap and an elbow, but that was from a low over-the-shoulder start; from a
  // tilted-down angle aimed at mid-body, seven units puts the whole figure at
  // 38% of the screen with the feet still in frame. Which is the point: you
  // paid for the dance, you should be able to see the dance.
  const EMOTE_CAM = { blend: 0, dist: 7.0, pitch: 0.40, orbit: 0, eye: 1.50 };
  // Everyone spawns on a ring facing the middle, and the monument is the
  // middle - so swinging the camera round to a character's front drove it
  // straight inside the stone. A slow orbit from wherever the camera already
  // is keeps the same radius from the player and cannot cross the plaza.
  const EMOTE_ORBIT_RATE = 0.55;   // radians a second
  const EMOTE_ORBIT_MAX  = 0.95;
  // The monument is the one thing standing in the middle of the square, so
  // rather than general collision the camera simply never comes closer to the
  // centre than its steps.
  const PLAZA_KEEPOUT = 3.6;
  // How long the character has been off frame, and who to tell if it happens.
  let driftFor = 0;
  let onDrift = null;
  /* What the camera is allowed to be blocked by.

     Raycasting the world was the obvious version and wrong twice over. A
     grove is sixty trees of a dozen meshes each, so it walked seven hundred
     objects every frame to answer a question about walls; and it needed those
     meshes to still exist, which stops the scenery ever being merged into
     batches.

     So the blockers are not meshes at all - they are upright cylinders, one
     per solid thing, tested analytically. Sixty cheap tests, no raycaster,
     and it survives baking. It is also the more correct answer: a camera
     should not be shoved forward by a leaf cluster it can see straight
     past. */
  let blockers = [];
  function blocker(x, z, r, h, baseY){
    blockers.push({ x, z, r, h, y: baseY === undefined ? terrainH(x, z) : baseY });
  }

  /* Distance along a ray, from a point, to the first solid thing.

     The 2D quadratic is the ray against an infinite vertical cylinder; the
     height check then throws away hits that pass over the roof or under the
     branches. Returns Infinity when the way is clear. */
  function firstBlocker(ox, oy, oz, dx, dy, dz, maxT){
    let best = Infinity;
    for (let i = 0; i < blockers.length; i++){
      const b = blockers[i];
      const px = ox - b.x, pz = oz - b.z;
      const a = dx*dx + dz*dz;
      if (a < 1e-6) continue;                      // straight up: nothing to hit
      const hb = px*dx + pz*dz;
      const c = px*px + pz*pz - b.r*b.r;
      const disc = hb*hb - a*c;
      if (disc <= 0) continue;
      const sq = Math.sqrt(disc);
      // The near root, unless we start inside - then the camera is already
      // past it and pulling in would make things worse, not better.
      let t = (-hb - sq) / a;
      if (t <= 0.9 || t >= maxT || t >= best) continue;
      const y = oy + dy * t;
      if (y < b.y || y > b.y + b.h) continue;
      best = t;
    }
    return best;
  }

  function updateCamera(dt){
    // The rig if there is one, the last known self position if there is not.
    // Only with neither - genuinely nobody in the world - does the camera fall
    // back to the establishing shot.
    const me = avatars.get(followPid) || selfAt;
    const target = me
      ? new THREE.Vector3(me.x, terrainH(me.x, me.z) + EYE_HEIGHT, me.z)
      : new THREE.Vector3(0, 2.2, 0);

    if (!me){
      // Nobody to follow yet: drift around the monument.
      camYaw += dt * 0.09;
    }

    // Ease in fast enough to catch the start of the emote, out slowly enough
    // that it does not snap.
    const emoting = !!(me && me.emote);
    const rate = emoting ? 3.4 : 1.9;
    EMOTE_CAM.blend += ((emoting ? 1 : 0) - EMOTE_CAM.blend) * Math.min(1, dt * rate);
    const k = EMOTE_CAM.blend;
    EMOTE_CAM.orbit = emoting
      ? Math.min(EMOTE_ORBIT_MAX, EMOTE_CAM.orbit + dt * EMOTE_ORBIT_RATE)
      : Math.max(0, EMOTE_CAM.orbit - dt * EMOTE_ORBIT_RATE * 1.6);

    let d = me ? camDist : 17;
    let p = me ? camPitch : 0.42;
    let yaw = camYaw;

    if (me && k > 0.001){
      d += (EMOTE_CAM.dist - d) * k;
      p += (EMOTE_CAM.pitch - p) * k;
      target.y += (terrainH(me.x, me.z) + EMOTE_CAM.eye - target.y) * k;
      yaw = camYaw + EMOTE_CAM.orbit * k;
    }

    // Shift camera and aim point together along the camera's own right, which
    // slides the character off-centre without turning the view. Eased out
    // during an emote, because a showcase wants them middle of frame.
    const shoulder = SHOULDER * (me ? 1 - k : 0);
    const rx = Math.cos(yaw) * shoulder;
    const rz = -Math.sin(yaw) * shoulder;
    target.x += rx; target.z += rz;

    const want = new THREE.Vector3(
      target.x + Math.sin(yaw) * Math.cos(p) * d,
      target.y + Math.sin(p) * d,
      target.z + Math.cos(yaw) * Math.cos(p) * d
    );
    // Never let the camera drop below the ground.
    // Never let the camera drop through a hill.
    want.y = Math.max(terrainH(want.x, want.z) + 1.4, want.y);

    // ...nor stand inside the monument.
    const fromCentre = Math.hypot(want.x, want.z);
    if (fromCentre < PLAZA_KEEPOUT && fromCentre > 0.001){
      const push = PLAZA_KEEPOUT / fromCentre;
      want.x *= push; want.z *= push;
    }

    /* Nor behind a house.

       Terrain and the monument were handled; everything else was not, so a
       palm or a wall between the camera and the player hid the player
       completely and there was nothing the player could do about it except
       walk away. Cast from the character out towards where the camera wants
       to be, and if scenery is in the way, stop short of it.

       Once a frame, against scenery only - characters never push the camera,
       or standing in a crowd would shove it into your own face. */
    const back = want.clone().sub(target);
    const backLen = back.length();
    if (backLen > 0.01){
      back.divideScalar(backLen);
      const near = firstBlocker(target.x, target.y, target.z, back.x, back.y, back.z, backLen);
      if (near < backLen){
        // A margin so the near plane does not eat the wall we stopped at.
        const d2 = Math.max(2.2, near - 0.45);
        want.copy(target).addScaledVector(back, d2);
        want.y = Math.max(terrainH(want.x, want.z) + 1.0, want.y);
      }
    }

    // Snapping out from behind an obstruction should be quicker than easing
    // in behind one, or the character stays hidden for half a second every
    // time you round a corner.
    camera.position.lerp(want, 1 - Math.pow(0.0005, dt));
    const s = shakeAmount * shakeAmount;
    camera.position.x += (Math.random()-0.5) * s * 0.5;
    camera.position.y += (Math.random()-0.5) * s * 0.5;
    camera.lookAt(target);

    /* The watchdog.

       lookAt puts the target dead centre, so arithmetically the player cannot
       drift off frame - and yet a player sent a screenshot of themselves in
       the bottom right corner with the camera pointed at empty paving. I could
       not reproduce it: the same build, driven the same way, measures 50/50
       idle and walking. Which means the cause is something I have not thought
       of, and a fix aimed at a cause I cannot name would be a guess.

       So this checks the outcome instead. Where the character actually lands
       on screen is measurable every frame; if it sits more than a quarter of
       the screen off centre for three quarters of a second, something has gone
       wrong whatever it was, and the camera snaps back to where it belongs.
       Half a second of drift beats a game that has quietly lost you. */
    if (me && me.group){
      camera.updateMatrixWorld();
      const p = new THREE.Vector3(target.x, target.y, target.z).project(camera);
      const off = Math.max(Math.abs(p.x), Math.abs(p.y));
      // Behind the camera projects to nonsense, and that counts as lost too.
      const behind = p.z > 1;
      if (off > 0.5 || behind){
        driftFor += dt;
        if (driftFor > 0.75){
          camera.position.copy(want);
          camera.lookAt(target);
          driftFor = 0;
          if (onDrift) onDrift(off, behind);
        }
      } else {
        driftFor = 0;
      }
    }

    // Follow the action with the shadow frustum, or distant players lose theirs.
    if (sun){
      sun.position.set(target.x + MAP.sun[2][0], MAP.sun[2][1], target.z + MAP.sun[2][2]);
      sun.target.position.set(target.x, 0, target.z);
      sun.target.updateMatrixWorld();
    }
  }

  /* Flicker and drift. Both are small, and both are the difference between a
     night scene and a daytime scene with the brightness turned down. */
  function animateNight(dt){
    for (let i = 0; i < lanternBulbs.length; i++){
      const b = lanternBulbs[i];
      // Uneven periods per lantern, or eight lamps pulse in unison and the
      // square reads as one machine.
      const f = 0.92 + Math.sin(clock * (2.1 + i * 0.37) + i) * 0.05
                     + Math.sin(clock * (7.3 + i * 0.11)) * 0.03;
      b.scale.setScalar(f);
    }
    if (fireflyPts){
      const pos = fireflyPts.geometry.attributes.position;
      const seed = fireflyPts.userData.seed;
      const n = pos.count;
      for (let i = 0; i < n; i++){
        const hx = seed[i*3], hz = seed[i*3+1], ph = seed[i*3+2];
        // A slow lissajous around a fixed home, so they wander without ever
        // drifting off the island.
        const x = hx + Math.sin(clock * 0.34 + ph) * 1.5;
        const z = hz + Math.cos(clock * 0.27 + ph * 1.7) * 1.5;
        pos.setXYZ(i, x,
          terrainH(x, z) + 1.0 + Math.sin(clock * 0.6 + ph * 2.3) * 0.55, z);
      }
      pos.needsUpdate = true;
      // The whole swarm breathes, which reads as individual blinking without
      // costing a per-point attribute update.
      fireflyPts.material.opacity = 0.72 + Math.sin(clock * 1.7) * 0.22;
      fireflyPts.material.transparent = true;
    }
  }

  /* You, specifically.

     Two jobs, and the second is why it exists at night. A ring on the ground
     answers "which one am I" in a crowd of eight Islanders wearing the same
     kind of clothes, and a soft warm light overhead keeps your own character
     readable after dark, when the sun that used to light everyone is a strip
     of orange on the horizon. It travels with you rather than with the world,
     so it costs one light no matter how big the island gets. */
  let selfMark = null;

  /* The "you" marker.

     A ring on the floor is fine until you are in a crowd, at which point it is
     under somebody's feet and you cannot tell whose. What works is something
     in the air above the heads that moves, so the eye finds it before it has
     finished reading the scene.

     It was a green diamond, and a green diamond floating over the character
     you control is The Sims' plumbob - close enough to theirs to be a problem
     rather than a reference. So it is a downward chevron in the island's own
     gold instead: an arrow pointing at a thing is about as generic as game UI
     gets, and it says "this one" more directly than a gem does.

     Unlit and drawn last with the depth test off, so it stays visible through
     a tree or a wall. Losing sight of the marker whose entire job is telling
     you where you are is the one thing it must never do. */
  function buildPlumbob(){
    const g = new THREE.Group();
    /* toneMapped false is the important flag.

       An unlit material still goes through the tone curve by default, and
       this world runs ACES at 0.78 exposure - so a bright green came out a
       washed sage that vanished against the plaster. The marker is UI that
       happens to live in the scene; it should be exactly the colour it is
       set to, whatever the hour of the map. */
    /* toneMapped false is the important flag.

       An unlit material still goes through the tone curve by default, and
       this world runs ACES at 0.78 exposure - so a bright colour came out a
       washed pastel that vanished against the plaster. The marker is UI that
       happens to live in the scene; it should be exactly the colour it is set
       to, whatever the hour of the map. */
    const mat = new THREE.MeshBasicMaterial({
      color: 0xFFC23D, depthTest: false, depthWrite: false, toneMapped: false
    });
    // A chevron: a flat triangular blade pointing down, given a little depth
    // by a second blade behind it so it turns rather than flickering edge-on.
    const blade = () => {
      const sh = new THREE.Shape();
      sh.moveTo(0, -0.34);
      sh.lineTo(0.30, 0.20);
      sh.lineTo(0.13, 0.20);
      sh.lineTo(0, -0.06);
      sh.lineTo(-0.13, 0.20);
      sh.lineTo(-0.30, 0.20);
      sh.closePath();
      return new THREE.ShapeGeometry(sh);
    };
    const front = new THREE.Mesh(blade(), mat);
    const back = new THREE.Mesh(blade(), mat);
    back.rotation.y = Math.PI / 2;
    g.add(front); g.add(back);
    // A darker copy a hair larger behind it: an outline. The marker has to
    // hold up against a pale wall as well as a dark tree, and a solid colour
    // alone can only manage one of those.
    const edgeMat = new THREE.MeshBasicMaterial({
      color: 0x4A2E05, depthTest: false, depthWrite: false, toneMapped: false,
      side: THREE.DoubleSide
    });
    [0, Math.PI / 2].forEach(rot => {
      const e = new THREE.Mesh(blade(), edgeMat);
      e.rotation.y = rot;
      e.scale.setScalar(1.18);
      e.position.z = rot === 0 ? -0.002 : 0;
      g.add(e);
    });
    g.renderOrder = 999;
    g.traverse(o => { o.renderOrder = 999; });
    // Sized against the character rather than in the abstract: about a fifth
    // of an Islander's height, small enough that eight on screen at once is
    // not a hedge of arrows.
    g.scale.setScalar(0.80);
    return g;
  }

  function updateSelfMark(dt){
    const me = avatars.get(followPid) || selfAt;
    if (!selfMark){
      selfMark = new THREE.Group();
      const ring = new THREE.Mesh(
        new THREE.RingGeometry(0.62, 0.80, 32),
        new THREE.MeshBasicMaterial({ color: 0x7FD4FF, transparent: true,
                                      opacity: 0.55, side: THREE.DoubleSide,
                                      depthWrite: false })
      );
      ring.rotation.x = -Math.PI/2;
      ring.position.y = 0.06;
      ring.renderOrder = 2;
      selfMark.add(ring);
      selfMark.userData.ring = ring;
      const key = new THREE.PointLight(0xFFE0B4, 1.5, 6.5, 2);
      key.position.y = 3.4;
      selfMark.add(key);
      selfMark.userData.key = key;
      const bob = buildPlumbob();
      selfMark.add(bob);
      selfMark.userData.bob = bob;
      scene.add(selfMark);
    }
    selfMark.visible = !!me;
    if (!me) return;
    selfMark.position.set(me.x, terrainH(me.x, me.z), me.z);
    const r = selfMark.userData.ring;
    r.scale.setScalar(1 + Math.sin(clock * 2.2) * 0.045);
    r.material.opacity = 0.42 + Math.sin(clock * 2.2) * 0.10;
    // Sits just above the name tag, which is at 3.32 and rises a little per
    // seat so a crowd's labels do not overlap. Turning slowly and bobbing;
    // both are there to be caught by peripheral vision rather than looked for.
    const bob = selfMark.userData.bob;
    bob.position.y = 4.02 + Math.sin(clock * 1.6) * 0.06;
    bob.rotation.y = clock * 1.15;
  }

  function frame(){
    const now = performance.now();
    const dt = Math.min(0.05, (now - lastFrame)/1000);
    lastFrame = now;
    clock += dt;

    fpsAvg = fpsAvg * 0.94 + (1/Math.max(dt, 0.001)) * 0.06;
    if (fpsAvg < 32 && quality > 1){ quality = 1; renderer.setPixelRatio(1); }

    if (monumentSpindle){
      monumentSpindle.rotation.y = clock * 0.6;
      monumentSpindle.position.y = 4.95 + Math.sin(clock * 1.4) * 0.09;
    }
    animateNight(dt);
    updateSelfMark(dt);

    avatars.forEach(rig => {
      animateRig(rig, dt);
      if (rig.bubble){
        // Hold for six seconds, then fade over one.
        const age = clock - rig.bubbleAt;
        const fade = age < 6 ? 1 : Math.max(0, 1 - (age - 6));
        rig.bubble.material.opacity = fade;
        if (fade <= 0){
          rig.group.remove(rig.bubble);
          rig.bubble.material.map.dispose();
          rig.bubble = null;
        }
      }
    });
    updateCamera(dt);

    shakeAmount = Math.max(0, shakeAmount - dt * 2.2);
    flashAmount = Math.max(0, flashAmount - dt * 1.6);

    // The flash is painted by the DOM layer, which is cheaper than a pass.
    const el = document.getElementById("flash");
    if (el){
      el.style.opacity = String(flashAmount * 0.62);
      el.style.background =
        `rgb(${flashColor.r*255|0},${flashColor.g*255|0},${flashColor.b*255|0})`;
    }

    renderer.render(scene, camera);
  }

  return {
    init, sync, applyPositions, setSelf, setFollow, selfRig, setMarkers,
    onSpawn(fn){ onSpawn = fn; },
    camera: () => camera,     // for framing checks
    renderer: () => renderer, // for draw-call and frame-time budgets
    rigs: () => avatars,      // for checking who has a speech bubble up
    faceTextureFor, flash, orbit, zoom, heading, separation, setSpeaking, say,
    // Every third-person game has one, and it is the answer to any framing
    // problem the player hits that nobody has diagnosed yet.
    recentre(){ camPitch = 0.44; camDist = 9.0; driftFor = 0; },
    onDrift(fn){ onDrift = fn; },
    applyMap, currentMap,
    // Exposed for the tile inspector: judging a repeating texture from a
    // screenshot of a field is guesswork, and the tile itself is the evidence.
    TEXTURE: (name) => (TEX[name] ? TEX[name]() : null),
    VILLAGE_RADIUS
  };
})();
