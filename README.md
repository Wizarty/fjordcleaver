# FJORDCLEAVER — Cozy Isometric Low-Poly Snow-Plowing Diorama

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

The seven upgrade tracks each have five paid levels. Starting prices range from 8,000 to 13,200 credits and double at each level, for 2,325,000 credits to fully upgrade every track. Clearing income and pickup rewards are reduced, while rescue missions remain valuable. An accelerated run using the actual simulation, automatic purchases, Dash and Melt Pulse reached maximum upgrades at about 82 simulated minutes. The target is 1–2 hours of active play; routes, weather and purchase choices affect the result.

Cars show **freed / arrived at refuge**; houses count cleared entrances; people count pedestrian arrivals at the refuge. A target is counted once per valley, including after reload. Old combined rescue totals are retained separately in the pause menu rather than guessed into categories. Purchases and statistics autosave every ten active seconds. Existing progression is retained. **Start New Career** in the pause menu resets gameplay progression after confirmation and preserves purchased cosmetics; **New Valley** retains upgrades.

Vortices redeposit snow, push the plow, chill its engine and temporarily freeze evacuees. Nitro or Dash dispels them; shields prevent engine chill and wind push; the upgraded horn thaws nearby evacuees. Salt keeps treated roads from being buried until its protection expires. Storms cycle through five weather phases, including a whiteout with strong crosswinds. Effect timers pause with the game.

## Validation

The HTML includes compiled Tailwind 3.4.17 styles and runs without a CDN. Google Fonts are optional. To run browser regressions, install Python's `playwright` package and either system Chromium or `python3 -m playwright install chromium`, then run:

```sh
python3 -m unittest discover -s tests -v
python3 tests/benchmark_career.py
```

The benchmark accelerates gameplay logic without drawing, automatically buys affordable upgrades and uses abilities. It prunes distant test terrain to bound memory; it does not measure rendering performance or guarantee the same completion time for every route.

## Touch controls

On phones and tablets, touch any free part of the game field to place a floating joystick under your finger. Drag a little for precise low-speed movement or farther for full throttle. Its base follows long swipes, making short direction reversals possible. The action buttons move to the opposite side when you start steering, so either hand can steer; a second finger can activate abilities without interrupting movement. Touch abilities activate on contact. Releasing, cancelling, pausing, rotating or leaving the page clears steering. Ground steering and braking respond faster to touch; ice and weather hazards retain their handling penalties. Keyboard and optional mouse-follow controls remain available on desktop.
