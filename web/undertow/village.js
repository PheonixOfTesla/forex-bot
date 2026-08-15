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
  const PLAZA     = 0xC9BE92;
  const WHITEWASH = 0xE8E0CE;
  const DOME      = 0x2E6FA8;
  const TERRA     = 0xCF6A47;
  const TRUNK     = 0x7A5636;
  const LEAF      = 0x5E8442;
  const GOLD      = 0xE8A33D;

  /* Three places to play. Same rules everywhere; only the scenery and the
     light change, so a group can run four games without the island going
     stale. Each is seeded, so every device builds the identical world. */
  const MAPS = {
    village: {
      name: "Molua Village",
      sky:  [0x4E9BD4, 0xA6CFE6],
      fog:  [0xC2D6DE, 34, 112],
      sun:  [0xFFF0CC, 1.0, [14, 22, 9]],
      sky_light: [0xBBD6EA, 0xB0A06A, 0.72],
      ground: "grass", ring: "dirt", relief: 1.0,
      houses: 14, trees: 26, palms: 0, rocks: 4, ferns: 0
    },
    grove: {
      name: "Kanu Grove",
      sky:  [0x2E7FA8, 0x86BFC4],
      fog:  [0x9FB894, 22, 78],          // closer fog: you cannot see far in a grove
      sun:  [0xE8F0C0, 0.82, [10, 24, -6]],
      sky_light: [0xA8C8B0, 0x6E7A46, 0.66],
      ground: "grass", ring: "dirt", relief: 1.35,
      houses: 4, trees: 60, palms: 6, rocks: 12, ferns: 40
    },
    bay: {
      name: "Halehua Bay",
      sky:  [0x59B4DC, 0xC8E6EE],
      fog:  [0xD8E6E4, 46, 140],         // open water, long sightlines
      sun:  [0xFFF6DA, 1.12, [18, 20, 14]],
      sky_light: [0xCFE8F2, 0xC8B482, 0.86],
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
  let camYaw = 0, camPitch = 0.22, camDist = 8.0;
  // Measured, not guessed: 0.90 put the body at 28% across, and centre is 50%,
  // so a unit of offset is worth about 24 points. A third of that lands the
  // character near 42% - off centre enough to leave the path ahead clear,
  // not so far that they are hugging the edge of the screen.
  const SHOULDER = 0.34;
  const EYE_HEIGHT = 2.05;    // aim above the waist; the body drops down frame
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
    const size = 256;
    const c = document.createElement("canvas");
    c.width = c.height = size;
    draw(c.getContext("2d"), size);
    const t = new THREE.CanvasTexture(c);
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
  function speckle(base, spots, density){
    return (g, S) => {
      g.fillStyle = base; g.fillRect(0, 0, S, S);
      grain(g, S, spots, density);
    };
  }
  function grain(g, S, spots, density){
    for (let i = 0; i < density; i++){
      g.fillStyle = spots[(Math.random() * spots.length) | 0];
      g.fillRect(Math.random() * S, Math.random() * S,
                 1 + Math.random() * 3, 1 + Math.random() * 2);
    }
  }

  /* Big soft blotches under everything else. A 256px tile repeated 28 times
     across a field reads as a grid unless something breaks the rhythm at a
     scale larger than the eye can pair up. */
  function patches(g, S, colors, count, radius, alpha){
    g.save();
    g.globalAlpha = alpha;
    for (let i = 0; i < count; i++){
      const x = Math.random() * S, y = Math.random() * S;
      const r = radius * (0.6 + Math.random() * 0.8);
      const grd = g.createRadialGradient(x, y, 0, x, y, r);
      const col = colors[(Math.random() * colors.length) | 0];
      grd.addColorStop(0, col);
      grd.addColorStop(1, "rgba(0,0,0,0)");
      g.fillStyle = grd;
      // Drawn four times, wrapped, so a blotch crossing an edge continues on
      // the far side instead of being sliced off at the seam.
      for (const [ox, oy] of [[0,0],[S,0],[0,S],[S,S]]){
        g.beginPath(); g.arc(x - ox, y - oy, r, 0, Math.PI*2); g.fill();
      }
    }
    g.restore();
  }

  const TEX = {
    /* Blades, not noise. Short tapered strokes at varying angles, over
       patches of lighter and darker turf. */
    grass: () => makeTex("grass", (g, S) => {
      g.fillStyle = "#6E8F3C"; g.fillRect(0, 0, S, S);
      patches(g, S, ["#7FA349", "#5A7730", "#87AC55"], 7, S * 0.28, 0.5);
      g.lineCap = "round";
      for (let i = 0; i < 1700; i++){
        const x = Math.random() * S, y = Math.random() * S;
        const a = -Math.PI/2 + (Math.random() - 0.5) * 1.5;
        const len = 2 + Math.random() * 5;
        g.strokeStyle = ["#7FA349","#8CB254","#5D7B33","#4F6B2C","#93B85E"][(Math.random()*5)|0];
        g.lineWidth = 0.8 + Math.random() * 1.1;
        g.beginPath();
        g.moveTo(x, y);
        g.lineTo(x + Math.cos(a) * len, y + Math.sin(a) * len);
        g.stroke();
      }
    }, 24, 2.4),

    /* Trodden earth: compacted patches, loose clods, small stones. */
    dirt: () => makeTex("dirt", (g, S) => {
      g.fillStyle = "#B39B63"; g.fillRect(0, 0, S, S);
      patches(g, S, ["#A28C57", "#C4AC73"], 4, S * 0.26, 0.30);
      for (let i = 0; i < 130; i++){
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
      patches(g, S, ["#E4D69F", "#CDBA7C"], 5, S * 0.34, 0.5);
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

    /* Hand-finished render: broad trowel sweep, then a fine tooth. */
    plaster: () => makeTex("plaster", (g, S) => {
      g.fillStyle = "#DCD3BE"; g.fillRect(0, 0, S, S);
      patches(g, S, ["#E6DECB", "#CFC5AE"], 5, S * 0.4, 0.55);
      g.strokeStyle = "rgba(203,193,170,.34)"; g.lineWidth = 3.5;
      for (let i = 0; i < 14; i++){
        const y = Math.random() * S, a = (Math.random() - 0.5) * 0.5;
        g.beginPath(); g.moveTo(-10, y); g.lineTo(S + 10, y + Math.tan(a) * S); g.stroke();
      }
      grain(g, S, ["#E6DECB","#CFC5AE"], 900);
    }, 2, 1.1),

    roof: () => makeTex("roof", (g,S)=>{
      g.fillStyle = "#B4573A"; g.fillRect(0,0,S,S);
      // overlapping tile courses
      for (let y = 0; y < S; y += 26){
        g.fillStyle = "#9C4830"; g.fillRect(0, y, S, 1);
        for (let x = (y/26 % 2) * 20; x < S; x += 40){
          g.fillStyle = "#C4634A"; g.fillRect(x, y + 3, 34, 20);
        }
      }
    }, 3, 2.6),
    bark: () => makeTex("bark", (g,S)=>{
      g.fillStyle = "#6E4E30"; g.fillRect(0,0,S,S);
      for (let i = 0; i < 150; i++){
        g.fillStyle = ["#5B3F26","#7E5B39","#4E3520"][(Math.random()*3)|0];
        g.fillRect(Math.random()*S, 0, 2 + Math.random()*6, S);   // vertical grain
      }
    }, 2, 2.2),
    leaf: () => makeTex("leaf", speckle("#4F7A33", ["#5E8C3E","#42682A","#6B9A48"], 3200), 3),
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
  function toon(color, opts){
    return new THREE.MeshStandardMaterial(
      Object.assign({ color, roughness: 0.94, metalness: 0.0 }, opts || {}));
  }

  /* Textured surface. The colour still tints it, so one texture serves several
     materials without redrawing the canvas. */
  function surf(texFn, tint, bumpScale){
    const map = texFn();
    const mat = new THREE.MeshStandardMaterial({ map, color: tint || 0xffffff,
                                                 roughness: 0.95, metalness: 0.0 });
    // The relief that came off the same canvas. Kept well under 1 - at full
    // strength procedural bumps read as crumpled foil rather than ground.
    if (map.userData && map.userData.normal){
      mat.normalMap = map.userData.normal;
      const k = bumpScale === undefined ? 0.55 : bumpScale;
      mat.normalScale = new THREE.Vector2(k, k);
    }
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

    buildSky();
    buildIsland();
    scatter();
    buildMonument();
    buildHorizon();
  }

  function currentMap(){ return MAP.name; }

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

  function buildSky(){
    const geo = new THREE.SphereGeometry(180, 24, 16);
    const mat = new THREE.ShaderMaterial({
      side: THREE.BackSide, depthWrite: false, fog: false,
      uniforms: {
        top:    { value: new THREE.Color(SKY_TOP) },
        bottom: { value: new THREE.Color(SKY_BOT) }
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
        uniform vec3 top; uniform vec3 bottom;
        // Cheap value noise, enough for soft cloud banding.
        float hash(vec2 p){ return fract(sin(dot(p, vec2(41.3, 289.1))) * 43758.5453); }
        float noise(vec2 p){
          vec2 i = floor(p), f = fract(p);
          f = f * f * (3.0 - 2.0 * f);
          return mix(mix(hash(i), hash(i + vec2(1,0)), f.x),
                     mix(hash(i + vec2(0,1)), hash(i + vec2(1,1)), f.x), f.y);
        }
        void main(){
          float t = smoothstep(-0.10, 0.30, vH);
          vec3 sky = mix(bottom, top, t);
          // Clouds sit in a band above the horizon and fade out overhead.
          vec2 uv = vDir.xz / max(0.18, vDir.y + 0.35) * 1.4;
          float n = noise(uv * 1.4) * 0.6 + noise(uv * 3.1) * 0.3 + noise(uv * 6.3) * 0.1;
          float cloud = smoothstep(0.52, 0.78, n) * smoothstep(0.02, 0.30, vH) * (1.0 - t * 0.45);
          gl_FragColor = vec4(mix(sky, vec3(0.97, 0.98, 1.0), cloud * 0.85), 1.0);
        }`
    });
    worldGroup.add(new THREE.Mesh(geo, mat));
  }

  function buildIsland(){
    // Sea, out to the horizon.
    const sea = new THREE.Mesh(
      new THREE.CircleGeometry(170, 48),
      new THREE.MeshBasicMaterial({ map: TEX.water() })
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
        new THREE.MeshBasicMaterial({ color: 0xD9C79B, transparent: true, opacity: 0.75 })
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
      const dome = new THREE.Mesh(
        new THREE.SphereGeometry(w * 0.46, 16, 10, 0, Math.PI*2, 0, Math.PI/2), toon(DOME));
      dome.position.y = h;
      g.add(dome);
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
      const hole = new THREE.Mesh(new THREE.BoxGeometry(ow, oh, 0.30),
                                  toon(glass ? 0x6FA6CE : 0x35455C));
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
  }

  function buildTree(rand, x, z){
    const g = new THREE.Group();
    const th = 1.5 + rand() * 1.0;
    const trunk = new THREE.Mesh(new THREE.CylinderGeometry(0.16, 0.24, th, 10), surf(TEX.bark));
    trunk.position.y = th/2;
    trunk.castShadow = true;
    g.add(trunk);
    // A few overlapping blobs make a nicer canopy than one sphere.
    for (let i = 0; i < 3; i++){
      const r = 0.85 + rand() * 0.55;
      const blob = new THREE.Mesh(new THREE.SphereGeometry(r, 16, 12), surf(TEX.leaf));
      blob.position.set((rand()-0.5) * 1.1, th + 0.25 + rand() * 0.6, (rand()-0.5) * 1.1);
      blob.scale.y = 0.82;
      blob.castShadow = true;
      g.add(blob);
    }
    g.position.set(x, terrainH(x, z), z);
    worldGroup.add(g);
  }

  /* The nightfall monument in the middle of the square - the game's namesake,
     and the thing everyone gathers around to vote. */
  /* A ring of hills well beyond the island. They sit inside the fog, so they
     read as distance rather than as geometry, which is the trick the console
     used to make a small world feel like a big one. */
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
        const hill = new THREE.Mesh(
          new THREE.ConeGeometry(rr, h, 10),
          new THREE.MeshStandardMaterial({
            color: new THREE.Color(0x6E8F3C).lerp(new THREE.Color(0x8FA5A0), 0.22 + rand() * 0.16),
            roughness: 1.0, flatShading: true })
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

    const spindle = new THREE.Mesh(new THREE.SphereGeometry(0.46, 18, 14), toon(GOLD));
    spindle.position.y = 4.95;
    g.add(spindle);
    monumentSpindle = spindle;

    worldGroup.add(g);
  }
  let monumentSpindle = null;

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
    // Above the name tag, and stepped per seat so two people talking at once
    // do not stack their bubbles on top of each other.
    sprite.position.y = 3.78 + ((rig.seat || 0) % 3) * 0.42;
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
    renderer.setSize(innerWidth, innerHeight, false);
    renderer.setClearColor(0xC2D6DE, 1);

    maxAniso = renderer.capabilities.getMaxAnisotropy();
    // Characters need this before any of them are built.
    if (window.Avatar && Avatar.environment) Avatar.environment(renderer);

    scene = new THREE.Scene();
    scene.fog = new THREE.Fog(0xC2D6DE, 34, 112);
    camera = new THREE.PerspectiveCamera(58, innerWidth/innerHeight, 0.1, 400);

    // Warm sun from above, cool bounce from the sky and sand.
    hemi = new THREE.HemisphereLight(0xBBD6EA, 0xB0A06A, 0.72);
    scene.add(hemi);
    sun = new THREE.DirectionalLight(0xFFF0CC, 0.95);
    sun.position.set(14, 22, 9);

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
    sun.shadow.bias = -0.0008;
    sun.shadow.normalBias = 0.02;
    scene.add(sun);
    scene.add(sun.target);

    // A dim, cool light from behind picks out the edge of a character against
    // the sky. It is what stops a figure sinking into the background.
    rim = new THREE.DirectionalLight(0xCFE4F5, 0.42);
    rim.position.set(-12, 9, -14);
    scene.add(rim);

    worldGroup = new THREE.Group();
    scene.add(worldGroup);
    applyMap(mapId || "village");

    addEventListener("resize", resize, { passive: true });
    renderer.setAnimationLoop(frame);
  }

  function resize(){
    if (!renderer) return;
    camera.aspect = innerWidth/innerHeight;
    camera.updateProjectionMatrix();
    renderer.setSize(innerWidth, innerHeight, false);
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

  function setSelf(pid, x, z, angle, moving){
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
  function zoom(delta){ camDist = Math.max(4.0, Math.min(14, camDist + delta)); }
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
  // Pull BACK for an emote, not in. Diving closer filled the screen with the
  // top of a cap and an elbow; the point of a showcase is the whole body, so
  // it steps back, lifts a little, and aims at mid-height instead of the
  // chest so head and feet both stay in frame.
  const EMOTE_CAM = { blend: 0, dist: 9.4, pitch: 0.30, orbit: 0, eye: 1.45 };
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

  function updateCamera(dt){
    const me = avatars.get(followPid);
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

    camera.position.lerp(want, 1 - Math.pow(0.0005, dt));
    const s = shakeAmount * shakeAmount;
    camera.position.x += (Math.random()-0.5) * s * 0.5;
    camera.position.y += (Math.random()-0.5) * s * 0.5;
    camera.lookAt(target);

    // Follow the action with the shadow frustum, or distant players lose theirs.
    if (sun){
      sun.position.set(target.x + MAP.sun[2][0], MAP.sun[2][1], target.z + MAP.sun[2][2]);
      sun.target.position.set(target.x, 0, target.z);
      sun.target.updateMatrixWorld();
    }
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
    faceTextureFor, flash, orbit, zoom, heading, separation, setSpeaking, say,
    applyMap, currentMap,
    // Exposed for the tile inspector: judging a repeating texture from a
    // screenshot of a field is guesswork, and the tile itself is the evidence.
    TEXTURE: (name) => (TEX[name] ? TEX[name]() : null),
    VILLAGE_RADIUS
  };
})();
