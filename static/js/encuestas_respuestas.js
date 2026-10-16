/*
 * Pestaña Respuestas (HU-09): buscador de la vista Individual y apertura
 * animada de cada respuesta (los <details> no animan solos).
 */
(function () {
    "use strict";

    const buscador = document.querySelector("[data-buscar-respuesta]");
    const respuestas = Array.from(document.querySelectorAll("[data-respuesta]"));
    const sinResultados = document.querySelector("[data-sin-resultados]");
    const sinMovimiento = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

    function normalizar(texto) {
        return texto.normalize("NFD").replace(/[̀-ͯ.\-\s]/g, "").toLowerCase();
    }

    if (buscador) {
        buscador.addEventListener("input", function () {
            const termino = normalizar(buscador.value);
            let visibles = 0;
            respuestas.forEach(function (respuesta) {
                const coincide = normalizar(respuesta.dataset.texto).includes(termino);
                respuesta.hidden = !coincide;
                visibles += coincide ? 1 : 0;
            });
            sinResultados.hidden = visibles > 0;
        });
    }

    respuestas.forEach(function (respuesta) {
        const resumen = respuesta.querySelector("summary");
        const detalle = respuesta.querySelector(".enc-respuesta-detalle");
        resumen.addEventListener("click", function (evento) {
            if (sinMovimiento) {
                return;
            }
            evento.preventDefault();
            if (respuesta.open) {
                const animacion = detalle.animate(
                    [{ height: detalle.offsetHeight + "px", opacity: 1 }, { height: "0px", opacity: 0 }],
                    { duration: 200, easing: "ease-in" },
                );
                respuesta.classList.remove("abierta");
                animacion.onfinish = function () {
                    respuesta.open = false;
                };
            } else {
                respuesta.open = true;
                respuesta.classList.add("abierta");
                detalle.animate(
                    [{ height: "0px", opacity: 0 }, { height: detalle.offsetHeight + "px", opacity: 1 }],
                    { duration: 240, easing: "ease-out" },
                );
            }
        });
    });
})();
