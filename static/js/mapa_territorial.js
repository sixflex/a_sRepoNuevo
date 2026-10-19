// Mapa territorial (RF-IND-03): un círculo por comuna, ubicado en el centro de
// la comuna y con tamaño según el total. Lo usan el panel del coordinador y el
// portal público. El público solo recibe totales; el del coordinador recibe
// además los datos de cada socio (dirección y contacto) y los
// muestra en la columna lateral al hacer clic en una comuna.
(function () {
    "use strict";

    const datos = document.getElementById("mapa-puntos");
    const contenedor = document.getElementById("mapaTerritorial");
    if (!datos || !contenedor || typeof L === "undefined") {
        return;
    }

    const puntos = JSON.parse(datos.textContent);
    const color = getComputedStyle(document.documentElement).getPropertyValue("--ua-red").trim() || "#C8232C";
    const mapa = L.map(contenedor, { scrollWheelZoom: false });
    L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
        maxZoom: 18,
        // Django responde con Referrer-Policy: same-origin; OSM bloquea los mosaicos sin Referer.
        referrerPolicy: "strict-origin-when-cross-origin",
        attribution: "&copy; OpenStreetMap",
    }).addTo(mapa);

    const capa = L.layerGroup().addTo(mapa);
    let modo = "proyectos";

    function texto(valor) {
        const span = document.createElement("span");
        span.textContent = valor;
        return span.innerHTML;
    }

    function plural(cantidad, singular, varios) {
        return cantidad + " " + (cantidad === 1 ? singular : varios);
    }

    // Columna lateral: ranking de comunas o, al elegir una, sus socios.
    const listas = document.querySelectorAll("[data-mapa-lista]");
    const titulo = document.querySelector("[data-mapa-titulo]");
    const detalle = document.querySelector("[data-mapa-detalle]");

    function mostrarRanking() {
        if (detalle) {
            detalle.classList.add("d-none");
        }
        if (titulo) {
            titulo.classList.remove("d-none");
            titulo.textContent = modo === "socios" ? "Comunas con más socios" : "Comunas con más proyectos";
        }
        listas.forEach(function (lista) {
            lista.classList.toggle("d-none", lista.dataset.mapaLista !== modo);
        });
    }

    function elemento(etiqueta, clase, contenido) {
        const nodo = document.createElement(etiqueta);
        if (clase) {
            nodo.className = clase;
        }
        if (contenido) {
            nodo.textContent = contenido;
        }
        return nodo;
    }

    function mostrarSocios(punto) {
        detalle.querySelector("[data-mapa-detalle-titulo]").textContent =
            punto.comuna + " · " + plural(punto.socios, "socio", "socios");
        const lista = detalle.querySelector("[data-mapa-detalle-lista]");
        lista.replaceChildren();

        // Solo los datos del socio; sus intervenciones se ven en su historial.
        function dato(icono, valor, enlace) {
            const fila = elemento("div", "mapa-socio-dato");
            const simbolo = elemento("i", "bi " + icono);
            simbolo.setAttribute("aria-hidden", "true");
            fila.appendChild(simbolo);
            const contenido = elemento(enlace ? "a" : "span", "", valor);
            if (enlace) {
                contenido.href = enlace;
            }
            fila.appendChild(contenido);
            return fila;
        }

        punto.detalle.forEach(function (socio) {
            const item = elemento("li", "mapa-socio");
            item.appendChild(elemento("span", "mapa-socio-nombre", socio.nombre));
            item.appendChild(dato("bi-geo-alt", socio.direccion || "Sin dirección registrada"));
            if (socio.contacto) {
                item.appendChild(dato("bi-person", socio.contacto));
            }
            if (socio.telefono) {
                item.appendChild(dato("bi-telephone", socio.telefono, "tel:" + socio.telefono.replace(/[^+\d]/g, "")));
            }
            if (socio.correo) {
                item.appendChild(dato("bi-envelope", socio.correo, "mailto:" + socio.correo));
            }
            const historial = elemento("a", "mapa-socio-historial", "Ver historial");
            historial.href = socio.url;
            item.appendChild(historial);
            lista.appendChild(item);
        });

        if (titulo) {
            titulo.classList.add("d-none");
        }
        listas.forEach(function (otra) { otra.classList.add("d-none"); });
        detalle.classList.remove("d-none");
        detalle.focus();
    }

    function dibujar() {
        capa.clearLayers();
        const maximo = Math.max(1, ...puntos.map(function (p) { return p[modo]; }));
        puntos.forEach(function (punto) {
            const valor = punto[modo];
            if (!valor) {
                return;
            }
            const marcador = L.circleMarker([punto.lat, punto.lon], {
                radius: 8 + 18 * (valor / maximo),
                color: color,
                fillColor: color,
                fillOpacity: 0.7,
                weight: 1,
            }).bindTooltip(String(valor), { permanent: true, direction: "center", className: "mapa-etiqueta" });

            const popup =
                "<strong>" + texto(punto.comuna) + "</strong><br>" +
                plural(punto.socios, "socio", "socios") + " · " +
                plural(punto.proyectos, "proyecto", "proyectos") +
                (punto.carreras.length ? "<br>Carreras: " + texto(punto.carreras.join(", ")) : "") +
                (punto.anios.length ? "<br>Años: " + punto.anios.join(", ") : "");
            marcador.bindPopup(popup);
            if (detalle && punto.detalle) {
                marcador.on("click", function () { mostrarSocios(punto); });
            }
            marcador.addTo(capa);
        });
    }

    const limites = L.latLngBounds(puntos.map(function (p) { return [p.lat, p.lon]; }));
    mapa.fitBounds(limites.pad(0.3), { maxZoom: 12 });
    dibujar();

    if (detalle) {
        detalle.querySelector("[data-mapa-volver]").addEventListener("click", mostrarRanking);
    }

    const botones = document.querySelectorAll("[data-mapa-modo]");
    botones.forEach(function (boton) {
        boton.addEventListener("click", function () {
            botones.forEach(function (otro) {
                const activo = otro === boton;
                otro.classList.toggle("active", activo);
                otro.setAttribute("aria-pressed", activo ? "true" : "false");
            });
            modo = boton.dataset.mapaModo;
            mostrarRanking();
            dibujar();
        });
    });
})();
