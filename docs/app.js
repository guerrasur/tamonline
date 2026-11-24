/* Tamo online? — interfaz. JS puro, sin dependencias. */
(function () {
  "use strict";
  var params = new URLSearchParams(location.search);
  var DEMO = params.get("demo") === "1";
  var MISMO_ORIGEN = /^(localhost|127\.0\.0\.1)(:8765)?$/.test(location.host);
  var API = MISMO_ORIGEN ? "" : "http://127.0.0.1:8765";
  var TZ = "America/Argentina/Buenos_Aires";
  var DIAS = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"];
  var TEXTOS = {
    online: "Online", online_fuera: "Online", offline_horario: "Offline (debería estar abierta)",
    offline_fuera: "Cerrada (fuera de horario)", error: "Sin datos",
    sin_link: "Sin link configurado", pendiente: "Verificando…"
  };

  var estado = { data: null, localActivo: null, config: null, plataformas: [] };
  var $ = function (id) { return document.getElementById(id); };

  /* ---------- utilidades ---------- */
  function hm(iso) {
    if (!iso) return "—";
    return new Date(iso).toLocaleTimeString("es-AR", { hour: "2-digit", minute: "2-digit", timeZone: TZ, hour12: false });
  }
  function fechaHm(iso) {
    var d = new Date(iso), hoy = new Date();
    var f = function (x) { return x.toLocaleDateString("es-AR", { timeZone: TZ }); };
    return (f(d) === f(hoy) ? "" : d.toLocaleDateString("es-AR", { day: "2-digit", month: "2-digit", timeZone: TZ }) + " ") + hm(iso);
  }
  function el(tag, cls, txt) {
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    if (txt !== undefined) e.textContent = txt;
    return e;
  }
  function guardarLS(k, v) { try { localStorage.setItem(k, v); } catch (e) { /* sin almacenamiento */ } }
  function leerLS(k) { try { return localStorage.getItem(k); } catch (e) { return null; } }

  async function api(ruta, opciones) {
    var r = await fetch(API + ruta, opciones);
    if (!r.ok) throw new Error("HTTP " + r.status);
    return r.json();
  }

  /* ---------- datos demo ---------- */
  function datosDemo() {
    var ahora = new Date(), t = function (min) { return new Date(ahora.getTime() - min * 60000).toISOString(); };
    var p = function (clave, nombre, clase, min, extra) {
      return Object.assign({ clave: clave, nombre: nombre, url: "https://example.com/" + clave, clase: clase,
        ultima_verificacion: t(1), desde: t(min), motivo: "", horario_hoy: "Hoy: 11:00–23:00",
        fuente_horario: "manual", sin_horario: false }, extra || {});
    };
    return {
      version: "demo", ahora: ahora.toISOString(), configurado: true, intervalo: 120, sonido: false,
      locales: [
        { id: "a", nombre: "Local demo A", plataformas: [
          p("pedidosya", "PedidosYa", "online", 190), p("rappi", "Rappi", "offline_horario", 12),
          p("rappi_turbo", "Rappi Turbo", "offline_fuera", 480)] },
        { id: "b", nombre: "Local demo B", plataformas: [
          p("pedidosya", "PedidosYa", "error", 9, { motivo: "Bloqueado por la plataforma (HTTP 403)" }),
          p("rappi", "Rappi", "online_fuera", 25), p("rappi_turbo", "Rappi Turbo", "online", 60)] }
      ],
      eventos: [
        { id: 3, hora: t(12), mensaje: "Local demo A · Rappi: la tienda se apagó fuera de lo esperado (" + hm(t(12)) + ")", tipo: "offline_horario", notificar: true },
        { id: 2, hora: t(25), mensaje: "Local demo B · Rappi: la tienda está online fuera de horario (" + hm(t(25)) + ")", tipo: "online_fuera", notificar: true },
        { id: 1, hora: t(190), mensaje: "Local demo A · PedidosYa: la tienda está online (" + hm(t(190)) + ")", tipo: "online", notificar: false }
      ]
    };
  }

  /* ---------- render ---------- */
  function renderPestanas(locales) {
    var nav = $("pestanas");
    nav.innerHTML = "";
    nav.hidden = locales.length < 2;
    if (locales.length < 2) return;
    locales.forEach(function (l) {
      var b = el("button", l.id === estado.localActivo ? "activa" : "", l.nombre);
      b.onclick = function () { estado.localActivo = l.id; guardarLS("localActivo", l.id); render(); };
      nav.appendChild(b);
    });
  }

  function crearTarjeta(p) {
    var t = el(p.url ? "a" : "div", "tarjeta c-" + p.clase);
    if (p.url) { t.href = p.url; t.target = "_blank"; t.rel = "noopener"; t.title = "Abrir la tienda en " + p.nombre; }
    var arriba = el("div");
    arriba.appendChild(el("div", "plat", p.nombre));
    var est = el("div", "estado", TEXTOS[p.clase] || p.clase);
    if (p.clase === "offline_fuera" && p.sin_horario) est.textContent = "Cerrada";
    arriba.appendChild(est);
    if (p.clase === "online_fuera") arriba.appendChild(el("span", "etiqueta", "Online fuera de horario"));
    if (p.clase === "offline_fuera" && p.sin_horario) arriba.appendChild(el("span", "etiqueta", "Sin horario cargado"));
    t.appendChild(arriba);
    var datos = el("div", "datos");
    if (p.clase !== "sin_link" && p.clase !== "pendiente") {
      datos.appendChild(el("div", "", "Última verificación: " + hm(p.ultima_verificacion)));
      datos.appendChild(el("div", "", (p.clase === "error" ? "Sin datos desde: " : "En este estado desde: ") + fechaHm(p.desde)));
      if (p.horario_hoy) datos.appendChild(el("div", "", p.horario_hoy + (p.fuente_horario ? " (" + p.fuente_horario + ")" : "")));
    }
    if (p.motivo) datos.appendChild(el("div", "motivo", p.motivo));
    t.appendChild(datos);
    return t;
  }

  function render() {
    var d = estado.data;
    if (!d) return;
    $("version").textContent = "v" + d.version + (DEMO ? " · demo" : "");
    var locales = d.locales || [];
    if (!locales.some(function (l) { return l.id === estado.localActivo; }))
      estado.localActivo = locales.length ? locales[0].id : null;
    renderPestanas(locales);
    var cont = $("tarjetas");
    cont.innerHTML = "";
    var actual = locales.filter(function (l) { return l.id === estado.localActivo; })[0];
    if (actual) actual.plataformas.forEach(function (p) { cont.appendChild(crearTarjeta(p)); });
    $("info-act").textContent = "Actualizado " + hm(d.ahora) + " · se consulta cada " + d.intervalo + " s";
    renderHistorial(d.eventos || []);
  }

  function renderHistorial(evs) {
    var ul = $("lista-historial");
    ul.innerHTML = "";
    if (!evs.length) { ul.appendChild(el("li", "vacio", "Sin cambios registrados todavía.")); return; }
    evs.slice(0, 50).forEach(function (e) {
      var cls = e.tipo === "offline_horario" ? "alerta" : (e.tipo === "online_fuera" || e.tipo === "error") ? "aviso" : "";
      var li = el("li", cls);
      li.appendChild(el("span", "hora", fechaHm(e.hora)));
      li.appendChild(el("span", "txt", e.mensaje));
      ul.appendChild(li);
    });
  }

  /* ---------- notificaciones ---------- */
  function actualizarAvisoNotif() {
    var b = $("aviso-notif");
    if (!("Notification" in window)) { b.hidden = true; return; }
    var p = Notification.permission;
    b.hidden = p === "granted";
    $("aviso-notif-texto").textContent = p === "denied"
      ? "Las notificaciones están bloqueadas. Habilitalas desde el candado de la barra de direcciones y recargá."
      : "Activá las notificaciones para enterarte cuando cambie el estado de tus tiendas.";
    $("btn-notif").hidden = p === "denied";
  }
  function pedirPermiso() {
    if (!("Notification" in window)) return;
    Notification.requestPermission().then(actualizarAvisoNotif);
  }
  function pitido() {
    try {
      var ctx = new (window.AudioContext || window.webkitAudioContext)();
      var o = ctx.createOscillator(), g = ctx.createGain();
      o.type = "sine"; o.frequency.value = 660; g.gain.value = 0.08;
      o.connect(g); g.connect(ctx.destination); o.start(); o.stop(ctx.currentTime + 0.25);
    } catch (e) { /* sin audio */ }
  }
  function toast(msg) {
    var t = el("div", "toast", msg);
    $("toasts").appendChild(t);
    setTimeout(function () { t.remove(); }, 9000);
  }
  function notificar(msg, id) {
    toast(msg);
    if ("Notification" in window && Notification.permission === "granted") {
      try { new Notification("Tamo online?", { body: msg, icon: "icono.png", tag: "tamo-" + id }); } catch (e) { /* ignorar */ }
    }
    if (sonidoActivo()) pitido();
  }
  function sonidoActivo() {
    return estado.config ? !!estado.config.sonido : !!(estado.data && estado.data.sonido);
  }
  /* Notifica eventos nuevos (id mayor al último visto). En la primera carga solo marca el máximo. */
  function procesarEventos(evs) {
    if (!evs.length) return;
    var maxId = Math.max.apply(null, evs.map(function (e) { return e.id; }));
    var visto = leerLS("ultimoEvento");
    if (visto === null) { guardarLS("ultimoEvento", String(maxId)); return; }
    visto = parseInt(visto, 10);
    evs.slice().sort(function (a, b) { return a.id - b.id; }).forEach(function (e) {
      var reciente = Date.now() - new Date(e.hora).getTime() < 15 * 60000;
      if (e.id > visto && e.notificar && reciente) notificar(e.mensaje, e.id);
    });
    if (maxId > visto) guardarLS("ultimoEvento", String(maxId));
  }

  /* ---------- carga periódica ---------- */
  async function cargar() {
    if (DEMO) {
      estado.data = datosDemo();
      $("aviso-local").hidden = true;
      render();
      return;
    }
    try {
      estado.data = await api("/api/status");
      $("aviso-local").hidden = true;
      if (!estado.config) { try { estado.config = await api("/api/config"); } catch (e) { /* se reintenta luego */ } }
      render();
      procesarEventos(estado.data.eventos || []);
      if (!estado.data.configurado && !$("dlg-ajustes").open) abrirAjustes(true);
    } catch (e) {
      $("aviso-local").hidden = false;
      try { var v = await fetch(API + "/api/version"); if (v.ok) $("aviso-local").hidden = true; } catch (e2) { /* sigue sin servidor */ }
    }
  }

  async function actualizarAhora() {
    var b = $("btn-actualizar");
    if (DEMO) { toast("En modo demo no hay nada que actualizar."); return; }
    b.disabled = true; b.textContent = "Actualizando…";
    try { await api("/api/refresh", { method: "POST" }); } catch (e) { toast("No se pudo actualizar: " + e.message); }
    b.disabled = false; b.textContent = "Actualizar ahora";
    cargar();
  }

  /* ---------- ajustes ---------- */
  var borrador = null;
  function localVacio() {
    var l = { id: "", nombre: "", links: {}, horarios: {} };
    estado.plataformas.forEach(function (p) { l.links[p.clave] = ""; });
    return l;
  }
  async function abrirAjustes(primeraVez) {
    try {
      estado.config = await api("/api/config");
    } catch (e) { toast("No se pudo leer la configuración: el programa local no responde."); return; }
    estado.plataformas = estado.config.plataformas || [];
    borrador = JSON.parse(JSON.stringify(estado.config));
    if (!borrador.locales.length) { var l = localVacio(); l.nombre = "Mi local"; borrador.locales.push(l); }
    $("titulo-ajustes").textContent = primeraVez ? "Configuración inicial" : "Ajustes";
    $("intro-ajustes").textContent = primeraVez
      ? "Cargá el nombre del local y los links públicos de cada plataforma (los mismos que usa un cliente para comprar). Podés dejar vacía la que no uses."
      : "Podés editar los locales, los links y los horarios manuales.";
    $("btn-cancelar").hidden = !!primeraVez;
    $("cfg-intervalo").value = borrador.intervalo_segundos;
    $("cfg-errores").value = borrador.errores_para_notificar;
    $("cfg-sonido").checked = borrador.sonido;
    $("cfg-abrir").value = borrador.abrir_en;
    $("error-ajustes").hidden = true;
    renderLocalesAjustes();
    $("dlg-ajustes").showModal();
  }

  function renderLocalesAjustes() {
    var cont = $("ajustes-locales");
    cont.innerHTML = "";
    borrador.locales.forEach(function (l, i) {
      var box = el("div", "local-box");
      var cab = el("div", "cab");
      cab.appendChild(el("strong", "", "Local " + (i + 1)));
      if (borrador.locales.length > 1) {
        var q = el("button", "btn chico", "Quitar"); q.type = "button";
        q.onclick = function () { if (confirm("¿Quitar este local?")) { borrador.locales.splice(i, 1); renderLocalesAjustes(); } };
        cab.appendChild(q);
      }
      box.appendChild(cab);
      var lbl = el("label", "", "Nombre del local");
      var inp = el("input"); inp.type = "text"; inp.value = l.nombre;
      inp.oninput = function () { l.nombre = inp.value; };
      lbl.appendChild(inp); box.appendChild(lbl);
      estado.plataformas.forEach(function (p) {
        var lb = el("label", "", "Link de " + p.nombre);
        var u = el("input"); u.type = "url"; u.placeholder = "https://…"; u.value = l.links[p.clave] || "";
        u.oninput = function () { l.links[p.clave] = u.value.trim(); };
        lb.appendChild(u); box.appendChild(lb);
      });
      box.appendChild(editorHorarios(l));
      cont.appendChild(box);
    });
  }

  /* Horarios manuales: por plataforma, por día, varios tramos (cierre menor = pasa medianoche). */
  function editorHorarios(l) {
    var det = el("details");
    det.appendChild(el("summary", "", "Horarios manuales (opcional)"));
    det.appendChild(el("p", "chica", "Se usan si la plataforma no publica su horario. Si cerrás después de medianoche, poné una hora menor que la de apertura (ej. 18:00 a 02:00)."));
    estado.plataformas.forEach(function (p) {
      var sub = el("details");
      sub.appendChild(el("summary", "", p.nombre));
      l.horarios[p.clave] = l.horarios[p.clave] || {};
      for (var d = 0; d < 7; d++) sub.appendChild(filaDia(l.horarios[p.clave], d));
      det.appendChild(sub);
    });
    return det;
  }
  function filaDia(h, d) {
    var fila = el("div", "dia");
    fila.appendChild(el("span", "", DIAS[d]));
    var tr = el("div");
    function pintar() {
      tr.innerHTML = "";
      (h[d] || []).forEach(function (t, i) {
        var f = el("div", "tramo");
        var a = el("input"); a.type = "time"; a.value = t[0];
        var c = el("input"); c.type = "time"; c.value = t[1];
        a.onchange = function () { t[0] = a.value; };
        c.onchange = function () { t[1] = c.value; };
        var x = el("button", "btn chico", "✕"); x.type = "button";
        x.onclick = function () { h[d].splice(i, 1); if (!h[d].length) delete h[d]; pintar(); };
        f.appendChild(a); f.appendChild(el("span", "", "a")); f.appendChild(c); f.appendChild(x);
        tr.appendChild(f);
      });
      var add = el("button", "btn chico", "+ tramo"); add.type = "button";
      add.onclick = function () { (h[d] = h[d] || []).push(["11:00", "23:00"]); pintar(); };
      tr.appendChild(add);
    }
    pintar();
    fila.appendChild(tr);
    return fila;
  }

  async function guardarAjustes() {
    var err = $("error-ajustes");
    var hayLink = borrador.locales.some(function (l) { return Object.keys(l.links).some(function (k) { return l.links[k]; }); });
    if (!borrador.locales.every(function (l) { return l.nombre.trim(); })) { err.textContent = "Cada local necesita un nombre."; err.hidden = false; return; }
    if (!hayLink) { err.textContent = "Cargá al menos un link de alguna plataforma."; err.hidden = false; return; }
    borrador.intervalo_segundos = parseInt($("cfg-intervalo").value, 10) || 120;
    borrador.errores_para_notificar = parseInt($("cfg-errores").value, 10) || 3;
    borrador.sonido = $("cfg-sonido").checked;
    borrador.abrir_en = $("cfg-abrir").value;
    try {
      estado.config = await api("/api/config", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(borrador) });
      $("dlg-ajustes").close();
      toast("Configuración guardada. Verificando las tiendas…");
      setTimeout(cargar, 1500);
      cargar();
    } catch (e) { err.textContent = "No se pudo guardar: " + e.message; err.hidden = false; }
  }

  /* ---------- eventos de la página ---------- */
  function simular(tipo) {
    var msgs = {
      offline_horario: "Local demo A · Rappi: la tienda se apagó fuera de lo esperado (" + hm(new Date().toISOString()) + ")",
      online_fuera: "Local demo B · Rappi: la tienda está online fuera de horario (" + hm(new Date().toISOString()) + ")",
      error: "Local demo B · PedidosYa: sin datos hace 3 verificaciones (" + hm(new Date().toISOString()) + ")"
    };
    notificar(msgs[tipo], "prueba-" + Date.now());
  }

  function iniciar() {
    $("btn-notif").onclick = pedirPermiso;
    $("btn-actualizar").onclick = actualizarAhora;
    $("btn-ajustes").onclick = function () { abrirAjustes(false); };
    $("btn-cancelar").onclick = function () { $("dlg-ajustes").close(); };
    $("btn-guardar").onclick = guardarAjustes;
    $("btn-add-local").onclick = function () { var l = localVacio(); l.nombre = "Local " + (borrador.locales.length + 1); borrador.locales.push(l); renderLocalesAjustes(); };
    $("btn-probar-notif").onclick = function () { $("cfg-sonido").checked ? pitido() : 0; notificar("Prueba: así se verán las notificaciones de Tamo online?", "prueba"); };
    $("dlg-ajustes").addEventListener("cancel", function (ev) { if (estado.data && !estado.data.configurado) ev.preventDefault(); });
    document.querySelectorAll("[data-demo]").forEach(function (b) { b.onclick = function () { simular(b.dataset.demo); }; });
    estado.localActivo = leerLS("localActivo");
    $("aviso-demo").hidden = !DEMO;
    // Pide permiso la primera vez que se abre la web (si el navegador lo permite sin gesto; si no, queda el botón)
    if ("Notification" in window && Notification.permission === "default" && !leerLS("permisoPedido")) {
      guardarLS("permisoPedido", "1");
      try { pedirPermiso(); } catch (e) { /* queda el botón */ }
    }
    actualizarAvisoNotif();
    fetch(API + "/api/version").then(function (r) { return r.json(); }).then(function (v) { $("version").textContent = "v" + v.version + (DEMO ? " · demo" : ""); }).catch(function () { $("version").textContent = DEMO ? "demo" : "v—"; });
    cargar();
    setInterval(cargar, 15000);
  }
  iniciar();
})();
