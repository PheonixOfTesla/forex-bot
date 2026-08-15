# MOLUA — Spec

The build target. Every line is either **DONE**, **PARTIAL** or **TODO**, and
nothing is marked DONE until it has been driven in a real browser.

---

## 0. Names — locked

| Thing | Name | Why |
|---|---|---|
| The game | **MOLUA** | Invented, Polynesian-sounding, short enough to text |
| The killer | **THE UNDERTOW** | Invisible, takes people from below, no gore |
| The seer | **THE NAVIGATOR** | Wayfinding — reads a person the way you read stars |
| The accomplice | **THE REEF** | Hides what the water is doing |
| Everyone else | **VILLAGER** |  |
| The dead | **SPIRITS** | Still present, still loud |
| Your avatar | **ISLANDER** |  |
| Night phase | **NIGHTFALL** |  |
| Day phase | **THE GATHERING** |  |
| Maps | **Molua Village**, **Kanu Grove**, **Halehua Bay** | Invented place names |

> Verify "Molua", "Kanu" and "Halehua" are not real Hawaiian words before
> commercial launch. Cultural and trademark check, not a code task.

---

## 1. Feel — the bar

Nintendo, not "web game". Concretely:

- **S1.1** Every control is big, round, and obviously pressable — DONE
- **S1.2** Buttons depress on touch with a hard shadow underneath — DONE
- **S1.3** No dead ends: every screen says what to do next in plain words — DONE
- **S1.4** Nothing is pixelated or blurry. Sharp at full resolution — DONE
- **S1.5** Warm, sunlit, friendly. Never grim — DONE
- **S1.6** Sound on every meaningful beat — DONE
- **S1.7** A title screen that looks like a game, not a form — PARTIAL
- **S1.8** No emoji anywhere. Inline SVG icons only, stroked on currentColor
  so a control's state colours its icon — DONE

## 2. Graphics — Ocarina art direction, modern clarity

- **S2.1** Textured ground, walls, bark, foliage, water — DONE
  - Each surface is drawn as itself: grass is blades, sand is wind ripples,
    stone is running-bond paving with mortar, dirt is clods and pebbles,
    plaster is a trowelled mottle. Five of them used to be one speckle
    function in five colours, which is why they all read as the same material
  - Every ground texture carries a normal map derived from its own canvas, so
    the sun actually catches the surface instead of lighting flat colour
  - Macro blotches break up tiling on the low-repeat surfaces. Deliberately
    not on paving: at seven repeats the blotches *become* the pattern and the
    plaza came out as a giant checkerboard
- **S2.2** Blue sky with drifting cloud banding — DONE
- **S2.3** Distant terrain in haze so the world feels bigger than it is — DONE
- **S2.4** Low third-person camera, behind the shoulder — DONE
- **S2.5** Full resolution, antialiased, anisotropic ground — DONE
- **S2.6** Real shadows under characters and props — DONE
- **S2.7** Warm directional sun with cool sky bounce — DONE
- **S2.8** Grass and prop variation, not a flat plane — DONE
- **S2.9** Terrain with shape — DONE
  - The island was a flat disc, and no texture fixes that: Ocarina's fields
    read the way they do because the ground has form to walk over and behind
  - One pure height function of x and z with fixed constants, so every device
    raises identical hills and the server never mentions height. Ground mesh,
    props, players and camera all sample that one function
  - Dead flat inside the plaza on purpose. The Gathering is an argument
    between people looking at each other; it must not matter that one of them
    is standing in a dip
  - Biased so the field only rises. Centred on zero it cut troughs below the
    sea plane and the island filled with water in every dip
  - Per-map relief: the grove rolls, the bay is nearly flat
- **S2.10** Ridged horizon, not cardboard — DONE
  - Two or three overlapping peaks per bearing. A single cone is a cut-out;
    the overlap of one shoulder passing behind another is what reads as land
  - Haze comes from the map's fog, so the rock keeps its own colour instead
    of being painted pale up front
- **S2.11** Buildings, not boxes — DONE
  - Doors and windows are recesses with frames, not planes painted on a wall.
    A flat decal has no thickness and no shadow at any angle but straight on
  - Roof overhang, eaves, a plinth and a doorstep, so a house meets the
    ground instead of being dropped onto it

## 3. Maps

- **S3.1** More than one map — DONE
- **S3.2** Host picks the map in the lobby, everyone sees it — DONE
- **S3.3** Each map is visually distinct at a glance — DONE
  - Each map's declared ground material is actually used. It had been in the
    map definitions from the start and never read, so Halehua Bay — a bay —
    was a green field with palm trees standing in it
- **S3.4** Same rules on every map — DONE
- **S3.5** Maps are seeded, so every device builds the identical world — DONE

## 4. Characters

- **S4.1** Full body, walk cycle, idle, emotes — DONE
- **S4.2** Costumes with personality: bear, scientist, explorer, crown, chef, diver — DONE
- **S4.3** Photo → cartoon face, on device, never uploaded — PARTIAL (untested on a real photo)
- **S4.4** Skin, hair, outfit and cap colour customisable — DONE
- **S4.13** Ten hair styles, and a picker in the maker for them — DONE
  - crop, buzz, bob, long, wavy, braids, ponytail, curls, bun, topknot
  - The library and the server whitelist had styles from the start; the maker
    never exposed them, so everyone got a random style they could not change
  - Long, wavy, braids and bob read unmistakably as long hair, with strands
    down the front of each shoulder — without those it is a hood, not hair
- **S4.14** A cap takes the crown and leaves the length — DONE
  - Hair is built in two parts, and only the crown is skipped under a hat, so
    a player in a Clockwork Hub cap still has her hair down her back
  - Verified through the real server: the style relays to other players, and
    a value that is not on the list is rejected
- **S4.5** Figures, not toys — DONE
  - The body is one continuous surface, hip to collar, lathed from a profile
    instead of assembled from a cylinder and two spheres. No seams to catch
    the light at the waist or the shoulder
  - Limbs taper: wide at the joint, swelling at the bicep and the calf,
    narrowing into the wrist and the ankle
  - A sphere at every elbow and knee, so a bent joint is a joint and not a
    wedge of missing arm
  - Hands with thumbs, not stumps. Shoes with a toe and a heel, so a walking
    character has a direction
  - Deltoids, a short neck, a jaw. Soft specular from a generated environment
- **S4.6** Hand-modelled character quality (Smash Bros tier) — **STILL SHORT,
  and it is a question of authorship, not effort.** Every shape here is a
  surface of revolution or a sphere because that is what code can describe;
  a modelled character has asymmetry, cloth folds, a face that is geometry
  rather than a decal, and a rig with weighted skinning. The parts library is
  the same *structure* a bought character set would drop into, and swapping
  the mesh source is a config change, not a rewrite
- **S4.12** An ink outline on the silhouette — DONE
  - Inverted hull, offset along vertex normals so it is correct on any shape
    at any origin, and scaled to the part so a crown spike does not vanish
  - Silhouette only - head, body, limbs, hands, feet. Measured at 36 meshes a
    character without it and 52 with; inking the costumes and hat as well
    roughly doubles the count, which sixteen players on a phone cannot afford
  - `Avatar.setOutlines(false)` turns it off
- **S4.7** Emotes and dances, Fortnite / Apex style — DONE
  - 14 to choose from: wave, dance, spin, clap, cheer, point, bow, flex,
    laugh, think, sit, sleep, robot, wiggle
  - Each one is a distinct full-body animation with real joint bends, not a
    recoloured wave
- **S4.8** A customisable wheel: pick any 8 of the 14 in the character maker,
  and they are the 8 on your radial — DONE
- **S4.9** The wheel opens over the world without leaving it, slots laid on a
  circle from the top going clockwise, thumb-reachable on a phone — DONE
- **S4.10** Three quick-picks on the HUD for the emotes you use most, so the
  common case is one tap — DONE
- **S4.11** The loadout is yours and only yours: the server whitelists every
  name, de-duplicates, clamps to 8, and nobody can set another player's — DONE

## 5. Multiplayer

- **S5.1** Open a room, share one link, no install, no account — DONE
- **S5.2** Free roam with everyone visible and moving — DONE
- **S5.3** Rejoin after a dropped phone — DONE
- **S5.4** 4–16 players — DONE

## 6. Talking

- **S6.1** Text chat, living and spirits separate — DONE
- **S6.5** Speech bubbles over the speaker's head, Wizard101 / Free Realms
  style, with a running transcript in the corner — DONE
- **S6.6** A say bar always reachable while walking — DONE
- **S6.2** Browser mic, click to talk, peer to peer — DONE
- **S6.3** See who is speaking — DONE
- **S6.4** Works behind strict NAT — TODO (needs a paid TURN relay)

## 7. The game itself

- **S7.1** Nightfall → Forty Seconds → Gathering → Verdict — DONE
- **S7.2** The Undertow's order performed out loud in the real room — DONE
- **S7.3** Spirits see every role and get one anonymous Omen — DONE
- **S7.4** Secrecy enforced server side, never in the client — DONE
- **S7.5** An opening sequence that sets the scene before round one — TODO

## 9. The games index

- **S9.1** `/games` lists every game — DONE
- **S9.2** Search by name, theme or what the game is — DONE
- **S9.3** Pasting a room code offers to join, and a five-letter search word
  is not mistaken for one — DONE
- **S9.4** Each game has its own slug, so names cannot collide — DONE
- **S9.5** A texted or AirDropped link previews as a card with the game's
  name, art and player count — DONE
- **S9.6** The share card is rendered from the real game, so it cannot drift
  from what players actually see — DONE

## 8. Shipping

- **S8.1** Lives at `theclockworkhub.com/games/molua` — DONE (routing)
- **S8.2** Client served as static files, light on the web — DONE
- **S8.3** Game server running somewhere — **BLOCKED: needs a host**
- **S8.4** Moderation for chat and voice before minors use it commercially — TODO
