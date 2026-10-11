"""Browser voice regression with deterministic speech/mic fixtures; no API spend."""
import os
from playwright.sync_api import sync_playwright, expect

BASE=os.environ.get('MTG_TEST_URL','http://127.0.0.1:8008')
SPEECH_FIXTURE="""
window.testRecognizers=[];window.testUtterances=[];window.testCancels=0;
class Recognition {start(){window.testRecognizers.push(this);}stop(){this.onend?.();}abort(){this.aborted=true;this.onend?.();}}
window.TestRecognition=Recognition;window.SpeechRecognition=Recognition;window.webkitSpeechRecognition=undefined;
window.SpeechSynthesisUtterance=class {constructor(text){this.text=text;}};
Object.defineProperty(window,'speechSynthesis',{value:{getVoices(){return [];},addEventListener(){},cancel(){window.testCancels++;},speak(u){window.testUtterances.push(u);}}});
localStorage.setItem('mtgvibes-library',JSON.stringify([{id:'voice-deck',name:'Voice deck',commander:'Omnath, Locus of Mana',cards:[{name:'Omnath, Locus of Mana',quantity:1},{name:'Forest',quantity:99}]}]));
localStorage.setItem('mtgvibes-deck',localStorage.getItem('mtgvibes-library').slice(1,-1));
"""
RECORD_FIXTURE="""
window.SpeechRecognition=undefined;window.webkitSpeechRecognition=undefined;window.testMicStops=0;
Object.defineProperty(navigator.mediaDevices,'getUserMedia',{value:async()=>({getTracks(){return [{stop(){window.testMicStops++;}}];}})});
window.MediaRecorder=class {static isTypeSupported(){return true;}constructor(){this.mimeType='audio/webm;codecs=opus';this.state='inactive';}start(){this.state='recording';}stop(){this.state='inactive';this.ondataavailable?.({data:new Blob(['audio-fixture'],{type:'audio/webm'})});this.onstop?.();}};
window.AudioContext=class {async resume(){}async close(){}createMediaStreamSource(){return {connect(){},disconnect(){}};}createAnalyser(){let count=0;return {fftSize:2048,getByteTimeDomainData(array){array.fill(count++<3?145:128);}};}};
"""
with sync_playwright() as p:
    browser=p.chromium.launch()
    context=browser.new_context(viewport={'width':1440,'height':900})
    context.add_init_script(SPEECH_FIXTURE)
    page=context.new_page()
    errors,calls=[],[]
    page.on('pageerror',lambda error:errors.append(str(error)))
    def reply(route):
        calls.append(route.request.post_data_json)
        answer='Your chance is 72.5 percent.' if calls[-1]['message']=='Read the odds.' else 'Your commander is green, so blue additions are outside its identity.'
        route.fulfill(json={'answer':answer, 'rule_references':[{'number':'903.5c','url':'https://yawgatog.com/resources/magic-rules/#R9035c'}]})
    page.route('**/api/chat',reply)
    page.goto(BASE)
    page.locator('#voice-toggle').click()
    expect(page.locator('#voice-toggle')).to_have_attribute('aria-pressed','true')
    expect(page.locator('#voice-status')).to_contain_text('Listening')
    page.evaluate("testRecognizers.at(-1).onresult({resultIndex:0,results:[Object.assign([{transcript:'Would a blue spell fit this deck?'}],{isFinal:true})]})")
    expect(page.locator('#voice-status')).to_contain_text('speaking')
    assert calls[0]['context']['deck']['commander']=='Omnath, Locus of Mana'
    assert calls[0]['message']=='Would a blue spell fit this deck?'
    assert page.evaluate('testRecognizers.length')==1, 'Microphone must not restart during speech'
    expect(page.locator('.rule-references a')).to_have_attribute('href','https://yawgatog.com/resources/magic-rules/#R9035c')
    page.locator('#voice-interrupt').click()
    expect(page.locator('#voice-status')).to_contain_text('Listening')
    assert page.evaluate('testRecognizers.length')==2
    page.evaluate("testRecognizers.at(-1).onresult({resultIndex:0,results:[Object.assign([{transcript:'What should I use instead?'}],{isFinal:true})]})")
    expect(page.locator('#voice-status')).to_contain_text('speaking')
    assert calls[1]['history'][0]['content']=='Would a blue spell fit this deck?'
    page.locator('#voice-toggle').click()
    expect(page.locator('#voice-toggle')).to_have_attribute('aria-pressed','false')
    expect(page.locator('#voice-status')).to_have_text('Voice is off')
    page.locator('#voice-toggle').click()
    page.evaluate("testRecognizers.at(-1).onerror({error:'not-allowed'})")
    expect(page.locator('#voice-status')).to_contain_text('permission was denied')
    expect(page.locator('#voice-toggle')).to_have_attribute('aria-pressed','false')
    page.locator('#read-replies').check()
    page.locator('#prompt').fill('Read the odds.')
    page.locator('#chat-form button').click()
    expect(page.locator('#voice-status')).to_contain_text('speaking')
    assert '72.5' in page.evaluate('testUtterances.at(-1).text'), 'Decimal probabilities must not split into separate numbers'
    page.locator('#voice-interrupt').click()
    expect(page.locator('#voice-status')).to_have_text('Playback stopped')
    for width,height in [(1366,768),(390,844)]:
        page.set_viewport_size({'width':width,'height':height})
        assert page.evaluate('document.documentElement.scrollHeight<=innerHeight')
        form=page.locator('#chat-form').bounding_box()
        assert form['y']+form['height']<=height
    context.close()

    fallback=browser.new_context()
    fallback.add_init_script(SPEECH_FIXTURE+RECORD_FIXTURE)
    page=fallback.new_page()
    page.on('pageerror',lambda error:errors.append(str(error)))
    recordings=[]
    def transcript(route):
        recordings.append(route.request.post_data_json)
        route.fulfill(json={'text':'Explain commander tax.'})
    page.route('**/api/transcribe',transcript)
    page.route('**/api/chat',reply)
    page.goto(BASE)
    page.locator('#voice-toggle').click()
    expect(page.locator('#voice-status')).to_contain_text('speaking',timeout=10000)
    assert recordings and recordings[0]['mime']=='audio/webm;codecs=opus'
    assert calls[-1]['message']=='Explain commander tax.'
    # Finishing the spoken reply automatically starts the next listening turn.
    page.evaluate('testUtterances.at(-1).onend()')
    expect(page.locator('#voice-status')).to_contain_text('Listening')
    page.locator('#voice-toggle').click()
    assert page.evaluate('testMicStops')>0
    fallback.close()
    recovery=browser.new_context()
    recovery.add_init_script(SPEECH_FIXTURE+RECORD_FIXTURE+'window.SpeechRecognition=window.TestRecognition;')
    page=recovery.new_page()
    page.on('pageerror',lambda error:errors.append(str(error)))
    page.route('**/api/transcribe',transcript)
    page.route('**/api/chat',reply)
    page.goto(BASE)
    page.locator('#voice-toggle').click()
    page.evaluate("testRecognizers.at(-1).onerror({error:'network'})")
    expect(page.locator('#voice-status')).to_contain_text('speaking',timeout=10000)
    assert len(recordings)==2,'Browser provider failure must recover through recording'
    page.evaluate("testUtterances.at(-1).onerror({error:'voice-unavailable'})")
    expect(page.locator('#voice-status')).to_contain_text('Speech playback failed')
    expect(page.locator('#voice-toggle')).to_have_attribute('aria-pressed','false')
    assert page.evaluate('testMicStops')>0
    recovery.close()
    assert not errors,errors
    browser.close()
    print('Voice questions, deck/history context, spoken replies, interrupt/end, permission denial, recording/transcription fallback, automatic next turn, microphone release, citations, and compact layouts passed.')
