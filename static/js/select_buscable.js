// Lista desplegable en la que también se puede escribir: <select data-buscable>.
// Al abrirla muestra todas las opciones; al escribir deja solo las que
// empiezan con lo escrito, sin distinguir mayúsculas ni tildes ("la" -> La Florida, La Reina).
// El <select> original queda oculto y es el que se envía con el formulario.
(function () {
    "use strict";

    function normalizar(texto) {
        return texto.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase().trim();
    }

    function iniciar(select) {
        const opciones = Array.from(select.options);
        const vacia = opciones.find(function (opcion) { return opcion.value === ""; });
        const idLista = select.id + "-opciones";

        const contenedor = document.createElement("div");
        contenedor.className = "select-buscable";

        const input = document.createElement("input");
        input.type = "text";
        input.className = select.className;
        input.id = select.id;
        input.autocomplete = "off";
        input.placeholder = vacia ? vacia.text : "";
        input.setAttribute("role", "combobox");
        input.setAttribute("aria-autocomplete", "list");
        input.setAttribute("aria-expanded", "false");
        input.setAttribute("aria-controls", idLista);

        const lista = document.createElement("ul");
        lista.className = "select-buscable-lista";
        lista.id = idLista;
        lista.setAttribute("role", "listbox");
        lista.hidden = true;

        select.id = select.id + "-valor";
        select.hidden = true;
        select.tabIndex = -1;
        select.parentNode.insertBefore(contenedor, select);
        contenedor.append(input, lista, select);

        let visibles = [];
        let activa = -1;

        function textoElegido() {
            const elegida = select.options[select.selectedIndex];
            return elegida && elegida.value !== "" ? elegida.text : "";
        }

        function marcar(indice) {
            activa = indice;
            lista.querySelectorAll("li[role=option]").forEach(function (item, i) {
                item.classList.toggle("activa", i === indice);
                item.setAttribute("aria-selected", i === indice ? "true" : "false");
                if (i === indice) {
                    item.scrollIntoView({ block: "nearest" });
                    input.setAttribute("aria-activedescendant", item.id);
                }
            });
        }

        function dibujar(filtro) {
            const buscado = normalizar(filtro);
            visibles = opciones.filter(function (opcion) {
                return opcion.value === "" ? buscado === "" : normalizar(opcion.text).startsWith(buscado);
            });
            lista.innerHTML = "";
            visibles.forEach(function (opcion, i) {
                const item = document.createElement("li");
                item.id = idLista + "-" + i;
                item.setAttribute("role", "option");
                item.textContent = opcion.text;
                item.addEventListener("mousedown", function (evento) {
                    evento.preventDefault();
                    elegir(opcion);
                });
                lista.appendChild(item);
            });
            if (!visibles.length) {
                const item = document.createElement("li");
                item.className = "sin-resultados";
                item.textContent = "Sin coincidencias";
                lista.appendChild(item);
            }
            marcar(visibles.length ? 0 : -1);
        }

        function abrir(filtro) {
            dibujar(filtro);
            lista.hidden = false;
            input.setAttribute("aria-expanded", "true");
        }

        function cerrar() {
            lista.hidden = true;
            input.setAttribute("aria-expanded", "false");
            input.removeAttribute("aria-activedescendant");
            input.value = textoElegido();
        }

        function elegir(opcion) {
            select.value = opcion.value;
            select.dispatchEvent(new Event("change", { bubbles: true }));
            cerrar();
        }

        input.value = textoElegido();
        input.addEventListener("focus", function () { input.select(); abrir(""); });
        input.addEventListener("click", function () { if (lista.hidden) { abrir(""); } });
        input.addEventListener("input", function () { abrir(input.value); });
        input.addEventListener("blur", cerrar);
        input.addEventListener("keydown", function (evento) {
            if (evento.key === "ArrowDown" || evento.key === "ArrowUp") {
                evento.preventDefault();
                if (lista.hidden) {
                    abrir("");
                    return;
                }
                const paso = evento.key === "ArrowDown" ? 1 : -1;
                marcar(Math.max(0, Math.min(visibles.length - 1, activa + paso)));
            } else if (evento.key === "Enter" && !lista.hidden) {
                evento.preventDefault();
                if (activa >= 0) {
                    elegir(visibles[activa]);
                }
            } else if (evento.key === "Escape") {
                cerrar();
            }
        });
        // Borrar todo el texto vuelve a «Todas».
        input.addEventListener("change", function () {
            if (input.value.trim() === "" && vacia) {
                select.value = "";
            }
        });
    }

    document.querySelectorAll("select[data-buscable]").forEach(iniciar);
})();
