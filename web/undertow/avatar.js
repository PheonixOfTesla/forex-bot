"use strict";
/* ===========================================================================
   ISLANDER - the avatar system

   A component library rather than a single procedural blob: sculpted hair
   styles, drawn facial features, layered outfits, and a toon outline pass.
   Everything is generated at runtime, so there is nothing to download and
   nothing to license.

   Honest about the ceiling: Bitmoji and Fortnite avatars are hand-authored by
   artists. This is the same *structure* - a parts library driven by a
   customiser - built with geometry instead of art. It gets a long way, and it
   is the right skeleton to drop real artwork into later.

   One config object describes a character completely, so the maker preview and
   the characters walking around the island are built by the same code.
   =========================================================================== */

const Avatar = (() => {

  const INK = 0x2A2333;          // outline and line-art colour

  /* ---------------------------------------------------------------------
     Palettes
     --------------------------------------------------------------------- */
  const SKIN = ["#FFDCBC","#F2C9A0","#E8B187","#C68642","#A9673B","#8D5524","#63391F","#4A2A17"];
  const HAIR = ["#1C1410","#3B2417","#5A3825","#8B5A2B","#B87333","#D9A441","#E8C87A",
                "#B33A3A","#3B5BA5","#2E7D5B","#8E5FA8","#E86FA8","#9AA0A6","#F2EFE6"];
  const CLOTH = ["#E05B4B","#3B82C4","#4CAF6E","#E8A33D","#8E5FA8","#E86FA8","#38B2AC",
                 "#F2F0E6","#3A4657","#C7643C","#6E8E3F","#D64F7A"];
  const PANTS = ["#3A4657","#2F3A46","#5A6B7D","#7A6A55","#31445E","#4A3B52","#8A8175","#2B2438"];
  const SHOES = ["#2B2438","#F2F0E6","#E05B4B","#3B82C4","#7A6A55","#4CAF6E"];

  const HAIR_STYLES = ["crop","buzz","bob","long","ponytail","curls","bun","topknot"];
  const EYE_STYLES  = ["round","almond","wide","happy","sleepy","wink"];
  const BROW_STYLES = ["soft","flat","arched","thick"];
  const MOUTH_STYLES = ["smile","grin","smirk","open","calm"];

  function defaults(){
    const pick = (a) => a[Math.floor(Math.random()*a.length)];
    return {
      skin: pick(SKIN), hair: pick(HAIR), hairStyle: pick(HAIR_STYLES),
      shirt: pick(CLOTH), pants: pick(PANTS), shoes: pick(SHOES),
      eyes: pick(EYE_STYLES), brows: pick(BROW_STYLES), mouth: pick(MOUTH_STYLES),
      glasses: Math.random() < 0.22, face: null,
      hat: true, hatStyle: pick(HAT_STYLES), hatColor: pick(HAT_COLORS),
      costume: pick(COSTUMES),
      brand: "CLOCKWORK HUB"
    };
  }

  /* ---------------------------------------------------------------------
     The face

     Drawn on a transparent canvas holding only the features, so the head mesh
     supplies the skin tone and changing skin never needs a redraw.
     --------------------------------------------------------------------- */
  const S = 512;

  function faceTexture(cfg){
    const c = document.createElement("canvas");
    c.width = c.height = S;
    const g = c.getContext("2d");
    g.clearRect(0, 0, S, S);

    // A photo, if the player supplied one, sits under the drawn features.
    if (cfg.face && cfg.faceImage){
      g.save();
      g.beginPath(); g.arc(S/2, S/2, S/2, 0, Math.PI*2); g.clip();
      g.drawImage(cfg.faceImage, 0, 0, S, S);
      g.restore();
      return finish(c);
    }

    const eyeY = S * 0.455, eyeDx = S * 0.142, eyeR = S * 0.060;
    drawBrows(g, cfg, eyeY - eyeR * 2.5, eyeDx);
    drawEyes(g, cfg, eyeY, eyeDx, eyeR);
    drawNose(g, cfg, eyeY + eyeR * 1.7);
    drawMouth(g, cfg, S * 0.655);
    drawBlush(g, eyeY + eyeR * 1.9, eyeDx * 1.55);
    if (cfg.glasses) drawGlasses(g, eyeY, eyeDx, eyeR);
    return finish(c);
  }

  function finish(canvas){
    const tex = new THREE.CanvasTexture(canvas);
    tex.minFilter = THREE.LinearFilter;
    tex.needsUpdate = true;
    return tex;
  }

  function drawEyes(g, cfg, y, dx, r){
    [-1, 1].forEach(side => {
      const x = S/2 + side * dx;
      const closed = cfg.eyes === "happy" || (cfg.eyes === "wink" && side === 1);

      if (closed){
        // A closed, upturned lash line reads as a smile from across a room.
        g.strokeStyle = "#2A2333";
        g.lineWidth = r * 0.42; g.lineCap = "round";
        g.beginPath();
        g.arc(x, y + r*0.35, r * 0.95, Math.PI * 1.12, Math.PI * 1.88);
        g.stroke();
        return;
      }

      let rx = r, ry = r * 1.12;
      if (cfg.eyes === "almond"){ rx = r * 1.06; ry = r * 0.82; }
      if (cfg.eyes === "wide")  { rx = r * 1.10; ry = r * 1.30; }
      if (cfg.eyes === "sleepy"){ rx = r * 1.02; ry = r * 0.66; }

      // White, iris, pupil, highlight - the four layers that make an eye read.
      g.fillStyle = "#FFFFFF";
      g.beginPath(); g.ellipse(x, y, rx, ry, 0, 0, Math.PI*2); g.fill();

      g.fillStyle = cfg.eyeColor || "#5B4636";
      g.beginPath(); g.ellipse(x, y + ry*0.06, rx*0.62, ry*0.62, 0, 0, Math.PI*2); g.fill();

      g.fillStyle = "#1C1622";
      g.beginPath(); g.ellipse(x, y + ry*0.06, rx*0.34, ry*0.36, 0, 0, Math.PI*2); g.fill();

      g.fillStyle = "rgba(255,255,255,0.95)";
      g.beginPath(); g.ellipse(x - rx*0.26, y - ry*0.32, rx*0.20, ry*0.20, 0, 0, Math.PI*2); g.fill();

      // Lash line across the top, heavier on the outside.
      g.strokeStyle = "#2A2333";
      g.lineWidth = r * 0.20; g.lineCap = "round";
      g.beginPath();
      g.ellipse(x, y, rx, ry, 0, Math.PI * 1.05, Math.PI * 1.95);
      g.stroke();
    });
  }

  function drawBrows(g, cfg, y, dx){
    const w = S * 0.115;
    let thickness = S * 0.020, lift = 0, tilt = 0;
    if (cfg.brows === "thick")  thickness = S * 0.032;
    if (cfg.brows === "arched"){ lift = -S * 0.012; tilt = 0.16; }
    if (cfg.brows === "flat")   tilt = 0;
    else if (cfg.brows === "soft") tilt = 0.09;

    g.strokeStyle = spirit(cfg.hair, -0.18);
    g.lineWidth = thickness; g.lineCap = "round";
    [-1, 1].forEach(side => {
      const x = S/2 + side * dx;
      g.beginPath();
      g.moveTo(x - w/2, y + lift + tilt * w * side * 0.35);
      g.quadraticCurveTo(x, y + lift - w * (cfg.brows === "arched" ? 0.42 : 0.24),
                         x + w/2, y + lift - tilt * w * side * 0.35);
      g.stroke();
    });
  }

  function drawNose(g, cfg, y){
    g.strokeStyle = "rgba(90,60,45,0.45)";
    g.lineWidth = S * 0.013; g.lineCap = "round";
    g.beginPath();
    g.moveTo(S/2 - S*0.012, y);
    g.quadraticCurveTo(S/2 + S*0.016, y + S*0.030, S/2 - S*0.006, y + S*0.040);
    g.stroke();
  }

  function drawMouth(g, cfg, y){
    g.lineCap = "round"; g.lineJoin = "round";
    const w = S * 0.115;

    if (cfg.mouth === "open"){
      g.fillStyle = "#8E3B3B";
      g.beginPath(); g.ellipse(S/2, y + S*0.012, w*0.72, S*0.052, 0, 0, Math.PI*2); g.fill();
      g.fillStyle = "#FFFFFF";
      g.beginPath();
      g.ellipse(S/2, y - S*0.028, w*0.62, S*0.020, 0, 0, Math.PI*2);
      g.fill();
      return;
    }
    if (cfg.mouth === "grin"){
      g.fillStyle = "#FFFFFF";
      g.strokeStyle = "#2A2333"; g.lineWidth = S*0.016;
      g.beginPath();
      g.moveTo(S/2 - w, y - S*0.010);
      g.quadraticCurveTo(S/2, y + S*0.062, S/2 + w, y - S*0.010);
      g.closePath(); g.fill(); g.stroke();
      return;
    }
    g.strokeStyle = "#7A3B32";
    g.lineWidth = S * 0.019;
    g.beginPath();
    if (cfg.mouth === "smirk"){
      g.moveTo(S/2 - w*0.75, y);
      g.quadraticCurveTo(S/2, y + S*0.030, S/2 + w*0.95, y - S*0.018);
    } else if (cfg.mouth === "calm"){
      g.moveTo(S/2 - w*0.6, y);
      g.quadraticCurveTo(S/2, y + S*0.012, S/2 + w*0.6, y);
    } else {
      g.moveTo(S/2 - w*0.85, y - S*0.008);
      g.quadraticCurveTo(S/2, y + S*0.055, S/2 + w*0.85, y - S*0.008);
    }
    g.stroke();
  }

  function drawBlush(g, y, dx){
    g.fillStyle = "rgba(228,110,105,0.26)";
    [-1, 1].forEach(side => {
      g.beginPath();
      g.ellipse(S/2 + side*dx, y, S*0.055, S*0.034, 0, 0, Math.PI*2);
      g.fill();
    });
  }

  function drawGlasses(g, y, dx, r){
    g.strokeStyle = "#2A2333";
    g.lineWidth = S * 0.014;
    [-1, 1].forEach(side => {
      const x = S/2 + side*dx;
      g.beginPath();
      g.roundRect ? g.roundRect(x - r*1.5, y - r*1.25, r*3, r*2.5, r*0.7)
                  : g.rect(x - r*1.5, y - r*1.25, r*3, r*2.5);
      g.stroke();
    });
    g.beginPath();
    g.moveTo(S/2 - dx + r*1.5, y);
    g.lineTo(S/2 + dx - r*1.5, y);
    g.stroke();
  }

  /* Lighten or darken a hex colour. */
  function spirit(hex, amount){
    const n = parseInt(String(hex).slice(1), 16);
    let r = (n>>16)&255, g = (n>>8)&255, b = n&255;
    const t = amount < 0 ? 0 : 255;
    const p = Math.abs(amount);
    r = Math.round((t - r) * p + r);
    g = Math.round((t - g) * p + g);
    b = Math.round((t - b) * p + b);
    return "#" + ((1<<24) + (r<<16) + (g<<8) + b).toString(16).slice(1);
  }

  /* ---------------------------------------------------------------------
     Geometry
     --------------------------------------------------------------------- */
  let ramp = null;
  function gradientMap(){
    if (ramp) return ramp;
    // Five steps rather than three: three bands make a limb read as a flat
    // panel, five keeps the toon look while letting cylinders read as round.
    const data = new Uint8Array([104,104,104, 150,150,150, 190,190,190, 226,226,226, 255,255,255]);
    ramp = new THREE.DataTexture(data, 5, 1, THREE.RGBFormat);
    ramp.minFilter = ramp.magFilter = THREE.NearestFilter;
    ramp.generateMipmaps = false;
    ramp.needsUpdate = true;
    return ramp;
  }

  /* Lambert is flat paint - it has no highlight, so a character reads as
     plastic cut-out. Standard with a low roughness and a small environment
     gives the soft sheen along an arm or a cheek that makes a figure look
     modelled rather than coloured in. The environment is generated, so this
     still ships without assets. */
  let envMap = null;
  function environment(renderer){
    if (envMap || !renderer) return envMap;
    // A vertical sky-to-ground ramp is enough: it puts a bright rim along the
    // top of every surface and a warm bounce underneath.
    const c = document.createElement("canvas");
    c.width = 8; c.height = 128;
    const g = c.getContext("2d");
    const grd = g.createLinearGradient(0, 0, 0, 128);
    grd.addColorStop(0.00, "#DFF1FF");
    grd.addColorStop(0.45, "#BBD8EC");
    grd.addColorStop(0.55, "#C7BC9A");
    grd.addColorStop(1.00, "#8E8467");
    g.fillStyle = grd; g.fillRect(0, 0, 8, 128);
    const tex = new THREE.CanvasTexture(c);
    tex.mapping = THREE.EquirectangularReflectionMapping;
    const pmrem = new THREE.PMREMGenerator(renderer);
    pmrem.compileEquirectangularShader();
    envMap = pmrem.fromEquirectangular(tex).texture;
    pmrem.dispose(); tex.dispose();
    return envMap;
  }

  function toon(color){
    return new THREE.MeshStandardMaterial({
      color: new THREE.Color(color),
      roughness: 0.62,
      metalness: 0.0,
      envMap: envMap,
      envMapIntensity: 0.55
    });
  }

  /* The inverted-hull outline. The old version scaled the whole mesh up, which
     only works when a shape is centred on its own origin - on a lathe whose
     geometry sits a metre above its pivot, scaling it launches the part across
     the character. This version pushes each vertex along its own normal by a
     fixed distance in world units, so it is correct for any shape at any
     origin, and the line has the same weight everywhere instead of being thick
     on big parts and invisible on small ones.

     Inking every part roughly doubles the mesh count, and sixteen characters
     of that on a phone is not a budget that survives. So the line goes on the
     silhouette only: head, body, limbs, hands, feet. Those are the shapes a
     player picks out of a crowd at ten metres; a crown spike or a goggle lens
     is detail nobody reads at that distance and costs the same to ink.
     Measured: 36 meshes a character without, 52 with. Sixteen more, not
     thirty-five, and the character still has an edge.

     Avatar.setOutlines(false) turns the pass off entirely. */
  let OUTLINES = true;
  const INK_WIDTH = 0.012;
  let inkMat = null;

  function inkHull(geo, width){
    const g = geo.clone();
    if (!g.attributes.normal) g.computeVertexNormals();
    const p = g.attributes.position, n = g.attributes.normal;
    // Scale the line to the part. One fixed width is 12mm of ink on a torso,
    // which is right, and 12mm on a crown spike, which swallows the spike.
    g.computeBoundingSphere();
    const rad = (g.boundingSphere && g.boundingSphere.radius) || 0.2;
    const d = width || Math.max(0.004, Math.min(INK_WIDTH, rad * 0.055));
    for (let i = 0; i < p.count; i++){
      p.setXYZ(i, p.getX(i) + n.getX(i) * d,
                  p.getY(i) + n.getY(i) * d,
                  p.getZ(i) + n.getZ(i) * d);
    }
    p.needsUpdate = true;
    g.computeBoundingSphere();
    return g;
  }

  /* Third argument is ignored - it used to be a scale fraction. Kept in the
     signature because every costume calls through here. Costume and hat parts
     come through this one and never get a line; the silhouette pieces are
     built with `ink` below. */
  function outlined(geo, mat){
    return new THREE.Mesh(geo, mat);
  }

  function ink(geo, mat){
    const solid = new THREE.Mesh(geo, mat);
    if (!OUTLINES) return solid;
    const group = new THREE.Group();
    group.add(solid);
    inkMat = inkMat || new THREE.MeshBasicMaterial({ color: INK, side: THREE.BackSide });
    const ink = new THREE.Mesh(inkHull(geo), inkMat);
    ink.castShadow = false; ink.receiveShadow = false;
    group.add(ink);
    group.userData.solid = solid;
    return group;
  }

  /* ---------------------------------------------------------------------
     Surfaces of revolution

     A cylinder has one radius; a body does not. Lathing a profile gives a
     single continuous skin - hip to waist to chest to collar - instead of
     three primitives pushed into each other with the seams showing. It is the
     difference between a figure and a stack of shapes, and it costs the same
     to draw.
     --------------------------------------------------------------------- */
  function lathe(profile, segments){
    return new THREE.LatheGeometry(
      profile.map(p => new THREE.Vector2(p[0], p[1])), segments || 28);
  }

  /* A limb section: wide at the joint it hangs from, swelling at the bicep or
     the calf, narrowing into the next joint. Capped at both ends so nothing
     shows through; the caps sit inside the joint spheres anyway. */
  function taper(rTop, rSwell, rEnd, len){
    return lathe([
      [0.001, 0],
      [rTop, 0.004],
      [rTop * 0.4 + rSwell * 0.6, len * 0.15],
      [rSwell, len * 0.34],
      [(rSwell + rEnd) * 0.5, len * 0.68],
      [rEnd, len * 0.99],
      [0.001, len]
    ], 18);
  }

  /* Hands. A sphere on the end of an arm is a stump; a mitten with a thumb is
     a hand, and it is two meshes. Nintendo has been making this exact trade
     since Mario had gloves. */
  function buildHand(mat, R, wrap, plain){
    const g = new THREE.Group();
    const palm = wrap(new THREE.SphereGeometry(R * 1.20, 14, 12), mat);
    palm.scale.set(0.86, 1.15, 0.62);
    palm.position.y = -R * 0.60;
    g.add(palm);
    const thumb = plain(new THREE.SphereGeometry(R * 0.46, 10, 8), mat);
    thumb.scale.set(0.85, 1.30, 0.85);
    thumb.position.set(R * 0.72, -R * 0.34, R * 0.10);
    thumb.rotation.z = 0.6;
    g.add(thumb);
    return g;
  }

  /* Shoes. The old foot was one squashed sphere, which points nowhere - so a
     character walking away looked identical to one walking towards you. A toe
     box and a heel give the foot a direction. */
  function buildShoe(mat, R, wrap, plain){
    const g = new THREE.Group();
    const toe = wrap(new THREE.SphereGeometry(R * 1.02, 14, 12), mat);
    toe.scale.set(1.10, 0.66, 1.72);
    toe.position.set(0, -R * 0.46, R * 0.66);
    g.add(toe);
    const heel = plain(new THREE.SphereGeometry(R * 0.86, 12, 10), mat);
    heel.scale.set(1.04, 0.96, 1.02);
    heel.position.set(0, -R * 0.26, -R * 0.20);
    g.add(heel);
    return g;
  }

  /* --- hair ------------------------------------------------------------ */
  function buildHair(style, color, R){
    const g = new THREE.Group();
    const mat = toon(color);
    const cap = (coverage, scaleY, lift) => {
      const shell = outlined(
        new THREE.SphereGeometry(R * 1.05, 24, 18, 0, Math.PI*2, 0, Math.PI * coverage),
        mat, 0.038);
      shell.scale.set(1, scaleY, 1);
      shell.position.y = lift || 0;
      // Nudged back so the fringe clears the brow rather than covering the eyes.
      shell.position.z = -R * 0.05;
      g.add(shell);
      return shell;
    };

    if (style === "buzz"){ cap(0.40, 0.94, 0); }
    else if (style === "crop"){ cap(0.45, 1.0, 0.01); }
    else if (style === "bob"){
      cap(0.48, 1.0, 0.01);
      [-1, 1].forEach(s => {
        const side = outlined(new THREE.SphereGeometry(R*0.42, 14, 12), mat, 0.04);
        side.position.set(s * R * 0.82, -R * 0.34, 0);
        side.scale.set(0.62, 1.25, 0.9);
        g.add(side);
      });
    }
    else if (style === "long"){
      cap(0.47, 1.0, 0.01);
      const back = outlined(new THREE.SphereGeometry(R*0.82, 16, 14), mat, 0.04);
      back.position.set(0, -R * 0.60, -R * 0.22);
      back.scale.set(0.94, 1.35, 0.72);
      g.add(back);
    }
    else if (style === "ponytail"){
      cap(0.44, 1.0, 0.01);
      const tail = outlined(new THREE.SphereGeometry(R*0.34, 14, 12), mat, 0.045);
      tail.position.set(0, -R * 0.28, -R * 1.02);
      tail.scale.set(0.72, 1.9, 0.72);
      tail.rotation.x = -0.35;
      g.add(tail);
    }
    else if (style === "curls"){
      cap(0.40, 0.92, 0.01);
      for (let i = 0; i < 9; i++){
        const a = (i/9) * Math.PI * 2;
        const curl = outlined(new THREE.SphereGeometry(R*0.30, 10, 9), mat, 0.05);
        curl.position.set(Math.cos(a) * R * 0.78, R * 0.34 + Math.sin(i*2.1) * R * 0.16,
                          Math.sin(a) * R * 0.78);
        g.add(curl);
      }
    }
    else if (style === "bun"){
      cap(0.44, 1.0, 0.01);
      const bun = outlined(new THREE.SphereGeometry(R*0.36, 14, 12), mat, 0.05);
      bun.position.set(0, R * 0.92, -R * 0.30);
      g.add(bun);
    }
    else if (style === "topknot"){
      cap(0.38, 0.9, 0.01);
      const knot = outlined(new THREE.SphereGeometry(R*0.24, 12, 10), mat, 0.055);
      knot.position.set(0, R * 1.05, 0);
      knot.scale.set(1, 1.5, 1);
      g.add(knot);
    }
    return g;
  }

  /* --- headwear --------------------------------------------------------
     Hats do a job hair cannot. Procedural hair reads as a helmet because the
     hairline is the hard part; a cap is honestly just a crown and a brim, so
     it renders clean, gives the whole cast one silhouette, and carries a
     brand. A little fringe underneath keeps nobody looking bald.
     -------------------------------------------------------------------- */
  // One hat, tuned properly. Five styles each needed their own fitting pass
  // and all five came out worse than a single cap that fits.
  const HAT_STYLES = ["cap", "capBack"];

  /* Costumes. A cast of one silhouette gets dull fast, so headwear carries the
     character: a crown, a lab band, bear ears. Each is built from the same
     primitives as everything else, so a costume costs nothing to ship. */
  const COSTUMES = ["cap", "crown", "scientist", "bear", "explorer", "chef", "diver", "none"];
  const HAT_COLORS = ["#2B2438","#E05B4B","#3B82C4","#4CAF6E","#E8A33D","#F2F0E6","#8E5FA8","#38B2AC"];

  const brandCache = {};
  function brandTexture(label, ink, cloth){
    const key = label + "|" + ink + "|" + cloth;
    if (brandCache[key]) return brandCache[key];
    const c = document.createElement("canvas");
    c.width = 512; c.height = 256;
    const g = c.getContext("2d");
    g.fillStyle = cloth; g.fillRect(0, 0, 512, 256);

    const parts = String(label || "CLOCKWORK HUB").trim().split(/\s+/);
    const top = parts.slice(0, -1).join(" ") || parts[0];
    const bottom = parts.length > 1 ? parts[parts.length - 1] : "";

    g.fillStyle = ink;
    g.textAlign = "center"; g.textBaseline = "middle";
    const fit = (text, maxW, size) => {
      let s = size;
      g.font = `900 ${s}px ui-rounded, -apple-system, "Segoe UI", system-ui, sans-serif`;
      while (g.measureText(text).width > maxW && s > 12){
        s -= 4;
        g.font = `900 ${s}px ui-rounded, -apple-system, "Segoe UI", system-ui, sans-serif`;
      }
    };
    if (bottom){
      fit(top, 430, 92);    g.fillText(top, 256, 100);
      fit(bottom, 430, 92); g.fillText(bottom, 256, 186);
    } else {
      fit(top, 430, 110);   g.fillText(top, 256, 128);
    }
    const tex = new THREE.CanvasTexture(c);
    tex.minFilter = THREE.LinearFilter;
    brandCache[key] = tex;
    return tex;
  }

  function buildCostume(cfg, R, wrap){
    const kind = cfg.costume || "cap";
    if (kind === "none") return new THREE.Group();
    if (kind === "cap") return buildHat(cfg, R, wrap);

    const g = new THREE.Group();
    const cloth = cfg.hatColor || "#2B2438";

    if (kind === "crown"){
      const gold = toon("#E8C15A");
      const band = wrap(new THREE.CylinderGeometry(R*0.96, R*1.0, R*0.34, 14), gold, 0.06);
      band.position.y = R * 0.78;
      g.add(band);
      // Points around the rim, alternating tall and short.
      for (let i = 0; i < 8; i++){
        const a = (i/8) * Math.PI * 2;
        const tall = i % 2 === 0;
        const spike = wrap(new THREE.ConeGeometry(R*0.14, tall ? R*0.42 : R*0.26, 5), gold, 0.07);
        spike.position.set(Math.cos(a) * R*0.94, R * (tall ? 1.16 : 1.08), Math.sin(a) * R*0.94);
        g.add(spike);
      }
      const jewel = wrap(new THREE.SphereGeometry(R*0.13, 8, 6), toon("#C4162A"), 0.1);
      jewel.position.set(0, R*0.82, R*1.0);
      g.add(jewel);
    }
    else if (kind === "scientist"){
      // Wild hair either side, and goggles pushed up on the forehead.
      const hair = toon(cfg.hair || "#E8E4DA");
      [-1, 1].forEach(sd => {
        const puff = wrap(new THREE.SphereGeometry(R*0.34, 10, 8), hair, 0.06);
        puff.position.set(sd * R*0.86, R*0.42, -R*0.1);
        puff.scale.set(0.9, 0.8, 0.9);
        g.add(puff);
      });
      const strap = wrap(new THREE.CylinderGeometry(R*1.04, R*1.04, R*0.16, 16), toon("#4A4A55"), 0.05);
      strap.position.y = R * 0.62;
      g.add(strap);
      [-1, 1].forEach(sd => {
        const lens = wrap(new THREE.CylinderGeometry(R*0.24, R*0.24, R*0.12, 12), toon("#9FE0F0"), 0.07);
        lens.rotation.x = Math.PI/2;
        lens.position.set(sd * R*0.34, R*0.66, R*0.86);
        g.add(lens);
      });
    }
    else if (kind === "bear"){
      const fur = toon(cfg.hair || "#8B5A2B");
      [-1, 1].forEach(sd => {
        const ear = wrap(new THREE.SphereGeometry(R*0.30, 10, 8), fur, 0.06);
        ear.position.set(sd * R*0.62, R*0.86, -R*0.06);
        ear.scale.set(1, 1, 0.6);
        g.add(ear);
        const inner = wrap(new THREE.SphereGeometry(R*0.17, 8, 6), toon("#D9A98A"), 0.08);
        inner.position.set(sd * R*0.62, R*0.86, R*0.06);
        inner.scale.set(1, 1, 0.5);
        g.add(inner);
      });
      const snout = wrap(new THREE.SphereGeometry(R*0.26, 10, 8), toon("#D9BC96"), 0.06);
      snout.position.set(0, -R*0.16, R*0.88);
      snout.scale.set(1.1, 0.8, 0.8);
      g.add(snout);
      const nose = wrap(new THREE.SphereGeometry(R*0.11, 8, 6), toon("#2A2333"), 0.1);
      nose.position.set(0, -R*0.10, R*1.06);
      g.add(nose);
    }
    else if (kind === "explorer"){
      const felt = toon(cfg.hatColor || "#8A6242");
      const crown = wrap(new THREE.CylinderGeometry(R*0.82, R*0.92, R*0.52, 14), felt, 0.05);
      crown.position.y = R * 0.74;
      g.add(crown);
      const brim = wrap(new THREE.CylinderGeometry(R*1.5, R*1.5, R*0.08, 18), felt, 0.05);
      brim.position.y = R * 0.5;
      g.add(brim);
      const band = wrap(new THREE.CylinderGeometry(R*0.84, R*0.94, R*0.16, 14), toon("#5E4028"), 0.05);
      band.position.y = R * 0.56;
      g.add(band);
    }
    else if (kind === "chef"){
      const white = toon("#F4F1E8");
      const band = wrap(new THREE.CylinderGeometry(R*1.0, R*1.0, R*0.26, 14), white, 0.05);
      band.position.y = R * 0.68;
      g.add(band);
      const puff = wrap(new THREE.SphereGeometry(R*0.92, 12, 10), white, 0.05);
      puff.position.y = R * 1.16;
      puff.scale.set(1, 0.82, 1);
      g.add(puff);
    }
    else if (kind === "diver"){
      const rubber = toon(cfg.hatColor || "#3B5BA5");
      const hood = wrap(new THREE.SphereGeometry(R*1.06, 14, 12, 0, Math.PI*2, 0, Math.PI*0.62), rubber, 0.05);
      hood.position.y = R * 0.04;
      g.add(hood);
      const mask = wrap(new THREE.BoxGeometry(R*1.36, R*0.5, R*0.3), toon("#9FE0F0"), 0.05);
      mask.position.set(0, R*0.30, R*0.82);
      g.add(mask);
      const snorkel = wrap(new THREE.CylinderGeometry(R*0.09, R*0.09, R*1.1, 8), toon("#E8A33D"), 0.07);
      snorkel.position.set(R*0.92, R*0.62, R*0.1);
      snorkel.rotation.z = -0.16;
      g.add(snorkel);
    }
    return g;
  }

  function buildHat(cfg, R, wrap){
    const g = new THREE.Group();
    const back = (cfg.hatStyle || "cap") === "capBack";
    const cloth = cfg.hatColor || "#2B2438";
    const mat = toon(cloth);
    const lum = (() => {
      const n = parseInt(cloth.slice(1), 16);
      return (((n>>16)&255)*0.299 + ((n>>8)&255)*0.587 + (n&255)*0.114) / 255;
    })();
    const ink = lum > 0.6 ? "#2A2333" : "#FFFFFF";

    // Crown: a squashed dome sitting on the top of the skull.
    const crown = wrap(
      new THREE.SphereGeometry(R*1.06, 24, 16, 0, Math.PI*2, 0, Math.PI*0.5), mat, 0.05);
    crown.scale.set(1, 0.84, 1);
    crown.position.y = R * 0.16;
    g.add(crown);

    // Band around the base of the crown.
    const band = wrap(new THREE.CylinderGeometry(R*1.065, R*1.065, R*0.20, 24),
                      toon(spirit(cloth, -0.14)), 0.05);
    band.position.y = R * 0.22;
    g.add(band);

    const button = wrap(new THREE.SphereGeometry(R*0.09, 10, 8), toon(spirit(cloth, 0.25)), 0.09);
    button.position.y = R * 0.95;
    g.add(button);

    // Peak: a flattened blob offset to one side. Explicit placement rather
    // than a cylinder wedge, whose angular origin is easy to get backwards.
    const facing = back ? -1 : 1;
    const peak = wrap(new THREE.SphereGeometry(R*0.92, 20, 12), mat, 0.06);
    peak.scale.set(1.16, 0.075, 0.92);
    peak.position.set(0, R * 0.30, facing * R * 0.70);
    peak.rotation.x = facing * -0.10;
    g.add(peak);

    // Brand panel on the crown front, above the peak and clear of the mesh.
    const panel = new THREE.Mesh(
      new THREE.PlaneGeometry(R * 1.06, R * 0.50),
      new THREE.MeshBasicMaterial({
        map: brandTexture(cfg.brand || "CLOCKWORK HUB", ink, cloth)
      }));
    // The logo lives on the same panel the peak hangs off, as on a real cap:
    // wear it backwards and the wordmark faces backwards too. 1.0R clears the
    // crown's cross-section at this height so the lettering cannot sink in.
    panel.position.set(0, R * 0.62, facing * R * 0.98);
    panel.rotation.y = back ? Math.PI : 0;
    panel.rotation.x = -0.10;
    g.add(panel);

    return g;
  }

  /* Just enough hair to show under a hat: a back fringe and sideburns. */
  function buildFringe(color, R, wrap){
    const g = new THREE.Group();
    const mat = toon(color);
    const back = wrap(new THREE.SphereGeometry(R*0.98, 18, 14, 0, Math.PI*2, Math.PI*0.32, Math.PI*0.34), mat, 0.04);
    back.position.z = -R * 0.08;
    back.scale.set(1.02, 1.0, 1.04);
    g.add(back);
    [-1, 1].forEach(s => {
      const burn = wrap(new THREE.SphereGeometry(R*0.22, 10, 8), mat, 0.05);
      burn.position.set(s * R * 0.88, -R * 0.22, -R * 0.06);
      burn.scale.set(0.5, 0.95, 0.8);
      g.add(burn);
    });
    return g;
  }

  /* --- the whole character -------------------------------------------- */
  function build(cfg, opts){
    const o = opts || {};
    const outline = o.outline !== false;
    const root = new THREE.Group();
    // Everything hangs off this, lifted so the soles rest on y = 0 rather
    // than sinking the feet through the ground.
    const rig = new THREE.Group();
    rig.position.y = 0.06;   // recomputed from the finished legs at the end
    root.add(rig);

    const skinMat  = toon(cfg.skin);
    const shirtMat = toon(cfg.shirt);
    const pantMat  = toon(cfg.pants);
    const shoeMat  = toon(cfg.shoes);

    const plain = (geo, mat) => new THREE.Mesh(geo, mat);
    const wrap = plain;                       // detail: no line
    const edge = outline ? ink : plain;       // silhouette: gets the line
    const HEAD_R = 0.385;
    const HEAD_Y = 2.14;
    const BODY_Y = 1.18;      // the pivot the body leans and breathes around

    /* ---------------------------------------------------------------
       The body: one silhouette, three materials.

       Three lathes that share their end radii exactly, so the outline runs
       unbroken from ankle-height to jaw while the trousers, shirt and neck
       stay separately coloured. Nothing intersects, so there are no seams to
       catch the light at the waist or the collar.

       All three hang off one group pivoted at mid-torso, so the walk lean and
       the idle breath move the whole body instead of sliding the shirt off
       the trousers.
       --------------------------------------------------------------- */
    const body = new THREE.Group();
    body.position.y = BODY_Y;
    rig.add(body);

    const at = (geo) => { geo.translate(0, -BODY_Y, 0); return geo; };

    const legsTop  = [0.240, 0.985];
    const chestTop = [0.128, 1.635];

    const hips = edge(at(lathe([
      [0.020, 0.640], [0.150, 0.652], [0.232, 0.680], [0.270, 0.722],
      [0.278, 0.790], [0.266, 0.868], [0.250, 0.938], legsTop
    ])), pantMat);
    body.add(hips);

    const torso = edge(at(lathe([
      legsTop,        [0.244, 1.042], [0.259, 1.122], [0.279, 1.222],
      [0.297, 1.330], [0.308, 1.428], [0.305, 1.498], [0.284, 1.558],
      [0.236, 1.604], chestTop
    ])), shirtMat);
    body.add(torso);

    const neck = edge(at(lathe([
      chestTop,       [0.110, 1.672], [0.103, 1.730], [0.109, 1.798],
      [0.020, 1.816]
    ], 20)), skinMat);
    body.add(neck);

    // Deltoids: without them an arm reads as a rod stuck into a barrel. With
    // them the shoulder is a joint the arm swings from. Tucked in and slightly
    // flattened - proud of the torso they stop being shoulders and become
    // shoulder pads.
    const shoulders = new THREE.Group();
    [-1, 1].forEach(s => {
      const d = wrap(new THREE.SphereGeometry(0.118, 16, 12), shirtMat);
      d.position.set(s * 0.268, 1.486 - BODY_Y, 0);
      d.scale.set(1.0, 0.90, 1.0);
      body.add(d);
      shoulders.add(d);
    });

    const collar = torso;   // kept for callers that reach for it by name

    /* Head. */
    const head = new THREE.Group();
    head.position.y = HEAD_Y;
    const skull = edge(new THREE.SphereGeometry(HEAD_R, 32, 24), skinMat);
    skull.scale.set(1, 1.06, 0.95);
    head.add(skull);

    // A slight jaw: the skull alone is a ball, and a ball has no chin. Kept
    // shallow - push it any lower and the drawn face rides up into the
    // forehead with a bare slab of chin under the mouth.
    const jaw = wrap(new THREE.SphereGeometry(HEAD_R * 0.88, 20, 16), skinMat);
    jaw.position.set(0, -HEAD_R * 0.18, HEAD_R * 0.05);
    jaw.scale.set(0.95, 0.74, 0.93);
    head.add(jaw);

    // The drawn features sit on a shallow cap across the front of the head.
    const faceGeo = new THREE.SphereGeometry(HEAD_R * 1.008, 30, 24,
      -Math.PI/2 - 0.78, 1.56, Math.PI * 0.16, Math.PI * 0.66);
    const faceMat = new THREE.MeshBasicMaterial({
      transparent: true, map: cfg.faceTexture || faceTexture(cfg), depthWrite: false
    });
    const face = new THREE.Mesh(faceGeo, faceMat);
    face.rotation.y = Math.PI;
    face.scale.set(1, 1.07, 0.95);
    head.add(face);

    // Ears.
    [-1, 1].forEach(s => {
      const ear = wrap(new THREE.SphereGeometry(HEAD_R*0.17, 10, 8), skinMat, 0.06);
      ear.position.set(s * HEAD_R * 0.97, -HEAD_R*0.04, 0);
      ear.scale.set(0.55, 1, 0.8);
      head.add(ear);
    });

    if (cfg.hat === false){
      head.add(buildHair(cfg.hairStyle, cfg.hair, HEAD_R));
    } else {
      head.add(buildFringe(cfg.hair, HEAD_R, wrap));
      head.add(buildCostume(cfg, HEAD_R, wrap));
    }
    rig.add(head);

    /* Limbs, pivoted so they swing from shoulder and hip.

       Each section is a lathe rather than a cylinder, and there is a sphere at
       the elbow and the knee. That sphere is the whole reason a bent arm looks
       like it bent instead of snapping: two cylinders meeting at an angle leave
       a wedge of empty air on the outside of the joint, and every one of the
       fourteen emotes bends something. */
    function limb(x, y, upperLen, lowerLen, upperMat, lowerMat, rTop, rSwell,
                  rJoint, rEnd, endBuilder){
      const pivot = new THREE.Group();
      pivot.position.set(x, y, 0);

      const upper = edge(taper(rTop, rSwell, rJoint, upperLen), upperMat);
      upper.rotation.x = Math.PI;      // lathes build upward; hang it downward
      pivot.add(upper);

      const knee = new THREE.Group();
      knee.position.y = -upperLen;

      // Exactly the radius the two sections meet at. A percent or two proud of
      // them looked anatomically right in a still and read as a hard shading
      // band on a moving leg - the ring is a lit sphere against an unlit
      // cylinder wall, and the eye reads a band as a seam, not a knee.
      const joint = wrap(new THREE.SphereGeometry(rJoint, 16, 14), lowerMat);
      knee.add(joint);

      const lower = edge(taper(rJoint, rJoint * 1.06, rEnd, lowerLen), lowerMat);
      lower.rotation.x = Math.PI;
      knee.add(lower);

      const end = endBuilder(rEnd);
      end.position.y = -lowerLen;
      knee.add(end);

      pivot.add(knee);
      rig.add(pivot);
      pivot.userData.knee = knee;
      return pivot;
    }

    const sleeveMat = toon(spirit(cfg.shirt, -0.14));
    const hand = (R) => buildHand(skinMat, R, edge, plain);
    const shoe = (R) => buildShoe(shoeMat, R, edge, plain);

    // Long legs relative to the body. The gap between a toy and a figure is
    // mostly leg: the same torso on short legs reads as a doll every time.
    const armL = limb(-0.318, 1.486, 0.42, 0.40, sleeveMat, skinMat,
                      0.100, 0.105, 0.079, 0.063, hand);
    const armR = limb( 0.318, 1.486, 0.42, 0.40, sleeveMat, skinMat,
                      0.100, 0.105, 0.079, 0.063, hand);
    const legL = limb(-0.142, 0.80, 0.47, 0.45, pantMat, pantMat,
                      0.132, 0.136, 0.100, 0.070, shoe);
    const legR = limb( 0.142, 0.80, 0.47, 0.45, pantMat, pantMat,
                      0.132, 0.136, 0.100, 0.070, shoe);

    // Plant the soles on y = 0 rather than guessing at the lift. The lowest
    // point is the underside of the toe box, which buildShoe puts at
    // -(0.46 + 0.66 * 0.66) of the ankle radius below the ankle.
    const ankleY = 0.80 - 0.47 - 0.45;
    rig.position.y = -(ankleY - 0.070 * (0.46 + 1.02 * 0.66));

    return {
      root, rig, body, head, face, faceMat, torso, collar, hips, neck, shoulders,
      armL, armR, legL, legR,
      headY: HEAD_Y, bodyY: BODY_Y,
      height: HEAD_Y + HEAD_R * 1.06 + rig.position.y
    };
  }

  return {
    build, faceTexture, defaults, toon, gradientMap, spirit, environment,
    setOutlines(v){ OUTLINES = !!v; },
    get outlines(){ return OUTLINES; },
    SKIN, HAIR, CLOTH, PANTS, SHOES, HAT_COLORS,
    HAIR_STYLES, HAT_STYLES, COSTUMES, EYE_STYLES, BROW_STYLES, MOUTH_STYLES
  };
})();
