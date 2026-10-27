# Snow City: Thermal Cooperative

A finite valley becomes a connected, self-sufficient town. The plow opens routes;
roads carry a geothermal loop; utilities turn collected snow into stored heat,
water and food. Snow is a cooling medium and water source, not a combustible fuel:
the exchanger recovers waste heat from the refuge's refrigeration plant. Building
costs represent snow/mineral cryo-composite fabrication at the refuge.

## Campaign

1. **Outpost:** clear 10%, connect an exchanger, waterworks and home.
2. **Village:** settle 8 people, build a greenhouse and second home.
3. **Cooperative:** settle 24 people and restore two outer districts.
4. **Living valley:** connect a climate hub, restore all four districts, settle
   40 people and clear every tile. Continue building after completion.

Each completed chapter permanently unlocks its catalogue and raises the plow's
engine, blade and thermal level (up to 4). Arcade progression is separate.
District relays must be placed at marked survey sites, connected by roads, with
at least 85% of the surrounding 9×9 district cleared. A relay permanently keeps
its district clear of new snowfall while connected. No repeatable quest payouts.

## Economy

All rates are per simulated minute; menus pause time, no offline gains. An
exchanger consumes 4 snow -> 8 heat + 2 water; waterworks uses 3 snow + 1 heat ->
12 water; greenhouse uses 3 water + 2 heat -> 6 food. Geothermal provides 8 heat.
A snow collector captures 6 snow from high-altitude precipitation before it
reaches the ground, including after the climate hub is built. It ensures the
finite terrain cannot exhaust the economy. Collectors unlock with the village.
The refuge provides an emergency 1.5 snow/minute up to 90 stock, so a bad early
spending decision is recoverable. The configurable snow reserve (0/30/60) stops
processors consuming construction stock. All outputs stop at storage capacity;
inputs are not spent producing a full primary output.

Initial stores: 50 snow / 30 heat / 12 water / 6 food. Capacity: 240 / 180 /
160 / 100, each depot adds 240 / 180 / 160 / 100. One home holds 8 people.
Each resident consumes .10 water and .06 food/minute; insufficient services pause
immigration rather than killing residents. Immigration is .72 people/home/minute,
with food and water also required for arrivals. A greenhouse supports 100 existing
residents on food; water is the tighter shared input during expansion.

Heat-network capacity is separate from stored heat used in fabrication. The
refuge supplies 12 units, each exchanger +16, geothermal +60, hub +100. Roads
use .15, homes 2, waterworks 2, greenhouse 4, collector 3, relay 3, climate hub 20.
An over-budget construction is rejected with the exact deficit; legacy overloaded
networks throttle production. Disconnected buildings stop producing and housing
stops accepting arrivals. Dismantling refunds 50% of nominal costs, capped by
storage; removal cannot disconnect occupied infrastructure or overload the grid.

The intended first loop is a few minutes and full development roughly 45–75
minutes of active building/clearing, dependent on layout and route. This is a
design target, not a measured playtest claim. `python3 tests/benchmark_city.py`
completes the ideal economy scenario in 2,768 simulated seconds (46.13 minutes),
without resource grants, excluding travel and weather. Automated simulation checks rates,
resource conservation, recovery and completion; Arcade retains its 3–4 hour economy.

## Interface

A compact city HUD replaces rescue counters. A planning panel has Plan, Build and
Economy tabs. Plan shows the next chapter's individual goals and a full-valley
map with surveyed districts, roads and the plow. Tapping the map sets a waypoint.
Economy shows stock/capacity, actual net rates and service status. Build cards show
costs, outputs, network load, limits and unlock reasons. Select a structure, tap a
tile, inspect the green/red footprint and reason, then confirm. A persistent
Cancel button returns to driving. Desktop side panel becomes a bottom sheet on
phones, including short landscape screens. Planning and placement pause the
simulation without changing the user's pause state.

Existing city layouts, resources and cleared terrain are retained. Legacy stocks
above new storage limits remain usable; further production waits for capacity.
