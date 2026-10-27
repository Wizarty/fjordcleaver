"""Browser regressions: python3 -m unittest discover -s tests -v (requires Playwright)."""
import functools
import http.server
import json
from pathlib import Path
import shutil
import threading
import unittest
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]

class GameTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(ROOT))
        cls.server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), handler)
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()
        cls.url = f'http://127.0.0.1:{cls.server.server_port}/'
        cls.pw = sync_playwright().start()
        options = {'headless': True, 'args': ['--no-sandbox']}
        if shutil.which('chromium'):
            options['executable_path'] = shutil.which('chromium')
        cls.browser = cls.pw.chromium.launch(**options)

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.pw.stop()
        cls.server.shutdown()
        cls.server.server_close()

    def setUp(self):
        self.page = self.browser.new_page(viewport={'width': 1280, 'height': 900})
        self.errors = []
        self.page.on('pageerror', lambda e: self.errors.append(str(e)))
        self.page.route('https://**/*', lambda r: r.abort())

    def tearDown(self):
        self.page.close()
        self.assertEqual(self.errors, [])

    def game(self):
        source = (ROOT / 'index.html').read_text()
        hook = '''window.gameTest = {state, chunks, keys, updateSimulation, updateActiveChunksAndPOIs,
          getUpgradeCost, buyUpgrade, syncHUD, getCellAtWorld, saveProgress, loadProgress,
          performSnowPlowing, recordRescue, triggerHornPing, createChunk, WEATHER_PHASES, renderScene, triggerPlowDash, triggerMeltPulse, joystick, getSteeringInput, getMaxSpeed, switchGameMode, buildTownAt, cityStats, updateTown, townProtected, progressSnapshot, worldToScreen, townBuildReason, townCaps, townNetwork, townGoals, townDistricts, townDeposit, invalidateTown, townPlanning, frameLoop};'''
        source = source.replace('let lastTime = performance.now();', hook + 'let lastTime = performance.now();')
        self.page.route('**/index.html', lambda r: r.fulfill(content_type='text/html', body=source))
        self.page.add_init_script('window.requestAnimationFrame = () => 0;')
        self.page.goto(self.url + 'index.html', wait_until='domcontentloaded')
        self.page.wait_for_function('window.gameTest')
        self.page.evaluate('gameTest.state.vortices = []')

    def test_offline_desktop_and_mobile_are_visible_and_clickable(self):
        for width, height in [(1280, 900), (390, 844), (844, 390), (320, 480)]:
            self.page.set_viewport_size({'width': width, 'height': height})
            self.page.goto(self.url, wait_until='domcontentloaded')
            self.page.locator('#btn-start-game').click()
            self.assertTrue(self.page.locator('#modal-backdrop').is_hidden())
            self.assertEqual(self.page.evaluate('document.elementFromPoint(innerWidth/2,innerHeight/2).id'), 'game-canvas')
            self.page.wait_for_timeout(300)
            colors = self.page.evaluate('''() => {
              const c=document.querySelector('canvas'),d=c.getContext('2d').getImageData(0,0,c.width,c.height).data;
              const colors=new Set(); for(let i=0;i<d.length;i+=400) colors.add(`${d[i]},${d[i+1]},${d[i+2]}`);
              return colors.size;
            }''')
            self.assertGreater(colors, 100)
            self.page.locator('#btn-pause').click()
            self.page.locator('#btn-pause-close').click()
            ids = self.page.locator('[id]').evaluate_all('(els) => els.map(e => e.id)')
            self.assertEqual(len(ids), len(set(ids)))

    def test_pickups_and_upgrades(self):
        self.game()
        result = self.page.evaluate('''() => {
          const {state,chunks,updateActiveChunksAndPOIs,buyUpgrade,syncHUD}=gameTest;
          const chunk=chunks.get('0,0');
          for(const type of ['nitro','salt','shield','wrench','cider']) {
            chunk.pois.push({id:'test_'+type,type,wx:0,wy:0,collected:false,bobPhase:0});
          }
          state.plow.dashCooldown=4; state.plow.pulseCooldown=7;
          updateActiveChunksAndPOIs(.05);
          const pickups={nitro:state.nitroTimer,salt:state.saltTimer,shield:state.shieldTimer,
            dash:state.plow.dashCooldown,pulse:state.plow.pulseCooldown};
          state.credits=0; const before=state.upgrades.heater; buyUpgrade('heater');
          const rejected=state.upgrades.heater===before;
          state.credits=1000000;
          for(const track of Object.keys(state.upgrades)) buyUpgrade(track);
          syncHUD();
          return {pickups,rejected,levels:state.upgrades,effects:document.querySelector('#active-effects').textContent};
        }''')
        self.assertEqual(result['pickups'], {'nitro': 7, 'salt': 14, 'shield': 16, 'dash': 0, 'pulse': 0})
        self.assertTrue(result['rejected'])
        self.assertTrue(all(v == 2 for v in result['levels'].values()))
        self.assertIn('Shield', result['effects'])

    def test_salt_expiry_freeze_and_vortex_counterplay(self):
        self.game()
        result = self.page.evaluate('''() => {
          const {state,chunks,performSnowPlowing,getCellAtWorld,updateSimulation,updateActiveChunksAndPOIs,triggerHornPing}=gameTest;
          state.plow.wx=500;state.plow.wy=500;state.saltTimer=5;
          performSnowPlowing(.05);
          const cell=getCellAtWorld(500,500),expiry=cell.saltedUntil;
          const salted=cell.snow===0 && expiry>state.elapsed;
          const citizen={id:'freeze_test',type:'citizen',wx:510,wy:510,status:'moving',speed:25,
            angle:0,walkAnimTimer:0,speechTimer:0,path:[],pathTimer:0};
          chunks.get('0,0').pois.push(citizen);
          state.vortices=[{wx:510,wy:510,vx:0,vy:0,radius:40,spin:0,active:true}];
          updateSimulation(.05);
          const frozen=citizen.frozenFor>0 && citizen.speed===0 && state.chilledTimer>0;
          state.upgrades.siren=6;triggerHornPing();const thawed=citizen.frozenFor===0;
          state.shieldTimer=10;state.chilledTimer=0;updateSimulation(.05);
          const protectedEngine=state.chilledTimer===0;
          state.nitroTimer=5;updateSimulation(.05);
          const dispelled=!state.vortices[0].active;
          state.elapsed=expiry+1;const expired=cell.saltedUntil<=state.elapsed;
          return {salted,frozen,thawed,protectedEngine,dispelled,expired};
        }''')
        self.assertTrue(all(result.values()), result)

    def test_rescue_categories_arrivals_and_reload_deduplication(self):
        self.game()
        result = self.page.evaluate('''() => {
          const {state,chunks,updateActiveChunksAndPOIs,getCellAtWorld,syncHUD,saveProgress,loadProgress}=gameTest;
          const chunk=chunks.get('0,0');chunk.pois=[];
          const car={id:'testcar',type:'vehicle',wx:0,wy:0,status:'trapped',speed:0,angle:0,path:[],pathTimer:0,speechTimer:0};
          const house={id:'testhouse',type:'cabin',wx:0,wy:0,completed:false};
          chunk.pois.push(car,house);
          for(let y=-2;y<=2;y++)for(let x=-2;x<=2;x++)getCellAtWorld(x*18,y*18).snow=0;
          updateActiveChunksAndPOIs(.05);
          const freed=state.rescuedCars,homes=state.savedCabins;
          updateActiveChunksAndPOIs(.05);updateActiveChunksAndPOIs(.05);
          const arrived=state.evacuatedCars,people=state.evacuatedPeople;
          saveProgress();loadProgress();
          car.status='trapped';house.completed=false;
          updateActiveChunksAndPOIs(.05);updateActiveChunksAndPOIs(.05);syncHUD();
          return {freed,homes,arrived,people,after:[state.rescuedCars,state.savedCabins,state.evacuatedCars,state.evacuatedPeople],
            carsText:document.querySelector('#hud-rescued').textContent,peopleText:document.querySelector('#hud-escorted').textContent};
        }''')
        self.assertEqual(result['freed'], 1)
        self.assertEqual(result['homes'], 1)
        self.assertEqual(result['arrived'], 1)
        self.assertIn(result['people'], (2, 3))
        self.assertEqual(result['after'], [1, 1, 1, result['people']])
        self.assertEqual(result['carsText'], '1 / 1')
        self.assertEqual(result['peopleText'], str(result['people']))

    def test_all_weather_and_hazard_renderers(self):
        self.game()
        result = self.page.evaluate('''() => {
          const {state,chunks,renderScene,WEATHER_PHASES}=gameTest;
          const chunk=chunks.get('0,0');
          for(const type of ['nitro','salt','wrench','cider','shield','black_ice','snowbank'])
            chunk.pois.push({id:'render_'+type,type,wx:80,wy:80,radius:22,collected:false,cleared:false});
          state.vortices=[{wx:100,wy:100,vx:0,vy:0,radius:40,spin:1,active:true}];
          state.shieldTimer=10;
          for(let i=0;i<WEATHER_PHASES.length;i++){state.weatherIndex=i;renderScene(.016);}
          return WEATHER_PHASES.length;
        }''')
        self.assertEqual(result, 5)

    def test_new_career_preserves_cosmetics_and_requires_confirmation(self):
        self.game()
        self.page.evaluate("gameTest.state.credits=999999;gameTest.state.upgrades.blade=6;gameTest.state.unlockedLiveries=[0,1];gameTest.saveProgress()")
        self.page.locator('#btn-new-career').dispatch_event('click')
        self.page.locator('#btn-cancel-career-reset').click()
        self.assertEqual(self.page.evaluate('gameTest.state.upgrades.blade'), 6)
        self.page.locator('#btn-new-career').dispatch_event('click')
        self.page.locator('#btn-confirm-career-reset').click()
        self.page.wait_for_function('gameTest.state.upgrades.blade === 1', polling=20)
        self.assertEqual(self.page.evaluate('gameTest.state.credits'), 80)
        self.assertEqual(self.page.evaluate('gameTest.state.upgrades.blade'), 1)
        self.assertEqual(self.page.evaluate('gameTest.state.unlockedLiveries'), [0, 1])

    def test_real_multitouch_steering_and_opposite_hand_actions(self):
        self.page.set_viewport_size({'width': 390, 'height': 844})
        self.game()
        self.page.locator('#btn-start-game').click()
        cdp = self.page.context.new_cdp_session(self.page)
        def touch(kind, points):
            cdp.send('Input.dispatchTouchEvent', {'type': kind, 'touchPoints': [
                {'x': x, 'y': y, 'id': i, 'radiusX': 8, 'radiusY': 8, 'force': 1}
                for i, x, y in points]})
        touch('touchStart', [(1, 290, 360)])
        touch('touchMove', [(1, 370, 360)])
        state = self.page.evaluate("({active:gameTest.joystick.active,base:gameTest.joystick.baseX,dx:gameTest.joystick.dx,input:gameTest.getSteeringInput(),left:document.querySelector('#action-controls').classList.contains('actions-left')})")
        self.assertTrue(state['active'])
        self.assertTrue(state['left'])
        self.assertAlmostEqual(state['base'], 326, delta=1)
        self.assertAlmostEqual(state['input']['throttle'], 1)
        knob = self.page.locator('#joystick-zone').bounding_box()
        self.assertAlmostEqual(knob['x'] + knob['width']/2, state['base'], delta=1)
        touch('touchMove', [(1, 310, 360)])
        self.page.wait_for_function('gameTest.joystick.dx < 0', polling=20, timeout=3000)
        self.assertLess(self.page.evaluate('gameTest.joystick.dx'), 0)
        box = self.page.locator('#btn-dash').bounding_box()
        x, y = box['x'] + box['width']/2, box['y'] + box['height']/2
        touch('touchStart', [(1, 310, 360), (2, x, y)])
        self.assertGreater(self.page.evaluate('gameTest.state.plow.dashTimer'), 0)
        self.assertLess(self.page.evaluate('gameTest.joystick.dx'), 0)
        touch('touchEnd', [(2, x, y)])
        self.assertTrue(self.page.evaluate('gameTest.joystick.active'))
        touch('touchEnd', [])
        self.assertFalse(self.page.evaluate('gameTest.getSteeringInput().active'))
        self.assertEqual(self.page.locator('#joystick-zone').evaluate('(e)=>getComputedStyle(e).opacity'), '0')
        # Change hands on free terrain, then verify the vacant old joystick area.
        touch('touchStart', [(3, 40, 650)])
        self.assertTrue(self.page.evaluate('gameTest.joystick.active'))
        self.assertFalse(self.page.locator('#action-controls').evaluate("e=>e.classList.contains('actions-left')"))
        touch('touchCancel', [])
        self.assertFalse(self.page.evaluate('gameTest.joystick.active'))
        touch('touchStart', [(4, 40, 760)])
        self.assertTrue(self.page.evaluate('gameTest.joystick.active'))
        touch('touchEnd', [])

    def test_touch_deadzone_cleanup_and_mouse_independence(self):
        self.game()
        self.page.locator('#btn-start-game').click()
        def event(kind, x=700, y=400, pointer=5):
            self.page.locator('#game-canvas').dispatch_event(kind, {'pointerId': pointer,
                'pointerType': 'touch', 'clientX': x, 'clientY': y, 'button': 0})
        event('pointerdown')
        event('pointermove', 702, 400)
        self.assertFalse(self.page.evaluate('gameTest.getSteeringInput().active'))
        event('pointermove', 710, 400)
        self.assertGreater(self.page.evaluate('gameTest.getSteeringInput().throttle'), .2)
        event('pointermove', 700, 330)
        response = self.page.evaluate('''() => {
          const desired=gameTest.getSteeringInput();
          for(let i=0;i<3;i++)gameTest.updateSimulation(.05);
          let error=Math.atan2(desired.wy,desired.wx)-gameTest.state.plow.angle;
          error=Math.atan2(Math.sin(error),Math.cos(error));
          return Math.abs(error);
        }''')
        self.assertLess(response, .4)
        event('pointerup', 700, 330)
        self.page.evaluate('for(let i=0;i<5;i++)gameTest.updateSimulation(.05)')
        self.assertLess(self.page.evaluate('gameTest.state.plow.speed'), 2)
        event('pointerdown')
        self.page.locator('#btn-pause').click()
        self.assertFalse(self.page.evaluate('gameTest.joystick.active'))
        self.page.locator('#btn-pause-close').click()
        self.assertFalse(self.page.evaluate('gameTest.getSteeringInput().active'))
        event('pointerdown')
        self.page.evaluate("window.dispatchEvent(new Event('blur'))")
        self.assertFalse(self.page.evaluate('gameTest.joystick.active'))
        event('pointerdown')
        self.page.set_viewport_size({'width': 844, 'height': 390})
        self.page.wait_for_timeout(100)
        self.assertFalse(self.page.evaluate('gameTest.joystick.active'))
        self.page.locator('#game-canvas').dispatch_event('pointerdown', {'pointerId': 9,
            'pointerType': 'mouse', 'clientX': 400, 'clientY': 200, 'button': 0})
        self.assertTrue(self.page.evaluate('gameTest.joystick.active'))
        self.assertEqual(self.page.locator('#joystick-zone').evaluate('(e)=>getComputedStyle(e).display'), 'none')

    def test_nitro_boost_is_not_autopilot(self):
        self.game()
        result = self.page.evaluate('''() => {
          const {state,keys,updateSimulation}=gameTest;
          state.nitroTimer=7;const before={x:state.plow.wx,y:state.plow.wy};
          for(let i=0;i<10;i++)updateSimulation(.02);
          const idleDistance=Math.hypot(state.plow.wx-before.x,state.plow.wy-before.y);
          keys.add('KeyD');for(let i=0;i<30;i++)updateSimulation(.02);
          const boostedSpeed=state.plow.speed;keys.clear();
          for(let i=0;i<15;i++)updateSimulation(.02);
          return {idleDistance,boostedSpeed,stoppedSpeed:state.plow.speed,nitro:state.nitroTimer};
        }''')
        self.assertLess(result['idleDistance'], .01)
        self.assertGreater(result['boostedSpeed'], 50)
        self.assertLess(result['stoppedSpeed'], 2)
        self.assertGreater(result['nitro'], 0)

    def test_mouse_drag_stops_and_switches_back_from_touch(self):
        self.game()
        self.page.locator('#btn-start-game').click()
        self.page.locator('#game-canvas').dispatch_event('pointerdown', {'pointerId': 7, 'pointerType': 'touch', 'clientX': 700, 'clientY': 400})
        self.page.locator('#game-canvas').dispatch_event('pointerup', {'pointerId': 7, 'pointerType': 'touch'})
        self.page.mouse.move(700, 400)
        self.page.mouse.down()
        self.page.mouse.move(750, 400)
        self.assertTrue(self.page.evaluate('gameTest.getSteeringInput().active'))
        self.assertFalse(self.page.locator('html').evaluate("e=>e.classList.contains('touch-controls')"))
        self.assertEqual(self.page.locator('#joystick-zone').evaluate('(e)=>getComputedStyle(e).display'), 'none')
        self.page.mouse.up()
        self.assertFalse(self.page.evaluate('gameTest.getSteeringInput().active'))

    def test_motion_response_is_consistent_across_frame_rates(self):
        results=[]
        for hz in (30, 120):
            self.game()
            results.append(self.page.evaluate('''hz => {
              gameTest.keys.add('KeyW');
              for(let i=0;i<hz*.4;i++)gameTest.updateSimulation(1/hz);
              const p=gameTest.state.plow;return {angle:p.angle,speed:p.speed,x:p.wx,y:p.wy};
            }''', hz))
            self.page.unroute('**/index.html')
        self.assertAlmostEqual(results[0]['angle'], results[1]['angle'], delta=.01)
        self.assertAlmostEqual(results[0]['speed'], results[1]['speed'], delta=2)
        self.assertAlmostEqual(results[0]['x'], results[1]['x'], delta=4)
        self.assertAlmostEqual(results[0]['y'], results[1]['y'], delta=4)

    def test_supplies_are_sparse_spaced_and_independent_of_chunk_load_order(self):
        self.game()
        result=self.page.evaluate('''() => {
          const {chunks,createChunk}=gameTest;
          const types=new Set(['crystal','crate','vent','nitro','salt','wrench','cider','shield']);
          const collect=()=>[...chunks.values()].flatMap(c=>c.pois).filter(p=>types.has(p.type));
          chunks.clear();
          for(let y=-9;y<=9;y++)for(let x=-9;x<=9;x++)createChunk(x,y);
          const first=collect();let min=Infinity;
          for(let i=0;i<first.length;i++)for(let j=i+1;j<first.length;j++)
            min=Math.min(min,Math.hypot(first[i].wx-first[j].wx,first[i].wy-first[j].wy));
          const signature=ps=>ps.map(p=>[p.id,p.type,p.wx,p.wy].join(':')).sort().join('|');
          chunks.clear();
          for(let y=9;y>=-9;y--)for(let x=9;x>=-9;x--)createChunk(x,y);
          return {count:first.length,min,same:signature(first)===signature(collect())};
        }''')
        self.assertGreater(result['count'], 10)
        self.assertLess(result['count'], 55)
        self.assertGreaterEqual(result['min'], 468)
        self.assertTrue(result['same'])

    def test_engine_progression_starts_slow_and_improves_each_level(self):
        self.game()
        speeds=self.page.evaluate('''() => {
          const values=[];
          for(let level=1;level<=6;level++){
            gameTest.state.upgrades.engine=level;values.push(gameTest.getMaxSpeed());
          }
          return values;
        }''')
        self.assertLessEqual(speeds[0], 40)
        self.assertGreater(speeds[-1], speeds[0]*4)
        self.assertTrue(all(b>a for a,b in zip(speeds,speeds[1:])))

    def test_melt_removes_snow_and_berms_without_creating_a_ring(self):
        self.game()
        result=self.page.evaluate('''() => {
          const {state,getCellAtWorld,triggerMeltPulse}=gameTest;
          const cells=[];for(let y=-8;y<=8;y++)for(let x=-8;x<=8;x++){
            const c=getCellAtWorld(x*26+13,y*26+13);c.snow=0;c.berm=0;cells.push(c);
          }
          const inner=getCellAtWorld(13,13),outer=getCellAtWorld(117,13);
          inner.snow=.01;inner.berm=.4;outer.snow=.7;outer.berm=.3;
          triggerMeltPulse();
          const cleaned=inner.snow===0 && inner.berm===0;
          const outsideUnchanged=outer.snow===.7 && outer.berm===.3;
          for(const c of cells){c.snow=0;c.berm=0;}
          state.plow.pulseCooldown=0;const particles=state.particles.length,credits=state.credits;
          triggerMeltPulse();
          return {cleaned,outsideUnchanged,noNewSnow:cells.every(c=>c.snow===0&&c.berm===0),
            noEmptySteam:state.particles.length===particles,noEmptyReward:state.credits===credits};
        }''')
        self.assertTrue(all(result.values()),result)

    def test_dash_has_longer_travel_and_cannot_be_recast_during_cooldown(self):
        distances=[]
        for duration in (.52,.8):
            self.game()
            distances.append(self.page.evaluate('''duration => {
              const {state,triggerPlowDash,updateSimulation}=gameTest;
              triggerPlowDash();state.plow.dashTimer=duration;
              for(let i=0;i<45;i++)updateSimulation(.02);
              const distance=Math.hypot(state.plow.wx,state.plow.wy);
              const timer=state.plow.dashTimer;triggerPlowDash();
              return {distance,recastBlocked:state.plow.dashTimer===timer};
            }''',duration))
            self.page.unroute('**/index.html')
        self.assertGreater(distances[1]['distance'],distances[0]['distance']*1.35)
        self.assertTrue(distances[1]['recastBlocked'])

    def test_rescue_ping_thaws_boosts_marks_and_respects_range_and_cooldown(self):
        self.game()
        result=self.page.evaluate('''() => {
          const {state,chunks,createChunk,getCellAtWorld,triggerHornPing,updateActiveChunksAndPOIs,renderScene}=gameTest;
          state.plow.wx=330;state.plow.wy=0;
          const chunk=createChunk(1,0);chunk.pois=[];
          for(let x=0;x<20;x++)for(let y=-2;y<=2;y++)getCellAtWorld(x*26+13,y*26+13).snow=0;
          const car={id:'pingcar',type:'vehicle',wx:330,wy:0,angle:Math.PI,status:'blocked',speed:48,
            frozenFor:3,path:[{wx:300,wy:0}],pathTimer:999,speechTimer:0,stuckBlinkTimer:0};
          const far={...car,id:'farcar',wx:1000,frozenFor:3};chunk.pois.push(car,far);
          triggerHornPing();
          const thawed=car.frozenFor===0,farFrozen=far.frozenFor===3;
          const marked=state.pingTarget===car && state.pingTimer===12;
          const waves=state.shockwaves.length;triggerHornPing();const cooldown=state.shockwaves.length===waves;
          updateActiveChunksAndPOIs(.05);const boosted=car.speed>48;
          state.vortices=[{wx:car.wx,wy:car.wy,vx:0,vy:0,radius:40,spin:0,active:true}];
          gameTest.updateSimulation(.05);
          const protectedFromFreeze=car.rallyTimer>0 && !car.frozenFor;
          const blockedNode={wx:300,wy:0};getCellAtWorld(300,0).snow=1;
          car.path=[blockedNode];car.pathTimer=999;const beforeX=car.wx;
          updateActiveChunksAndPOIs(.05);
          const respectsSnow=car.status==='blocked' && car.wx===beforeX;
          state.showRadarBeacons=false;renderScene(.016);
          return {thawed,farFrozen,marked,cooldown,boosted,protectedFromFreeze,respectsSnow};
        }''')
        self.assertTrue(all(result.values()),result)

    def test_city_and_arcade_profiles_are_separate_and_persistent(self):
        self.game()
        result=self.page.evaluate('''async () => {
          const g=gameTest;g.state.credits=12345;g.state.upgrades.engine=3;
          await g.switchGameMode('city');
          const fresh=g.state.credits===80 && g.state.upgrades.engine===1;
          g.state.city.snow=345;g.getCellAtWorld(400,0).snow=.17;g.saveProgress();
          await g.switchGameMode('arcade');
          const arcade=g.state.credits===12345 && g.state.upgrades.engine===3;
          await g.switchGameMode('city');
          const city=g.state.city.snow===345 && Math.abs(g.getCellAtWorld(400,0).snow-.17)<.001;
          g.saveProgress();g.loadProgress();
          return {fresh,arcade,city,reloaded:g.state.mode==='city' && g.state.city.snow===345};
        }''')
        self.assertTrue(all(result.values()),result)

    def test_city_construction_connections_costs_and_snow_protection(self):
        self.game()
        result=self.page.evaluate('''async () => {
          const g=gameTest;await g.switchGameMode('city');
          Object.assign(g.state.city,{snow:1000,heat:1000,water:1000});
          const distantRejected=!g.buildTownAt(20,20,'road');
          for(let x=0;x<15;x++)g.getCellAtWorld(x*26+13,13).snow=0;
          // Connect a chain out of the existing refuge plaza.
          let built=0;for(let x=0;x<14;x++)if(g.buildTownAt(x,0,'road'))built++;
          const key=Object.keys(g.state.city.tiles)[0];const [x,y]=key.split(',').map(Number);
          const c=g.getCellAtWorld(x*26+13,y*26+13);c.snow=.8;c.berm=.5;
          g.updateTown(.1);const protectedRoad=c.snow===0 && c.berm===0 && g.townProtected(x,y);
          const before=g.state.city.snow;
          const duplicateRejected=!g.buildTownAt(x,y,'road') && g.state.city.snow===before;
          const prematureHubRejected=!g.buildTownAt(14,0,'climate');
          return {distantRejected,built:built>0,paid:g.state.city.snow<1000,protectedRoad,duplicateRejected,prematureHubRejected};
        }''')
        self.assertTrue(all(result.values()),result)

    def test_city_economy_conserves_resources_and_holds_reserve(self):
        self.game()
        result=self.page.evaluate('''async () => {
          const g=gameTest;await g.switchGameMode('city');const c=g.state.city;
          c.tiles={'4,0':'boiler'};g.invalidateTown();
          Object.assign(c,{snow:100,heat:30,water:12,population:0});
          g.updateTown(60);
          const recipe=Math.abs(c.snow-96)<.001 && Math.abs(c.heat-38)<.001 && Math.abs(c.water-14)<.001;
          c.snow=31;c.heat=30;g.updateTown(120);const reserve=Math.abs(c.snow-30)<.001;
          c.snow=100;c.heat=g.townCaps().heat;g.updateTown(60);const full=c.snow===100;
          c.snow=0;g.updateTown(120);const recovery=c.snow>1.9;
          c.tiles={'20,20':'collector'};g.invalidateTown();c.snow=100;g.updateTown(60);const disconnected=c.snow===100;
          c.tiles={'4,0':'collector'};g.invalidateTown();g.updateTown(60);const renewable=Math.abs(c.snow-106)<.001;
          c.snow=g.townCaps().snow;g.updateTown(600);const capped=c.snow===g.townCaps().snow;
          g.state.plow.wx=9999;g.state.plow.wy=-9999;g.updateTown(.1);
          return {recipe,reserve,full,recovery,disconnected,renewable,capped,bounded:Math.abs(g.state.plow.wx)<624&&Math.abs(g.state.plow.wy)<624};
        }''')
        self.assertTrue(all(result.values()),result)

    def test_city_campaign_completes_without_resource_grants(self):
        self.game()
        result=self.page.evaluate((ROOT/'tests/city_campaign.js').read_text())
        self.assertTrue(result['completed'],result)
        self.assertEqual(result['cleared'],2304)
        self.assertGreaterEqual(result['population'],40)
        self.assertGreater(result['minutes'],15)
        self.assertLess(result['minutes'],90)
        self.assertTrue(all(value>=0 for value in result['stock'].values()),result)

    def test_mobile_city_menu_and_canvas_placement(self):
        self.page.set_viewport_size({'width':390,'height':844})
        self.game()
        self.page.locator('[data-game-mode="city"]').last.click()
        self.page.wait_for_function("gameTest.state.mode==='city'",polling=20)
        self.page.locator('#btn-start-game').click()
        self.page.evaluate('gameTest.getCellAtWorld(117,13).snow=0;gameTest.renderScene(.016)')
        self.page.locator('#city-open').click()
        self.page.locator('[data-city-tab="build"]').click()
        self.page.locator('[data-town-build="road"]').click()
        position=self.page.evaluate('gameTest.worldToScreen(117,13)')
        self.page.mouse.click(position['x'],position['y'])
        self.assertIsNone(self.page.evaluate("gameTest.state.city.tiles['4,0']"))
        self.page.locator('#city-confirm').click()
        self.assertEqual(self.page.evaluate("gameTest.state.city.tiles['4,0']"),'road')
        self.assertFalse(self.page.evaluate('gameTest.joystick.active'))

    def test_city_districts_network_and_dismantling(self):
        self.game()
        result=self.page.evaluate('''async()=>{
          const g=gameTest;await g.switchGameMode('city');const c=g.state.city;
          Object.assign(c,{snow:1000,heat:1000,water:1000,stage:1});
          for(let x=4;x<=12;x++){const cell=g.getCellAtWorld(x*26+13,13);cell.snow=0;g.buildTownAt(x,0,'road');}
          for(let y=1;y<12;y++){g.getCellAtWorld(325,y*26+13).snow=0;g.buildTownAt(12,y,'road');}
          const relayLocked=!!g.townBuildReason(12,12,'relay');
          for(let y=8;y<=16;y++)for(let x=8;x<=16;x++){const cell=g.getCellAtWorld(x*26+13,y*26+13);cell.snow=cell.berm=0;}
          const relay=g.buildTownAt(12,12,'relay'),protectedDistrict=g.townProtected(16,16)&&!g.townProtected(17,17);
          const before=c.snow,blocked=!g.buildTownAt(8,0,'demolish')&&c.snow===before;
          const dismantled=g.buildTownAt(12,12,'demolish')&&!g.townProtected(16,16);
          const retry=g.buildTownAt(12,12,'relay');
          // Disconnected branches do not bypass the road rule.
          c.tiles['20,20']='road';g.invalidateTown();g.getCellAtWorld(21*26+13,20*26+13).snow=0;
          const island=!g.buildTownAt(21,20,'home');
          return {relayLocked,relay,protectedDistrict,blocked,dismantled,retry,island};
        }''')
        self.assertTrue(all(result.values()),result)

    def test_city_legacy_migration_and_chapter_save(self):
        self.game()
        result=self.page.evaluate('''async()=>{
          const g=gameTest;await g.switchGameMode('city');
          Object.assign(g.state.city,{snow:999,heat:777,stage:2,reserve:60,tiles:{'4,0':'geothermal'}});
          g.invalidateTown();g.saveProgress();g.loadProgress();
          const persisted=g.state.city.stage===2&&g.state.city.reserve===60&&g.state.city.tiles['4,0']==='geothermal';
          g.updateTown(1);const legacyStock=g.state.city.snow===999&&g.state.city.heat===777;
          g.state.city.version=undefined;g.state.city.stage=undefined;g.saveProgress();g.loadProgress();
          return {persisted,legacyStock,migrated:g.state.city.stage===1&&g.state.city.snow===999};
        }''')
        self.assertTrue(all(result.values()),result)

    def test_city_growth_requires_services_and_network_capacity(self):
        self.game()
        result=self.page.evaluate('''async()=>{
          const g=gameTest;await g.switchGameMode('city');const c=g.state.city;
          c.tiles={'4,0':'home'};g.invalidateTown();Object.assign(c,{population:4,water:0,food:0});
          g.updateTown(60);const noGrowth=c.population===4&&c.service.includes('paused');
          Object.assign(c,{water:20,food:20});g.updateTown(60);const growth=Math.abs(c.population-4.72)<.001;
          // Six homes consume the initial 12 units of heat-network capacity.
          c.tiles={'4,0':'home','-5,0':'home','0,4':'home','0,-5':'home','3,2':'home','2,3':'home'};g.invalidateTown();
          Object.assign(c,{snow:500,heat:100,water:100});g.getCellAtWorld(4*26+13,39).snow=0;
          const full=g.townBuildReason(4,1,'home').includes('network full');
          const source=g.buildTownAt(4,1,'boiler');
          return {noGrowth,growth,full,source};
        }''')
        self.assertTrue(all(result.values()),result)

    def test_city_planner_fits_small_screens_and_pauses_controls(self):
        self.game()
        self.page.evaluate("gameTest.switchGameMode('city')")
        self.page.locator('#btn-start-game').click()
        for width,height in [(320,480),(390,844),(844,390),(1280,900)]:
            self.page.set_viewport_size({'width':width,'height':height})
            self.page.locator('#city-open').click()
            self.assertTrue(self.page.evaluate('gameTest.townPlanning()'))
            self.assertTrue(self.page.evaluate('''()=>{const g=gameTest,before=g.state.elapsed;
              g.frameLoop(performance.now()+50);return g.state.elapsed===before;}'''))
            panel=self.page.locator('#city-panel').bounding_box()
            self.assertGreaterEqual(panel['x'],0)
            self.assertGreaterEqual(panel['y'],0)
            self.assertLessEqual(panel['x']+panel['width'],width)
            self.assertLessEqual(panel['y']+panel['height'],height)
            self.page.locator('[data-city-tab="economy"]').click()
            self.page.locator('#city-reserve').select_option('60')
            self.assertEqual(self.page.evaluate('gameTest.state.city.reserve'),60)
            self.page.keyboard.press('Escape')
            self.assertFalse(self.page.evaluate('gameTest.townPlanning() || gameTest.state.paused'))
        self.page.locator('#city-open').click()
        self.page.locator('[data-city-tab="build"]').click()
        self.assertTrue(self.page.locator('[data-town-build="climate"]').is_disabled())
        self.page.locator('[data-town-build="road"]').click()
        self.page.keyboard.press('Space')
        self.assertEqual(self.page.evaluate('gameTest.state.plow.dashTimer'),0)
        self.page.locator('#city-cancel').click()
        self.assertFalse(self.page.evaluate('gameTest.townPlanning()'))

    def test_city_ping_locates_the_last_snow_patch(self):
        self.game()
        result=self.page.evaluate('''async()=>{
          const g=gameTest;await g.switchGameMode('city');
          for(let y=-24;y<24;y++)for(let x=-24;x<24;x++){
            const c=g.getCellAtWorld(x*26+13,y*26+13);c.snow=0;c.berm=0;
          }
          const c=g.getCellAtWorld(13*26+13,15*26+13);c.snow=.7;
          g.triggerHornPing();const target=g.state.pingTarget;
          c.snow=0;g.state.plow.hornCooldown=0;g.triggerHornPing();
          return {located:target?.type==='snow' && target.wx===351 && target.wy===403,empty:g.state.pingTarget===null};
        }''')
        self.assertTrue(all(result.values()),result)

    def test_upgrade_prices_and_max_level(self):
        self.game()
        result = self.page.evaluate('''() => {
          const {state,getUpgradeCost,buyUpgrade}=gameTest;let total=0;const costs=[];
          for(const track of Object.keys(state.upgrades)){
            const row=[];for(let level=1;level<6;level++){state.upgrades[track]=level;const c=getUpgradeCost(track);row.push(c);total+=c;}
            costs.push(row);state.upgrades[track]=6;
          }
          state.credits=1000000;const before=state.credits;buyUpgrade('blade');
          return {total,costs,max:state.upgrades.blade,uncharged:before===state.credits};
        }''')
        self.assertEqual(result['total'], 2325000)
        self.assertTrue(all(b > a for row in result['costs'] for a, b in zip(row, row[1:])))
        self.assertEqual(result['max'], 6)
        self.assertTrue(result['uncharged'])

if __name__ == '__main__':
    unittest.main()
