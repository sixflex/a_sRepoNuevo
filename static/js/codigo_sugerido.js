// Sugiere el código de una facultad o carrera mientras se escribe el nombre.
// Misma regla que academico/services.py (sugerir_codigo y codigo_unico):
// iniciales de las palabras con significado, sin tildes y en mayúsculas;
// si el código ya existe se agrega 2, 3... El usuario puede editarlo, y si
// lo deja vacío el servidor lo genera al guardar.
(function () {
    const codigo = document.querySelector("[data-codigo-desde]");
    if (!codigo) return;

    const nombre = document.getElementById(codigo.dataset.codigoDesde);
    const leer = (id) => JSON.parse(document.getElementById(id).textContent);
    const usados = new Set(leer("codigos-usados"));
    const sinInicial = new Set(leer("palabras-sin-inicial"));
    const largo = leer("largo-codigo");
    let automatico = !codigo.value;

    function sugerir(texto) {
        const palabras = (
            texto.normalize("NFKD").replace(/[̀-ͯ]/g, "").toUpperCase().match(/[A-Z0-9]+/g) || []
        ).filter((palabra) => !sinInicial.has(palabra.toLowerCase()));

        if (!palabras.length) return "";

        const sigla = palabras.length === 1
            ? palabras[0].slice(0, 4)
            : palabras.map((palabra) => palabra[0]).join("");
        const base = sigla.slice(0, largo);

        let candidato = base;
        for (let sufijo = 2; usados.has(candidato); sufijo++) {
            candidato = base + sufijo;
        }
        return candidato;
    }

    nombre.addEventListener("input", function () {
        if (automatico) codigo.value = sugerir(nombre.value);
    });

    codigo.addEventListener("input", function () {
        automatico = !codigo.value;
    });
})();
