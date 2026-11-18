// Bộ ghi âm micro dùng chung (MediaRecorder + VU meter).
// createMic({btn, meter, timeEl, status, review, audioEl, retryBtn, onStart}) → { blob(), seconds(), reset() }
window.createMic = function (el) {
  let recorder = null, chunks = [], blob = null, stream = null, t0 = 0, secs = 0, timer = null, raf = null, ctx = null;
  const idleLabel = el.btn.textContent;

  function reset() {
    el.review.hidden = true; blob = null; secs = 0; el.status.textContent = ''; el.timeEl.textContent = '0.0s';
  }

  async function start() {
    try {
      stream = await navigator.mediaDevices.getUserMedia({
        audio: { echoCancellation: false, noiseSuppression: false, autoGainControl: false, channelCount: 1 },
      });
    } catch (e) {
      el.status.textContent = 'Không truy cập được micro (' + e.message + '). Cho phép quyền micro trong Cài đặt hệ thống › '
        + 'Quyền riêng tư & Bảo mật › Micro, hoặc mở ' + location.origin + location.pathname + ' bằng Safari/Chrome để ghi âm.';
      return;
    }
    const mime = ['audio/webm;codecs=opus', 'audio/mp4', 'audio/webm'].find((m) => MediaRecorder.isTypeSupported(m)) || '';
    recorder = new MediaRecorder(stream, mime ? { mimeType: mime, audioBitsPerSecond: 256000 } : {});
    chunks = [];
    recorder.ondataavailable = (e) => e.data.size && chunks.push(e.data);
    recorder.onstop = () => {
      blob = new Blob(chunks, { type: recorder.mimeType });
      secs = (Date.now() - t0) / 1000;
      el.audioEl.src = URL.createObjectURL(blob);
      el.review.hidden = false;
      el.status.textContent = secs < 3 ? 'Hơi ngắn — nên ghi 5–10 giây.'
        : secs > 15 ? 'Hơi dài — mẫu tốt nhất 5–12 giây.' : 'Nghe lại, nếu ổn thì bấm Lưu.';
      stream.getTracks().forEach((t) => t.stop());
      cancelAnimationFrame(raf);
      ctx && ctx.close();
      el.meter.style.width = '0';
    };
    ctx = new AudioContext();
    const an = ctx.createAnalyser(); an.fftSize = 1024;
    ctx.createMediaStreamSource(stream).connect(an);
    const buf = new Float32Array(an.fftSize);
    const tick = () => {
      an.getFloatTimeDomainData(buf);
      let peak = 0; for (const v of buf) peak = Math.max(peak, Math.abs(v));
      el.meter.style.width = Math.min(100, peak * 140) + '%';
      el.meter.style.background = peak > 0.95 ? 'var(--err)' : 'var(--ok)';
      raf = requestAnimationFrame(tick);
    };
    tick();
    recorder.start();
    t0 = Date.now();
    timer = setInterval(() => (el.timeEl.textContent = ((Date.now() - t0) / 1000).toFixed(1) + 's'), 100);
    el.btn.textContent = '■ Dừng'; el.review.hidden = true; el.status.textContent = 'Đang ghi… đọc câu phía trên.';
    el.onStart && el.onStart();
  }

  function stop() {
    clearInterval(timer);
    recorder && recorder.state !== 'inactive' && recorder.stop();
    el.btn.textContent = idleLabel;
  }

  el.btn.addEventListener('click', (e) => { e.preventDefault(); recorder && recorder.state === 'recording' ? stop() : start(); });
  el.retryBtn && el.retryBtn.addEventListener('click', (e) => { e.preventDefault(); reset(); start(); });

  return {
    blob: () => blob,
    seconds: () => secs,
    reset,
    fileName: () => 'recording' + (blob && blob.type.includes('mp4') ? '.m4a' : '.webm'),
  };
};
