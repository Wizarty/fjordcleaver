"""Contract tests use an explicit SDK mock, not the real YouTube sandbox."""
import json
from pathlib import Path
import tempfile
import unittest
import zipfile
import test_game
from tools.build_playables import build

ROOT = Path(__file__).resolve().parents[1]
MOCK = '''
window.sdkEvents=[];window.sdkCallbacks={};window.sdkSaves=[];window.storageCalls=0;
window.failSave=false;window.failLoad=FAIL_LOAD;window.deferSave=false;window.saveResolvers=[];
window.ytgame={IN_PLAYABLES_ENV:true,
 game:{
  firstFrameReady:()=>sdkEvents.push('firstFrameReady'),gameReady:()=>sdkEvents.push('gameReady'),
  loadData:async()=>{sdkEvents.push('loadData');if(failLoad)throw Error('Offline');return JSON.stringify({credits:1234,upgrades:{engine:2}});},
  saveData:raw=>{sdkSaves.push(raw);if(failSave)return Promise.reject(Error('Save offline'));return deferSave?new Promise(resolve=>saveResolvers.push(resolve)):Promise.resolve();}
 },
 system:{isAudioEnabled:()=>false,
  onPause:cb=>{sdkCallbacks.pause=cb;sdkEvents.push('subscribePause');},
  onResume:cb=>{sdkCallbacks.resume=cb;sdkEvents.push('subscribeResume');},
  onAudioEnabledChange:cb=>{sdkCallbacks.audio=cb;sdkEvents.push('subscribeAudio');}},
 health:{logError:()=>sdkEvents.push('logError'),logWarning:()=>sdkEvents.push('logWarning')}
};
Storage.prototype.getItem=Storage.prototype.setItem=()=>{storageCalls++;throw Error('Local storage is forbidden in SDK tests');};
'''

class PlayablesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        test_game.GameTests.setUpClass()
        cls.browser=test_game.GameTests.browser
        cls.url=test_game.GameTests.url

    @classmethod
    def tearDownClass(cls):
        test_game.GameTests.tearDownClass()

    def setUp(self):
        self.page=self.browser.new_page(viewport={'width':1280,'height':900})
        self.errors=[]
        self.page.on('pageerror',lambda error:self.errors.append(str(error)))
        self.page.route('https://**/*',lambda r:r.abort())

    def tearDown(self):
        self.page.close()
        self.assertEqual(self.errors,[])

    def start(self,fail=False):
        self.page.add_init_script(MOCK.replace('FAIL_LOAD','true' if fail else 'false'))
        source=(ROOT/'index.html').read_text()
        source=source.replace('let lastTime = performance.now();',
            'window.gameTest={state,platform,audio,keys,saveProgress};let lastTime = performance.now();')
        self.page.route('**/hosted.html',lambda r:r.fulfill(content_type='text/html',body=source))
        self.page.goto(self.url+'hosted.html',wait_until='domcontentloaded')
        self.page.wait_for_function("!document.querySelector('#btn-start-game').disabled")
        if not fail:self.page.wait_for_function("sdkEvents.includes('gameReady')")

    def test_ready_order_cloud_load_and_no_browser_storage(self):
        self.start()
        result=self.page.evaluate('''() => ({events:sdkEvents,credits:gameTest.state.credits,
          engine:gameTest.state.upgrades.engine,storageCalls})''')
        self.assertEqual(result['credits'],1234)
        self.assertEqual(result['engine'],2)
        self.assertEqual(result['storageCalls'],0)
        events=result['events']
        self.assertEqual(events.count('firstFrameReady'),1)
        self.assertEqual(events.count('gameReady'),1)
        self.assertLess(events.index('firstFrameReady'),events.index('gameReady'))

    def test_platform_audio_pause_resume_preserve_user_pause(self):
        self.start()
        self.page.locator('#btn-start-game').click()
        self.assertTrue(self.page.evaluate('gameTest.audio.platformMuted'))
        self.assertEqual(self.page.evaluate('gameTest.audio.master.gain.value'),0)
        self.page.evaluate('sdkCallbacks.audio(true)')
        self.page.wait_for_function("gameTest.audio.ctx.state === 'running'")
        self.page.keyboard.down('d')
        self.page.wait_for_timeout(150)
        self.page.evaluate('sdkCallbacks.pause()')
        before=self.page.evaluate('[gameTest.state.plow.wx,gameTest.state.plow.wy]')
        self.page.wait_for_timeout(150)
        self.assertEqual(before,self.page.evaluate('[gameTest.state.plow.wx,gameTest.state.plow.wy]'))
        self.page.wait_for_function("gameTest.audio.ctx.state === 'suspended'")
        self.page.evaluate('gameTest.state.paused=true;sdkCallbacks.resume()')
        self.assertTrue(self.page.evaluate('gameTest.state.paused'))
        self.page.evaluate('sdkCallbacks.audio(false);gameTest.audio.muted=false;gameTest.platform.syncAudio()')
        self.assertTrue(self.page.evaluate('gameTest.audio.platformMuted'))
        self.assertEqual(self.page.evaluate('storageCalls'),0)

    def test_cloud_writes_are_serialized_and_coalesce_latest_state(self):
        self.start()
        self.page.evaluate('''() => {
          deferSave=true;
          gameTest.state.credits=111;gameTest.saveProgress();
          gameTest.state.credits=222;gameTest.saveProgress();
          gameTest.state.credits=333;gameTest.saveProgress();
        }''')
        self.assertEqual(self.page.evaluate('sdkSaves.length'),1)
        self.page.evaluate('saveResolvers.shift()()')
        self.page.wait_for_function('sdkSaves.length===2')
        self.assertEqual(json.loads(self.page.evaluate('sdkSaves[1]'))['credits'],333)
        self.page.evaluate('saveResolvers.shift()()')
        self.page.wait_for_function('!gameTest.platform.saving')
        self.assertEqual(self.page.evaluate('storageCalls'),0)

    def test_failed_cloud_load_cannot_overwrite_progress_and_can_retry(self):
        self.start(fail=True)
        self.assertIn('Retry',self.page.locator('#btn-start-game').inner_text())
        rejected=self.page.evaluate("gameTest.platform.write('{}').then(()=>false,()=>true)")
        self.assertTrue(rejected)
        self.assertEqual(self.page.evaluate('sdkSaves.length'),0)
        self.page.evaluate('failLoad=false')
        self.page.locator('#btn-start-game').click()
        self.page.wait_for_function("sdkEvents.includes('gameReady')")
        self.assertEqual(self.page.evaluate("sdkEvents.filter(e=>e==='subscribePause').length"),1)
        self.assertEqual(self.page.evaluate("sdkEvents.filter(e=>e==='firstFrameReady').length"),1)
        self.assertEqual(self.page.evaluate('gameTest.state.credits'),1234)

    def test_failed_save_is_reported_and_later_save_recovers(self):
        self.start()
        result=self.page.evaluate('''async () => {
          failSave=true;
          const rejected=await gameTest.platform.write('{"credits":100}').then(()=>false,()=>true);
          failSave=false;
          await gameTest.platform.write('{"credits":200}');
          return {rejected,reported:sdkEvents.includes('logError'),saving:gameTest.platform.saving,last:JSON.parse(sdkSaves.at(-1))};
        }''')
        self.assertTrue(result['rejected'])
        self.assertTrue(result['reported'])
        self.assertFalse(result['saving'])
        self.assertEqual(result['last']['credits'],200)

    def test_packaged_game_runs_with_only_the_expected_sdk_request(self):
        with tempfile.TemporaryDirectory() as temp:
            output=build(Path(temp)/'playable.zip')
            with zipfile.ZipFile(output) as package: source=package.read('index.html').decode()
        self.page.route('**/packaged.html',lambda r:r.fulfill(content_type='text/html',body=source))
        self.page.route('https://www.youtube.com/game_api/v1',lambda r:r.fulfill(
            content_type='application/javascript',body=MOCK.replace('FAIL_LOAD','false')))
        self.page.goto(self.url+'packaged.html',wait_until='domcontentloaded')
        self.page.wait_for_function("sdkEvents.includes('gameReady')")
        self.assertEqual(self.page.locator('#hud-credits').inner_text(),'1.2K')
        self.page.locator('#btn-start-game').click()
        self.assertTrue(self.page.locator('#modal-backdrop').is_hidden())
        self.assertEqual(self.page.evaluate('storageCalls'),0)

    def test_packaging_loads_sdk_first_and_has_no_font_or_app_dependencies(self):
        with tempfile.TemporaryDirectory() as temp:
            output=build(Path(temp)/'playable.zip')
            with zipfile.ZipFile(output) as package:
                self.assertEqual(set(package.namelist()),{'index.html','THIRD_PARTY_NOTICES.txt'})
                source=package.read('index.html').decode()
            self.assertLess(output.stat().st_size,100000)
        self.assertIn('<script src="https://www.youtube.com/game_api/v1"></script>',source)
        self.assertLess(source.index('https://www.youtube.com/game_api/v1'),source.index('__YOUTUBE_PLAYABLES_BUILD__'))
        self.assertNotIn('fonts.googleapis.com',source)
        self.assertNotIn('window.confirm(',source)
        self.assertNotIn('window.location.reload(',source)
        self.assertNotIn('fetch(',source)

if __name__=='__main__': unittest.main()
