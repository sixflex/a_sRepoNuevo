
 // Importar históricos: arrastrar Excel y mostrar indicador de revisión.
(function () {
    "use strict";

    const formulario = document.getElementById("formCarga");
    if (!formulario) {
        return;
    }

    const zona = document.querySelector("[data-zona-carga]");
    const entrada = document.getElementById("archivo");
    const tipo = document.getElementById("tipo");
    const selectorHoja = document.getElementById("nombre_hoja");
    const boton = formulario.querySelector("[data-boton-analizar]");
    const archivoPendiente = formulario.dataset.archivoPendiente === "true";

    function mostrarCargando() {
        if (!boton) {
            return;
        }

        boton.disabled = true;
        const indicador = boton.querySelector("[data-cargando]");
        if (indicador) {
            indicador.classList.remove("d-none");
        }
    }

    // Segunda etapa: seleccionar una hoja del Excel ya guardado.
    if (archivoPendiente) {
        formulario.addEventListener("submit", function (e) {
            // Permitir reiniciar la carga sin seleccionar una hoja.
            if (e.submitter && e.submitter.name === "reiniciar_carga") {
                return;
            }

            if (!selectorHoja || !selectorHoja.value) {
                e.preventDefault();

                if (selectorHoja) {
                    selectorHoja.focus();
                    selectorHoja.classList.add("is-invalid");
                }
                return;
            }

            mostrarCargando();
        });

        if (selectorHoja) {
            selectorHoja.addEventListener("change", function () {
                this.classList.remove("is-invalid");
            });
        }

        return;
    }

    // Primera etapa: seleccionar o arrastrar el archivo Excel.
    if (!zona || !entrada) {
        return;
    }

    const texto = zona.querySelector("[data-zona-texto]");
    const textoInicial = texto.innerHTML;

    function mostrarArchivo() {
        const archivo = entrada.files[0];

        zona.classList.toggle("con-archivo", Boolean(archivo));

        if (archivo) {
            texto.textContent = archivo.name + " (" +
                Math.max(1, Math.round(archivo.size / 1024)) + " KB)";
        } else {
            texto.innerHTML = textoInicial;
        }
    }

    ["dragenter", "dragover"].forEach(function (evento) {
        zona.addEventListener(evento, function (e) {
            e.preventDefault();
            zona.classList.add("arrastrando");
        });
    });

    ["dragleave", "drop"].forEach(function (evento) {
        zona.addEventListener(evento, function (e) {
            e.preventDefault();
            zona.classList.remove("arrastrando");
        });
    });

    zona.addEventListener("drop", function (e) {
        if (e.dataTransfer && e.dataTransfer.files.length) {
            entrada.files = e.dataTransfer.files;
            mostrarArchivo();
        }
    });

    entrada.addEventListener("change", mostrarArchivo);

    formulario.addEventListener("submit", function (e) {
        if (!tipo.value) {
            e.preventDefault();
            tipo.focus();
            tipo.classList.add("is-invalid");
            return;
        }

        if (!entrada.files.length) {
            e.preventDefault();
            zona.classList.add("arrastrando");

            setTimeout(function () {
                zona.classList.remove("arrastrando");
            }, 600);

            return;
        }

        mostrarCargando();
    });

    tipo.addEventListener("change", function () {
        this.classList.remove("is-invalid");
    });
})();
