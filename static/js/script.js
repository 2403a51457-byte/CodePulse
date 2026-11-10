document.addEventListener("DOMContentLoaded", () => {
  const canvas = document.getElementById("healthChart");
  if (!canvas) return;
  const labels = JSON.parse(canvas.dataset.labels || "[]");
  const values = JSON.parse(canvas.dataset.values || "[]");
  const draw = () => {
    const width = Math.max(canvas.clientWidth || 600, 280), height = 245;
    const dpr = window.devicePixelRatio || 1;
    canvas.width = width * dpr; canvas.height = height * dpr;
    const ctx = canvas.getContext("2d"); ctx.scale(dpr, dpr);
    const left = 32, right = 14, top = 20, bottom = 48;
    const plotW = width-left-right, plotH = height-top-bottom;
    ctx.font = "11px Segoe UI"; ctx.fillStyle = "#8ea2bd"; ctx.strokeStyle = "#253750";
    for (let tick=0; tick<=100; tick+=25) {
      const y = top + plotH - tick/100*plotH;
      ctx.beginPath(); ctx.moveTo(left,y); ctx.lineTo(width-right,y); ctx.stroke();
      ctx.fillText(String(tick), 4, y+4);
    }
    const slot = plotW / Math.max(values.length,1);
    values.forEach((value,index) => {
      if (value == null) return;
      const v = Math.max(0,Math.min(100,Number(value)));
      const barH = plotH*v/100, bw = Math.min(54,slot*.56), x = left+index*slot+(slot-bw)/2, y=top+plotH-barH;
      const grad=ctx.createLinearGradient(0,y,0,top+plotH); grad.addColorStop(0,"#5bdfd0"); grad.addColorStop(1,"#397fe5");
      ctx.fillStyle=grad; ctx.beginPath(); ctx.roundRect(x,y,bw,barH,6); ctx.fill();
      ctx.fillStyle="#eaf2ff"; ctx.textAlign="center"; ctx.fillText(String(v),x+bw/2,Math.max(12,y-7));
      ctx.fillStyle="#8ea2bd"; const label=labels[index]||""; ctx.fillText(label.length>11?label.slice(0,10)+"…":label,x+bw/2,height-18);
    });
  };
  draw(); window.addEventListener("resize", draw);
});
