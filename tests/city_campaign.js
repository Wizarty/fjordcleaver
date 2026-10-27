// Economy scenario: actual harvesting and construction; no resource grants or forced unlocks.
// Travel/rendering/weather are excluded. This measures an ideal planning baseline, not playtime.
async () => {
  const g=gameTest;await g.switchGameMode('city');
  const city=g.state.city;let seconds=0,harvests=0;const events=[];
  const tick=()=>{g.updateTown(1);g.state.plow.pulseCooldown=Math.max(0,g.state.plow.pulseCooldown-1);seconds++;};
  function meltAt(x,y){g.state.plow.wx=(x+.5)*26;g.state.plow.wy=(y+.5)*26;g.triggerMeltPulse();harvests++;}
  function harvest(){
    if(g.state.plow.pulseCooldown>0 || city.snow>g.townCaps().snow-35)return;
    for(let y=-24;y<24;y++)for(let x=-24;x<24;x++){
      if(g.getCellAtWorld(x*26+13,y*26+13).snow>.02){meltAt(x,y);return;}
    }
  }
  function build(x,y,type){
    while(seconds<7200){
      const cell=g.getCellAtWorld(x*26+13,y*26+13);
      if((cell.snow>.02||cell.berm>.02)&&g.state.plow.pulseCooldown<=0)meltAt(x,y);
      if(!g.townBuildReason(x,y,type)){
        if(!g.buildTownAt(x,y,type))throw Error('Validated build failed');
        events.push({type,time:seconds,stage:city.stage});return;
      }
      harvest();tick();
    }
    throw Error(`${type} at ${x},${y} stalled: ${g.townBuildReason(x,y,type)}; ${JSON.stringify(city)}`.slice(0,900));
  }
  for(let x=4;x<=14;x++)build(x,0,'road');
  build(4,1,'boiler');build(5,1,'water');build(6,1,'home');build(7,1,'depot');
  // The first chapter also needs 10% cleared; harvesting while waiting fulfills it.
  build(8,1,'greenhouse');build(9,1,'home');build(10,1,'geothermal');
  build(11,1,'home');build(13,1,'home');build(14,1,'home');
  build(4,-1,'boiler');build(5,-1,'water');
  build(6,-1,'collector');build(7,-1,'collector');build(8,-1,'collector');build(9,-1,'greenhouse');
  for(let x=-5;x>=-12;x--)build(x,0,'road');
  for(const x of [12,-12])for(const sign of [-1,1]){
    for(let y=sign;y!==12*sign;y+=sign)build(x,y,'road');
    // Clear the full district with real pulses before commissioning its relay.
    for(let y=sign*12-4;y<=sign*12+4;y+=3)for(let dx=x-4;dx<=x+4;dx+=3){
      while(g.state.plow.pulseCooldown>0)tick();meltAt(dx,y);
    }
    build(x,sign*12,'relay');
  }
  build(10,-1,'climate');
  while(!city.completed && seconds<7200){
    if(g.state.plow.pulseCooldown<=0){
      let found=false;
      for(let y=-24;y<24&&!found;y++)for(let x=-24;x<24;x++){
        const c=g.getCellAtWorld(x*26+13,y*26+13);
        if(c.snow>.02||c.berm>.02){meltAt(x,y);found=true;break;}
      }
    }
    tick();
  }
  return {seconds,minutes:seconds/60,harvests,events,completed:city.completed,stage:city.stage,population:city.population,
    cleared:g.cityStats().cleared,stock:{snow:city.snow,heat:city.heat,water:city.water,food:city.food}};
}
