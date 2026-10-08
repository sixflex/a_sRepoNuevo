/*
 * Utilidades que comparten el constructor (encuestas_constructor.js) y el
 * panel de tema (encuestas_tema.js) del editor de formularios (HU-09).
 */
window.Encuestas = (function () {
    "use strict";

    function csrf() {
        const campo = document.querySelector('[name="csrfmiddlewaretoken"]');
        return campo ? campo.value : "";
    }

    // El servidor responde JSON cuando la petición trae "X-Requested-With: fetch".
    async function pedir(url, cuerpo) {
        const opciones = { headers: { "X-Requested-With": "fetch", "X-CSRFToken": csrf() } };
        if (cuerpo !== undefined) {
            opciones.method = "POST";
            opciones.body = cuerpo instanceof FormData ? cuerpo : new URLSearchParams(cuerpo);
        }
        let respuesta;
        try {
            respuesta = await fetch(url, opciones);
        } catch (error) {
            throw new Error("No hay conexión. Revisa tu internet y vuelve a intentarlo.");
        }
        let datos;
        try {
            datos = await respuesta.json();
        } catch (error) {
            throw new Error("Algo falló al guardar. Recarga la página e inténtalo de nuevo.");
        }
        if (!respuesta.ok && !datos.errores) {
            throw new Error(datos.error || "No se pudo guardar el cambio.");
        }
        return datos;
    }

    function avisar(texto) {
        const avisos = document.querySelector("[data-avisos]");
        const aviso = document.createElement("div");
        aviso.className = "enc-aviso";
        aviso.setAttribute("role", "alert");
        aviso.innerHTML = '<i class="bi bi-exclamation-triangle me-2" aria-hidden="true"></i>';
        aviso.appendChild(document.createTextNode(texto));
        avisos.appendChild(aviso);
        setTimeout(function () {
            aviso.classList.add("saliendo");
            aviso.addEventListener("animationend", function () { aviso.remove(); });
        }, 6000);
    }

    // Texto junto al estado de la versión: "Guardando…", "Todos los cambios se guardaron", etc.
    function marcarEstado(texto, tipo) {
        const estado = document.querySelector("[data-estado-guardado]");
        estado.textContent = texto;
        estado.dataset.tipo = tipo || "";
    }

    return { pedir: pedir, avisar: avisar, marcarEstado: marcarEstado };
})();
