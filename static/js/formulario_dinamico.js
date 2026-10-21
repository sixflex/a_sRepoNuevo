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
        paginar();
    });
    let listo = false;
    aplicar();
    listo = true;

    // ---------- Una sección por página, como en Microsoft Forms ----------
    // Todas las secciones siguen en el mismo <form> y se envían juntas al final;
    // aquí solo se muestran de a una. Las ocultas por una condición se saltan,
    // así "Siguiente" lleva a la sección que corresponde según lo respondido.

    const botonAnterior = formulario.querySelector("[data-anterior]");
    const botonSiguiente = formulario.querySelector("[data-siguiente]");
    const botonEnviar = formulario.querySelector("[data-enviar]");
    const progreso = formulario.querySelector("[data-progreso]");
    const secciones = Array.from(formulario.querySelectorAll("[data-seccion]"));
    let actual = secciones[0] || null;

    function paginas() {
        return secciones.filter(function (seccion) {
            return !seccion.hidden;
        });
    }

    function paginar() {
        const lista = paginas();
        if (!botonSiguiente || lista.length < 2) {
            secciones.forEach(function (seccion) {
                seccion.classList.remove("enc-fuera-de-pagina");
            });
            [botonAnterior, botonSiguiente, progreso].forEach(function (elemento) {
                if (elemento) {
                    elemento.hidden = true;
                }
            });
            if (botonEnviar) {
                botonEnviar.hidden = false;
            }
            return;
        }
        if (lista.indexOf(actual) === -1) {
            // La sección actual dejó de aplicar: se vuelve a la anterior que sí aplica.
            const previas = secciones.slice(0, secciones.indexOf(actual)).filter(function (seccion) {
                return !seccion.hidden;
            });
            actual = previas.length ? previas[previas.length - 1] : lista[0];
        }
        const indice = lista.indexOf(actual);
        secciones.forEach(function (seccion) {
            seccion.classList.toggle("enc-fuera-de-pagina", seccion !== actual);
        });
        botonAnterior.hidden = indice === 0;
        botonSiguiente.hidden = indice === lista.length - 1;
        botonEnviar.hidden = indice !== lista.length - 1;
        progreso.hidden = false;
        progreso.textContent = "Sección " + (indice + 1) + " de " + lista.length;
    }

    function irA(seccion) {
        if (!seccion || seccion === actual) {
            return;
        }
        actual = seccion;
        paginar();
        seccion.classList.remove("enc-aparece");
        void seccion.offsetWidth;
        seccion.classList.add("enc-aparece");
        const destino = document.querySelector(".enc-encabezado") || seccion;
        destino.scrollIntoView({ behavior: "smooth", block: "start" });
    }

    // Obligatorias sin responder de la sección actual (el servidor vuelve a validar).
    function respondida(pregunta) {
        const campos = Array.from(pregunta.querySelectorAll("input, select, textarea")).filter(function (campo) {
            return !campo.disabled && !campo.closest("[data-otro]") && campo.type !== "hidden";
        });
        return campos.some(function (campo) {
            if (campo.type === "radio" || campo.type === "checkbox") {
                return campo.checked;
            }
            if (campo.type === "file") {
                return campo.files && campo.files.length > 0;
            }
            return campo.value.trim() !== "";
        });
    }

    function obligatoria(pregunta) {
        if (pregunta.querySelector(".enc-obligatoria")) {
            return true;
        }
        // Filas de una cuadrícula: el asterisco está en el enunciado de la tabla.
        return Boolean(pregunta.querySelector("input[required]"));
    }

    function validarSeccion(seccion) {
        let primera = null;
        seccion.querySelectorAll("[data-pregunta]").forEach(function (pregunta) {
            const previo = pregunta.querySelector("[data-error-pagina]");
            if (previo) {
                previo.remove();
            }
            if (pregunta.hidden || !obligatoria(pregunta) || respondida(pregunta)) {
                if (!pregunta.querySelector(".enc-error")) {
                    pregunta.classList.remove("tiene-error");
                }
                return;
            }
            pregunta.classList.add("tiene-error");
            const aviso = document.createElement("div");
            aviso.className = "enc-error";
            aviso.dataset.errorPagina = "";
            const icono = document.createElement("i");
            icono.className = "bi bi-exclamation-circle me-1";
            icono.setAttribute("aria-hidden", "true");
            aviso.append(icono, "Esta pregunta es obligatoria.");
            (pregunta.querySelector(".enc-cuadricula-fila") || pregunta).appendChild(aviso);
            primera = primera || pregunta;
        });
        if (primera) {
            primera.scrollIntoView({ behavior: "smooth", block: "center" });
            const campo = primera.querySelector("input, select, textarea");
            if (campo) {
                campo.focus({ preventScroll: true });
            }
        }
        return !primera;
    }

    if (botonSiguiente) {
        botonSiguiente.addEventListener("click", function () {
            if (!validarSeccion(actual)) {
                return;
            }
            const lista = paginas();
            irA(lista[lista.indexOf(actual) + 1]);
        });
        botonAnterior.addEventListener("click", function () {
            const lista = paginas();
            irA(lista[lista.indexOf(actual) - 1]);
        });
        // La última página se valida igual antes de enviar.
        formulario.addEventListener("submit", function (evento) {
            if (paginas().length > 1 && !validarSeccion(actual)) {
                evento.preventDefault();
                evento.stopImmediatePropagation();
            }
        });
    }

    // Si el servidor devolvió errores, se abre la sección del primero; los
    // enlaces del resumen de errores también llevan a su sección.
    const conError = formulario.querySelector("[data-seccion] .tiene-error");
    if (conError) {
        actual = conError.closest("[data-seccion]");
    }
    paginar();
    document.querySelectorAll("[data-resumen-errores] a[href^='#pregunta-']").forEach(function (enlace) {
        enlace.addEventListener("click", function () {
            const destino = document.querySelector(enlace.getAttribute("href"));
            if (destino) {
                irA(destino.closest("[data-seccion]"));
            }
        });
    });

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
