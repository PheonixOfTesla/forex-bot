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

## 2. Graphics — Ocarina art direction, modern clarity

- **S2.1** Textured ground, walls, bark, foliage, water — DONE
- **S2.2** Blue sky with drifting cloud banding — DONE
- **S2.3** Distant terrain in haze so the world feels bigger than it is — DONE
- **S2.4** Low third-person camera, behind the shoulder — DONE
- **S2.5** Full resolution, antialiased, anisotropic ground — DONE
- **S2.6** Real shadows under characters and props — DONE
- **S2.7** Warm directional sun with cool sky bounce — DONE
- **S2.8** Grass and prop variation, not a flat plane — DONE

## 3. Maps

- **S3.1** More than one map — DONE
- **S3.2** Host picks the map in the lobby, everyone sees it — DONE
- **S3.3** Each map is visually distinct at a glance — DONE
- **S3.4** Same rules on every map — DONE
- **S3.5** Maps are seeded, so every device builds the identical world — DONE

## 4. Characters

- **S4.1** Full body, walk cycle, idle, emotes — DONE
- **S4.2** Costumes with personality: bear, scientist, explorer, crown, chef, diver — DONE
- **S4.3** Photo → cartoon face, on device, never uploaded — PARTIAL (untested on a real photo)
- **S4.4** Skin, hair, outfit and cap colour customisable — DONE

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
