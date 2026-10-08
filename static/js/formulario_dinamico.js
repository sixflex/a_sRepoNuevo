/*
 * Formularios configurables (HU-09): muestra u oculta secciones, preguntas y
 * opciones según lo elegido (por ejemplo, la pestaña de programa o carrera).
 * Repite en el navegador la misma regla que aplica el servidor en
 * encuestas/services.py: {"pregunta": id, "valores": [...]}.
 * El servidor vuelve a validar todo; esto solo mejora la experiencia.
 */
(function () {
    "use strict";

    const formulario = document.querySelector("[data-formulario-dinamico]");
    if (!formulario) {
        return;
    }

    function leerRegla(elemento, atributo) {
        const texto = elemento.getAttribute(atributo);
        if (!texto) {
            return null;
        }
        try {
            return JSON.parse(texto);
        } catch (error) {
            return null;
        }
    }

    function leerSeleccion() {
        const seleccion = {};
        formulario.querySelectorAll("[data-condicionante]").forEach(function (pregunta) {
            const id = pregunta.dataset.condicionante;
            const valores = new Set();
            pregunta.querySelectorAll('[name="p' + id + '"]').forEach(function (campo) {
                if (campo.tagName === "SELECT") {
                    if (campo.value) {
                        valores.add(campo.value);
                    }
                } else if (campo.checked) {
                    valores.add(campo.value);
                }
            });
            seleccion[id] = valores;
        });
        return seleccion;
    }

    function mostrar(elemento, visible) {
        // Lo que aparece al cambiar de programa entra con un fundido suave.
        if (visible && elemento.hidden && listo && !elemento.matches("option")) {
            elemento.classList.remove("enc-aparece");
            void elemento.offsetWidth;
            elemento.classList.add("enc-aparece");
        }
        elemento.hidden = !visible;
        const campos = elemento.matches("input, select, textarea, option")
            ? [elemento]
            : elemento.querySelectorAll("input, select, textarea");
        campos.forEach(function (campo) {
            campo.disabled = !visible;
            if (!visible && elemento.matches("[data-opcion]")) {
                if (campo.tagName === "OPTION") {
                    campo.selected = false;
                } else {
                    campo.checked = false;
                }
            }
        });
    }

    function actualizarOtros(pregunta) {
        const otro = pregunta.querySelector("[data-otro]");
        if (!otro) {
            return;
        }
        const elegido = pregunta.querySelector("input[data-es-otras]:checked, option[data-es-otras]:checked");
        mostrar(otro, Boolean(elegido) && !pregunta.hidden);
    }

    function aplicar() {
        const seleccion = leerSeleccion();
        const visibles = new Set();

        function cumple(regla) {
            if (!regla) {
                return true;
            }
            const id = String(regla.pregunta);
            if (!visibles.has(id)) {
                return false;
            }
            const elegidos = seleccion[id] || new Set();
            return (regla.valores || []).some(function (valor) {
                return elegidos.has(valor);
            });
        }

        formulario.querySelectorAll("[data-seccion]").forEach(function (seccion) {
            const seccionVisible = cumple(leerRegla(seccion, "data-regla"));
            mostrar(seccion, seccionVisible);

            seccion.querySelectorAll("[data-pregunta]").forEach(function (pregunta) {
                const visible = seccionVisible && cumple(leerRegla(pregunta, "data-regla"));
                mostrar(pregunta, visible);
                if (!visible) {
                    return;
                }
                visibles.add(pregunta.dataset.pregunta);
                pregunta.querySelectorAll("[data-opcion]").forEach(function (opcion) {
                    mostrar(opcion, cumple(leerRegla(opcion, "data-opcion-regla")));
                });
                actualizarOtros(pregunta);
            });
        });
    }

    formulario.addEventListener("change", function () {
        // Dos pasadas: ocultar una opción puede cambiar otra condición.
        aplicar();
        aplicar();
    });
    let listo = false;
    aplicar();
    listo = true;

    // ---------- Ayudas al escribir ----------

    // RUT: al salir del campo se deja sin puntos y con guion (12345678-5), el
    // formato que usan los forms del cliente. El servidor acepta cualquier forma.
    function formatearRut(valor) {
        const limpio = valor.replace(/[^0-9kK]/g, "").toUpperCase();
        if (limpio.length < 2) {
            return valor;
        }
        return limpio.slice(0, -1) + "-" + limpio.slice(-1);
    }

    formulario.querySelectorAll("[data-rut]").forEach(function (campo) {
        campo.addEventListener("blur", function () {
            campo.value = campo.value.trim() ? formatearRut(campo.value) : "";
        });
    });

    // Contador de caracteres cuando la pregunta tiene largo máximo.
    formulario.querySelectorAll("[data-contador]").forEach(function (campo) {
        const contador = document.createElement("div");
        contador.className = "enc-contador-caracteres";
        campo.after(contador);
        function actualizar() {
            const restantes = campo.maxLength - campo.value.length;
            contador.textContent = campo.value.length + " / " + campo.maxLength;
            contador.classList.toggle("cerca", restantes <= 20);
        }
        campo.addEventListener("input", actualizar);
        actualizar();
    });

    // Al volver con errores, se lleva la vista al resumen para que se lea primero.
    const resumenErrores = document.querySelector("[data-resumen-errores]");
    if (resumenErrores) {
        resumenErrores.focus();
    }

    // Evita el doble envío mientras se procesa (el servidor también lo controla).
    // Si se vuelve con "Atrás", el botón queda disponible de nuevo.
    window.addEventListener("pageshow", function (evento) {
        const boton = formulario.querySelector("[data-enviar]");
        if (evento.persisted && boton) {
            boton.disabled = false;
            boton.querySelector("[data-enviando]").hidden = true;
        }
    });

    formulario.addEventListener("submit", function () {
        const boton = formulario.querySelector("[data-enviar]");
        if (boton) {
            boton.disabled = true;
            boton.querySelector("[data-enviando]").hidden = false;
        }
    });
})();
