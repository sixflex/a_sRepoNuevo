// Sugiere, al escribir la asignatura, las ya registradas en la carrera elegida
// en esa misma fila (datalist). Se puede escribir otra: si es nueva, la
// Coordinación A+S la registra al aprobar la planificación.
(function () {
    "use strict";

    const datos = document.getElementById("asignaturas-por-carrera");
    if (!datos) {
        return;
    }
    const porCarrera = JSON.parse(datos.textContent);
    const listas = {};
    let contador = 0;

    function listaDe(carrera) {
        if (!carrera || !porCarrera[carrera]) {
            return "";
        }
        if (!listas[carrera]) {
            contador += 1;
            const lista = document.createElement("datalist");
            lista.id = "asignaturas-carrera-" + contador;
            porCarrera[carrera].forEach(function (nombre) {
                const opcion = document.createElement("option");
                opcion.value = nombre;
                lista.appendChild(opcion);
            });
            document.body.appendChild(lista);
            listas[carrera] = lista.id;
        }
        return listas[carrera];
    }

    function vincular(input) {
        const contenedor = input.closest("tbody, form");
        const carrera = contenedor && contenedor.querySelector('select[name$="carrera_texto"]');
        const id = listaDe(carrera ? carrera.value : "");
        if (id) {
            input.setAttribute("list", id);
        } else {
            input.removeAttribute("list");
        }
    }

    // focusin: también sirve para las filas que se agregan después.
    document.addEventListener("focusin", function (evento) {
        if (evento.target.matches('input[name$="asignatura_texto"]')) {
            vincular(evento.target);
        }
    });
    document.addEventListener("change", function (evento) {
        if (!evento.target.matches('select[name$="carrera_texto"]')) {
            return;
        }
        const contenedor = evento.target.closest("tbody, form");
        const input = contenedor && contenedor.querySelector('input[name$="asignatura_texto"]');
        if (input) {
            vincular(input);
        }
    });
})();
