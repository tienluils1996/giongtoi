// Trang hồ sơ giọng: ghi thêm mẫu theo câu mẫu + tải file lên.
(function () {
  const $ = (id) => document.getElementById(id);
  const sel = $('prompt-select'), promptText = $('prompt-text'), status = $('rec-status');

  const mic = createMic({
    btn: $('rec-btn'), meter: $('meter-bar'), timeEl: $('rec-time'), status,
    review: $('rec-review'), audioEl: $('rec-audio'), retryBtn: $('rec-retry'),
  });

  sel.addEventListener('change', () => { promptText.textContent = PROMPTS[+sel.value]; mic.reset(); });
  // mở trang: nhảy tới câu đầu tiên chưa ghi
  const firstTodo = [...sel.options].findIndex((o) => !o.textContent.includes('✓'));
  if (firstTodo > 0) { sel.value = String(firstTodo); promptText.textContent = PROMPTS[firstTodo]; }

  $('rec-save').addEventListener('click', async (e) => {
    e.preventDefault();
    if (!mic.blob()) return;
    const fd = new FormData();
    fd.append('file', mic.blob(), mic.fileName());
    fd.append('transcript', PROMPTS[+sel.value]);
    fd.append('label', $('rec-label').value || 'bình thường');
    fd.append('denoise', '1');
    status.textContent = 'Đang xử lý (khử ồn, cắt khoảng lặng)…';
    $('rec-save').disabled = true;
    const r = await fetch(`/api/voices/${VOICE_ID}/refs`, { method: 'POST', body: fd });
    $('rec-save').disabled = false;
    if (!r.ok) { status.textContent = 'Lỗi: ' + (await r.json()).detail; return; }
    status.textContent = 'Đã lưu ✓ Chuyển sang câu tiếp theo…';
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
