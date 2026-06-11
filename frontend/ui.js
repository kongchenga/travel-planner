// === UI: mode switching, form, progress, results ===

var secConf = { dest: {c:"#558B6E",i:"",l:"目的地"}, flights: {c:"#8B7355",i:"",l:"航班"}, hotels: {c:"#558B6E",i:"",l:"住宿"}, dining: {c:"#C1795A",i:"",l:"美食"}, budget: {c:"#6B8E6B",i:"",l:"预算"}, days: {c:"#5B7B6F",i:"",l:"行程"} };

function setMode(mode) {
  document.querySelectorAll(".pm").forEach(function(p){ p.classList.remove("active"); });
  var el = $("mode-" + mode);
  if (el) el.classList.add("active");
  var st = $("h-status");
  st.className = "h-status " + (mode === "progress" ? "busy" : mode === "result" ? "done" : "");
  $("h-text").textContent = mode === "progress" ? "规划中.." : mode === "result" ? "完成" : "就绪";
}

function setA(a) { var s = document.querySelector(".ps[data-a='" + a + "']"); if (!s) return; s.classList.add("active"); s.classList.remove("done"); s.querySelector(".ps-s").textContent = "处理中…"; s.querySelector(".ps-sp").classList.remove("hidden"); s.querySelector(".ps-ok").classList.add("hidden"); }
function setD(a, summary) {
  var s = document.querySelector(".ps[data-a='" + a + "']");
  if (!s) return;
  s.classList.remove("active"); s.classList.add("done");
  s.querySelector(".ps-s").textContent = summary ? summary : "完成";
  s.querySelector(".ps-sp").classList.add("hidden"); s.querySelector(".ps-ok").classList.remove("hidden");
}
function resetProg() {
  document.querySelectorAll(".ps").forEach(function(s) {
    s.classList.remove("active","done");
    s.querySelector(".ps-s").textContent = "等待中";
    s.querySelector(".ps-sp").classList.add("hidden"); s.querySelector(".ps-ok").classList.add("hidden");
    var sumEl = s.querySelector(".ps-summary");
    if (sumEl) sumEl.textContent = "";
  });
}

function switchResTab(name, btn) {
  document.querySelectorAll(".rt-btn").forEach(function(b){ b.classList.remove("active"); });
  if (btn) btn.classList.add("active");
  document.querySelectorAll(".res-scroll").forEach(function(p){ p.classList.add("hidden"); });
  var el = $("res-" + name); if (el) el.classList.remove("hidden");
  var nav = $("res-nav");
  if (nav) nav.classList.toggle("hidden", name !== "plan");
}

function scrollToDay(dayNum) {
  var sec = document.querySelector(".day-section[data-day='" + dayNum + "']");
  if (sec) sec.scrollIntoView({ behavior: "smooth", block: "start" });
  document.querySelectorAll(".rn-dot").forEach(function(d){ d.classList.remove("active"); });
  var dot = document.querySelector(".rn-dot[data-day='" + dayNum + "']");
  if (dot) dot.classList.add("active");
}

function showErr(msg) {
  goBtn.disabled = false; goBtn.classList.remove("loading");
  try { $("res-plan").innerHTML = "<div class=rc style=border-left-color:#ef4444><div class=rc-b><p>" + esc(msg) + "</p></div></div>"; } catch(_){}
  try { $("res-route").innerHTML = ""; } catch(_){}
  try { $("res-details").innerHTML = ""; } catch(_){}
  setMode("result");
}

function renderPlan(tp) {
  if (!tp || !tp.destination) { $("res-plan").innerHTML = "<div class=rc><div class=rc-b><p>无数据</p></div></div>"; return; }

  var routes = tp.routes || [];

  // Plan tab: show first route details (days + budget)
  if (routes.length > 0) {
    var r0 = routes[0];
    // Debug: check days length
    if (typeof console !== 'undefined') console.log('r0.days.length:', r0.days ? r0.days.length : 'null', 'r0.name:', r0.name);
    var budgetHtml = "";
    if (r0.budget && r0.budget.length) {
      var bg = r0.budget;
      var mx = 1;
      for (var i = 0; i < bg.length; i++) { if (bg[i].percentage > mx) mx = bg[i].percentage; }
      var bars = "";
      for (var i2 = 0; i2 < bg.length; i2++) {
        var b = bg[i2];
        var w = Math.round((b.percentage / mx) * 100);
        bars += "<div style=display:flex;align-items:center;gap:6px;margin-bottom:3px;font-size:10px>" +
          "<span style=width:40px;color:var(--tx2)>" + esc(b.category) + "</span>" +
          "<div style=flex:1;height:5px;background:var(--srf2);border-radius:3px;overflow:hidden><div style=height:100%;width:" + w + "%;background:linear-gradient(90deg,#6c5ce7,#00cec9);border-radius:3px></div></div>" +
          "<span style=width:50px;text-align:right;font-weight:600;color:var(--pr2)>" + (b.amount || 0) + "</span>" +
          "<span style=width:20px;text-align:right;color:var(--tx3)>" + (b.percentage || 0) + "%</span></div>";
      }
      budgetHtml = "<div style=margin-bottom:4px;font-size:11px;font-weight:600>预算: Y" + (r0.total_cost || tp.total_budget || 0) + "</div>" + bars;
    }

    var planHtml = "";
    planHtml += secRaw("dest", "", "目的地概况", "#558B6E", buildDestInfo(tp.destination_info));
    if (r0.days && r0.days.length) {
      planHtml += '<div class="res-nav" id="res-nav">' + buildRouteDayNav(r0) + '</div>';
      planHtml += buildDaysHtml(r0.days, "plan-days");
    }
    if (budgetHtml) planHtml += card("", "预算明细", "#6B8E6B", budgetHtml);
    if (r0.flights && r0.flights.length) planHtml += sec("flights", r0.flights, tp);
    if (r0.hotels && r0.hotels.length) planHtml += sec("hotels", r0.hotels, tp);
    if (r0.dining && r0.dining.length) planHtml += sec("dining", r0.dining, tp);
    $("res-plan").innerHTML = planHtml;
  } else {
    $("res-plan").innerHTML = buildHtml_legacy(tp, "plan");
  }

  // Route comparison tab
  $("res-route").innerHTML = buildRoutesHtml(routes, tp);

  // Details tab
  $("res-details").innerHTML = buildRoutesDetails(routes);

  // Switch to plan tab
  var planBtn = document.querySelector(".rt-btn[data-tab=plan]");
  if (planBtn) switchResTab("plan", planBtn);
}

function buildDestInfo(di) {
  if (!di) return "<p>无数据</p>";
  var h = "<p><b>" + esc(di.summary || "") + "</b></p>";
  if (di.attractions && di.attractions.length) h += "<p>推荐景点：" + di.attractions.slice(0, 8).map(esc).join("、") + "</p>";
  if (di.weather) h += "<p>天气：" + esc(di.weather) + "</p>";
  if (di.tips) h += "<p>贴士：" + esc(di.tips) + "</p>";
  if (di.best_season) h += "<p>最佳季节：" + esc(di.best_season) + "</p>";
  return h;
}

function buildRouteDayNav(route) {
  if (!route.days || !route.days.length) return "";
  var dots = "";
  for (var i = 0; i < route.days.length; i++) {
    var d = route.days[i];
    var num = d.day_number || (i + 1);
    var title = d.title || "";
    var label = title.length > 4 ? title.slice(0, 4) + "..." : title;
    dots += '<div style="display:flex;flex-direction:column;align-items:center">' +
      '<div class="rn-dot" data-day="' + num + '" onclick="scrollToDay(' + num + ')" title="' + escAttr(title) + '">' + num + '</div>' +
      '<span class="rn-label">' + esc(label) + '</span></div>';
  }
  return dots;
}

function buildDaysHtml(days, cls) {
  var dh = "";
  for (var i = 0; i < days.length; i++) {
    var day = days[i];
    var num = day.day_number || (i + 1);
    var acts = "";
    if (day.activities) {
      for (var j = 0; j < day.activities.length; j++) {
        var a = day.activities[j];
        var pts = [];
        if (a.location) pts.push(esc(a.location));
        if (a.transport) pts.push(esc(a.transport));
        if (a.duration_min) pts.push(a.duration_min + "分钟");
        if (a.cost) pts.push("Y" + a.cost);
        var pStr = pts.join(" | ");
        acts += "<div style=display:flex;gap:6px;padding:2px 0>" +
          "<div style=width:5px;height:5px;border-radius:50%;background:var(--pr2);margin-top:4px;flex-shrink:0></div>" +
          "<div style=flex:1><div style=font-size:9px;font-weight:600;color:var(--pr2)>" + esc(a.time_slot) + "</div>" +
          "<div style=font-size:11px;color:var(--txt)>" + esc(a.description) + "</div>" +
          "<div style=font-size:9px;color:var(--tx2)>" + pStr + "</div></div></div>";
      }
    }
    dh += "<div class=\"day-section " + cls + "\" data-day=\"" + num + "\" style=background:var(--srf2);border-radius:8px;padding:8px 10px;margin-bottom:5px;border:1px solid var(--brd)>" +
      "<div style=display:flex;align-items:baseline;gap:5px;margin-bottom:4px>" +
      "<span style=width:22px;height:22px;border-radius:50%;background:linear-gradient(135deg,var(--pr),var(--ac));color:#fff;display:flex;align-items:center;justify-content:center;font-size:9px;font-weight:700>" + num + "</span>" +
      "<span style=font-weight:600;font-size:11px>" + esc(day.title || "") + "</span>" +
      (day.date ? "<span style=font-size:9px;color:var(--tx3)>" + esc(day.date) + "</span>" : "") +
      "</div>" + (acts || "<p style=color:var(--tx3);font-size:10px>---</p>") + "</div>";
  }
  return dh;
}

function buildRoutesHtml(routes, tp) {
  if (!routes || !routes.length) return "<div class=rc><div class=rc-b><p>暂未生成路线，请先规划行程</p></div></div>";

  var colorPalette = ["#059669", "#F59E0B", "#3B82F6", "#EF4444"];
  var totalBudget = tp.total_budget || 1;

  // Header
  var h = "<div style=\"margin-bottom:8px;font-size:11px;color:var(--tx2)\">共生成 <b style=\"color:var(--pr2)\">" + routes.length + "</b> 条路线，点击路线卡片可切换查看详情</div>";

  // Route comparison cards
  h += "<div class=\"route-compare-grid\">";
  for (var i = 0; i < routes.length; i++) {
    var r = routes[i];
    var col = colorPalette[i % colorPalette.length];
    var costPercent = Math.round((r.total_cost || 0) / totalBudget * 100);
    var barColor = costPercent > 90 ? "#ef4444" : (costPercent > 70 ? "#f59e0b" : "#10b981");

    // Hotel tier
    var tiers = { economy: "经济", comfort: "舒适", luxury: "豪华" };
    var hotelName = "?";
    var hotelTier = "";
    if (r.hotels && r.hotels.length) {
      hotelName = r.hotels[0].name || "?";
      hotelTier = tiers[r.hotels[0].tier] || r.hotels[0].tier || "";
    }

    // Day count and activity count
    var dayCount = r.days ? r.days.length : 0;
    var actCount = 0;
    if (r.days) {
      for (var di = 0; di < r.days.length; di++) {
        actCount += (r.days[di].activities || []).length;
      }
    }
    var diningCount = r.dining ? r.dining.length : 0;

    h += "<div class=\"route-card\" data-route-idx=\"" + i + "\" onclick=\"switchRouteView(" + i + ")\" style=\"cursor:pointer\">" +
      "<div class=\"route-card-title\" style=\"color:" + col + "\">" + esc(r.name || ("路线 " + (i+1))) + "</div>" +
      "<div class=\"route-card-desc\">" + esc(r.description || "") + "</div>" +
      "<div class=\"route-card-cost\" style=\"color:" + col + "\">Y" + (r.total_cost || 0) +
        "<span style=\"font-size:10px;color:var(--tx3);margin-left:4px\"> / Y" + totalBudget + "</span></div>" +
      "<div class=\"route-card-meta\">" + dayCount + "天 · " + actCount + "个活动 · " + diningCount + "家餐厅 · " + esc(hotelName) + (hotelTier ? " [" + hotelTier + "]" : "") + "</div>" +
      "<div class=\"route-card-bar\"><div class=\"route-card-bar-fill\" style=\"width:" + costPercent + "%;background:" + barColor + "\"></div></div>" +
      "</div>";
  }
  h += "</div>";

  // Route detail section
  h += "<div id=\"route-detail\" style=\"margin-top:8px\"></div>";

  return h;
}

// Switch which route is shown in detail (and update the plan tab + map)
function switchRouteView(idx) {
  var tp = savedTripPlan;
  if (!tp || !tp.routes) return;
  var r = tp.routes[idx];
  if (!r) return;

  // Highlight selected card
  var cards = document.querySelectorAll(".route-card");
  for (var ci = 0; ci < cards.length; ci++) {
    cards[ci].classList.toggle("selected", ci === idx);
  }

  // Update map to show this route's markers and lines
  if (typeof switchRouteMap === 'function') {
    switchRouteMap(idx);
  }

  // Build detail view
  var colMap = ["#059669", "#F59E0B", "#3B82F6", "#EF4444"];
  var col = colMap[idx % colMap.length];
  var detail = "";

  // Budget bars
  if (r.budget && r.budget.length) {
    var bg = r.budget;
    var mx = 1;
    for (var i = 0; i < bg.length; i++) { if (bg[i].percentage > mx) mx = bg[i].percentage; }
    var bars = "";
    for (var i2 = 0; i2 < bg.length; i2++) {
      var b = bg[i2];
      var w = Math.round((b.percentage / mx) * 100);
      bars += "<div style=\"display:flex;align-items:center;gap:4px;margin-bottom:2px;font-size:9px\">" +
        "<span style=\"width:35px;color:var(--tx2)\">" + esc(b.category) + "</span>" +
        "<div style=\"flex:1;height:4px;background:var(--bg);border-radius:2px;overflow:hidden\"><div style=\"height:100%;width:" + w + "%;background:linear-gradient(90deg," + col + ",#00cec9);border-radius:2px\"></div></div>" +
        "<span style=\"width:45px;text-align:right;font-weight:600;color:var(--pr2);font-size:9px\">" + (b.amount || 0) + "</span>" +
        "<span style=\"width:20px;text-align:right;color:var(--tx3);font-size:9px\">" + (b.percentage || 0) + "%</span></div>";
    }
    detail += card("", "预算明细", col, "<div style=\"margin-bottom:2px;font-size:10px\"><b>总花费:</b> Y" + (r.total_cost || 0) + "</div>" + bars);
  }

  // Days
  if (r.days && r.days.length) {
    detail += buildDaysHtml(r.days, "route-days");
  }

  // Hotels
  if (r.hotels && r.hotels.length) {
    var hotelH = r.hotels.map(function(h) {
      var tierLabels = { economy: "经济", comfort: "舒适", luxury: "豪华" };
      return "<p><b>" + esc(h.name) + "</b> [" + (tierLabels[h.tier] || h.tier || "-") + "] Y" + (h.price_per_night || "?") + "/晚 · " + (h.rating || "-") + (h.address ? "<br><span style=\"font-size:9px;color:var(--tx3)\">" + esc(h.address) + "</span>" : "") + "</p>";
    }).join("");
    detail += card("", "住宿", col, hotelH);
  }

  // Dining
  if (r.dining && r.dining.length) {
    var diningH = r.dining.map(function(d) {
      return "<p><b>" + esc(d.name) + "</b> [" + esc(d.cuisine) + "] Y" + (d.price_per_person || "?") + "/人 · " + (d.rating || "-") + "</p>";
    }).join("");
    detail += card("", "美食", col, diningH);
  }

  // Flights
  if (r.flights && r.flights.length) {
    var flightH = r.flights.map(function(f) {
      return "<p><b>" + esc(f.airline) + "</b> " + esc(f.route) + " Y" + (f.price_estimate || "?") + " " + (f.duration_min || "?") + "min" + (f.recommendation ? "<br><span style=\"font-size:9px;color:var(--tx3)\">" + esc(f.recommendation) + "</span>" : "") + "</p>";
    }).join("");
    detail += card("", "航班", col, flightH);
  }

  $("route-detail").innerHTML = detail;
}

function buildRoutesDetails(routes) {
  if (!routes || !routes.length) return "<div class=dc><p>无详细数据</p></div>";
  var h = "";
  for (var i = 0; i < routes.length; i++) {
    var r = routes[i];
    h += "<div class=dc><h4>🗺️ " + esc(r.name || ("路线" + (i + 1))) + "</h4>";
    h += "<p><b>描述：</b>" + esc(r.description || "") + "</p>";
    h += "<p><b>总花费：</b>Y" + (r.total_cost || 0) + "</p>";
    if (r.flights && r.flights.length) h += "<p><b>航班：</b>" + r.flights.map(function(f){return esc(f.airline)+" "+esc(f.route)+" Y"+(f.price_estimate||"?");}).join("<br>") + "</p>";
    if (r.hotels && r.hotels.length) h += "<p><b>酒店：</b>" + r.hotels.map(function(h){return esc(h.name)+" Y"+(h.price_per_night||"?")+"/night";}).join("<br>") + "</p>";
    if (r.dining && r.dining.length) h += "<p><b>餐厅：</b>" + r.dining.map(function(d){return esc(d.name)+" ("+esc(d.cuisine)+") Y"+(d.price_per_person||"?")+"/person";}).join("<br>") + "</p>";
    h += "</div>";
  }
  return h;
}

// Legacy render for old single-plan format
function buildHtml_legacy(tp, mode) {
  var h = "";
  h += sec("dest", tp.destination_info, tp);
  if (tp.flights && tp.flights.length) h += (mode === "det" ? bDet("航班", tp.flights, "") : sec("flights", tp.flights, tp));
  if (tp.hotels && tp.hotels.length) h += (mode === "det" ? bDet("住宿", tp.hotels, "") : sec("hotels", tp.hotels, tp));
  if (tp.dining && tp.dining.length) h += (mode === "det" ? bDet("美食", tp.dining, "") : sec("dining", tp.dining, tp));
  if (tp.budget && tp.budget.length) h += sec("budget", tp.budget, tp);
  if (tp.days && tp.days.length) h += sec("days", tp.days, tp);
  return h;
}

function secRaw(type, icon, label, color, body) {
  return card(icon, label, color, body);
}

function sec(type, data, tp) {
  var s = secConf[type] || {c:"#666",i:"",l:type};
  if (type === "dest") { var d = data; var b = "<p><b>" + esc(d.summary) + "</b></p>" + (d.attractions? "<p>" + d.attractions.slice(0,6).join(", ") + "</p>" : "") + (d.weather?"<p>"+esc(d.weather)+"</p>":"") + (d.tips?"<p>"+esc(d.tips)+"</p>":""); return card(s.i, s.l, s.c, b); }
  if (type === "flights") { var b = data.map(function(f){return "<p><b>"+esc(f.airline)+"</b> "+esc(f.route)+" Y"+(f.price_estimate||"?")+" "+(f.duration_min||"?")+"min"+(f.recommendation?"<br><span>"+esc(f.recommendation)+"</span>":"")+"</p>";}).join(""); return card(s.i, s.l, s.c, b); }
  if (type === "hotels") { var tiers = {economy:"经济",comfort:"舒适",luxury:"豪华"}; var b = data.map(function(h){var l="<span class=rc-name>"+esc(h.name)+"</span><span class=rc-meta>"+(h.rating||"-")+" · "+tiers[h.tier]+" · Y"+(h.price_per_night||"?")+"/晚</span><span class=rc-addr>"+esc(h.address)+(h.phone?" · "+esc(h.phone):"")+"</span>"; return "<p>"+l+"</p>";}).join(""); return card(s.i, s.l, s.c, b); }
  if (type === "dining") { var b = data.map(function(d){var l="<span class=rc-name>"+esc(d.name)+"</span><span class=rc-meta>"+esc(d.cuisine)+" · "+(d.rating||"-")+" · Y"+(d.price_per_person||"?")+"/人</span><span class=rc-addr>"+esc(d.address)+(d.phone?" · "+esc(d.phone):"")+"</span>"; return "<p>"+l+"</p>";}).join(""); return card(s.i, s.l, s.c, b); }
  if (type === "budget") { var bg = data; var mx = 1; for(var i=0;i<bg.length;i++){if(bg[i].percentage>mx)mx=bg[i].percentage;} var bars=""; for(var i=0;i<bg.length;i++){var b=bg[i];var w=Math.round((b.percentage/mx)*100); bars+="<div style=display:flex;align-items:center;gap:6px;margin-bottom:3px;font-size:10px><span style=width:40px;color:var(--tx2)>"+esc(b.category)+"</span><div style=flex:1;height:5px;background:var(--srf2);border-radius:3px;overflow:hidden><div style=height:100%;width:"+w+"%;background:linear-gradient(90deg,#6c5ce7,#00cec9);border-radius:3px></div></div><span style=width:50px;text-align:right;font-weight:600;color:var(--pr2)>"+(b.amount||0)+"</span><span style=width:20px;text-align:right;color:var(--tx3)>"+(b.percentage||0)+"%</span></div>";} var hdr="<div style=margin-bottom:4px><b>总计: "+(tp.total_budget||0)+(tp.currency||"")+"</b></div>"; return card(s.i, s.l, s.c, hdr+bars); }
  if (type === "days") { var dh=""; for(var i=0;i<data.length;i++){var day=data[i];var num=day.day_number||(i+1);var acts="";if(day.activities){for(var j=0;j<day.activities.length;j++){var a=day.activities[j];var pts=[];if(a.location)pts.push(esc(a.location));if(a.transport)pts.push(esc(a.transport));if(a.duration_min)pts.push(a.duration_min+"分钟");if(a.cost)pts.push("Y"+a.cost);var pStr=pts.join(" | ");acts+="<div style=display:flex;gap:6px;padding:2px 0><div style=width:5px;height:5px;border-radius:50%;background:var(--pr2);margin-top:4px;flex-shrink:0></div><div style=flex:1><div style=font-size:9px;font-weight:600;color:var(--pr2)>"+esc(a.time_slot)+"</div><div style=font-size:11px;color:var(--txt)>"+esc(a.description)+"</div><div style=font-size:9px;color:var(--tx2)>"+pStr+"</div></div></div>";}} dh+="<div class=\"day-section\" data-day=\""+num+"\" style=background:var(--srf2);border-radius:8px;padding:8px 10px;margin-bottom:5px;border:1px solid var(--brd)><div style=display:flex;align-items:baseline;gap:5px;margin-bottom:4px><span style=width:22px;height:22px;border-radius:50%;background:linear-gradient(135deg,var(--pr),var(--ac));color:#fff;display:flex;align-items:center;justify-content:center;font-size:9px;font-weight:700>"+num+"</span><span style=font-weight:600;font-size:11px>"+esc(day.title||"")+"</span>"+(day.date?"<span style=font-size:9px;color:var(--tx3)>"+esc(day.date)+"</span>":"")+"</div>"+(acts||"<p style=color:var(--tx3);font-size:10px>---</p>")+"</div>";} return card(s.i, s.l, s.c, dh); }
  return "";
}

function card(icon,label,color,body){
  var iconHtml = icon ? "<div class=rc-i>"+icon+"</div>" : "";
  return "<div class=rc style=border-left-color:"+color+"><div class=rc-h>"+iconHtml+"<div class=rc-t>"+label+"</div></div><div class=rc-b>"+body+"</div></div>";
}
function bDet(label,data,icon){return "<div class=dc><h4>"+icon+" "+label+"</h4><p>"+data.map(function(x){return x.name||x.airline||"";}).join("<br>")+"</p></div>";}

// Clear all on filter btn click
document.querySelectorAll(".pf-btn").forEach(function(btn) {
  btn.addEventListener("click", function() {
    this.classList.toggle("active");
    var type = this.dataset.type;
    var visible = this.classList.contains("active");
    exploreMarkers.forEach(function(m) {
      if (!m._poiData || !m._poiData.poiType) return;
      if (String(m._poiData.poiType) === type) {
        if (visible) exploreMap.addLayer(m); else exploreMap.removeLayer(m);
      }
    });
  });
});
