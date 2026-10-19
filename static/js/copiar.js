// Botones para copiar un dato al portapapeles: <button data-copiar="texto">.
(function () {
    "use strict";

    function copiar(texto) {
        if (navigator.clipboard && window.isSecureContext) {
            return navigator.clipboard.writeText(texto);
        }
        // Respaldo para http sin TLS (por ejemplo, la red local).
        const area = document.createElement("textarea");
        area.value = texto;
        area.setAttribute("readonly", "");
        area.style.position = "fixed";
        area.style.opacity = "0";
        document.body.appendChild(area);
        area.select();
        const ok = document.execCommand("copy");
        area.remove();
        return ok ? Promise.resolve() : Promise.reject();
    }

    document.addEventListener("click", function (e) {
        const boton = e.target.closest("[data-copiar]");
        if (!boton) {
            return;
        }
        const icono = boton.querySelector("i");
        const original = boton.getAttribute("aria-label");
        copiar(boton.dataset.copiar).then(function () {
            boton.classList.add("copiado");
            if (icono) {
                icono.className = "bi bi-check2";
            }
            boton.setAttribute("aria-label", "Copiado");
            boton.title = "Copiado";
            clearTimeout(boton._temporizador);
            boton._temporizador = setTimeout(function () {
                boton.classList.remove("copiado");
                if (icono) {
                    icono.className = "bi bi-copy";
                }
                boton.setAttribute("aria-label", original);
                boton.title = original;
            }, 1500);
        });
    });
})();
