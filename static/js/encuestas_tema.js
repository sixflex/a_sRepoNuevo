/*
 * Panel "Tema" del editor (HU-09): cada cambio de color o de foto se guarda
 * al instante y se ve en la muestra del panel y en el encabezado del editor.
 */
(function () {
    "use strict";

    const formulario = document.querySelector("[data-tema]");
    if (!formulario) {
        return;
    }
    const muestra = formulario.querySelector("[data-tema-muestra]");
    const fondoActual = formulario.querySelector("[data-fondo-actual]");
    const miniatura = formulario.querySelector("[data-fondo-miniatura]");
    const textoSubir = formulario.querySelector("[data-texto-subir]");
    const error = formulario.querySelector("[data-error-tema]");
    const archivo = formulario.querySelector('[name="fondo"]');

    function aplicar(tema) {
        // Todo lo marcado con data-tema-vivo (la muestra y el encabezado del editor) toma el tema nuevo.
        document.querySelectorAll("[data-tema-vivo]").forEach(function (elemento) {
            elemento.setAttribute("style", tema.estilo);
        });
        muestra.classList.toggle("con-fondo", Boolean(tema.fondo_url));
        fondoActual.hidden = !tema.fondo_url;
        miniatura.src = tema.fondo_url || "";
        textoSubir.textContent = tema.fondo_url ? "Cambiar foto" : "Subir una foto";
    }

    async function guardar(datos) {
        error.textContent = "";
        window.Encuestas.marcarEstado("Guardando tema…", "guardando");
        formulario.setAttribute("aria-busy", "true");
        try {
            const respuesta = await window.Encuestas.pedir(formulario.action, datos);
            aplicar(respuesta.tema);
            window.Encuestas.marcarEstado("Tema guardado", "ok");
        } catch (fallo) {
            error.textContent = fallo.message;
            window.Encuestas.marcarEstado("No se guardó el tema", "error");
        } finally {
            formulario.removeAttribute("aria-busy");
            archivo.value = "";
        }
    }

    formulario.addEventListener("change", function (evento) {
        if (evento.target.name === "color") {
            guardar({ color: evento.target.value });
        } else if (evento.target === archivo && archivo.files.length) {
            const datos = new FormData();
            datos.append("fondo", archivo.files[0]);
            guardar(datos);
        }
    });

    formulario.querySelector("[data-quitar-fondo]").addEventListener("click", function (evento) {
        evento.preventDefault();
        guardar({ quitar_fondo: "1" });
    });
})();
