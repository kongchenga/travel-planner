// === State & DOM refs ===
var selectedPois = [], exploreMarkers = [], exploreMap = null, mapInstance = null;
var _sseClosed = false, savedTripPlan = null;

var $ = function(id){ return document.getElementById(id); };
var dest = $("destination"), originInp = $("origin");
var startDateInp = $("start-date"), endDateInp = $("end-date");
var travelers = $("travelers"), budget = $("budget");
var special = $("special") || { value: "" }, interestsCustom = $("interests-custom") || { value: "" };
var goBtn = $("go-btn");

function esc(s) { return (s || "").replace(/[<>&\"']/g," "); }
function escAttr(s) { return (s || "").replace(/"/g,"&quot;"); }
function adj(d) { var v = parseInt(travelers.value) || 1; travelers.value = Math.max(1, Math.min(99, v + d)); }
