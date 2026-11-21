/* Notificações globais: dispensar e pausar a contagem ao interagir. */
(function () {
    "use strict";

    const DURACAO = 5000;
    const SAIDA = 400;

    document.querySelectorAll("[data-alert]").forEach(function (alerta) {
        let restante = DURACAO;
        let inicio = Date.now();
        let removido = false;
        let temporizador = null;

        function remover() {
            if (removido) {
                return;
            }
            removido = true;
            window.clearTimeout(temporizador);
            alerta.classList.add("alert-hide");
            window.setTimeout(function () {
                alerta.remove();
            }, SAIDA);
        }

        function iniciar() {
            inicio = Date.now();
            temporizador = window.setTimeout(remover, Math.max(800, restante));
        }

        function pausar() {
            if (removido) {
                return;
            }
            window.clearTimeout(temporizador);
            restante -= Date.now() - inicio;
        }

        function retomar() {
            if (removido) {
                return;
            }
            restante = Math.max(restante, 1200);
            iniciar();
        }

        const botao = alerta.querySelector(".alert-close");
        if (botao) {
            botao.addEventListener("click", remover);
        }

        alerta.addEventListener("mouseenter", pausar);
        alerta.addEventListener("mouseleave", retomar);
        alerta.addEventListener("focusin", pausar);
        alerta.addEventListener("focusout", retomar);

        iniciar();
    });
})();
