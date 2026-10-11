// Turn-based voice conversation uses the same checked Libby chat as typing.
const recognitionClass=window.SpeechRecognition || window.webkitSpeechRecognition;
let useBrowserRecognition=!!recognitionClass;
const deviceSpeech=window.speechSynthesis;
let voiceActive=false,voiceEpoch=0,voiceBusy=false,recognizer=null,microphone=null,recording=null,audioContext=null;
let silenceTimer=null,recordTimer=null,voiceAbort=null,pendingVoiceTurn=null,replyReceived=false,speechDone=null,quietEnds=0;
const voiceStatus=text=>{$('#voice-status').textContent=text;};
function populateVoices(){
 const choice=$('#voice-choice'),selected=choice.value;choice.replaceChildren();
 const option=make('option','Device default');option.value='';choice.append(option);
 for(const voice of deviceSpeech?.getVoices() || []){const option=make('option',`${voice.name} · ${voice.lang}`);option.value=voice.voiceURI;choice.append(option);}
 choice.value=selected;
}
populateVoices();if(deviceSpeech)deviceSpeech.addEventListener('voiceschanged',populateVoices);
function cancelSpeaking(){deviceSpeech?.cancel();if(speechDone){const done=speechDone;speechDone=null;done();}$('#voice-interrupt').disabled=true;}
function clearRecordingTimers(){clearInterval(silenceTimer);clearTimeout(recordTimer);silenceTimer=recordTimer=null;}
function endVoice(text='Voice is off'){
 voiceActive=false;voiceBusy=false;voiceEpoch++;clearRecordingTimers();
 recognizer?.abort();recognizer=null;voiceAbort?.abort();voiceAbort=null;
 if(recording?.state==='recording'){recording.onstop=null;recording.stop();}recording=null;
 microphone?.getTracks().forEach(track=>track.stop());microphone=null;
 audioContext?.close().catch(()=>{});audioContext=null;cancelSpeaking();
 $('#voice-toggle').textContent='🎙 Talk to Libby';$('#voice-toggle').setAttribute('aria-pressed','false');voiceStatus(text);
}
async function sayReply(text,epoch){
 if(!deviceSpeech){endVoice('Your device has no speech playback. Replies are still shown in chat.');return;}
 cancelSpeaking();voiceStatus('Libby is speaking…');$('#voice-interrupt').disabled=false;
 // Short chunks avoid device speech engines stalling on long replies.
 const clean=text.replace(/https?:\/\/\S+/g,'').replace(/[◇↗↑*#]/g,'');
 const chunks=(clean.match(/.+?(?:[.!?](?=\s|$)|\n|$)/gs) || [clean]).flatMap(sentence=>{const parts=[];while(sentence.length>180){const at=sentence.lastIndexOf(' ',180);const split=at>0?at:180;parts.push(sentence.slice(0,split));sentence=sentence.slice(split).trim();}if(sentence.trim())parts.push(sentence);return parts;});
 for(const chunk of chunks){
  if(epoch!==voiceEpoch)return;
  await new Promise((resolve,reject)=>{
   const utterance=new SpeechSynthesisUtterance(chunk);utterance.lang='en-US';utterance.rate=1;
   utterance.voice=deviceSpeech.getVoices().find(v=>v.voiceURI===$('#voice-choice').value) || null;
   speechDone=resolve;utterance.onend=()=>{if(speechDone===resolve)speechDone=null;resolve();};utterance.onerror=event=>{if(speechDone===resolve)speechDone=null;if(['canceled','interrupted'].includes(event.error)||epoch!==voiceEpoch)resolve();else reject(new Error('Speech playback failed.'));};deviceSpeech.speak(utterance);
  });
 }
 if(epoch!==voiceEpoch)return;$('#voice-interrupt').disabled=true;
 if(voiceActive&&epoch===voiceEpoch){voiceBusy=false;setTimeout(()=>listen(epoch),350);}else voiceStatus('Voice is off');
}
function libbyVoiceReply(text){
 const pending=pendingVoiceTurn;replyReceived=true;
 if(pending&&pending.epoch!==voiceEpoch)return;
 if(voiceActive || $('#read-replies').checked){
  if(recognizer){recognizer.onresult=recognizer.onend=recognizer.onerror=null;recognizer.abort();recognizer=null;}
  if(recording?.state==='recording'){recording.onstop=null;recording.stop();clearRecordingTimers();}
  voiceBusy=true;sayReply(text,voiceEpoch).catch(()=>endVoice('Speech playback failed. You can still read the reply.'));
 }
}
async function submitSpeech(text,epoch){
 if(!voiceActive||epoch!==voiceEpoch)return;
 text=text.trim();if(!text){voiceBusy=false;listen(epoch);return;}
 if(text.length>4000){endVoice('Please ask a shorter question.');return;}
 voiceBusy=true;quietEnds=0;replyReceived=false;pendingVoiceTurn={epoch};voiceStatus('Libby is thinking…');
 await send(text);
 if(pendingVoiceTurn?.epoch===epoch)pendingVoiceTurn=null;
 if(!replyReceived&&voiceActive&&epoch===voiceEpoch)endVoice('Libby could not reply. Check the chat message and Check AI.');
}
function listen(epoch){
 if(!voiceActive||epoch!==voiceEpoch||voiceBusy)return;
 if(chatBusy){setTimeout(()=>listen(epoch),350);return;}
 voiceStatus('Listening… speak your question');
 if(useBrowserRecognition){
  const instance=new recognitionClass();recognizer=instance;instance.lang='en-US';instance.interimResults=true;instance.continuous=false;
  let submitted=false,failed=false;
  instance.onresult=event=>{
   if(epoch!==voiceEpoch||submitted)return;
   let final='',interim='';
   for(let i=event.resultIndex;i<event.results.length;i++){if(event.results[i].isFinal)final+=event.results[i][0].transcript;else interim+=event.results[i][0].transcript;}
   if(interim)voiceStatus('Hearing: '+interim);
   if(final){submitted=true;instance.stop();submitSpeech(final,epoch);}
  };
  instance.onerror=event=>{
   if(epoch!==voiceEpoch)return;
   if(event.error==='no-speech')return;
   failed=true;
   if(['network','service-not-allowed'].includes(event.error)&&navigator.mediaDevices?.getUserMedia&&window.MediaRecorder){instance.onresult=instance.onend=instance.onerror=null;instance.abort();recognizer=null;useBrowserRecognition=false;listen(epoch);return;}
   const messages={'not-allowed':'Microphone permission was denied. Allow it in your browser’s site settings to use voice.','audio-capture':'No microphone was found. Check your input device.','network':'Browser speech recognition is unavailable. Try again or type your question.'};
   endVoice(messages[event.error] || 'Speech recognition stopped. Try again or type your question.');
  };
  instance.onend=()=>{if(recognizer===instance)recognizer=null;if(voiceActive&&epoch===voiceEpoch&&!submitted&&!failed){if(++quietEnds>=3)endVoice('Voice paused after no speech. Click Talk to Libby to resume.');else setTimeout(()=>listen(epoch),350);}};
  try{instance.start();}catch{endVoice('Could not start your microphone. Try again.');}
 }else recordQuestion(epoch).catch(error=>{if(epoch===voiceEpoch)endVoice(error.name==='NotAllowedError'?'Microphone permission was denied. Allow it in your browser’s site settings.':error.message || 'Recording failed. Try again.');});
}
async function recordQuestion(epoch){
 if(!microphone){const stream=await navigator.mediaDevices.getUserMedia({audio:{echoCancellation:true,noiseSuppression:true}});if(!voiceActive||epoch!==voiceEpoch){stream.getTracks().forEach(track=>track.stop());return;}microphone=stream;}
 if(!voiceActive||epoch!==voiceEpoch){microphone?.getTracks().forEach(t=>t.stop());microphone=null;return;}
 const mime=['audio/webm;codecs=opus','audio/webm','audio/mp4'].find(type=>MediaRecorder.isTypeSupported(type));
 if(!mime)throw new Error('This browser cannot record a supported audio format. Try Chrome, Edge, or Safari.');
 const recorder=new MediaRecorder(microphone,mime?{mimeType:mime}:{});recording=recorder;
 const parts=[];let bytes=0,spoke=false,lastSound=performance.now(),started=lastSound;
 recorder.ondataavailable=event=>{if(event.data.size){parts.push(event.data);bytes+=event.data.size;if(bytes>6000000)endVoice('Recording is too long. Ask a shorter question.');}};
 recorder.onerror=()=>endVoice('The microphone recording failed. Try again.');
 recorder.onstop=async()=>{
  clearRecordingTimers();if(!voiceActive||epoch!==voiceEpoch)return;
  if(!spoke){endVoice('No speech detected. Click Talk to Libby to try again.');return;}
  voiceBusy=true;voiceStatus('Transcribing your question…');
  try{
   const audio=new Blob(parts,{type:recorder.mimeType});const buffer=new Uint8Array(await audio.arrayBuffer());let encoded='';for(let i=0;i<buffer.length;i+=8192)encoded+=String.fromCharCode(...buffer.subarray(i,i+8192));
   voiceAbort=new AbortController();const response=await fetch('/api/transcribe',{method:'POST',headers:{'Content-Type':'application/json'},signal:voiceAbort.signal,body:JSON.stringify({audio:btoa(encoded),mime:recorder.mimeType})});const result=await response.json();
   if(!response.ok)throw new Error(result.error || 'Transcription failed.');
   await submitSpeech(result.text,epoch);
  }catch(error){if(epoch===voiceEpoch)endVoice(error.message || 'Could not transcribe your question.');}
 };
 const Context=window.AudioContext || window.webkitAudioContext;
 if(!Context)throw new Error('This browser does not support voice recording. Try Chrome or Edge.');
 if(!audioContext)audioContext=new Context();await audioContext.resume();
 if(!voiceActive||epoch!==voiceEpoch)return;
 const source=audioContext.createMediaStreamSource(microphone),analyser=audioContext.createAnalyser();analyser.fftSize=2048;source.connect(analyser);
 const samples=new Uint8Array(analyser.fftSize);recorder.start(250);
 silenceTimer=setInterval(()=>{
  analyser.getByteTimeDomainData(samples);const rms=Math.sqrt(samples.reduce((sum,n)=>sum+((n-128)/128)**2,0)/samples.length);const now=performance.now();
  if(rms>.018){spoke=true;lastSound=now;}
  if((spoke&&now-lastSound>1500&&now-started>1500)||(!spoke&&now-started>12000)){source.disconnect();clearRecordingTimers();if(recorder.state==='recording')recorder.stop();}
 },100);
 recordTimer=setTimeout(()=>{source.disconnect();clearRecordingTimers();if(recorder.state==='recording')recorder.stop();},60000);
}
$('#voice-toggle').onclick=()=>{
 if(voiceActive){endVoice();return;}
 if(!window.isSecureContext){voiceStatus('Voice needs a secure HTTPS website.');return;}
 if(!recognitionClass && (!navigator.mediaDevices?.getUserMedia || !window.MediaRecorder)){voiceStatus('Voice input is unavailable in this browser. Try Chrome or Edge.');return;}
 if(chatBusy){voiceStatus('Wait for the current reply, then start voice.');return;}
 voiceActive=true;voiceBusy=false;quietEnds=0;voiceEpoch++;$('#voice-toggle').textContent='■ End voice';$('#voice-toggle').setAttribute('aria-pressed','true');listen(voiceEpoch);
};
$('#voice-interrupt').onclick=()=>{voiceEpoch++;const epoch=voiceEpoch;cancelSpeaking();voiceBusy=false;if(voiceActive)setTimeout(()=>listen(epoch),350);else voiceStatus('Playback stopped');};
$('#read-replies').onchange=()=>{if(!$('#read-replies').checked&&!voiceActive)cancelSpeaking();};
if(!deviceSpeech){$('#read-replies').disabled=true;$('#voice-choice').disabled=true;}
// Navigating, changing decks, or starting a new conversation releases the mic.
document.addEventListener('click',event=>{if(event.target.closest('[data-tab],#sidebar-decks button,#clear-chat,#manage-decks,#sidebar-add'))endVoice();},true);
$('#saved-decks').addEventListener('change',()=>endVoice());
document.addEventListener('visibilitychange',()=>{if(document.hidden)endVoice('Voice paused while this tab is hidden.');});
window.addEventListener('pagehide',()=>endVoice());
