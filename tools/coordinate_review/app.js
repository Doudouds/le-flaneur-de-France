/* PC-only reviewer. The catalogue is never edited. */
"use strict";
const $ = id => document.getElementById(id);
const labels = {a_verifier:"À vérifier",bon:"Bon emplacement",mauvais:"Mauvais emplacement"};
const reasons = {hors_departement_declare:"Position hors du département déclaré",plus_de_10km_de_la_commune:"Position à plus de 10 km de la commune",hors_commune_plus_de_1km:"Position hors de la commune (plus de 1 km)",code_insee_et_departement_incoherents:"Le code INSEE et le département se contredisent"};
let rows = [], reviews = {}, token = "", selected = null, markers = [], boundary = null, contourSerial = 0, busy = false;
let editMode=false, hasCorrections=false;
const map = L.map("map").setView([46.5,2.3],5);
const streets = L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png",{maxZoom:19,attribution:'© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'}).addTo(map);
const aerial = L.tileLayer("https://data.geopf.fr/wmts?SERVICE=WMTS&REQUEST=GetTile&VERSION=1.0.0&LAYER=ORTHOIMAGERY.ORTHOPHOTOS&STYLE=normal&FORMAT=image/jpeg&TILEMATRIXSET=PM&TILEMATRIX={z}&TILEROW={y}&TILECOL={x}",{maxZoom:19,attribution:'© <a href="https://www.ign.fr/">IGN</a>'});
L.control.layers({"Plan OSM":streets,"Photo aérienne IGN":aerial},null,{collapsed:false}).addTo(map);
const comparison=L.layerGroup().addTo(map);
function position(row) {return reviews[row.reference]?.correction || row;}
function setEdit(active) {
  editMode=active; $("map").classList.toggle("correction-active",active);
  $("relocate").setAttribute("aria-pressed",String(active));
  $("cancel-relocate").hidden=!active; $("correction-help").hidden=!active;
}
function renderCorrection() {
  if(!selected)return;
  const review=reviews[selected.reference], corrected=review?.correction;
  $("corrected-position").hidden=!corrected; $("origin").hidden=!corrected; $("restore-position").hidden=!corrected;
  $("relocate").disabled=!hasCorrections || busy;
  $("corrected-position").textContent=corrected?`Position corrigée : ${corrected.latitude.toFixed(6)}, ${corrected.longitude.toFixed(6)} — enregistrée sur ce PC`:"";
  const metres=corrected?CoordinateReviewRules.distanceMeters(selected,corrected):null;
  $("correction-distance").hidden=metres===null;
  $("correction-distance").textContent=metres===null?"":`Écart depuis l’origine : ${metres.toLocaleString("fr-FR",{maximumFractionDigits:2})} m${CoordinateReviewRules.smallCorrection(selected,review) && decision(selected)==="bon"?" — inférieur à 10 m, considéré bon":""}`;
  comparison.clearLayers();
  if(corrected) {
    L.circleMarker([selected.latitude,selected.longitude],{radius:7,color:"#555",fillOpacity:0.2,dashArray:"3 3",interactive:false}).addTo(comparison);
    L.polyline([[selected.latitude,selected.longitude],[corrected.latitude,corrected.longitude]],{color:"#555",weight:1,dashArray:"5 5",interactive:false}).addTo(comparison);
  }
  const entries=review?(review.history?.length?review.history:[review]):[];
  $("history-title").textContent=`Historique (${entries.length} entrées)`; $("history-list").replaceChildren();
  const actions={etat_initial_conserve:"État précédent conservé",position_corrigee:"Position corrigée",position_retablie:"Position d’origine rétablie",decision_ou_commentaire:"Décision ou commentaire"};
  for(const entry of entries) {
    const line=document.createElement("li"), target=entry.correction;
    line.textContent=`${entry.updated_at?new Date(entry.updated_at).toLocaleString("fr-FR"):"Date non renseignée"} · ${actions[entry.action]||"État enregistré"} · ${labels[entry.decision]||entry.decision}${target?` · ${target.latitude.toFixed(6)}, ${target.longitude.toFixed(6)}`:" · position d’origine"}${entry.note?` · ${entry.note}`:""}`;
    $("history-list").append(line);
  }
}
function changed(row) { const r=reviews[row.reference]; return r && (r.latitude!==row.latitude || r.longitude!==row.longitude); }
function decision(row) { return CoordinateReviewRules.decision(row,reviews[row.reference]); }
function fail(message) { $("error").textContent=message; $("error").hidden=false; }
function shown() {
  const text=$("search").value.toLocaleLowerCase("fr").normalize("NFD").replace(/[\u0300-\u036f]/g,"");
  return rows.filter(row => ($("filter").value==="all" || ($("filter").value==="corrige"?Boolean(reviews[row.reference]?.correction):decision(row)===$("filter").value)) &&
    [row.nom,row.commune,row.reference,row.departement].join(" ").toLocaleLowerCase("fr").normalize("NFD").replace(/[\u0300-\u036f]/g,"").includes(text));
}
function draw() {
  const counts={bon:0,mauvais:0,a_verifier:0}; rows.forEach(row=>counts[decision(row)]++);
  const visible=shown();
  if(selected) {
    if(visible.some(row=>row.reference===selected.reference)) {
      renderCorrection();if(boundary && !map.hasLayer(boundary))boundary.addTo(map);
    } else {
      setEdit(false);comparison.clearLayers();if(boundary)boundary.remove();
    }
  }
  $("counts").textContent=`${visible.length} affichés sur ${rows.length} · ${counts.a_verifier} à vérifier · ${counts.bon} bons · ${rows.filter(row=>reviews[row.reference]?.correction).length} corrigés`;
  $("pending-view").setAttribute("aria-pressed",String($("filter").value==="a_verifier"));
  $("corrected-view").setAttribute("aria-pressed",String($("filter").value==="corrige"));
  $("list").replaceChildren();
  for(const row of visible) {
    const button=document.createElement("button"); button.type="button";
    button.dataset.ref=row.reference; button.setAttribute("aria-current",String(selected?.reference===row.reference));
    button.textContent=row.nom;
    const small=document.createElement("small");small.textContent=`${row.commune} (${row.departement}) · ${row.reference} · ${labels[decision(row)]}${reviews[row.reference]?.correction?" · position corrigée":""}`;
    button.append(small); button.onclick=()=>select(row); $("list").append(button);
  }
  markers.forEach(marker=>marker.remove()); markers=[];
  const groups=new Map();
  for(const row of visible) {const p=position(row),key=`${p.latitude},${p.longitude}`;if(!groups.has(key))groups.set(key,[]);groups.get(key).push(row);}
  for(const group of groups.values()) {
    const states=group.map(row=>decision(row)==="bon"?"bon":reviews[row.reference]?.correction?"corrige":decision(row));
    const state=states.every(value=>value===states[0])?states[0]:"a_verifier";
    const active=group.some(row=>row.reference===selected?.reference);
    const icon=L.divIcon({className:"",html:`<div class="pin ${state}${active?" selected":""}">${group.length>1?group.length:""}</div>`,iconSize:[24,24],iconAnchor:[12,12]});
    const p=position(group[0]);
    const marker=L.marker([p.latitude,p.longitude],{icon,title:group.map(row=>row.nom).join(" / "),alt:group.map(row=>row.nom).join(" / ")}).addTo(map);
    marker.getElement().setAttribute("aria-label",group.length===1?group[0].nom:`${group.length} lieux : ${group.map(row=>row.nom).join(" / ")}`);
    marker.on("click",()=>{
      if(editMode) {correctAt(marker.getLatLng());return;}
      if(group.length===1) {select(group[0],false);return;}
      const menu=document.createElement("div");menu.className="shared-choice";
      for(const row of group) {const b=document.createElement("button");b.textContent=`${row.nom} — ${row.reference}`;b.onclick=()=>{map.closePopup();select(row,false);};menu.append(b);}
      L.popup().setLatLng(marker.getLatLng()).setContent(menu).openOn(map);
    });
    markers.push(marker);
  }
}
async function select(row, focus=true) {
  if(busy) return;
  if(selected && $("note").value!==(reviews[selected.reference]?.note || "")) {
    if(!await save(decision(selected))) return;
  }
  setEdit(false); selected=row; $("empty").hidden=true; $("selected").hidden=false;
  $("name").textContent=row.nom; $("reference").textContent=`${row.reference} · Priorité ${row.priorite}`;
  $("place").textContent=`Commune déclarée : ${row.commune} · Département ${row.departement}`;
  $("position").textContent=`Position d’origine : ${row.latitude.toFixed(6)}, ${row.longitude.toFixed(6)}`;
  $("reason").textContent=reasons[row.motif] || row.motif;
  $("distances").textContent=`Écart au contour de la commune : ${row.ecart_commune_km || "non déterminé"} km · au département : ${row.ecart_departement_km || "non déterminé"} km`;
  $("reference-place").textContent=`Commune(s) du code INSEE ${row.insee} : ${row.communes_reference}`;
  $("caution").textContent=row.avertissement ? "Attention : l’implantation maritime de ce lieu peut être légitime." : "";
  $("changed").hidden=!changed(row); $("note").value=reviews[row.reference]?.note || "";
  $("pop").href=row.fiche_pop;
  $("save-status").textContent=labels[decision(row)];
  renderCorrection();
  const p=position(row); $("osm").href=`https://www.openstreetmap.org/?mlat=${p.latitude}&mlon=${p.longitude}#map=18/${p.latitude}/${p.longitude}`;
  if(focus) map.setView([p.latitude,p.longitude],16);
  if(boundary) {boundary.remove();boundary=null;}
  $("expected").disabled=true;
  const serial=++contourSerial;
  try {
    const response=await fetch(`/api/contours/${row.reference}`); if(!response.ok) throw Error();
    const data=await response.json();if(serial!==contourSerial)return;
    if(data.features.length) {boundary=L.geoJSON(data,{style:{color:"#2063c9",weight:2,fillOpacity:0.04},interactive:false}).addTo(map);$("expected").disabled=false;}
  } catch {if(serial===contourSerial)$("expected").title="Contours non disponibles sur ce PC.";}
  draw();
}
async function persist(route,payload,message) {
  if(!selected || busy)return false;
  const row=selected; busy=true; $("save-status").textContent="Enregistrement…";
  for(const id of ["good","bad","pending","next","relocate","restore-position","save-note"])$(id).disabled=true;
  try {
    const response=await fetch(`/api/${route}/${row.reference}`,{method:"PUT",headers:{"Content-Type":"application/json","X-Review-Token":token},body:JSON.stringify(payload)});
    const data=await response.json();if(!response.ok)throw Error(data.error || "Enregistrement impossible.");
    reviews[row.reference]=data; $("save-status").textContent=message+" — enregistré sur ce PC";
    $("changed").hidden=true; $("error").hidden=true; renderCorrection(); draw();
    const p=position(row); $("osm").href=`https://www.openstreetmap.org/?mlat=${p.latitude}&mlon=${p.longitude}#map=18/${p.latitude}/${p.longitude}`;
    return true;
  } catch(error) {$("save-status").textContent="Non enregistré";fail(error.message+" Le serveur local doit rester ouvert ; réessaie avant de quitter.");return false;}
  finally {busy=false;for(const id of ["good","bad","pending","next","restore-position","save-note"])$(id).disabled=false;$("relocate").disabled=!hasCorrections;}
}
function save(state) {return persist("reviews",{decision:state,note:$("note").value},labels[state]);}
async function correctAt(latlng) {
  if(!editMode || busy)return;
  const p=latlng.wrap();
  if(await persist("corrections",{correction:{latitude:p.lat,longitude:p.lng},note:$("note").value},"Nouvelle position"))setEdit(false);
}
map.on("click",event=>{if(editMode)correctAt(event.latlng);});
$("relocate").onclick=()=>{if(selected&&!busy&&hasCorrections)setEdit(!editMode);};
$("cancel-relocate").onclick=()=>setEdit(false);
$("restore-position").onclick=async()=>{if(await persist("corrections",{correction:null,note:$("note").value},"Position d’origine rétablie"))setEdit(false);};
$("save-note").onclick=()=>{if(selected)save(decision(selected));};
$("good").onclick=()=>save("bon");$("bad").onclick=()=>save("mauvais");$("pending").onclick=()=>save("a_verifier");
$("next").onclick=async()=>{const current=selected;if(current && !await save(decision(current)))return;const visible=shown();const start=visible.findIndex(row=>row.reference===current?.reference);const ordered=visible.slice(start+1).concat(visible.slice(0,start+1));const next=ordered.find(row=>row.reference!==current?.reference && decision(row)==="a_verifier");if(next)select(next);else $("save-status").textContent="Aucun autre lieu à vérifier dans ce filtre.";};
function changeFilter(value) {
  setEdit(false);
  $("filter").value=value;
  const url=new URL(location.href);url.searchParams.set("filter",value);history.replaceState(null,"",url);
  draw();
}
$("search").oninput=draw;$("filter").onchange=()=>changeFilter($("filter").value);
$("pending-view").onclick=()=>changeFilter("a_verifier");
$("corrected-view").onclick=()=>changeFilter("corrige");
$("france").onclick=()=>map.setView([46.5,2.3],5);
$("all").onclick=()=>{const visible=shown();if(visible.length)map.fitBounds(visible.map(row=>{const p=position(row);return[p.latitude,p.longitude];}),{padding:[30,30],maxZoom:16});};
$("zoom").onclick=()=>{if(selected){const p=position(selected);map.setView([p.latitude,p.longitude],18);}};
$("origin").onclick=()=>{if(selected)map.setView([selected.latitude,selected.longitude],18);};
$("expected").onclick=()=>{if(boundary)map.fitBounds(boundary.getBounds(),{padding:[25,25],maxZoom:16});};
$("stop").onclick=async()=>{if(busy)return;if(selected && $("note").value!==(reviews[selected.reference]?.note||"") && !await save(decision(selected)))return;try{const response=await fetch("/api/stop",{method:"POST",headers:{"X-Review-Token":token}});if(!response.ok)throw Error();document.querySelectorAll("button,input,select,textarea").forEach(el=>el.disabled=true);fail("Outil arrêté. Pour reprendre, relance Ouvrir-carte-positions.cmd puis recharge la page.");}catch{fail("Impossible d’arrêter le serveur local.");}};
window.addEventListener("beforeunload",event=>{if(busy || (selected && $("note").value!==(reviews[selected.reference]?.note || ""))){event.preventDefault();event.returnValue="";}});
fetch("/api/data").then(async response=>{if(!response.ok)throw Error("Impossible de charger les lieux.");return response.json();}).then(data=>{rows=data.monuments;reviews=data.reviews;token=data.token;hasCorrections=Boolean(data.capabilities?.corrections);const params=new URLSearchParams(location.search),filter=params.get("filter");if([...$("filter").options].some(option=>option.value===filter))$("filter").value=filter;draw();if(!hasCorrections)fail("Le serveur doit être redémarré pour activer les corrections. Tes décisions existantes sont conservées.");const requested=params.get("ref");if(requested){const row=rows.find(row=>row.reference===requested);if(row)select(row);}}).catch(error=>fail(error.message));
