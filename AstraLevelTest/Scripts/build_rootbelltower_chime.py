"""Synthesize an original quiet bronze bell, no external samples required."""
import array,json,math,wave
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];output=ROOT/'ArtSource/Audio/RootBelltower';output.mkdir(parents=True,exist_ok=True)
rate=44100;duration=5.;partials=[(1,.8,.65),(2.76,.28,.9),(5.41,.13,1.35),(8.93,.06,2.1),(13.34,.035,3.3)]
samples=[]
for i in range(int(rate*duration)):
    t=i/rate;attack=1-math.exp(-t*250);end=min(1,(duration-t)/.25)
    value=sum(amplitude*math.exp(-t*decay)*math.sin(math.tau*196*ratio*t+.12*math.sin(math.tau*.7*t)) for ratio,amplitude,decay in partials)
    samples.append(value*attack*end)
peak=max(abs(s) for s in samples);pcm=array.array('h',(int(s/peak*.48*32767) for s in samples))
with wave.open(str(output/'A_RB_BronzeChime.wav'),'wb') as stream:
    stream.setnchannels(1);stream.setsampwidth(2);stream.setframerate(rate);stream.writeframes(pcm.tobytes())
(output/'SYNTHESIS.json').write_text(json.dumps(dict(source='Original additive synthesis; no external recordings',sample_rate_hz=rate,duration_seconds=duration,fundamental_hz=196,partials=partials,peak=.48),indent=2)+'\n')
print('Original bronze chime saved, 5 seconds mono PCM16')
