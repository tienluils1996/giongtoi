// Tiện ích chung: hiển thị thời gian tương đối.
(function () {
  const rtf = new Intl.RelativeTimeFormat('vi', { numeric: 'auto' });
  document.querySelectorAll('[data-ts]').forEach((el) => {
    const diff = (+el.dataset.ts * 1000 - Date.now()) / 1000;
    const abs = Math.abs(diff);
    const [v, u] = abs < 60 ? [diff, 'second'] : abs < 3600 ? [diff / 60, 'minute']
      : abs < 86400 ? [diff / 3600, 'hour'] : [diff / 86400, 'day'];
    el.textContent = rtf.format(Math.round(v), u);
  });
})();
