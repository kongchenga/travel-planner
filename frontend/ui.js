// === UI: mode switching, form, progress, results ===

var secConf = { dest: {c:"#06b6d4",i:"📋",l:"目的地"}, flights: {c:"#f59e0b",i:"✈️",l:"航班"}, hotels: {c:"#10b981",i:"🏨",l:"住宿"}, dining: {c:"#ef4444",i:"🍽️",l:"美食"}, budget: {c:"#8b5cf6",i:"💰",l:"预算"}, days: {c:"#ec4899",i:"📅",l:"行程"} };

function setMode(mode) {
  document.querySelectorAll(".pm").forEach(p => p.classList.remove("active"));
  const el = $("mode-" + mode);
  if (el) el.classList.add("active");
  const st = $("h-status");
  st.className = "h-status " + (mode === "progress" ? "busy" : mode === "result" ? "done" : "");
  $("h-text").textContent = mode === "progress" ? "规划中…" : mode === "result" ? "完成" : "就绪";
}

function setA(a) { var s = document.querySelector(".ps[data-a='" + a + "']"); if (!s) return; s.classList.add("active"); s.classList.remove("done"); s.querySelector(".ps-s").textContent = "处理中…"; s.querySelector(".ps-sp").classList.remove("hidden"); s.querySelector(".ps-ok").classList.add("hidden"); }
function setD(a) { var s = document.querySelector(".ps[data-a='" + a + "']"); if (!s) return; s.classList.remove("active"); s.classList.add("done"); s.querySelector(".ps-s").textContent = "完成"; s.querySelector(".ps-sp").classList.add("hidden"); s.querySelector(".ps-ok").classList.remove("hidden"); }
function resetProg() { document.querySelectorAll(".ps").forEach(function(s) { s.classList.remove("active","done"); s.querySelector(".ps-s").textContent = "等待中"; s.querySelector(".ps-sp").classList.add("hidden"); s.querySelector(".ps-ok").classList.add("hidden"); }); }

function switchResTab(name, btn) {
  document.querySelectorAll(".rt-btn").forEach(b => b.classList.remove("active"));
  if (btn) btn.classList.add("active");
  document.querySelectorAll(".res-scroll").forEach(p => p.classList.add("hidden"));
  var el = $("res-" + name); if (el) el.classList.remove("hidden");
}

function showErr(msg) {
  goBtn.disabled = false; goBtn.classList.remove("loading");
  $("res-plan").innerHTML = "<div class=rc style=border-left-color:#ef4444><div class=rc-b><p>" + esc(msg) + "</p></div></div>";
  $("res-details").innerHTML = ""; setMode("result");
}

function renderPlan(tp) {
  if (!tp || !tp.destination) { $("res-plan").innerHTML = "<div class=rc><div class=rc-b><p>无数据</p></div></div>"; return; }
  $("res-plan").innerHTML = buildHtml(tp, "plan");
  $("res-details").innerHTML = buildHtml(tp, "det");
}

function buildHtml(tp, mode) {
  var h = "";
  h += sec("dest", tp.destination_info, tp);
  if (tp.flights && tp.flights.length) h += (mode === "det" ? bDet("航班", tp.flights, "✈️") : sec("flights", tp.flights, tp));
  if (tp.hotels && tp.hotels.length) h += (mode === "det" ? bDet("住宿", tp.hotels, "🏨") : sec("hotels", tp.hotels, tp));
  if (tp.dining && tp.dining.length) h += (mode === "det" ? bDet("美食", tp.dining, "🍽️") : sec("dining", tp.dining, tp));
  if (tp.budget && tp.budget.length) h += sec("budget", tp.budget, tp);
  if (tp.days && tp.days.length) h += sec("days", tp.days, tp);
  return h;
}

function sec(type, data, tp) {
  var s = secConf[type] || {c:"#666",i:"",l:type};
  if (type === "dest") { var d = data; var b = "<p><b>" + esc(d.summary) + "</b></p>" + (d.attractions? "<p>" + d.attractions.slice(0,6).join(", ") + "</p>" : "") + (d.weather?"<p>"+esc(d.weather)+"</p>":"") + (d.tips?"<p>"+esc(d.tips)+"</p>":""); return card(s.i, s.l, s.c, b); }
  if (type === "flights") { var b = data.map(function(f){return "<p><b>"+esc(f.airline)+"</b> "+esc(f.route)+" ¥"+(f.price_estimate||"?")+" "+(f.duration_min||"?")+"min"+(f.recommendation?"<br><span>"+esc(f.recommendation)+"</span>":"")+"</p>";}).join(""); return card(s.i, s.l, s.c, b); }
  if (type === "hotels") { var tiers = {economy:"经济",comfort:"舒适",luxury:"豪华"}; var b = data.map(function(h){var l="<span class=rc-name>"+esc(h.name)+"</span><span class=rc-meta>⭐"+(h.rating||"-")+" · "+tiers[h.tier]+" · ¥"+(h.price_per_night||"?")+"/晚</span><span class=rc-addr>"+esc(h.address)+(h.phone?" · 📞"+esc(h.phone):"")+"</span>"; return "<p>"+l+"</p>";}).join(""); return card(s.i, s.l, s.c, b); }
  if (type === "dining") { var b = data.map(function(d){var l="<span class=rc-name>"+esc(d.name)+"</span><span class=rc-meta>"+esc(d.cuisine)+" · ⭐"+(d.rating||"-")+" · ¥"+(d.price_per_person||"?")+"/人</span><span class=rc-addr>"+esc(d.address)+(d.phone?" · 📞"+esc(d.phone):"")+"</span>"; return "<p>"+l+"</p>";}).join(""); return card(s.i, s.l, s.c, b); }
  if (type === "budget") { var bg = data; var mx = 1; for(var i=0;i<bg.length;i++){if(bg[i].percentage>mx)mx=bg[i].percentage;} var bars=""; for(var i=0;i<bg.length;i++){var b=bg[i];var w=Math.round((b.percentage/mx)*100); bars+="<div style=display:flex;align-items:center;gap:6px;margin-bottom:3px;font-size:10px><span style=width:40px;color:var(--tx2)>"+esc(b.category)+"</span><div style=flex:1;height:5px;background:var(--srf2);border-radius:3px;overflow:hidden><div style=height:100%;width:"+w+"%;background:linear-gradient(90deg,#6c5ce7,#00cec9);border-radius:3px></div></div><span style=width:50px;text-align:right;font-weight:600;color:var(--pr2)>"+(b.amount||0)+"</span><span style=width:20px;text-align:right;color:var(--tx3)>"+(b.percentage||0)+"%</span></div>";} var hdr="<div style=margin-bottom:4px><b>总计: "+(tp.total_budget||0)+(tp.currency||"")+"</b></div>"; return card(s.i, s.l, s.c, hdr+bars); }
  if (type === "days") { var dh=""; for(var i=0;i<data.length;i++){var day=data[i];var acts="";if(day.activities){for(var j=0;j<day.activities.length;j++){var a=day.activities[j];var pts=[];if(a.location)pts.push(esc(a.location));if(a.transport)pts.push(esc(a.transport));if(a.duration_min)pts.push(a.duration_min+"分钟");if(a.cost)pts.push("¥"+a.cost);var pStr=pts.join(" | ");acts+="<div style=display:flex;gap:6px;padding:2px 0><div style=width:5px;height:5px;border-radius:50%;background:var(--pr2);margin-top:4px;flex-shrink:0></div><div style=flex:1><div style=font-size:9px;font-weight:600;color:var(--pr2)>"+esc(a.time_slot)+"</div><div style=font-size:11px;color:var(--txt)>"+esc(a.description)+"</div><div style=font-size:9px;color:var(--tx2)>"+pStr+"</div></div></div>";}} dh+="<div style=background:var(--srf2);border-radius:8px;padding:8px 10px;margin-bottom:5px;border:1px solid var(--brd)><div style=display:flex;align-items:baseline;gap:5px;margin-bottom:4px><span style=width:22px;height:22px;border-radius:50%;background:linear-gradient(135deg,var(--pr),var(--ac));color:#fff;display:flex;align-items:center;justify-content:center;font-size:9px;font-weight:700>"+(day.day_number||i+1)+"</span><span style=font-weight:600;font-size:11px>"+esc(day.title||"")+"</span>"+(day.date?"<span style=font-size:9px;color:var(--tx3)>"+esc(day.date)+"</span>":"")+"</div>"+(acts||"<p style=color:var(--tx3);font-size:10px>---</p>")+"</div>";} return card(s.i, s.l, s.c, dh); }
  return "";
}

function card(icon,label,color,body){return "<div class=rc style=border-left-color:"+color+"><div class=rc-h><div class=rc-i>"+icon+"</div><div class=rc-t>"+label+"</div></div><div class=rc-b>"+body+"</div></div>";}
function bDet(label,data,icon){return "<div class=dc><h4>"+icon+" "+label+"</h4><p>"+data.map(function(x){return x.name||x.airline||"";}).join("<br>")+"</p></div>";}

// Clear all on filter btn click
document.querySelectorAll(".pf-btn").forEach(btn => {
  btn.addEventListener("click", function() {
    this.classList.toggle("active");
    const type = this.dataset.type;
    const visible = this.classList.contains("active");
    exploreMarkers.forEach(m => {
      if (!m._poiData || !m._poiData.poiType) return;
      if (String(m._poiData.poiType) === type) {
        if (visible) exploreMap.addLayer(m); else exploreMap.removeLayer(m);
      }
    });
  });
});
