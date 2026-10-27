// Planilla pública de la Dirección de Carrera: agregar y quitar asignaturas
// (filas del formset "filas"), docentes (formset "docentes-N" de cada fila)
// y posibles socios opcionales (formset "socios-N" de cada fila).
(function () {
    "use strict";

    const tabla = document.getElementById("tabla-planificacion");
    if (!tabla) {
        return;
    }

    // Quitar un docente o socio: se marca su DELETE, se limpian sus datos y se oculta.
    function vincularQuitarDocente(raiz) {
        raiz.querySelectorAll('.docente-subcard input[type="checkbox"][name$="-DELETE"], .socio-subcard input[type="checkbox"][name$="-DELETE"]').forEach(function (check) {
            if (check.dataset.vinculado) {
                return;
            }
            check.dataset.vinculado = "true";
            check.addEventListener("change", function () {
                if (!check.checked) {
                    return;
                }
                const tarjeta = check.closest(".docente-subcard, .socio-subcard");
                tarjeta.querySelectorAll('input[type="text"], input[type="email"]').forEach(function (input) { input.value = ""; });
                tarjeta.querySelectorAll("select").forEach(function (select) { select.selectedIndex = 0; });
                tarjeta.classList.add("saliendo");
                setTimeout(function () { tarjeta.hidden = true; }, 200);
            });
        });
    }

    function vincularAgregarDocente(raiz) {
        raiz.querySelectorAll(".agregar-docente, .agregar-socio").forEach(function (boton) {
            if (boton.dataset.vinculado) {
                return;
            }
            boton.dataset.vinculado = "true";
            boton.addEventListener("click", function () {
                const prefijo = boton.dataset.prefix;
                const contenedor = document.querySelector('.docentes-container[data-prefix="' + prefijo + '"], .socios-container[data-prefix="' + prefijo + '"]');
                const total = document.getElementById("id_" + prefijo + "-TOTAL_FORMS");
                const plantilla = document.getElementById("template-" + prefijo);
                if (!contenedor || !total || !plantilla) {
                    return;
                }
                const indice = parseInt(total.value, 10);
                contenedor.insertAdjacentHTML(
                    "beforeend",
                    plantilla.innerHTML.replaceAll("__doc_prefix__", indice).replaceAll("__soc_prefix__", indice).replaceAll("__prefix__", indice)
                );
                const encabezado = contenedor.previousElementSibling;
                if (encabezado && encabezado.classList.contains("socios-encabezado")) {
                    encabezado.hidden = false;
                }
                total.value = indice + 1;
                vincularQuitarDocente(contenedor);
                const nueva = contenedor.lastElementChild.querySelector("input:not([type=hidden])");
                if (nueva) {
                    nueva.focus();
                }
            });
        });
    }

    // Una fila nueva se marca con su DELETE y se oculta (no se borra del HTML,
    // así el total del formset y los prefijos de las demás filas no cambian).
    // Una fila ya guardada usa la casilla de quitar, que se aplica al guardar.
    function vincularQuitarFila(raiz) {
        raiz.querySelectorAll(".btn-quitar-fila").forEach(function (boton) {
            if (boton.dataset.vinculado) {
                return;
            }
            boton.dataset.vinculado = "true";
            boton.addEventListener("click", function () {
                const fila = boton.closest("tbody");
                const borrar = fila.querySelector('input[type="checkbox"][name^="filas-"][name$="-DELETE"]');
                if (borrar) {
                    borrar.checked = true;
                }
                fila.classList.add("saliendo");
                setTimeout(function () { fila.hidden = true; }, 200);
            });
        });
    }

    const agregarFila = document.getElementById("btn-agregar-fila");
    if (agregarFila) {
        agregarFila.addEventListener("click", function () {
            const total = document.getElementById("id_filas-TOTAL_FORMS");
            const plantilla = document.getElementById("template-fila");
            if (!total || !plantilla) {
                return;
            }
            const indice = parseInt(total.value, 10);
            tabla.insertAdjacentHTML("beforeend", plantilla.innerHTML.replaceAll("__prefix__", indice));
            total.value = indice + 1;

            const fila = tabla.tBodies[tabla.tBodies.length - 1];
            vincularAgregarDocente(fila);
            vincularQuitarDocente(fila);
            vincularQuitarFila(fila);
            fila.scrollIntoView({ behavior: "smooth", block: "nearest" });
            const primero = fila.querySelector("select, input:not([type=hidden])");
            if (primero) {
                primero.focus({ preventScroll: true });
            }
        });
    }

    vincularQuitarDocente(document);
    vincularAgregarDocente(document);
    vincularQuitarFila(document);
})();
