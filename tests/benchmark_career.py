"""Accelerate real gameplay logic to measure time to all seven maximum upgrades."""
import json
from test_game import GameTests

GameTests.setUpClass()
case = GameTests()
case.setUp()
try:
    case.game()
    result = case.page.evaluate('''() => {
      const {state,keys,updateSimulation,getUpgradeCost,buyUpgrade,chunks,triggerPlowDash,triggerMeltPulse}=gameTest;
      state.vortices=[
        {wx:140,wy:-160,vx:16,vy:14,spin:0,radius:42,active:true},
        {wx:-190,wy:130,vx:-14,vy:16,spin:0,radius:46,active:true},
        {wx:260,wy:210,vx:-15,vy:-14,spin:0,radius:44,active:true},
        {wx:-280,wy:-180,vx:18,vy:-12,spin:0,radius:40,active:true}
      ];
      keys.add('KeyD');let elapsed=0;const milestones=[];
      for(let i=0;i<288000;i++){
        updateSimulation(.05);elapsed+=.05;
        if(i%20===0){
          triggerPlowDash();triggerMeltPulse();
          const tracks=Object.keys(state.upgrades).sort((a,b)=>getUpgradeCost(a)-getUpgradeCost(b));
          for(const track of tracks) if(state.upgrades[track]<6 && state.credits>=getUpgradeCost(track)){
            buyUpgrade(track);milestones.push({minute:+(elapsed/60).toFixed(1),track,level:state.upgrades[track]});
          }
          const cx=Math.floor(state.plow.wx/312),cy=Math.floor(state.plow.wy/312);
          for(const [key,chunk] of chunks)if(Math.abs(chunk.cx-cx)>4 || Math.abs(chunk.cy-cy)>4)chunks.delete(key);
        }
        if(Object.values(state.upgrades).every(level=>level===6))break;
      }
      return {minutes:+(elapsed/60).toFixed(2),levels:state.upgrades,milestones,saveBytes:(localStorage.getItem('fjordcleaver_save_v1') || '').length*2};
    }''')
    print(json.dumps(result, indent=2))
    assert 180 <= result['minutes'] <= 240, result
    assert all(level == 6 for level in result['levels'].values()), result
finally:
    case.tearDown()
    GameTests.tearDownClass()
