const fs=require('fs'),vm=require('vm'),assert=require('assert');
const nodes=new Map();
class Element{constructor(){this.value='';this.children=[];this.disabled=false;this.dataset={};}append(e){this.children.push(e)}replaceChildren(){this.children=[]}addEventListener(){}scrollIntoView(){}}
const $=id=>{if(!nodes.has(id))nodes.set(id,new Element);return nodes.get(id)};
let values={Epsilon33:.02,NT_total:10,NT_start:6,NN:32},calls=[];
const output={params:values,stats:{rms:.1,peak:.2,dominant_frequency:.3},series:[]};
let response={action:{patch:{Epsilon33:.04},sweep:null,reply:'已调参'}};
const sandbox={$,console,Date,Error,JSON,Number,String,Object,Array,RegExp,
 document:{addEventListener(){},querySelectorAll(){return[]},createElement(){return new Element}},
 params:()=>({...values}),fillParameters:v=>{values=v},show:r=>{sandbox.shown=r},result:null,busy:false,ai:null,
 save(){},fetch:async(url,opts)=>{calls.push({url,body:JSON.parse(opts.body)});return{ok:true,json:async()=>url.endsWith('/chat')?response:url.endsWith('/sweep')?{param:'Epsilon33',runs:[{value:.02,result:output},{value:.08,result:output}],note:'本地仿真'}:output}}};
sandbox.window=sandbox;sandbox.requestApi=async(path,data)=>{const r=await sandbox.fetch('/api/'+path,{body:JSON.stringify(data)});return r.json()};
vm.createContext(sandbox);vm.runInContext(fs.readFileSync(require('path').join(__dirname,'../assistant.js'),'utf8'),sandbox);
(async()=>{
 $('chatInput').value='把 Epsilon33 改为0.04并运行';await vm.runInContext('sendChat()',sandbox);
 assert.equal(values.Epsilon33,.04);assert(sandbox.shown);assert.equal(calls.length,2);assert.equal($('sendChat').disabled,false);
 response={action:{patch:{},sweep:{param:'Epsilon33',from:.02,to:.08,n:6},reply:'扫频'}};
 $('chatInput').value='扫频';await vm.runInContext('sendChat()',sandbox);
 assert(calls[2].body.history.length);assert(calls[2].body.results.length);assert.equal($('caseSelect').disabled,false);
 assert.equal($('comparisonTable').children.length,3);assert.equal($('exportTask').disabled,false);
 for(let i=0;i<15;i++){ $('chatInput').value='继续解释';response={action:{patch:{},sweep:null,reply:'继续回答'}};await vm.runInContext('sendChat()',sandbox)}assert(vm.runInContext('chatHistory.length',sandbox)>30);$('clearChat').onclick();assert.equal(vm.runInContext('chatHistory.length',sandbox),1);
 console.log('PASS: frontend patch/run, history/results context, sweep table, export and busy state');
})().catch(e=>{console.error(e);process.exitCode=1});
