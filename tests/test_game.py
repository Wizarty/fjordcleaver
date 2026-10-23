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
          performSnowPlowing, recordRescue, triggerHornPing, createChunk, WEATHER_PHASES, renderScene, triggerPlowDash, triggerMeltPulse, joystick, getSteeringInput, getMaxSpeed};'''
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
            self.page.locator('canvas').dispatch_event(kind, {'pointerId': pointer,
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
        self.page.locator('canvas').dispatch_event('pointerdown', {'pointerId': 9,
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
        self.page.locator('canvas').dispatch_event('pointerdown', {'pointerId': 7, 'pointerType': 'touch', 'clientX': 700, 'clientY': 400})
        self.page.locator('canvas').dispatch_event('pointerup', {'pointerId': 7, 'pointerType': 'touch'})
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
