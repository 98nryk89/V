// Loopback-only synthetic iPhone for the browser integration test.
import dgram from 'node:dgram';
import readline from 'node:readline';
import {createBridge} from '../kamikan-bridge/src/bridge.js';
const phone=dgram.createSocket('udp4');
await new Promise(resolve=>phone.bind(0,'127.0.0.1',resolve));
let destination,frame={FaceFound:true,Hotkey:-1,Rotation:{x:0,y:0,z:0},Position:{x:0,y:0,z:0},BlendShapes:[]};
phone.on('message',(message,remote)=>{destination={port:JSON.parse(message).ports[0],address:remote.address}});
const bridge=createBridge({iphoneIp:'127.0.0.1',iphonePort:phone.address().port,udpPort:0,httpPort:0,htmlDir:new URL('../dist',import.meta.url).pathname},{log:()=>{}});
const address=await bridge.start();
const timer=setInterval(()=>{if(destination)phone.send(JSON.stringify(frame),destination.port,destination.address)},16);
console.log(JSON.stringify(address));
readline.createInterface({input:process.stdin}).on('line',line=>{frame=JSON.parse(line)});
process.on('SIGTERM',async()=>{clearInterval(timer);await bridge.stop();phone.close();process.exit(0)});
