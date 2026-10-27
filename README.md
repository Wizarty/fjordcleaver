# FJORDCLEAVER — Cozy Isometric Low-Poly Snow-Plowing Diorama

## [▶ Play FJORDCLEAVER](https://wizarty.github.io/fjordcleaver/)

An interactive Nordic winter simulation built in pure HTML5 Canvas and procedural Web Audio.

## ❄️ Features
- **Tactile Snow Plowing**: Clean, responsive snow-carving with real-time terrain heightfield deformation.
- **Reworked Rescue Counters**: Dedicated tracking for unburied cars (🚗), cleared cabins (🏡), and refugees escorted to Fjordhaven City (🏛️).
- **Valley Buffs & Hazards**:
  - 🏎️ **Nitro Boost**: 7s of hyper-speed and instant drift ramming.
  - 🧂 **De-Icing Salt Kegs**: Automated brine spreader keeping roads clear.
  - 🔧 **Emergency Repair Kits**: Instant cooldown resets.
  - 🌪️ **Blizzard Vortices**: Wandering polar whirlwinds that redeposit snow and freeze refugees.
  - 🛡️ **Storm Shield**: 16 seconds of protection from wind and engine freeze.
  - ☕ **Spiced Cider**: Maximum flow combo.
  - ❄️ **Glacial Snowbanks**: Slow the plow; break through with Dash or Nitro.
  - 🧊 **Black Ice Slicks**: High-slip road patches that test your steering.
- **7 Workshop Tech Upgrades**:
  1. V-Blade Span
  2. Turbine Thrust
  3. Thermal Melt Core
  4. Studded Snow-Tracks (Traction Cleats)
  5. Rescue Beacon Siren
  6. Cabin & Engine Heater
  7. Brine Spreader

## 🚀 How to Run
- **Local Play**: Double-click `index.html` in any modern web browser.
- **GitHub Pages**: Push this repository to GitHub, go to **Settings -> Pages**, set source to **GitHub Actions**, and play online immediately.

## Career balance and rescue statistics

The seven upgrade tracks each have five paid levels. Starting prices range from 8,000 to 13,200 credits and double at each level, for 2,325,000 credits to fully upgrade every track. Income favors clearing snow and completing rescues rather than collecting frequent pickups. An accelerated run using the actual simulation, automatic purchases, Dash and Melt Pulse reached maximum upgrades at about 181 simulated minutes (3h 1m). The target is 3–4 hours of active play; routes, weather and purchase choices affect the result.

Cars show **freed / arrived at refuge**; houses count cleared entrances; people count pedestrian arrivals at the refuge. A target is counted once per valley, including after reload. Old combined rescue totals are retained separately in the pause menu rather than guessed into categories. Purchases and statistics autosave every ten active seconds. Existing progression is retained. **Start New Career** in the pause menu resets gameplay progression after confirmation and preserves purchased cosmetics; **New Valley** retains upgrades.

Vortices redeposit snow, push the plow, chill its engine and temporarily freeze evacuees. Nitro or Dash dispels them; shields prevent engine chill and wind push; the upgraded horn thaws nearby evacuees. Salt keeps treated roads from being buried until its protection expires. Storms cycle through five weather phases, including a whiteout with strong crosswinds. Effect timers pause with the game.

## Validation

The HTML includes compiled Tailwind 3.4.17 styles and runs without a CDN. All game styling is embedded; there are no external font requests. To run browser regressions, install Python's `playwright` package and either system Chromium or `python3 -m playwright install chromium`, then run:

```sh
python3 -m unittest discover -s tests -v
python3 tests/benchmark_career.py
```

The benchmark accelerates gameplay logic without drawing, automatically buys affordable upgrades and uses abilities. It prunes distant test terrain to bound memory; it does not measure rendering performance or guarantee the same completion time for every route.

## Touch controls

On phones and tablets, touch any free part of the game field to place a floating joystick under your finger. Drag a little for precise low-speed movement or farther for full throttle. Its base follows long swipes, making short direction reversals possible. The action buttons move to the opposite side when you start steering, so either hand can steer; a second finger can activate abilities without interrupting movement. Touch abilities activate on contact. Releasing, cancelling, pausing, rotating or leaving the page clears steering. Ground steering and braking respond faster to touch; ice and weather hazards retain their handling penalties. Keyboard and optional mouse-follow controls remain available on desktop.

## Smooth movement and desktop dragging

Hold the left mouse button and drag on the game field to steer, then release to brake. Desktop dragging uses the same floating origin as touch without displaying a joystick. Touch controls appear only for active touch input; pointer-mode changes reset stale gestures. Nitro increases available speed and clearing power, but never applies throttle by itself. Dash remains a short deliberate forward impulse. Steering, velocity and camera follow use exponential smoothing, including a separately eased lookahead. Camera shake is capped and follows gentle continuous oscillations instead of random per-frame jumps.

Supply pickups and thermal vents are spread across 3×3-chunk districts, with at most one per district and a minimum separation of 468 world units (about 59 displayed metres). One introductory crystal remains near spawn. Placement is deterministic and independent of chunk loading order.

Engine speed now progresses from 38 to 170 world units/second across six levels (38, 54, 74, 100, 132, 170), with a deliberately slow starter vehicle. Existing engine upgrades are preserved; start a new career to experience the full progression.

## YouTube Playables preparation (not certification)

See the [Russian audit matrix](docs/YOUTUBE_PLAYABLES_AUDIT.md) for verified checks, source references, and blockers. A hosted adapter handles SDK readiness, platform pause/audio and cloud saves; browser storage remains for the standalone Pages game. Create the isolated submission candidate with `python3 tools/build_playables.py`. The ZIP loads the original YouTube SDK first and contains only the game HTML and third-party notice. Native confirmation prompts and page reloads were replaced by an in-page reset dialog.

Current official requirements and the real SDK/Test Suite could not be accessed because of the environment network policy. Mock-SDK tests are not YouTube certification. No submission has been made. Publisher access, current normative requirements, device/memory tests and listing assets remain to be verified.

## Abilities

- **Melt** removes all snow and existing berms inside its radius without pushing snow outward. Clean ground stays clean and gives no empty-use reward or snow particles.
- **Dash** provides a 0.8-second forward thrust (previously 0.52 seconds), with the existing cooldown.
- **Rescue Ping (H)** marks the closest in-range stranded target for 12 seconds, prioritizing blocked evacuees. A blue SOS marker and direction line work even when the general radar is disabled. Nearby evacuees immediately thaw, recalculate their route, gain +50% movement speed on cleared roads and cannot be frozen by vortices for 8 seconds. It does not let them travel through snow. Siren upgrades extend range/duration and shorten its 8-second cooldown. The button displays remaining cooldown.

## Map modes: Arcade and Snow City

Choose **Arcade · Endless** or **Snow City · Build & restore** in the welcome screen or pause menu. Each mode has its own upgrades, credits and progress; existing saves migrate into Arcade. Switching modes saves the current profile before loading the other one.

Snow City is a finite 48×48-tile island with persistent terrain and construction. Open **Build**, select a structure and tap a cleared tile adjoining the refuge or a connected heated road. Reopen Build and choose **Cancel placement / Drive** to resume steering. Buildings require snow stock, heat and sometimes water; exact costs are displayed before placement. Terrain must be clear and occupied tiles cannot be replaced.

- **Heated road:** embedded waste-heat pipes melt snowfall immediately. Extend a connected road network to grow the city.
- **Snow furnace:** processes collected snow into usable heat and water.
- **Waterworks:** turns snow into a larger supply of water for the settlement.
- **Geothermal plant:** provides renewable heat and melts nearby snow into the resource stock.
- **Greenhouse:** uses water to produce food.
- **Eco housing:** adds space for ten residents; population grows when food is available.
- **Climate hub:** unlocks after a furnace, waterworks, greenhouse and two homes. The valley's heat network prevents new snowfall from accumulating, allowing final cleanup.

The goal is to clear all **2,304 tiles**, build the climate hub and settle at least six residents. Completing the goal does not stop further building. Snow harvested with the plow, Melt and salt becomes city stock; actual harvesting, production and construction are covered by an end-to-end completion test without free resource grants. The existing Arcade campaign retains its progression and mechanics.

In Snow City, **Ping** surveys the finite map and marks the nearest remaining patch of snow, making the last tiles easier to find.
