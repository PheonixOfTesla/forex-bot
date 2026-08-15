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
      ground: "grass", ring: "dirt",
      houses: 14, trees: 26, palms: 0, rocks: 4, ferns: 0
    },
    grove: {
      name: "Kanu Grove",
      sky:  [0x2E7FA8, 0x86BFC4],
      fog:  [0x9FB894, 22, 78],          // closer fog: you cannot see far in a grove
      sun:  [0xE8F0C0, 0.82, [10, 24, -6]],
      sky_light: [0xA8C8B0, 0x6E7A46, 0.66],
      ground: "grass", ring: "dirt",
      houses: 4, trees: 60, palms: 6, rocks: 12, ferns: 40
    },
    bay: {
      name: "Halehua Bay",
      sky:  [0x59B4DC, 0xC8E6EE],
      fog:  [0xD8E6E4, 46, 140],         // open water, long sightlines
      sun:  [0xFFF6DA, 1.12, [18, 20, 14]],
      sky_light: [0xCFE8F2, 0xC8B482, 0.86],
      ground: "sand", ring: "sand",
      houses: 8, trees: 6, palms: 22, rocks: 8, ferns: 0
    }
  };
  let MAP = MAPS.village;

  const ISLAND_RADIUS  = 30;
  const VILLAGE_RADIUS = 26;

  let renderer, scene, camera, sun, hemi;
  let toonGradient = null;
  let avatars = new Map();       // pid -> rig
  let clock = 0;
  let quality = 1, fpsAvg = 60, lastFrame = performance.now();
  let camYaw = 0, camPitch = 0.30, camDist = 11.0;
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

  function makeTex(key, draw, repeat){
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
    texCache[key] = t;
    return t;
  }

  /* Speckled noise, the workhorse for ground surfaces. */
  function speckle(base, spots, density){
    return (g, S) => {
      g.fillStyle = base; g.fillRect(0, 0, S, S);
      for (let i = 0; i < density; i++){
        g.fillStyle = spots[(Math.random() * spots.length) | 0];
        const x = Math.random() * S, y = Math.random() * S;
        const w = 1 + Math.random() * 3;
        g.fillRect(x, y, w, 1 + Math.random() * 2);
      }
    };
  }

  const TEX = {
    grass: () => makeTex("grass", speckle("#6E8F3C", ["#7FA349","#5D7B33","#87AC55","#4F6B2C"], 4200), 28),
    dirt:  () => makeTex("dirt",  speckle("#B39B63", ["#C4AC73","#9C8452","#CBB682"], 3200), 10),
    sand:  () => makeTex("sand",  speckle("#D9C88C", ["#E4D69F","#C8B478"], 2800), 22),
    stone: () => makeTex("stone", speckle("#C6BFAC", ["#D3CCBA","#AFA792","#DAD4C4"], 2400), 6),
    plaster: () => makeTex("plaster", speckle("#DCD3BE", ["#E6DECB","#CFC5AE"], 1400), 2),
    roof: () => makeTex("roof", (g,S)=>{
      g.fillStyle = "#B4573A"; g.fillRect(0,0,S,S);
      // overlapping tile courses
      for (let y = 0; y < S; y += 26){
        g.fillStyle = "#9C4830"; g.fillRect(0, y, S, 1);
        for (let x = (y/26 % 2) * 20; x < S; x += 40){
          g.fillStyle = "#C4634A"; g.fillRect(x, y + 3, 34, 20);
        }
      }
    }, 3),
    bark: () => makeTex("bark", (g,S)=>{
      g.fillStyle = "#6E4E30"; g.fillRect(0,0,S,S);
      for (let i = 0; i < 150; i++){
        g.fillStyle = ["#5B3F26","#7E5B39","#4E3520"][(Math.random()*3)|0];
        g.fillRect(Math.random()*S, 0, 2 + Math.random()*6, S);   // vertical grain
      }
    }, 2),
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
    return new THREE.MeshLambertMaterial(
      Object.assign({ color }, opts || {}));
  }

  /* Textured surface. The colour still tints it, so one texture serves several
     materials without redrawing the canvas. */
  function surf(texFn, tint){
    return new THREE.MeshLambertMaterial({ map: texFn(), color: tint || 0xffffff });
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

    // Beach, then grass, then the paved square in the middle.
    const beach = new THREE.Mesh(new THREE.CircleGeometry(ISLAND_RADIUS + 3.5, 56), surf(TEX.sand));
    beach.receiveShadow = true;
    beach.rotation.x = -Math.PI/2;
    beach.position.y = -0.34;
    worldGroup.add(beach);

    const grass = new THREE.Mesh(new THREE.CircleGeometry(ISLAND_RADIUS - 1.5, 56), surf(TEX.grass));
    grass.receiveShadow = true;
    grass.rotation.x = -Math.PI/2;
    grass.position.y = -0.12;
    worldGroup.add(grass);

    const plaza = new THREE.Mesh(new THREE.CircleGeometry(11, 40), surf(TEX.dirt));
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
      const roof = new THREE.Mesh(new THREE.ConeGeometry(w * 0.78, 1.15, 4), surf(TEX.roof));
      roof.position.y = h + 0.55;
      roof.rotation.y = Math.PI/4;
      g.add(roof);
    }

    // A door and a window, so the scale reads as a building.
    const door = new THREE.Mesh(new THREE.PlaneGeometry(0.62, 1.15), toon(0x4A6FA0));
    door.position.set(0, 0.58, d/2 + 0.01);
    g.add(door);
    const win = new THREE.Mesh(new THREE.PlaneGeometry(0.5, 0.5), toon(0x7FB4D8));
    win.position.set(w * 0.28, h * 0.66, d/2 + 0.01);
    g.add(win);

    g.position.set(x, 0, z);
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
    g.position.set(x, 0, z);
    worldGroup.add(g);
  }

  /* The nightfall monument in the middle of the square - the game's namesake,
     and the thing everyone gathers around to vote. */
  /* A ring of hills well beyond the island. They sit inside the fog, so they
     read as distance rather than as geometry, which is the trick the console
     used to make a small world feel like a big one. */
  function buildHorizon(){
    const rand = seeded(90210);
    for (let i = 0; i < 22; i++){
      const a = (i / 22) * Math.PI * 2 + rand() * 0.18;
      const dist = 78 + rand() * 26;
      const h = 9 + rand() * 16;
      const hill = new THREE.Mesh(
        new THREE.ConeGeometry(11 + rand() * 13, h, 9),
        new THREE.MeshLambertMaterial({ color: new THREE.Color(0x6E8F3C).lerp(new THREE.Color(0xBFD0B4), 0.45) })
      );
      hill.position.set(Math.cos(a) * dist, h * 0.5 - 3, Math.sin(a) * dist);
      hill.rotation.y = rand() * Math.PI;
      worldGroup.add(hill);
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
    g.position.set(x, 0, z);
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
    g.position.set(x, 0, z);
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
    tag.position.y = 2.95 + ((player.seat || 0) % 4) * 0.32;
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
      group: rig, avatar: a, head: a.head, body: a.torso, tag, marker, shadow,
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
  function applyPositions(rows, selfPid){
    rows.forEach(([pid, x, z, a, m, alive, emote]) => {
      const rig = avatars.get(pid);
      if (!rig) return;
      if (pid === selfPid) return;          // your own body is driven locally
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
  function zoom(delta){ camDist = Math.max(4.5, Math.min(16, camDist + delta)); }
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

    rig.group.position.set(rig.x, 0, rig.z);
    rig.group.rotation.y = rig.angle;

    const speed = rig.moving ? 1 : 0;
    rig.phase += dt * (rig.moving ? 9.5 : 2.2);
    const swing = Math.sin(rig.phase);

    // Walk cycle: opposite arm to leg, plus a bob and a slight forward lean.
    rig.legL.rotation.x =  swing * 0.85 * speed;
    rig.legR.rotation.x = -swing * 0.85 * speed;
    rig.armL.rotation.x = -swing * 0.7 * speed;
    rig.armR.rotation.x =  swing * 0.7 * speed;
    rig.group.position.y = Math.abs(Math.sin(rig.phase)) * 0.07 * speed;
    rig.body.rotation.x = speed * 0.09;

    // Idle: gentle breathing and a slow head sway.
    if (!rig.moving){
      const idle = Math.sin(rig.phase * 0.6);
      rig.body.scale.y = 1 + idle * 0.022;
      rig.head.position.y = 1.90 + idle * 0.02;
      rig.head.rotation.z = idle * 0.05;
      rig.armL.rotation.x = idle * 0.1;
      rig.armR.rotation.x = -idle * 0.1;
    } else {
      rig.body.scale.y = 1;
      rig.head.position.y = 1.90;
      rig.head.rotation.z = 0;
    }

    // Emotes override the arms for a couple of seconds.
    if (rig.emote){
      rig.emoteT += dt;
      const e = rig.emoteT;
      if (rig.emote === "wave"){
        rig.armR.rotation.x = -2.5;
        rig.armR.rotation.z = Math.sin(e * 11) * 0.5 - 0.3;
      } else if (rig.emote === "cheer"){
        rig.armL.rotation.x = rig.armR.rotation.x = -2.8;
        rig.group.position.y += Math.abs(Math.sin(e * 7)) * 0.28;
      } else if (rig.emote === "dance"){
        rig.group.rotation.y += Math.sin(e * 6) * 0.5;
        rig.group.position.y += Math.abs(Math.sin(e * 9)) * 0.22;
        rig.armL.rotation.x = -1.7 + Math.sin(e * 9) * 0.9;
        rig.armR.rotation.x = -1.7 - Math.sin(e * 9) * 0.9;
      } else if (rig.emote === "point"){
        rig.armR.rotation.x = -1.55;
        rig.armR.rotation.z = -0.12;
      } else if (rig.emote === "shrug"){
        rig.armL.rotation.z =  0.9; rig.armR.rotation.z = -0.9;
        rig.armL.rotation.x = -0.5; rig.armR.rotation.x = -0.5;
      } else if (rig.emote === "sit"){
        rig.group.position.y -= 0.42;
        rig.legL.rotation.x = -1.5; rig.legR.rotation.x = -1.5;
      }
      if (e > 3.2) rig.emote = "";
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

  function updateCamera(dt){
    const me = avatars.get(followPid);
    const target = me
      ? new THREE.Vector3(me.x, 1.9, me.z)
      : new THREE.Vector3(0, 2.2, 0);

    if (!me){
      // Nobody to follow yet: drift around the monument.
      camYaw += dt * 0.09;
    }

    const d = me ? camDist : 17;
    const p = me ? camPitch : 0.42;
    const want = new THREE.Vector3(
      target.x + Math.sin(camYaw) * Math.cos(p) * d,
      target.y + Math.sin(p) * d,
      target.z + Math.cos(camYaw) * Math.cos(p) * d
    );
    // Never let the camera drop below the ground.
    want.y = Math.max(1.1, want.y);

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

    avatars.forEach(rig => animateRig(rig, dt));
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
    faceTextureFor, flash, orbit, zoom, heading, separation, setSpeaking,
    applyMap, currentMap,
    VILLAGE_RADIUS
  };
})();
