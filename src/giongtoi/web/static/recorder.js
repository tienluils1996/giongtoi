// Ghi âm mẫu giọng theo câu mẫu (MediaRecorder) + tải file lên.
(function () {
  const $ = (id) => document.getElementById(id);
  const sel = $('prompt-select'), promptText = $('prompt-text');
  const btn = $('rec-btn'), review = $('rec-review'), audioEl = $('rec-audio');
  const status = $('rec-status'), timeEl = $('rec-time'), meter = $('meter-bar');
  let recorder = null, chunks = [], blob = null, stream = null, t0 = 0, timer = null, raf = null;

  sel.addEventListener('change', () => { promptText.textContent = PROMPTS[+sel.value]; reset(); });
  // mở trang: nhảy tới câu đầu tiên chưa ghi
  const firstTodo = [...sel.options].findIndex((o) => !o.textContent.includes('✓'));
  if (firstTodo > 0) { sel.value = String(firstTodo); promptText.textContent = PROMPTS[firstTodo]; }

  function reset() {
    review.hidden = true; blob = null; status.textContent = ''; timeEl.textContent = '0.0s';
  }

  async function start() {
    try {
      stream = await navigator.mediaDevices.getUserMedia({
        audio: { echoCancellation: false, noiseSuppression: false, autoGainControl: false, channelCount: 1 },
      });
    } catch (e) {
      status.textContent = 'Không truy cập được micro: ' + e.message + '. Hãy cho phép quyền micro trong trình duyệt / Cài đặt hệ thống.';
      return;
    }
    const mime = ['audio/webm;codecs=opus', 'audio/mp4', 'audio/webm'].find((m) => MediaRecorder.isTypeSupported(m)) || '';
    recorder = new MediaRecorder(stream, mime ? { mimeType: mime, audioBitsPerSecond: 256000 } : {});
    chunks = [];
    recorder.ondataavailable = (e) => e.data.size && chunks.push(e.data);
    recorder.onstop = () => {
      blob = new Blob(chunks, { type: recorder.mimeType });
      audioEl.src = URL.createObjectURL(blob);
      review.hidden = false;
      const secs = (Date.now() - t0) / 1000;
      status.textContent = secs < 3 ? 'Hơi ngắn — nên ghi 5–10 giây.' : secs > 15 ? 'Hơi dài — mẫu tốt nhất 5–12 giây.' : 'Nghe lại, nếu ổn thì bấm Lưu.';
      stream.getTracks().forEach((t) => t.stop());
      cancelAnimationFrame(raf);
      meter.style.width = '0';
    };
    // VU meter
    const ctx = new AudioContext();
    const an = ctx.createAnalyser(); an.fftSize = 1024;
    ctx.createMediaStreamSource(stream).connect(an);
    const buf = new Float32Array(an.fftSize);
    const tick = () => {
      an.getFloatTimeDomainData(buf);
      let peak = 0; for (const v of buf) peak = Math.max(peak, Math.abs(v));
      meter.style.width = Math.min(100, peak * 140) + '%';
      meter.style.background = peak > 0.95 ? 'var(--err)' : 'var(--ok)';
      raf = requestAnimationFrame(tick);
    };
    tick();
    recorder.start();
    t0 = Date.now();
    timer = setInterval(() => (timeEl.textContent = ((Date.now() - t0) / 1000).toFixed(1) + 's'), 100);
    btn.textContent = '■ Dừng'; review.hidden = true; status.textContent = 'Đang ghi… đọc câu phía trên.';
  }

  function stop() {
    clearInterval(timer);
    recorder && recorder.state !== 'inactive' && recorder.stop();
    btn.textContent = '● Bắt đầu ghi';
  }

  btn.addEventListener('click', (e) => { e.preventDefault(); recorder && recorder.state === 'recording' ? stop() : start(); });
  $('rec-retry').addEventListener('click', (e) => { e.preventDefault(); reset(); start(); });

  $('rec-save').addEventListener('click', async (e) => {
    e.preventDefault();
    if (!blob) return;
    const ext = blob.type.includes('mp4') ? '.m4a' : '.webm';
    const fd = new FormData();
    fd.append('file', blob, 'recording' + ext);
    fd.append('transcript', PROMPTS[+sel.value]);
    fd.append('label', $('rec-label').value || 'bình thường');
    fd.append('denoise', '1');
    status.textContent = 'Đang xử lý (khử ồn, cắt khoảng lặng)…';
    $('rec-save').disabled = true;
    const r = await fetch(`/api/voices/${VOICE_ID}/refs`, { method: 'POST', body: fd });
    $('rec-save').disabled = false;
    if (!r.ok) { status.textContent = 'Lỗi: ' + (await r.json()).detail; return; }
    status.textContent = 'Đã lưu ✓ Chuyển sang câu tiếp theo…';
    const opt = sel.options[sel.selectedIndex];
    if (!opt.textContent.includes('✓')) opt.textContent = opt.textContent.replace(' —', ' ✓ —');
    if (+sel.value < PROMPTS.length - 1) { sel.value = +sel.value + 1; promptText.textContent = PROMPTS[+sel.value]; }
    review.hidden = true;
    setTimeout(() => location.reload(), 700);
  });

  $('upload-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    const form = e.target, fd = new FormData(form);
    if (!form.denoise.checked) fd.set('denoise', '0');
    const st = $('upload-status'); st.textContent = 'Đang tải lên và xử lý…';
    const r = await fetch(`/api/voices/${VOICE_ID}/refs`, { method: 'POST', body: fd });
    if (!r.ok) { st.textContent = 'Lỗi: ' + (await r.json()).detail; return; }
    st.textContent = 'Đã lưu ✓'; setTimeout(() => location.reload(), 500);
  });
})();
