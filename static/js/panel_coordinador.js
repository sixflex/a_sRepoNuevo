// Panel del coordinador: filtros dependientes y botones de alternancia de la
// evolución por año. El mapa territorial está en mapa_territorial.js.
(function () {
    "use strict";

    // Selects dependientes del panel de filtros (Sede → Campus, Facultad → Carrera):
    // se ocultan las opciones que no pertenecen a lo elegido arriba.
    document.querySelectorAll("select[data-depende-de]").forEach(function (hijo) {
        const padre = document.getElementById(hijo.dataset.dependeDe);
        if (!padre) {
            return;
        }

        function filtrar() {
            const valor = padre.value;
            hijo.querySelectorAll("option[data-padre]").forEach(function (opcion) {
                const visible = !valor || opcion.dataset.padre === valor;
                opcion.hidden = !visible;
                opcion.disabled = !visible;
            });
            const elegida = hijo.selectedOptions[0];
            if (elegida && elegida.disabled) {
                hijo.value = "";
            }
        }

        padre.addEventListener("change", filtrar);
        filtrar();
    });

    // Grupo de botones donde solo uno queda activo.
    function alternar(botones, alElegir) {
        botones.forEach(function (boton) {
            boton.addEventListener("click", function () {
                botones.forEach(function (otro) {
                    const activo = otro === boton;
                    otro.classList.toggle("active", activo);
                    otro.setAttribute("aria-pressed", activo ? "true" : "false");
                });
                alElegir(boton);
            });
        });
    }

    // Evolución por año: un gráfico por indicador.
    alternar(document.querySelectorAll("[data-evolucion]"), function (boton) {
        document.querySelectorAll("[data-evolucion-grafico]").forEach(function (grafico) {
            grafico.classList.toggle("d-none", grafico.dataset.evolucionGrafico !== boton.dataset.evolucion);
        });
    });
})();
