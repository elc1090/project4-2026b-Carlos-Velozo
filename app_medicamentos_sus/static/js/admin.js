/* Interações do painel administrativo. */
(function () {
    "use strict";

    /* ---------------------------------------------- Menu lateral */
    const sidebar = document.getElementById("admin-sidebar");
    const toggle = document.getElementById("admin-menu-toggle");
    const overlay = document.getElementById("admin-overlay");
    const closeBtn = document.getElementById("admin-sidebar-close");
    const consultaMobile = window.matchMedia("(max-width: 900px)");

    function menuAberto() {
        return Boolean(sidebar && sidebar.classList.contains("is-open"));
    }

    function definirMenu(estado, devolverFoco) {
        if (!sidebar || !toggle || !overlay) {
            return;
        }

        sidebar.classList.toggle("is-open", estado);
        overlay.hidden = !estado;
        document.body.classList.toggle("admin-menu-open", estado);
        toggle.setAttribute("aria-expanded", estado ? "true" : "false");

        if (estado) {
            const primeiro =
                sidebar.querySelector(".admin-menu-link") ||
                sidebar.querySelector("a[href], button");
            if (primeiro) {
                primeiro.focus();
            }
        } else if (devolverFoco) {
            toggle.focus();
        }
    }

    if (toggle) {
        toggle.addEventListener("click", function () {
            definirMenu(!menuAberto(), false);
        });
    }

    if (closeBtn) {
        closeBtn.addEventListener("click", function () {
            definirMenu(false, true);
        });
    }

    if (overlay) {
        overlay.addEventListener("click", function () {
            definirMenu(false, true);
        });
    }

    if (sidebar) {
        sidebar.addEventListener("click", function (evento) {
            if (evento.target.closest("a[href]") && consultaMobile.matches) {
                definirMenu(false, false);
            }
        });

        sidebar.addEventListener("keydown", function (evento) {
            if (!menuAberto()) {
                return;
            }

            if (evento.key === "Escape") {
                evento.preventDefault();
                definirMenu(false, true);
                return;
            }

            if (evento.key !== "Tab") {
                return;
            }

            const focaveis = Array.from(
                sidebar.querySelectorAll(
                    'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'
                )
            ).filter(function (elemento) {
                return elemento.offsetParent !== null;
            });

            if (!focaveis.length) {
                return;
            }

            const primeiro = focaveis[0];
            const ultimo = focaveis[focaveis.length - 1];

            if (evento.shiftKey && document.activeElement === primeiro) {
                evento.preventDefault();
                ultimo.focus();
            } else if (!evento.shiftKey && document.activeElement === ultimo) {
                evento.preventDefault();
                primeiro.focus();
            }
        });
    }

    if (consultaMobile.addEventListener) {
        consultaMobile.addEventListener("change", function (evento) {
            if (!evento.matches) {
                definirMenu(false, false);
            }
        });
    }

    /* --------------------------------- Confirmação de exclusão */
    const dialogo = document.getElementById("confirm-dialog");
    const descricao = document.getElementById("confirm-desc");
    let formularioPendente = null;

    document.addEventListener(
        "submit",
        function (evento) {
            const formulario = evento.target;

            if (!(formulario instanceof HTMLFormElement)) {
                return;
            }

            const mensagem = formulario.dataset.confirm;
            if (!mensagem) {
                return;
            }

            if (!dialogo || typeof dialogo.showModal !== "function") {
                return;
            }

            evento.preventDefault();
            evento.stopImmediatePropagation();
            formularioPendente = formulario;

            if (descricao) {
                descricao.textContent = mensagem;
            }

            dialogo.returnValue = "";
            dialogo.showModal();
        },
        true
    );

    if (dialogo) {
        dialogo.addEventListener("click", function (evento) {
            if (evento.target === dialogo) {
                dialogo.close("cancelar");
            }
        });

        dialogo.addEventListener("close", function () {
            const formulario = formularioPendente;
            formularioPendente = null;

            if (dialogo.returnValue !== "confirmar" || !formulario) {
                return;
            }

            formulario.onsubmit = null;
            HTMLFormElement.prototype.submit.call(formulario);
        });
    }

    /* ------------------------------- Pré-visualização do upload */
    const entrada = document.querySelector("[data-upload]");
    const caixa = document.querySelector("[data-upload-preview]");

    if (entrada && caixa) {
        const imagem = caixa.querySelector("[data-upload-img]");
        const nome = caixa.querySelector("[data-upload-nome]");
        const tamanho = caixa.querySelector("[data-upload-tamanho]");
        const aviso = caixa.querySelector("[data-upload-aviso]");
        const limite = Number(entrada.dataset.maxSize || 0);
        let urlAtual = null;

        function formatarTamanho(bytes) {
            if (bytes >= 1024 * 1024) {
                return (bytes / (1024 * 1024)).toFixed(1).replace(".", ",") + " MB";
            }
            return Math.max(1, Math.round(bytes / 1024)) + " KB";
        }

        entrada.addEventListener("change", function () {
            const arquivo = entrada.files && entrada.files[0];

            if (urlAtual) {
                URL.revokeObjectURL(urlAtual);
                urlAtual = null;
            }

            if (!arquivo) {
                caixa.hidden = true;
                return;
            }

            caixa.hidden = false;
            if (nome) {
                nome.textContent = arquivo.name;
            }
            if (tamanho) {
                tamanho.textContent = formatarTamanho(arquivo.size);
            }

            const tipoValido = ["image/png", "image/jpeg", "image/webp"].includes(
                arquivo.type
            );

            if (!tipoValido) {
                if (imagem) {
                    imagem.hidden = true;
                }
                if (aviso) {
                    aviso.hidden = false;
                    aviso.textContent =
                        "Formato não suportado. Envie uma imagem PNG, JPG ou WEBP.";
                }
                return;
            }

            if (limite && arquivo.size > limite) {
                if (aviso) {
                    aviso.hidden = false;
                    aviso.textContent =
                        "A imagem excede o limite de 5 MB e será recusada.";
                }
            } else if (aviso) {
                aviso.hidden = true;
                aviso.textContent = "";
            }

            urlAtual = URL.createObjectURL(arquivo);
            if (imagem) {
                imagem.hidden = false;
                imagem.src = urlAtual;
            }
        });
    }

    /* ---------------------------------------- Inventário da farmácia */
    const marcarTodos = document.getElementById("marcar-todos");

    if (marcarTodos) {
        const caixas = Array.from(document.querySelectorAll(".inventario-check"));
        const contador = document.querySelector("[data-inv-counter]");

        function atualizarInventario() {
            const marcados = caixas.filter(function (caixa) {
                return caixa.checked;
            }).length;

            if (contador) {
                contador.textContent =
                    marcados +
                    " de " +
                    caixas.length +
                    " selecionado(s) nesta página";
            }

            marcarTodos.checked = caixas.length > 0 && marcados === caixas.length;
            marcarTodos.indeterminate = marcados > 0 && marcados < caixas.length;
        }

        marcarTodos.addEventListener("change", function () {
            caixas.forEach(function (caixa) {
                caixa.checked = marcarTodos.checked;
            });
            atualizarInventario();
        });

        caixas.forEach(function (caixa) {
            caixa.addEventListener("change", atualizarInventario);
        });

        atualizarInventario();
    }

    /* ----------------------------- Estado de envio dos formulários */
    document.addEventListener("submit", function (evento) {
        const formulario = evento.target;

        if (!(formulario instanceof HTMLFormElement)) {
            return;
        }

        if (!formulario.hasAttribute("data-loading") || evento.defaultPrevented) {
            return;
        }

        const botao = formulario.querySelector(
            'button[type="submit"], input[type="submit"]'
        );

        if (!botao || botao.dataset.enviando === "1") {
            return;
        }

        botao.dataset.enviando = "1";
        botao.classList.add("is-loading");
        botao.setAttribute("aria-busy", "true");

        const icone = botao.querySelector("i");
        if (icone) {
            botao.dataset.icone = icone.className;
            icone.className = "fa-solid fa-circle-notch fa-spin";
        }

        window.setTimeout(function () {
            botao.disabled = true;
        }, 0);
    });

    window.addEventListener("pageshow", function () {
        document.querySelectorAll("[data-loading] .is-loading").forEach(function (botao) {
            botao.disabled = false;
            botao.classList.remove("is-loading");
            botao.removeAttribute("aria-busy");
            delete botao.dataset.enviando;

            const icone = botao.querySelector("i");
            if (icone && botao.dataset.icone) {
                icone.className = botao.dataset.icone;
            }
        });
    });

    /* Mantém o botão do menu refletindo o estado ao redimensionar. */
    if (toggle) {
        toggle.setAttribute("aria-expanded", menuAberto() ? "true" : "false");
    }
})();
