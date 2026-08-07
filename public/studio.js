// jinx3 Studio — synth + visualizer + WAV export
// Self-contained Web Audio engine. No backend dependency.

(() => {
  const ctx = new (window.AudioContext || window.webkitAudioContext)();

  // ---- Master bus: audible path + silent monitor/record tap ----
  const masterGain = ctx.createGain();
  masterGain.gain.value = 0.8;

  const filterNode = ctx.createBiquadFilter();
  filterNode.type = "lowpass";
  filterNode.frequency.value = 8000;
  filterNode.Q.value = 0.7;

  const dryGain = ctx.createGain();
  const wetGain = ctx.createGain();
  dryGain.gain.value = 1;
  wetGain.gain.value = 0;

  const convolver = ctx.createConvolver();
  convolver.buffer = makeImpulseResponse(2.2, 2.5);

  const analyser = ctx.createAnalyser();
  analyser.fftSize = 2048;

  const monitorSilence = ctx.createGain();
  monitorSilence.gain.value = 0;

  const recorderNode = ctx.createScriptProcessor(4096, 2, 2);
  const pitchNode = ctx.createScriptProcessor(2048, 2, 2);

  pitchNode.connect(filterNode);
  filterNode.connect(dryGain);
  filterNode.connect(convolver);
  convolver.connect(wetGain);
  dryGain.connect(masterGain);
  wetGain.connect(masterGain);

  masterGain.connect(ctx.destination);
  masterGain.connect(analyser);
  analyser.connect(recorderNode);
  recorderNode.connect(monitorSilence);
  monitorSilence.connect(ctx.destination);

  function makeImpulseResponse(duration, decay) {
    const rate = ctx.sampleRate;
    const length = Math.max(1, Math.floor(rate * duration));
    const impulse = ctx.createBuffer(2, length, rate);
    for (let ch = 0; ch < 2; ch++) {
      const data = impulse.getChannelData(ch);
      for (let i = 0; i < length; i++) {
        data[i] = (Math.random() * 2 - 1) * Math.pow(1 - i / length, decay);
      }
    }
    return impulse;
  }

  // ---- Recording ----
  let recording = false;
  let chunksL = [];
  let chunksR = [];

  recorderNode.onaudioprocess = (e) => {
    if (!recording) return;
    chunksL.push(new Float32Array(e.inputBuffer.getChannelData(0)));
    chunksR.push(new Float32Array(e.inputBuffer.getChannelData(1)));
  };

  function startRecording() {
    chunksL = [];
    chunksR = [];
    recording = true;
  }

  function stopRecordingAndExport() {
    recording = false;
    const totalLen = chunksL.reduce((sum, c) => sum + c.length, 0);
    const left = new Float32Array(totalLen);
    const right = new Float32Array(totalLen);
    let offset = 0;
    for (let i = 0; i < chunksL.length; i++) {
      left.set(chunksL[i], offset);
      right.set(chunksR[i], offset);
      offset += chunksL[i].length;
    }
    return encodeWAV(left, right, ctx.sampleRate);
  }

  function writeString(view, offset, str) {
    for (let i = 0; i < str.length; i++) view.setUint8(offset + i, str.charCodeAt(i));
  }

  function encodeWAV(samplesL, samplesR, sampleRate) {
    const numFrames = samplesL.length;
    const numChannels = 2;
    const bytesPerSample = 2;
    const blockAlign = numChannels * bytesPerSample;
    const dataSize = numFrames * blockAlign;
    const buffer = new ArrayBuffer(44 + dataSize);
    const view = new DataView(buffer);

    writeString(view, 0, "RIFF");
    view.setUint32(4, 36 + dataSize, true);
    writeString(view, 8, "WAVE");
    writeString(view, 12, "fmt ");
    view.setUint32(16, 16, true);
    view.setUint16(20, 1, true);
    view.setUint16(22, numChannels, true);
    view.setUint32(24, sampleRate, true);
    view.setUint32(28, sampleRate * blockAlign, true);
    view.setUint16(32, blockAlign, true);
    view.setUint16(34, 16, true);
    writeString(view, 36, "data");
    view.setUint32(40, dataSize, true);

    let offset = 44;
    for (let i = 0; i < numFrames; i++) {
      let s = Math.max(-1, Math.min(1, samplesL[i]));
      view.setInt16(offset, s < 0 ? s * 0x8000 : s * 0x7fff, true);
      offset += 2;
      s = Math.max(-1, Math.min(1, samplesR[i]));
      view.setInt16(offset, s < 0 ? s * 0x8000 : s * 0x7fff, true);
      offset += 2;
    }
    return buffer;
  }

  // ---- Pitch correction (autotune) ----
  const SCALES = {
    chromatic: [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11],
    major: [0, 2, 4, 5, 7, 9, 11],
    minor: [0, 2, 3, 5, 7, 8, 10],
  };

  const pitchState = {
    enabled: false,
    rootOffset: 0, // 0 = C
    scale: "chromatic",
    speed: 0.35, // 0..1, higher = snappier/more robotic
  };

  let lastPitchInfo = { detected: null, target: null };
  let pitchInfoCallback = null;

  // Pre-allocated static buffers to eliminate Garbage Collection during playback
  let monoBuf = new Float32Array(4096);
  let dsBuf = new Float32Array(2048);
  let corrCache = new Float32Array(1024);

  class GranularPitchShifter {
    constructor(bufferSize, grainSize) {
      this.bufferSize = bufferSize;
      this.grainSize = grainSize;
      this.buf = new Float32Array(bufferSize);
      this.writePtr = 0;
      this.pos = 0;

      // Precompute Hann window table (eliminates Math.cos per sample)
      this.windowTable = new Float32Array(grainSize);
      for (let i = 0; i < grainSize; i++) {
        this.windowTable[i] = 0.5 - 0.5 * Math.cos((2 * Math.PI * i) / grainSize);
      }
    }

    processSample(inSample, ratio) {
      const bSize = this.bufferSize;
      const gSize = this.grainSize;
      const buf = this.buf;
      const win = this.windowTable;

      buf[this.writePtr] = inSample;

      // --- Grain 1 ---
      const pos1 = this.pos;
      const winIdx1 = pos1 | 0; // Fast integer bitwise truncation
      const w1 = win[winIdx1];

      // Linear interpolation for smooth audio reading (no pitch aliasing)
      let r1 = this.writePtr - pos1;
      if (r1 < 0) r1 += bSize;
      const r1_i = r1 | 0;
      const r1_frac = r1 - r1_i;
      const r1_next = (r1_i + 1) % bSize;
      const s1 = buf[r1_i] * (1 - r1_frac) + buf[r1_next] * r1_frac;

      // --- Grain 2 (180 degrees out of phase) ---
      let pos2 = pos1 + (gSize >> 1);
      if (pos2 >= gSize) pos2 -= gSize;
      const winIdx2 = pos2 | 0;
      const w2 = win[winIdx2];

      let r2 = this.writePtr - pos2;
      if (r2 < 0) r2 += bSize;
      const r2_i = r2 | 0;
      const r2_frac = r2 - r2_i;
      const r2_next = (r2_i + 1) % bSize;
      const s2 = buf[r2_i] * (1 - r2_frac) + buf[r2_next] * r2_frac;

      // Combine grains
      const out = s1 * w1 + s2 * w2;

      // Advance read pointer
      this.pos += ratio;
      if (this.pos >= gSize) this.pos -= gSize;

      this.writePtr = (this.writePtr + 1) % bSize;
      return out;
    }
  }

  const pitchShifters = [
    new GranularPitchShifter(4096, 2048),
    new GranularPitchShifter(4096, 2048),
  ];
  let smoothedRatio = 1;

  // Optimized pitch detection with 2x downsampling & parabolic interpolation
  function detectPitch(buffer, sampleRate, size) {
    let mean = 0;
    for (let i = 0; i < size; i++) mean += buffer[i];
    mean /= size;

    let rms = 0;
    for (let i = 0; i < size; i++) {
      const v = buffer[i] - mean;
      rms += v * v;
    }
    rms = Math.sqrt(rms / size);
    if (rms < 0.01) return null; // Noise gate threshold

    // Downsample 2x to cut processing cost
    const dsRate = sampleRate / 2;
    const dsSize = size >> 1;
    if (dsBuf.length < dsSize) dsBuf = new Float32Array(dsSize);

    for (let i = 0; i < dsSize; i++) {
      dsBuf[i] = buffer[i * 2] - mean;
    }

    const minLag = (dsRate / 1000) | 0; // Max ~1000 Hz
    const maxLag = (dsRate / 70) | 0; // Min ~70 Hz
    let bestLag = -1;
    let bestCorr = 0;

    let cIdx = 0;
    for (let lag = minLag; lag <= maxLag; lag++) {
      let corr = 0;
      const len = dsSize - lag;
      for (let i = 0; i < len; i += 2) {
        corr += dsBuf[i] * dsBuf[i + lag];
      }
      corr = (corr * 2) / len;
      corrCache[cIdx++] = corr;

      if (corr > bestCorr) {
        bestCorr = corr;
        bestLag = lag;
      }
    }

    const normalizedCorr = bestCorr / (rms * rms);
    if (bestLag <= 0 || normalizedCorr < 0.15) return null;

    // Parabolic interpolation for sub-sample frequency accuracy
    let refinedLag = bestLag;
    const bestIdx = bestLag - minLag;
    if (bestIdx > 0 && bestIdx < cIdx - 1) {
      const c1 = corrCache[bestIdx - 1];
      const c2 = corrCache[bestIdx];
      const c3 = corrCache[bestIdx + 1];
      const denom = 2 * (2 * c2 - c1 - c3);
      if (denom !== 0) {
        refinedLag += (c3 - c1) / denom;
      }
    }

    return dsRate / refinedLag;
  }

  function nearestScaleFreq(freq, rootOffset, scaleName) {
    const intervals = SCALES[scaleName] || SCALES.chromatic;
    const midi = 69 + 12 * Math.log2(freq / 440);
    let best = Math.round(midi);
    let bestDist = Infinity;

    for (let m = Math.floor(midi) - 12; m <= Math.floor(midi) + 12; m++) {
      const pc = (((m - rootOffset) % 12) + 12) % 12;
      if (intervals.includes(pc)) {
        const dist = Math.abs(m - midi);
        if (dist < bestDist) {
          bestDist = dist;
          best = m;
        }
      }
    }
    return 440 * Math.pow(2, (best - 69) / 12);
  }

  pitchNode.onaudioprocess = (e) => {
    const inL = e.inputBuffer.getChannelData(0);
    const inR = e.inputBuffer.getChannelData(1);
    const outL = e.outputBuffer.getChannelData(0);
    const outR = e.outputBuffer.getChannelData(1);
    const size = inL.length;

    let targetRatio = 1;
    let detected = null;
    let target = null;

    if (pitchState.enabled) {
      if (monoBuf.length < size) monoBuf = new Float32Array(size);

      for (let i = 0; i < size; i++) {
        monoBuf[i] = (inL[i] + inR[i]) * 0.5;
      }

      detected = detectPitch(monoBuf, e.outputBuffer.sampleRate, size);
      if (detected) {
        target = nearestScaleFreq(detected, pitchState.rootOffset, pitchState.scale);
        targetRatio = target / detected;
        // Clamp extreme pitch shifts to avoid breakdown artifacts
        targetRatio = Math.max(0.5, Math.min(2.0, targetRatio));
      }
    }

    // Exponential smoothing for natural vocal transitions
    smoothedRatio += (targetRatio - smoothedRatio) * pitchState.speed;

    // Granular pitch processing loop
    for (let i = 0; i < size; i++) {
      outL[i] = pitchShifters[0].processSample(inL[i], smoothedRatio);
      outR[i] = pitchShifters[1].processSample(inR[i], smoothedRatio);
    }

    lastPitchInfo = { detected, target };
    if (pitchInfoCallback) pitchInfoCallback(lastPitchInfo);
  };

  // ---- Synth voices ----
  const NOTE_KEYS = [
    ["a", "C4"], ["w", "C#4"], ["s", "D4"], ["e", "D#4"], ["d", "E4"],
    ["f", "F4"], ["t", "F#4"], ["g", "G4"], ["y", "G#4"], ["h", "A4"],
    ["u", "A#4"], ["j", "B4"], ["k", "C5"], ["o", "C#5"], ["l", "D5"],
    ["p", "D#5"], [";", "E5"],
  ];
  const NOTE_TO_MIDI = {};
  const NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"];
  for (let midi = 0; midi < 128; midi++) {
    const name = NAMES[midi % 12] + Math.floor(midi / 12 - 1);
    NOTE_TO_MIDI[name] = midi;
  }
  function noteToFreq(name, octaveShift) {
    const midi = NOTE_TO_MIDI[name] + octaveShift * 12;
    return 440 * Math.pow(2, (midi - 69) / 12);
  }

  const envelope = { attack: 0.02, decay: 0.15, sustain: 0.6, release: 0.3 };
  let oscType = "sawtooth";
  let octaveShift = 0;
  const activeVoices = new Map();

  function noteOn(noteName, voiceKey) {
    if (activeVoices.has(voiceKey)) return;
    const osc = ctx.createOscillator();
    osc.type = oscType;
    osc.frequency.value = noteToFreq(noteName, octaveShift);

    const voiceGain = ctx.createGain();
    const now = ctx.currentTime;
    voiceGain.gain.setValueAtTime(0, now);
    voiceGain.gain.linearRampToValueAtTime(1, now + envelope.attack);
    voiceGain.gain.linearRampToValueAtTime(
      envelope.sustain,
      now + envelope.attack + envelope.decay
    );

    osc.connect(voiceGain);
    voiceGain.connect(pitchNode);
    osc.start();

    activeVoices.set(voiceKey, { osc, voiceGain });
  }

  function noteOff(voiceKey) {
    const voice = activeVoices.get(voiceKey);
    if (!voice) return;
    const now = ctx.currentTime;
    voice.voiceGain.gain.cancelScheduledValues(now);
    voice.voiceGain.gain.setValueAtTime(voice.voiceGain.gain.value, now);
    voice.voiceGain.gain.linearRampToValueAtTime(0, now + envelope.release);
    voice.osc.stop(now + envelope.release + 0.02);
    voice.osc.onended = () => {
      voice.osc.disconnect();
      voice.voiceGain.disconnect();
    };
    activeVoices.delete(voiceKey);
  }

  // ---- File playback source ----
  let fileSourceNode = null;
  function connectFileSource(audioEl) {
    if (fileSourceNode) {
      fileSourceNode.disconnect();
    }
    fileSourceNode = ctx.createMediaElementSource(audioEl);
    fileSourceNode.connect(pitchNode);
  }

  // ---- Visualizer ----
  function drawVisualizers(waveCanvas, freqCanvas) {
    const waveCtx = waveCanvas.getContext("2d");
    const freqCtx = freqCanvas.getContext("2d");
    const bufferLength = analyser.frequencyBinCount;
    const timeData = new Uint8Array(bufferLength);
    const freqData = new Uint8Array(bufferLength);

    function render() {
      requestAnimationFrame(render);
      analyser.getByteTimeDomainData(timeData);
      analyser.getByteFrequencyData(freqData);

      waveCtx.fillStyle = "#0a0b0d";
      waveCtx.fillRect(0, 0, waveCanvas.width, waveCanvas.height);
      waveCtx.lineWidth = 2;
      waveCtx.strokeStyle = "#c4f542";
      waveCtx.beginPath();
      const sliceWidth = waveCanvas.width / bufferLength;
      let x = 0;
      for (let i = 0; i < bufferLength; i++) {
        const v = timeData[i] / 128.0;
        const y = (v * waveCanvas.height) / 2;
        if (i === 0) waveCtx.moveTo(x, y);
        else waveCtx.lineTo(x, y);
        x += sliceWidth;
      }
      waveCtx.stroke();

      freqCtx.fillStyle = "#0a0b0d";
      freqCtx.fillRect(0, 0, freqCanvas.width, freqCanvas.height);
      const barWidth = (freqCanvas.width / bufferLength) * 2.5;
      let bx = 0;
      for (let i = 0; i < bufferLength; i++) {
        const barHeight = (freqData[i] / 255) * freqCanvas.height;
        freqCtx.fillStyle = `hsl(${80 - (freqData[i] / 255) * 60}, 90%, 55%)`;
        freqCtx.fillRect(bx, freqCanvas.height - barHeight, barWidth, barHeight);
        bx += barWidth + 1;
        if (bx > freqCanvas.width) break;
      }
    }
    render();
  }

  // ---- Public API wired to DOM in studio.html ----
  window.JinxStudio = {
    ctx,
    NOTE_KEYS,
    noteOn,
    noteOff,
    noteToFreq,
    setOscType: (t) => (oscType = t),
    setOctaveShift: (n) => (octaveShift = n),
    setEnvelope: (partial) => Object.assign(envelope, partial),
    setFilterCutoff: (hz) => filterNode.frequency.setTargetAtTime(hz, ctx.currentTime, 0.01),
    setFilterQ: (q) => filterNode.Q.setTargetAtTime(q, ctx.currentTime, 0.01),
    setReverbMix: (wet) => {
      wetGain.gain.setTargetAtTime(wet, ctx.currentTime, 0.01);
      dryGain.gain.setTargetAtTime(1 - wet, ctx.currentTime, 0.01);
    },
    setMasterVolume: (v) => masterGain.gain.setTargetAtTime(v, ctx.currentTime, 0.01),
    setPitchCorrectionEnabled: (on) => (pitchState.enabled = !!on),
    setPitchRoot: (offset) => (pitchState.rootOffset = offset),
    setPitchScale: (name) => (pitchState.scale = SCALES[name] ? name : "chromatic"),
    setPitchSpeed: (v) => (pitchState.speed = Math.max(0.01, Math.min(1, v))),
    onPitchInfo: (cb) => (pitchInfoCallback = cb),
    connectFileSource,
    drawVisualizers,
    startRecording,
    stopRecordingAndExport,
    resume: () => ctx.state !== "running" && ctx.resume(),
  };
})();
