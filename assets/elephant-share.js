(function () {
  "use strict";
  function wrap(ctx, value, x, y, width, lineHeight, limit) {
    var words = String(value || "").split(/\s+/), line = "", lines = 0;
    words.forEach(function (word) {
      var next = line ? line + " " + word : word;
      if (ctx.measureText(next).width > width && line && lines < limit - 1) {
        ctx.fillText(line, x, y + lines * lineHeight); line = word; lines += 1;
      } else { line = next; }
    });
    if (line && lines < limit) ctx.fillText(line, x, y + lines * lineHeight);
    return lines + 1;
  }
  function build(title, items, eyebrow) {
    var canvas = document.createElement("canvas"), ctx = canvas.getContext("2d");
    canvas.width = 1200; canvas.height = 630;
    var gradient = ctx.createLinearGradient(0, 0, 1200, 630);
    gradient.addColorStop(0, "#080b18"); gradient.addColorStop(.55, "#29106b"); gradient.addColorStop(1, "#101629");
    ctx.fillStyle = gradient; ctx.fillRect(0, 0, 1200, 630);
    ctx.fillStyle = "rgba(156,255,59,.12)"; ctx.beginPath(); ctx.arc(1070, 110, 230, 0, Math.PI * 2); ctx.fill();
    ctx.fillStyle = "#9cff3b"; ctx.font = "800 24px system-ui"; ctx.fillText(String(eyebrow || "ARTIFICIAL.ONE · ELEPHANT DECISION"), 70, 70);
    ctx.fillStyle = "#ffffff"; ctx.font = "900 58px system-ui"; var lines = wrap(ctx, title, 70, 150, 940, 66, 3);
    ctx.font = "800 29px system-ui";
    (items || []).slice(0, 5).forEach(function (item, index) {
      var y = 175 + lines * 66 + index * 52;
      ctx.fillStyle = index === 0 ? "#9cff3b" : "#c4b5fd"; ctx.fillText((index + 1) + ".", 75, y);
      ctx.fillStyle = "#ffffff"; ctx.fillText(String(item), 120, y);
    });
    ctx.font = "900 70px system-ui"; ctx.fillText("🐘", 1010, 535);
    ctx.font = "800 25px system-ui"; ctx.fillStyle = "#d8b4fe"; ctx.fillText("artificial.one", 70, 575);
    return canvas;
  }
  function download(title, items, eyebrow) {
    var canvas = build(title, items, eyebrow), link = document.createElement("a");
    link.download = "artificial-one-elephant-decision.png";
    link.href = canvas.toDataURL("image/png"); link.click();
  }
  window.ElephantShare = { build: build, download: download };
}());
