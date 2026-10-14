// Panel del coordinador: filtros dependientes, mapa territorial y botones
// de alternancia (mapa y evolución por año). Sin datos personales: el mapa
// solo recibe totales por comuna.
(function () {
    "use strict";

    // Selects dependientes del panel de filtros (Sede → Campus, Facultad → Carrera):
    // se ocultan las opciones que no pertenecen a lo elegido arriba.
    document.querySelectorAll("select[data-depende-de]").forEach(function (hijo) {
        const padre = document.getElementById(hijo.dataset.dependeDe);
        if (!padre) {
            return;
        }

        function filtrar() {
            const valor = padre.value;
            hijo.querySelectorAll("option[data-padre]").forEach(function (opcion) {
                const visible = !valor || opcion.dataset.padre === valor;
                opcion.hidden = !visible;
                opcion.disabled = !visible;
            });
            const elegida = hijo.selectedOptions[0];
            if (elegida && elegida.disabled) {
                hijo.value = "";
            }
        }

        padre.addEventListener("change", filtrar);
        filtrar();
    });

    // Grupo de botones donde solo uno queda activo.
    function alternar(botones, alElegir) {
        botones.forEach(function (boton) {
            boton.addEventListener("click", function () {
                botones.forEach(function (otro) {
                    const activo = otro === boton;
                    otro.classList.toggle("active", activo);
                    otro.setAttribute("aria-pressed", activo ? "true" : "false");
                });
                alElegir(boton);
            });
        });
    }

    // Evolución por año: un gráfico por indicador.
    alternar(document.querySelectorAll("[data-evolucion]"), function (boton) {
        document.querySelectorAll("[data-evolucion-grafico]").forEach(function (grafico) {
            grafico.classList.toggle("d-none", grafico.dataset.evolucionGrafico !== boton.dataset.evolucion);
        });
    });

    // Mapa territorial (RF-IND-03): un círculo por comuna, tamaño según el total.
    const datos = document.getElementById("mapa-puntos");
    const contenedor = document.getElementById("mapaTerritorial");
    if (!datos || !contenedor || typeof L === "undefined") {
        return;
    }

    const puntos = JSON.parse(datos.textContent);
    const color = getComputedStyle(document.documentElement).getPropertyValue("--ua-red").trim() || "#C8232C";
    const mapa = L.map(contenedor, { scrollWheelZoom: false });
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
        maxZoom: 18,
        attribution: "&copy; OpenStreetMap",
    }).addTo(mapa);

    const capa = L.layerGroup().addTo(mapa);
    let modo = "proyectos";

    function texto(valor) {
        const span = document.createElement("span");
        span.textContent = valor;
        return span.innerHTML;
    }

    function dibujar() {
        capa.clearLayers();
        const maximo = Math.max(1, ...puntos.map(function (p) { return p[modo]; }));
        puntos.forEach(function (punto) {
            const valor = punto[modo];
            if (!valor) {
                return;
            }
            const popup =
                "<strong>" + texto(punto.comuna) + "</strong><br>" +
                punto.socios + " socio" + (punto.socios === 1 ? "" : "s") + " · " +
                punto.proyectos + " proyecto" + (punto.proyectos === 1 ? "" : "s") +
                (punto.carreras.length ? "<br>Carreras: " + texto(punto.carreras.join(", ")) : "") +
                (punto.anios.length ? "<br>Años: " + punto.anios.join(", ") : "");
            L.circleMarker([punto.lat, punto.lon], {
                radius: 8 + 18 * (valor / maximo),
                color: color,
                fillColor: color,
                fillOpacity: 0.7,
                weight: 1,
            })
                .bindTooltip(String(valor), { permanent: true, direction: "center", className: "mapa-etiqueta" })
                .bindPopup(popup)
                .addTo(capa);
        });
    }

    const limites = L.latLngBounds(puntos.map(function (p) { return [p.lat, p.lon]; }));
    mapa.fitBounds(limites.pad(0.3), { maxZoom: 12 });
    dibujar();

    const titulo = document.querySelector("[data-mapa-titulo]");
    alternar(document.querySelectorAll("[data-mapa-modo]"), function (boton) {
        modo = boton.dataset.mapaModo;
        document.querySelectorAll("[data-mapa-lista]").forEach(function (lista) {
            lista.classList.toggle("d-none", lista.dataset.mapaLista !== modo);
        });
        if (titulo) {
            titulo.textContent = modo === "socios" ? "Comunas con más socios" : "Comunas con más proyectos";
        }
        dibujar();
    });
})();
