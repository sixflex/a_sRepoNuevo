/*
 * Constructor de formularios en una sola página, al estilo de Forms (HU-09).
 *
 * - Clic en una tarjeta (pregunta o sección): se abre su editor en el mismo
 *   lugar. Los cambios se guardan solos; al salir se vuelve a la vista previa.
 * - Barra flotante: agrega una pregunta bajo la tarjeta activa, o una sección.
 * - Arrastrar desde la manija, o usar las flechas, cambia el orden.
 *
 * El servidor responde JSON cuando la petición trae "X-Requested-With: fetch"
 * (ver encuestas/views.py). Sin JavaScript, los enlaces llevan a las páginas
 * completas de edición.
 */
(function () {
    "use strict";

    const raiz = document.querySelector("[data-constructor]");
    if (!raiz) {
        return;
    }
    const lienzo = raiz.querySelector(".enc-lienzo");
    const contenedorSecciones = raiz.querySelector("[data-secciones]");
    const barra = raiz.querySelector("[data-barra]");
    const DEMORA_GUARDADO = 700;

    // ---------------------------------------------------------------- utilidades

    const pedir = window.Encuestas.pedir;
    const avisar = window.Encuestas.avisar;
    const marcarEstado = window.Encuestas.marcarEstado;

    function desdeHtml(html) {
        const plantilla = document.createElement("template");
        plantilla.innerHTML = html.trim();
        return plantilla.content.firstElementChild;
    }

    function animarEntrada(elemento) {
        elemento.classList.add("enc-entrando");
        elemento.addEventListener("animationend", function () {
            elemento.classList.remove("enc-entrando");
        }, { once: true });
    }

    function animarSalida(elemento) {
        return new Promise(function (resolver) {
            elemento.style.height = elemento.offsetHeight + "px";
            elemento.classList.add("enc-saliendo");
            requestAnimationFrame(function () {
                elemento.style.height = "0px";
            });
            setTimeout(function () {
                elemento.remove();
                resolver();
            }, 260);
        });
    }

    function seccionDe(elemento) {
        return elemento.closest("[data-seccion]");
    }

    function renumerarSecciones() {
        const secciones = contenedorSecciones.querySelectorAll("[data-seccion]");
        secciones.forEach(function (seccion, indice) {
            seccion.querySelector("[data-numero]").textContent = indice + 1;
            seccion.querySelector("[data-total]").textContent = secciones.length;
        });
    }

    // --------------------------------------------------------- errores en campos

    function limpiarErrores(formulario) {
        formulario.querySelectorAll("[data-error-para]").forEach(function (caja) {
            caja.innerHTML = "";
        });
        formulario.querySelectorAll(".is-invalid").forEach(function (campo) {
            campo.classList.remove("is-invalid");
        });
    }

    function mostrarErrores(formulario, errores) {
        let primero = null;
        Object.keys(errores || {}).forEach(function (campo) {
            const caja = formulario.querySelector('[data-error-para="' + campo + '"]') ||
                         formulario.querySelector('[data-error-para="__all__"]');
            const input = formulario.querySelector('[name="' + campo + '"]');
            if (input) {
                input.classList.add("is-invalid");
                primero = primero || input;
            }
            if (!caja) {
                return;
            }
            errores[campo].forEach(function (error) {
                const linea = document.createElement("div");
                linea.className = "enc-error";
                linea.textContent = error.message;
                caja.appendChild(linea);
            });
        });
        return primero;
    }

    // ------------------------------------------------------- guardado automático

    /*
     * Guarda el formulario poco después de cada cambio. Los guardados van en
     * fila (nunca dos a la vez) y uno pedido mientras otro corre se junta en
     * uno solo. guardar() devuelve la promesa del último guardado.
     */
    function autoguardado(formulario, alGuardar) {
        let temporizador = null;
        let cola = Promise.resolve({ ok: true });
        let enEspera = null;
        let sucio = false;

        async function enviar() {
            enEspera = null;
            if (!sucio) {
                return { ok: true, sinCambios: true };
            }
            sucio = false;
            const datos = new FormData(formulario);
            const filas = Array.from(formulario.querySelectorAll("[data-fila-opcion]")).filter(function (fila) {
                return fila.querySelector('[name="opcion_texto"]').value.trim() !== "";
            });
            marcarEstado("Guardando…", "guardando");
            try {
                const respuesta = await pedir(formulario.action, datos);
                limpiarErrores(formulario);
                if (!respuesta.ok) {
                    mostrarErrores(formulario, respuesta.errores);
                    marcarEstado("Revisa los campos marcados", "error");
                    return respuesta;
                }
                // Las opciones nuevas reciben su id para que el siguiente guardado las reconozca.
                (respuesta.opciones || []).forEach(function (id, indice) {
                    if (filas[indice]) {
                        filas[indice].querySelector('[name="opcion_id"]').value = id;
                    }
                });
                if (alGuardar) {
                    alGuardar(respuesta);
                }
                marcarEstado(sucio ? "Cambios sin guardar…" : "Todos los cambios se guardaron", sucio ? "" : "ok");
                return respuesta;
            } catch (error) {
                sucio = true;
                marcarEstado("Sin guardar", "error");
                avisar(error.message);
                return { ok: false };
            }
        }

        function guardar() {
            clearTimeout(temporizador);
            if (!enEspera) {
                enEspera = cola = cola.then(enviar);
            }
            return enEspera || cola;
        }

        function programar() {
            sucio = true;
            marcarEstado("Cambios sin guardar…", "");
            clearTimeout(temporizador);
            temporizador = setTimeout(guardar, DEMORA_GUARDADO);
        }

        ["input", "change", "editor:cambio"].forEach(function (evento) {
            formulario.addEventListener(evento, programar);
        });
        formulario.addEventListener("submit", function (evento) {
            evento.preventDefault();
            guardar();
        });

        return {
            guardar: guardar,
            pendiente: function () { return sucio || Boolean(enEspera); },
            detener: function () {
                clearTimeout(temporizador);
                sucio = false;
            },
        };
    }

    // ------------------------------------------- encabezado (título y descripción)

    const formDatos = raiz.querySelector("[data-datos-formulario]");
    const guardados = [];
    if (formDatos) {
        guardados.push(autoguardado(formDatos, function () {
            const titulo = formDatos.querySelector('[name="titulo"]').value.trim();
            document.querySelectorAll("[data-titulo-formulario]").forEach(function (el) {
                el.textContent = titulo;
            });
        }));
    }

    // ------------------------------------------------------------ tarjeta activa

    let activa = null; // { tarjeta, guardado, ultimoHtml }

    function moverBarra(tarjeta) {
        if (!barra) {
            return;
        }
        const arriba = tarjeta.getBoundingClientRect().top - lienzo.getBoundingClientRect().top;
        barra.style.setProperty("--barra-top", Math.max(arriba, 0) + "px");
    }

    async function abrir(tarjeta) {
        if (activa && activa.tarjeta === tarjeta) {
            return;
        }
        if (activa && !(await cerrar())) {
            return;
        }
        const editor = tarjeta.querySelector("[data-editor]");
        const sesion = { tarjeta: tarjeta, guardado: null, ultimoHtml: null };
        tarjeta.classList.add("activa", "cargando");
        activa = sesion;
        moverBarra(tarjeta);
        try {
            const respuesta = await pedir(tarjeta.dataset.urlEditar);
            if (activa !== sesion) {
                return;
            }
            editor.innerHTML = respuesta.html;
            tarjeta.querySelector("[data-vista]").hidden = true;
            editor.hidden = false;
            // Se inicia ya visible para que los textos midan bien su alto.
            window.EncuestasEditor.iniciar(editor);
            const formulario = editor.querySelector("form");
            sesion.guardado = autoguardado(formulario, function (datos) {
                sesion.ultimoHtml = datos.html;
            });
            animarEntrada(editor);
            const primero = formulario.querySelector('textarea[name="texto"], input[name="titulo"]');
            if (primero) {
                primero.focus();
                if (primero.value === "Pregunta sin título") {
                    primero.select();
                }
            }
        } catch (error) {
            avisar(error.message);
            tarjeta.classList.remove("activa");
            if (activa === sesion) {
                activa = null;
            }
        } finally {
            tarjeta.classList.remove("cargando");
            moverBarra(tarjeta);
        }
    }

    /* Guarda y vuelve a la vista previa. Devuelve false si hay errores por corregir. */
    async function cerrar() {
        if (!activa) {
            return true;
        }
        const actual = activa;
        if (actual.guardado) {
            const resultado = await actual.guardado.guardar();
            if (resultado && resultado.ok === false) {
                const campo = actual.tarjeta.querySelector(".is-invalid");
                if (campo) {
                    campo.focus();
                }
                avisar("Corrige lo marcado en rojo antes de seguir: así no se pierde el cambio.");
                return false;
            }
            actual.guardado.detener();
        }
        if (actual.ultimoHtml) {
            const nueva = desdeHtml(actual.ultimoHtml);
            const vistaNueva = nueva.querySelector("[data-vista]");
            actual.tarjeta.querySelector("[data-vista]").replaceWith(vistaNueva);
            // El lector de pantalla anuncia la tarjeta con su texto nuevo.
            if (nueva.hasAttribute("aria-label")) {
                actual.tarjeta.setAttribute("aria-label", nueva.getAttribute("aria-label"));
            }
        }
        const editor = actual.tarjeta.querySelector("[data-editor]");
        editor.hidden = true;
        editor.innerHTML = "";
        actual.tarjeta.querySelector("[data-vista]").hidden = false;
        actual.tarjeta.classList.remove("activa");
        if (activa === actual) {
            activa = null;
        }
        return true;
    }

    // Insertar y activar una tarjeta recién creada.
    function mostrarNueva(elemento, tarjeta) {
        animarEntrada(elemento);
        abrir(tarjeta);
        tarjeta.scrollIntoView({ behavior: "smooth", block: "center" });
    }

    // ------------------------------------------------------------------ acciones

    function destinoNuevaPregunta() {
        const tarjeta = activa ? activa.tarjeta : null;
        const seccion = tarjeta ? seccionDe(tarjeta) : contenedorSecciones.querySelector("[data-seccion]:last-child");
        return {
            seccion: seccion,
            despuesDe: tarjeta && tarjeta.dataset.tarjeta === "pregunta" ? tarjeta : null,
        };
    }

    async function agregarPregunta(seccion, despuesDe) {
        if (!seccion) {
            avisar("Primero agrega una sección.");
            return;
        }
        if (!(await cerrar())) {
            return;
        }
        try {
            const respuesta = await pedir(raiz.dataset.urlCrearPregunta, {
                bloque: seccion.dataset.seccion,
                despues_de: despuesDe ? despuesDe.dataset.id : "",
            });
            const tarjeta = desdeHtml(respuesta.html);
            if (despuesDe) {
                despuesDe.after(tarjeta);
            } else {
                seccion.querySelector("[data-lista-preguntas]").appendChild(tarjeta);
            }
            mostrarNueva(tarjeta, tarjeta);
            marcarEstado("Pregunta agregada", "ok");
        } catch (error) {
            avisar(error.message);
        }
    }

    async function agregarSeccion() {
        const actual = activa ? seccionDe(activa.tarjeta) : null;
        if (!(await cerrar())) {
            return;
        }
        try {
            const respuesta = await pedir(raiz.dataset.urlCrearSeccion, {
                despues_de: actual ? actual.dataset.seccion : "",
            });
            const seccion = desdeHtml(respuesta.html);
            if (actual) {
                actual.after(seccion);
            } else {
                contenedorSecciones.appendChild(seccion);
            }
            renumerarSecciones();
            prepararArrastre(seccion);
            mostrarNueva(seccion, seccion.querySelector('[data-tarjeta="seccion"]'));
            marcarEstado("Sección agregada", "ok");
        } catch (error) {
            avisar(error.message);
        }
    }

    async function duplicar(tarjeta) {
        if (!(await cerrar())) {
            return;
        }
        try {
            const respuesta = await pedir(tarjeta.dataset.urlDuplicar, {});
            const copia = desdeHtml(respuesta.html);
            tarjeta.after(copia);
            mostrarNueva(copia, copia);
            marcarEstado("Pregunta duplicada", "ok");
        } catch (error) {
            avisar(error.message);
        }
    }

    async function eliminar(tarjeta) {
        const esSeccion = tarjeta.dataset.tarjeta === "seccion";
        const pregunta = esSeccion
            ? "¿Eliminar esta sección? Debe estar vacía."
            : "¿Eliminar esta pregunta? Esta acción no se puede deshacer.";
        if (!window.confirm(pregunta)) {
            return;
        }
        try {
            if (activa && activa.tarjeta === tarjeta) {
                if (activa.guardado) {
                    activa.guardado.detener();
                }
                activa = null;
            }
            await pedir(tarjeta.dataset.urlEliminar, {});
            await animarSalida(esSeccion ? seccionDe(tarjeta) : tarjeta);
            if (esSeccion) {
                renumerarSecciones();
            }
            marcarEstado(esSeccion ? "Sección eliminada" : "Pregunta eliminada", "ok");
        } catch (error) {
            avisar(error.message);
        }
    }

    async function mover(tarjeta, direccion) {
        const esSeccion = tarjeta.dataset.tarjeta === "seccion";
        const elemento = esSeccion ? seccionDe(tarjeta) : tarjeta;
        const vecino = direccion === "arriba" ? elemento.previousElementSibling : elemento.nextElementSibling;
        if (!vecino) {
            return;
        }
        if (!(await cerrar())) {
            return;
        }
        try {
            await pedir(direccion === "arriba" ? tarjeta.dataset.urlSubir : tarjeta.dataset.urlBajar, {});
            if (direccion === "arriba") {
                vecino.before(elemento);
            } else {
                vecino.after(elemento);
            }
            animarEntrada(elemento);
            if (esSeccion) {
                renumerarSecciones();
            }
            const boton = tarjeta.querySelector('[data-accion="' + (direccion === "arriba" ? "subir" : "bajar") + '"]');
            if (boton) {
                boton.focus();
            }
        } catch (error) {
            avisar(error.message);
        }
    }

    raiz.addEventListener("click", function (evento) {
        const accion = evento.target.closest("[data-accion]");
        const tarjeta = evento.target.closest("[data-tarjeta]");

        if (accion) {
            const tipo = accion.dataset.accion;
            if (tipo === "abrir") {
                evento.preventDefault();
                abrir(tarjeta);
            } else if (tipo === "agregar-pregunta") {
                const destino = destinoNuevaPregunta();
                agregarPregunta(destino.seccion, destino.despuesDe);
            } else if (tipo === "agregar-en-seccion") {
                agregarPregunta(seccionDe(accion), null);
            } else if (tipo === "agregar-seccion") {
                agregarSeccion();
            } else if (tipo === "duplicar") {
                duplicar(tarjeta);
            } else if (tipo === "eliminar") {
                eliminar(tarjeta);
            } else if (tipo === "subir" || tipo === "bajar") {
                mover(tarjeta, tipo === "subir" ? "arriba" : "abajo");
            }
            return;
        }
        if (tarjeta && tarjeta.dataset.urlEditar) {
            abrir(tarjeta);
        }
    });

    // Clic fuera de las tarjetas: se cierra la activa (como en Forms).
    document.addEventListener("click", function (evento) {
        if (activa && !evento.target.closest("[data-tarjeta], [data-barra], .enc-avisos, .modal, .offcanvas")) {
            cerrar();
        }
    });

    raiz.addEventListener("keydown", function (evento) {
        const tarjeta = evento.target.closest("[data-tarjeta]");
        if (evento.key === "Escape" && activa) {
            const anterior = activa.tarjeta;
            cerrar().then(function (cerrada) {
                if (cerrada) {
                    anterior.focus();
                }
            });
        } else if ((evento.key === "Enter" || evento.key === " ") && tarjeta && evento.target === tarjeta) {
            evento.preventDefault();
            abrir(tarjeta);
        }
    });

    window.addEventListener("resize", function () {
        if (activa) {
            moverBarra(activa.tarjeta);
        }
    });

    window.addEventListener("beforeunload", function (evento) {
        const pendientes = guardados.concat(activa && activa.guardado ? [activa.guardado] : []);
        if (pendientes.some(function (g) { return g.pendiente(); })) {
            evento.preventDefault();
            evento.returnValue = "";
        }
    });

    // --------------------------------------------------------- arrastrar y soltar

    let arrastrada = null;
    let origen = null;

    function prepararArrastre(ambito) {
        ambito.querySelectorAll("[data-lista-preguntas]").forEach(function (lista) {
            lista.addEventListener("dragover", function (evento) {
                if (!arrastrada) {
                    return;
                }
                evento.preventDefault();
                const siguiente = Array.from(lista.querySelectorAll('[data-tarjeta="pregunta"]:not(.arrastrando)')).find(function (tarjeta) {
                    const caja = tarjeta.getBoundingClientRect();
                    return evento.clientY < caja.top + caja.height / 2;
                });
                if (siguiente) {
                    if (siguiente.previousElementSibling !== arrastrada) {
                        siguiente.before(arrastrada);
                    }
                } else if (lista.lastElementChild !== arrastrada) {
                    lista.appendChild(arrastrada);
                }
            });
        });
    }

    raiz.addEventListener("pointerdown", function (evento) {
        const asa = evento.target.closest("[data-asa]");
        if (asa) {
            const tarjeta = asa.closest('[data-tarjeta="pregunta"]');
            if (!tarjeta.classList.contains("activa")) {
                tarjeta.draggable = true;
            }
        }
    });

    raiz.addEventListener("pointerup", function (evento) {
        const asa = evento.target.closest("[data-asa]");
        if (asa && !arrastrada) {
            asa.closest('[data-tarjeta="pregunta"]').draggable = false;
        }
    });

    raiz.addEventListener("dragstart", function (evento) {
        const tarjeta = evento.target.closest('[data-tarjeta="pregunta"]');
        if (!tarjeta || !tarjeta.draggable) {
            return;
        }
        arrastrada = tarjeta;
        origen = { padre: tarjeta.parentNode, siguiente: tarjeta.nextElementSibling };
        evento.dataTransfer.effectAllowed = "move";
        evento.dataTransfer.setData("text/plain", tarjeta.dataset.id);
        requestAnimationFrame(function () {
            tarjeta.classList.add("arrastrando");
        });
    });

    raiz.addEventListener("dragend", async function () {
        if (!arrastrada) {
            return;
        }
        const tarjeta = arrastrada;
        const anterior = origen;
        arrastrada = null;
        tarjeta.classList.remove("arrastrando");
        tarjeta.draggable = false;
        if (tarjeta.parentNode === anterior.padre && tarjeta.nextElementSibling === anterior.siguiente) {
            return;
        }
        const lista = tarjeta.closest("[data-lista-preguntas]");
        const datos = new URLSearchParams({ bloque: lista.dataset.bloque });
        lista.querySelectorAll('[data-tarjeta="pregunta"]').forEach(function (t) {
            datos.append("preguntas", t.dataset.id);
        });
        try {
            await pedir(raiz.dataset.urlOrdenar, datos);
            marcarEstado("Orden guardado", "ok");
            animarEntrada(tarjeta);
        } catch (error) {
            anterior.padre.insertBefore(tarjeta, anterior.siguiente);
            avisar(error.message);
        }
    });

    prepararArrastre(raiz);
})();
