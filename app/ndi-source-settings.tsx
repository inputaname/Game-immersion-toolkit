'use client';
import {useInterfaceTranslation} from '../lib/interface-language';
import {GAME_NAMES,type GameId} from '../lib/games';
import {useEffect,useState} from 'react';
const API='http://127.0.0.1:8766';
type Discovery={available:boolean;message:string|null;sources:string[];link:string};
export type CaptureSourceSettings={capture_source:'window'|'ndi';ndi_source:string;ndi_game:GameId|null};
// NDI® is a trademark of Vizrt NDI AB. Its licence asks for an ndi.video link
// wherever NDI can be selected, so the link stays next to the source choice.
export function NdiSourceSettings({game,value,onChange}:{game:GameId;value:CaptureSourceSettings;onChange:(next:CaptureSourceSettings)=>void}){
 const uiText=useInterfaceTranslation();
 const active=value.capture_source==='ndi'&&value.ndi_game===game;
 const [discovery,setDiscovery]=useState<Discovery|null>(null),[busy,setBusy]=useState(false);
 async function discover(){setBusy(true);try{const response=await fetch(API+'/api/ndi/sources',{cache:'no-store'});if(!response.ok)throw Error();setDiscovery(await response.json() as Discovery);}
  catch{setDiscovery({available:false,message:uiText('Could not search for NDI sources.'),sources:[],link:'https://ndi.video/tools/'});}finally{setBusy(false);}}
 useEffect(()=>{if(active)void discover();},[active]);
 const sources=discovery?.sources??[],listed=!value.ndi_source||sources.includes(value.ndi_source);
 return <fieldset className="settings-key"><legend>{uiText('Capture source')}</legend>
  <label>{uiText('Read subtitles from')}<select aria-label={uiText('Capture source')} value={active?'ndi':'window'}
   onChange={e=>onChange(e.target.value==='ndi'?{...value,capture_source:'ndi',ndi_game:game}:{...value,capture_source:'window'})}>
   <option value="window">{uiText('Game window on this PC')}</option>
   <option value="ndi">{uiText('NDI® video on my local network')}</option>
  </select></label>
  {value.capture_source==='ndi'&&!active&&value.ndi_game&&<p className="toolkit-setup-note">{uiText('NDI capture is set to')} {GAME_NAMES[value.ndi_game]}. {uiText('Choose NDI here to switch it to this game.')}</p>}
  {active&&<>
   <label>{uiText('NDI source')}<select aria-label={uiText('NDI source')} value={value.ndi_source} disabled={busy}
    onChange={e=>onChange({...value,ndi_source:e.target.value})}>
    <option value="">{busy?uiText('Searching…'):uiText('Choose a source')}</option>
    {!listed&&<option value={value.ndi_source}>{value.ndi_source} ({uiText('not found now')})</option>}
    {sources.map(name=><option key={name} value={name}>{name}</option>)}
   </select></label>
   <div className="settings-key-actions"><button type="button" disabled={busy} onClick={()=>void discover()}>{uiText('Search again')}</button></div>
   {discovery&&!discovery.available&&<p role="status">{discovery.message}</p>}
   {discovery?.available&&!sources.length&&<p role="status">{uiText('No NDI sources found. Start the broadcast on your phone, tablet or streaming PC, then search again.')}</p>}
   <p className="toolkit-setup-note">{uiText('Video goes directly between your devices on this network, without a relay or cloud service. NDI is not encrypted: anyone on the same network can find and watch the stream, so use a home network you trust.')}</p>
  </>}
  <p className="toolkit-setup-note">NDI® {uiText('is a registered trademark of Vizrt NDI AB.')} <a href={discovery?.link??'https://ndi.video/tools/'} target="_blank" rel="noreferrer">ndi.video</a></p>
 </fieldset>;
}
