/*
 * Campos del editor de preguntas y secciones (HU-09): condición "Mostrar solo
 * si…", campos según el tipo de pregunta y lista de opciones.
 *
 * Sirve tanto para las páginas completas (editar pregunta o sección) como para
 * los editores que el constructor en vivo carga dentro de cada tarjeta: los
 * eventos se escuchan en el documento y EncuestasEditor.iniciar(raiz) prepara
 * lo que se acaba de insertar.
 */
window.EncuestasEditor = (function () {
    "use strict";

    // Los cambios hechos por botones (agregar o quitar opción) no disparan
    // "input"; este evento avisa al guardado automático.
    function avisarCambio(elemento) {
        elemento.dispatchEvent(new CustomEvent("editor:cambio", { bubbles: true }));
    }

    // ---------- Condición de visibilidad ----------
    function iniciarRegla(editor) {
        const selectPregunta = editor.querySelector("select");
        const contenedor = editor.querySelector("[data-regla-valores]");
        if (!selectPregunta || !contenedor) {
            return;
        }
        let opciones = {};
        try {
            opciones = JSON.parse(editor.dataset.opciones || "{}");
        } catch (error) {
            opciones = {};
        }
        const seleccionInicial = new Set((editor.dataset.seleccion || "").split("|").filter(Boolean));
        const prefijo = "regla_" + Math.random().toString(36).slice(2, 8) + "_";

        function dibujar() {
            contenedor.innerHTML = "";
            const lista = opciones[selectPregunta.value] || [];
            if (!lista.length) {
                return;
            }
            const titulo = document.createElement("div");
            titulo.className = "form-label-ua";
            titulo.textContent = "tiene alguna de estas respuestas";
            contenedor.appendChild(titulo);
            lista.forEach(function (par, indice) {
                const caja = document.createElement("div");
                caja.className = "form-check";
                const input = document.createElement("input");
                input.type = "checkbox";
                input.className = "form-check-input";
                input.name = "regla_valores";
                input.value = par[0];
                input.id = prefijo + indice;
                input.checked = seleccionInicial.has(par[0]);
                const etiqueta = document.createElement("label");
                etiqueta.className = "form-check-label";
                etiqueta.htmlFor = input.id;
                etiqueta.textContent = par[1];
                caja.appendChild(input);
                caja.appendChild(etiqueta);
                contenedor.appendChild(caja);
            });
        }

        selectPregunta.addEventListener("change", function () {
            seleccionInicial.clear();
            dibujar();
        });
        dibujar();
    }

    // ---------- Pregunta: campos según tipo y opciones ----------
    function datos(formulario) {
        return {
            tipo: formulario.querySelector('[name="tipo"]'),
            conOpciones: new Set(JSON.parse(formulario.dataset.tiposConOpciones || "[]")),
            iconos: JSON.parse(formulario.dataset.iconosTipo || "{}"),
            filas: formulario.querySelector("[data-filas-opciones]"),
            plantilla: formulario.querySelector("[data-plantilla-opcion]"),
        };
    }

    function mostrarSegunSelector(raiz, esSelector) {
        raiz.querySelectorAll("[data-solo-selector]").forEach(function (el) {
            el.hidden = !esSelector;
        });
        raiz.querySelectorAll("[data-no-selector]").forEach(function (el) {
            el.hidden = esSelector;
        });
    }

    function actualizarTipo(formulario) {
        const d = datos(formulario);
        const tipo = d.tipo.value;
        formulario.dataset.tipo = tipo;
        formulario.querySelectorAll("[data-para-tipos]").forEach(function (bloque) {
            bloque.hidden = !bloque.dataset.paraTipos.split(",").includes(tipo);
        });
        formulario.querySelector("[data-opciones-editor]").hidden = !d.conOpciones.has(tipo);
        const icono = formulario.querySelector("[data-icono-tipo]");
        if (icono) {
            icono.className = "bi " + (d.iconos[tipo] || "bi-question-circle");
        }
        mostrarSegunSelector(formulario, tipo === "SELECTOR_PROGRAMA");
        if (!d.filas.querySelector("[data-fila-opcion]") && d.conOpciones.has(tipo)) {
            agregarFila(formulario, null, false, false);
        }
    }

    function agregarFila(formulario, despuesDe, esOtros, enfocar) {
        const d = datos(formulario);
        const fila = d.plantilla.content.firstElementChild.cloneNode(true);
        if (esOtros) {
            fila.querySelector("[data-campo-otros]").value = "1";
            fila.querySelector("[data-etiqueta-otros]").hidden = false;
            fila.querySelector('[name="opcion_texto"]').value = "Otras";
        }
        // "Otros" va siempre al final, como en Forms.
        const otros = d.filas.querySelector('[data-campo-otros][value="1"]');
        if (despuesDe) {
            despuesDe.after(fila);
        } else if (otros && !esOtros) {
            otros.closest("[data-fila-opcion]").before(fila);
        } else {
            d.filas.appendChild(fila);
        }
        mostrarSegunSelector(fila, d.tipo.value === "SELECTOR_PROGRAMA");
        fila.classList.add("enc-entrando");
        if (enfocar) {
            fila.querySelector('[name="opcion_texto"]').focus();
        }
        avisarCambio(formulario);
        return fila;
    }

    function quitarFila(formulario, fila) {
        const anterior = fila.previousElementSibling;
        fila.remove();
        if (anterior) {
            const input = anterior.querySelector('[name="opcion_texto"]');
            input.focus();
            input.setSelectionRange(input.value.length, input.value.length);
        }
        avisarCambio(formulario);
    }

    // Textos que crecen con lo escrito, para no esconder preguntas largas.
    function ajustarAlto(area) {
        area.style.height = "auto";
        area.style.height = area.scrollHeight + 2 + "px";
    }

    function iniciar(raiz) {
        raiz.querySelectorAll("[data-regla-editor]").forEach(iniciarRegla);
        raiz.querySelectorAll("[data-pregunta-editor]").forEach(actualizarTipo);
        raiz.querySelectorAll("textarea[data-autoalto]").forEach(ajustarAlto);
    }

    document.addEventListener("input", function (evento) {
        if (evento.target.matches("textarea[data-autoalto]")) {
            ajustarAlto(evento.target);
        }
    });

    document.addEventListener("click", function (evento) {
        const boton = evento.target.closest("[data-pregunta-editor] button");
        if (!boton) {
            return;
        }
        const formulario = boton.closest("[data-pregunta-editor]");
        const fila = boton.closest("[data-fila-opcion]");
        if (boton.hasAttribute("data-agregar-opcion")) {
            agregarFila(formulario, null, false, true);
        } else if (boton.hasAttribute("data-agregar-otros")) {
            agregarFila(formulario, null, true, true);
        } else if (boton.hasAttribute("data-filtrar-opcion") && fila) {
            const chips = fila.querySelector("[data-chips-programas]");
            chips.classList.toggle("abierto");
            if (chips.classList.contains("abierto")) {
                chips.querySelector("input").focus();
            }
        } else if (boton.hasAttribute("data-quitar-opcion") && fila) {
            quitarFila(formulario, fila);
        } else if (boton.hasAttribute("data-subir-opcion") && fila && fila.previousElementSibling) {
            fila.parentNode.insertBefore(fila, fila.previousElementSibling);
            avisarCambio(formulario);
        } else if (boton.hasAttribute("data-bajar-opcion") && fila && fila.nextElementSibling) {
            fila.parentNode.insertBefore(fila.nextElementSibling, fila);
            avisarCambio(formulario);
        }
    });

    // Enter agrega la opción siguiente y Retroceso en una opción vacía la quita, como en Forms.
    document.addEventListener("keydown", function (evento) {
        const input = evento.target;
        if (!input.matches('[data-pregunta-editor] [name="opcion_texto"]')) {
            return;
        }
        const formulario = input.closest("[data-pregunta-editor]");
        const fila = input.closest("[data-fila-opcion]");
        if (evento.key === "Enter") {
            evento.preventDefault();
            agregarFila(formulario, fila, false, true);
        } else if (evento.key === "Backspace" && input.value === "" &&
                   formulario.querySelectorAll("[data-fila-opcion]").length > 1) {
            evento.preventDefault();
            quitarFila(formulario, fila);
        }
    });

    document.addEventListener("change", function (evento) {
        const objetivo = evento.target;
        const formulario = objetivo.closest("[data-pregunta-editor]");
        if (!formulario) {
            return;
        }
        if (objetivo.matches('[name="tipo"]')) {
            actualizarTipo(formulario);
        } else if (objetivo.matches("[data-programa]")) {
            // Las casillas "Solo para" se guardan como texto separado por comas.
            const fila = objetivo.closest("[data-fila-opcion]");
            const marcados = Array.from(fila.querySelectorAll("[data-programa]:checked")).map(function (caja) {
                return caja.value;
            });
            fila.querySelector("[data-campo-programas]").value = marcados.join(",");
        }
    });

    iniciar(document);
    return { iniciar: iniciar };
})();
