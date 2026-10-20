// Importar históricos: zona para arrastrar el Excel y aviso de "revisando".
(function () {
    "use strict";

    const formulario = document.getElementById("formCarga");
    const zona = document.querySelector("[data-zona-carga]");
    const entrada = document.getElementById("archivo");
    if (!formulario || !zona || !entrada) {
        return;
    }
    const texto = zona.querySelector("[data-zona-texto]");
    const textoInicial = texto.innerHTML;

    function mostrarArchivo() {
        const archivo = entrada.files[0];
        zona.classList.toggle("con-archivo", Boolean(archivo));
        if (archivo) {
            texto.textContent = archivo.name + " (" + Math.max(1, Math.round(archivo.size / 1024)) + " KB)";
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
        const tipo = document.getElementById("tipo");
        if (!tipo.value) {
            e.preventDefault();
            tipo.focus();
            tipo.classList.add("is-invalid");
            return;
        }
        if (!entrada.files.length) {
            e.preventDefault();
            zona.classList.add("arrastrando");
            setTimeout(function () { zona.classList.remove("arrastrando"); }, 600);
            return;
        }
        const boton = formulario.querySelector("[data-boton-analizar]");
        boton.disabled = true;
        boton.querySelector("[data-cargando]").classList.remove("d-none");
    });
    document.getElementById("tipo").addEventListener("change", function () {
        this.classList.remove("is-invalid");
    });
})();
