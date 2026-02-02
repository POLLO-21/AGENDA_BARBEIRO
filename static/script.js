document.addEventListener("DOMContentLoaded", () => {
    const rawRole = document.body.dataset.role;
    const role = rawRole && rawRole !== "None" ? rawRole : null;
    const agendaPage = document.getElementById("agenda-page");
    const agendaYear = agendaPage ? parseInt(agendaPage.dataset.ano) : null;
    const agendaMonth = agendaPage ? parseInt(agendaPage.dataset.mes) : null;
    const agendaBarberId = agendaPage && agendaPage.dataset.barberId ? parseInt(agendaPage.dataset.barberId) : null;

    // --- Modal e Agendamento (Agenda Cliente) ---
    const modal = document.getElementById('modalHorarios');
    const listaHorarios = document.getElementById("lista-horarios");
    const fecharBtn = document.querySelector(".fechar");

    // Fecha modal ao clicar no X
    if (fecharBtn && modal) {
        fecharBtn.addEventListener("click", () => {
            modal.style.display = 'none';
        });
    }

    // Fecha modal ao clicar fora
    window.addEventListener("click", (e) => {
        if (modal && e.target === modal) {
            modal.style.display = 'none';
        }
    });

    const painelBarbeiro = document.getElementById("painel-barbeiro");
    const painelYear = painelBarbeiro ? parseInt(painelBarbeiro.dataset.ano) : null;
    const painelMonth = painelBarbeiro ? parseInt(painelBarbeiro.dataset.mes) : null;
    let selectedDay = null;
    let selectedTime = null;
    let selectedService = null;

    if (!painelBarbeiro) {
        document.querySelectorAll(".dia[data-dia]").forEach(card => {
            card.addEventListener("click", (event) => {
                if (card.getAttribute('onclick')) return;

                // Se não for barbeiro e o dia não estiver disponível, ignora
                if (role !== 'barbeiro' && !card.classList.contains('disponivel')) return;

                let dia = card.dataset.dia;

                if (role === 'barbeiro') {
                    const urlParams = new URLSearchParams(window.location.search);
                    const mesParam = urlParams.get('mes') || agendaMonth || (new Date().getMonth() + 1);
                    const anoParam = urlParams.get('ano') || agendaYear || new Date().getFullYear();
                    window.location.href = `/editar_dia/${dia}?mes=${mesParam}&ano=${anoParam}`;
                    return;
                }

                const ano = agendaYear;
                const mes = agendaMonth;
                const params = new URLSearchParams();
                if (ano) params.append("ano", ano);
                if (mes) params.append("mes", mes);
                const query = params.toString() ? `?${params.toString()}` : "";
                fetch(`/horarios/${dia}${query}`)
                    .then(resp => resp.json())
                    .then(data => {
                        if (!listaHorarios) return;
                        
                        listaHorarios.innerHTML = "";
                        if (!data.horarios || data.horarios.length === 0) {
                            listaHorarios.innerHTML = '<li class="sem">Nenhum horário disponível</li>';
                        } else {
                            data.horarios.forEach(h => {
                                let li = document.createElement("li");
                                li.textContent = h;
                                li.classList.add("horario-item");

                                if (role === 'cliente' || !role) {
                                    li.style.cursor = "pointer";
                                    li.title = "Clique para reservar";
                                    li.addEventListener("click", () => {
                                        if (li.classList.contains("horario-selecionado")) {
                                            li.classList.remove("horario-selecionado");
                                            selectedTime = null;
                                            const seletor = document.getElementById("escolha-servico");
                                            if (seletor) seletor.remove();
                                            return;
                                        }

                                        selectedDay = dia;
                                        selectedTime = h;
                                        document.querySelectorAll("#lista-horarios .horario-item").forEach(el => {
                                            el.classList.remove("horario-selecionado");
                                        });
                                        li.classList.add("horario-selecionado");
                                        abrirEscolhaServico();
                                    });
                                } else {
                                    li.style.cursor = "default";
                                }
                                
                                listaHorarios.appendChild(li);
                            });
                        }
                        if (modal) modal.style.display = 'block';
                    })
                    .catch(err => console.error("Erro ao buscar horários:", err));
            });
        });
    } else {
        const btnShare = document.getElementById("btn-share-whatsapp");
        if (btnShare) {
            btnShare.addEventListener("click", () => {
                const path = btnShare.dataset.agendaUrl || "/agenda";
                const agendaUrl = `${window.location.origin}${path}`;
                const message = `Olá! Agende seu horário comigo pelo link: ${agendaUrl}`;
                const whatsappUrl = `https://wa.me/?text=${encodeURIComponent(message)}`;
                window.open(whatsappUrl, '_blank');
            });
        }

        document.querySelectorAll(".dia[data-dia]").forEach(card => {
            card.addEventListener("click", () => {
                const dia = card.dataset.dia;
                document.querySelectorAll(".dia[data-dia]").forEach(c => c.classList.remove("dia-selecionado"));
                card.classList.add("dia-selecionado");

                const ano = painelYear;
                const mes = painelMonth;
                const query = (ano && mes) ? `?ano=${ano}&mes=${mes}` : "";
                fetch(`/api/dia/${dia}/agendamentos${query}`)
                    .then(r => r.json())
                    .then(data => {
                        const container = document.getElementById("detalhes-dia-conteudo");
                        if (!container) return;
                        if (!data.success) {
                            container.innerHTML = "<p>Erro ao carregar agendamentos.</p>";
                            return;
                        }
                        let html = `<p><strong>Dia:</strong> ${data.dia}</p>`;
                        html += `<button id="btn-editar-dia-${dia}" class="btn btn-sm btn-primary">Configurar horários do dia</button>`;

                        if (!data.agendamentos || data.agendamentos.length === 0) {
                            html += "<ul><li class=\"sem-agendamento\">Nenhum agendamento para este dia.</li></ul>";
                        } else {
                            html += "<ul>";
                            data.agendamentos.forEach(a => {
                                const servico = a.service || "corte de cabelo";
                                const statusClass = a.status === "confirmado" ? "status-label status-confirmado" : "status-label status-cancelado";
                                const statusContent = a.status === "confirmado" ? "✅" : "cancelado";
                                const phone = a.phone ? ` <span style="font-size:0.85em; color:#555;">(${a.phone})</span>` : "";
                                html += `<li><strong>${a.time}</strong> - ${a.cliente}${phone} <span class="tag-service">${servico}</span> <span class="${statusClass}">${statusContent}</span></li>`;
                            });
                            html += "</ul>";
                        }
                        container.innerHTML = html;

                        const btnEditar = document.getElementById(`btn-editar-dia-${dia}`);
                        if (btnEditar) {
                            btnEditar.addEventListener("click", () => {
                                // Tenta pegar mes/ano do contexto da página ou da URL
                                const urlParams = new URLSearchParams(window.location.search);
                                const mes = urlParams.get('mes') || new Date().getMonth() + 1;
                                const ano = urlParams.get('ano') || new Date().getFullYear();
                                window.location.href = `/editar_dia/${dia}?mes=${mes}&ano=${ano}`;
                            });
                        }
                    })
                    .catch(() => {
                        const container = document.getElementById("detalhes-dia-conteudo");
                        if (container) container.innerHTML = "<p>Erro de comunicação com o servidor.</p>";
                    });
            });
        });
    }

    // --- Toast Function ---
    window.showToast = function(message, type = 'success') {
        const container = document.getElementById('toast-container');
        if (!container) return;
        
        const toast = document.createElement('div');
        toast.className = `toast ${type}`;
        toast.textContent = message;
        container.appendChild(toast);
        
        // Trigger reflow
        void toast.offsetWidth;
        
        toast.classList.add('show');
        
        setTimeout(() => {
            toast.classList.remove('show');
            setTimeout(() => {
                if (container.contains(toast)) {
                    container.removeChild(toast);
                }
            }, 300);
        }, 3000);
    };

    // --- AJAX Cancelation ---
    // Usando Event Delegation para forms presentes ou futuros
    document.addEventListener('submit', function(e) {
        if (e.target && e.target.classList.contains('form-cancelar')) {
            e.preventDefault();
            if(!confirm('Deseja realmente cancelar este agendamento?')) return;
            
            const form = e.target;
            const btn = form.querySelector('button[type="submit"]');
            const originalText = btn.textContent;
            
            btn.disabled = true;
            btn.textContent = 'Cancelando...';
            
            const formData = new FormData(form);
            
            fetch(form.action, {
                method: 'POST',
                body: formData
            })
            .then(r => r.json())
            .then(res => {
                if(res.success){
                    showToast('Agendamento cancelado com sucesso!', 'success');
                    // Remove visualmente o item
                    const li = form.closest('li.agendamento');
                    if (li) {
                        li.style.transition = 'opacity 0.5s';
                        li.style.opacity = '0';
                        setTimeout(() => li.remove(), 500);
                    }
                    // Se estiver no painel e cancelar, talvez precise recarregar calendário? 
                    // Mas o cancelamento libera o slot.
                    // Se estivermos na página de agendamentos, apenas remove da lista.
                } else {
                    showToast('Erro: ' + (res.error || 'Desconhecido'), 'error');
                    btn.disabled = false;
                    btn.textContent = originalText;
                }
            })
            .catch(() => {
                showToast('Erro de comunicação com o servidor.', 'error');
                btn.disabled = false;
                btn.textContent = originalText;
            });
        }
    });

    function abrirEscolhaServico() {
        if (!modal || !listaHorarios) return;
        let seletor = document.getElementById("escolha-servico");
        if (!seletor) {
            seletor = document.createElement("div");
            seletor.id = "escolha-servico";
            seletor.innerHTML = `
                <p style="margin-top: 1rem;">Escolha o tipo de serviço:</p>
                <div class="servico-options">
                    <button type="button" data-servico="corte de cabelo" class="btn btn-secondary btn-sm btn-servico">Corte de cabelo</button>
                    <button type="button" data-servico="corte de cabelo e barba" class="btn btn-secondary btn-sm btn-servico">Corte + barba</button>
                    <button type="button" data-servico="somente barba" class="btn btn-secondary btn-sm btn-servico">Somente barba</button>
                </div>
                <div style="margin-top:0.75rem; text-align:center;">
                    <input type="text" id="customer-name" placeholder="Seu Nome (opcional)" style="padding:8px; width:80%; border:1px solid #ccc; border-radius:4px; margin-bottom:0.5rem;">
                </div>
                <div style="margin-top:0.5rem;">
                    <button type="button" id="btn-confirmar-agendamento" class="btn btn-primary btn-sm" disabled>Confirmar agendamento</button>
                </div>
            `;
            modal.querySelector(".modal-content").appendChild(seletor);
        }

        const botoesServico = seletor.querySelectorAll(".btn-servico");
        const btnConfirmar = document.getElementById("btn-confirmar-agendamento");
        const inputName = document.getElementById("customer-name");

        selectedService = null;
        btnConfirmar.disabled = true;
        botoesServico.forEach(b => {
            b.classList.remove("btn-primary");
            b.classList.add("btn-secondary");
        });
        
        if(inputName) inputName.value = "";

        botoesServico.forEach(btn => {
            btn.onclick = () => {
                selectedService = btn.getAttribute("data-servico");
                botoesServico.forEach(b => {
                    b.classList.remove("btn-primary");
                    b.classList.add("btn-secondary");
                });
                btn.classList.remove("btn-secondary");
                btn.classList.add("btn-primary");
                if (selectedDay && selectedTime && selectedService) {
                    btnConfirmar.disabled = false;
                }
            };
        });

        btnConfirmar.onclick = () => {
            if (selectedDay && selectedTime && selectedService) {
                const name = inputName ? inputName.value : "";
                fazerReserva(selectedDay, selectedTime, selectedService, agendaYear, agendaMonth, name);
            }
        };
    }

    function fazerReserva(dia, horario, servico, ano, mes, name) {
        // Confirmação removida conforme pedido (o clique no botão já serve de confirmação)
        // if (!confirm(`Confirmar agendamento para dia ${dia} às ${horario} (${servico})?`)) return;

        const diaStr = String(dia).padStart(2, '0');
        const mesStr = String(mes).padStart(2, '0');
        
        // Desabilita botões para evitar duplo clique
        const btn = document.getElementById("btn-confirmar-agendamento");
        if(btn) {
            btn.disabled = true;
            btn.textContent = "Agendando...";
        }

        fetch("/reservar", {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify({dia: dia, horario: horario, service: servico, ano: ano, mes: mes, customer_name: name})
        }).then(r => r.json()).then(res => {
            if(res.success){
                // Mostra mensagem de sucesso e opção de WhatsApp no Modal
                const modalContent = modal.querySelector(".modal-content");
                
                let msg = `Olá! Acabei de agendar um horário:\nData: ${diaStr}/${mesStr}/${ano}\nHorário: ${horario}\nServiço: ${servico}`;
                if (name) {
                    msg += `\nCliente: ${name}`;
                }
                // Número do barbeiro configurado
                const numeroBarbeiro = "5517996673513";
                const waLink = `https://wa.me/${numeroBarbeiro}?text=${encodeURIComponent(msg)}`;

                // Redireciona automaticamente para o WhatsApp em nova aba após breve delay
                setTimeout(() => {
                   window.open(waLink, '_blank');
                }, 1500);

                modalContent.innerHTML = `
                    <div style="text-align: center;">
                        <div style="font-size: 3rem; color: #4caf50; margin-bottom: 1rem;">✅</div>
                        <h2 style="color: #2e7d32; margin-top:0;">Agendamento Confirmado!</h2>
                        <p>Seu horário foi reservado com sucesso.</p>
                        <p><strong>${diaStr}/${mesStr}/${ano} às ${horario}</strong></p>
                        <p>${servico}</p>
                        <p style="color:#666; font-size:0.9rem; margin-top:1rem;">Você será redirecionado para o WhatsApp do barbeiro...</p>
                        <div style="margin-top: 1.5rem;">
                            <a href="${waLink}" target="_blank" class="btn btn-whatsapp" style="text-decoration:none; display:inline-block; padding:0.8rem 1.2rem; border-radius:999px; background:#25D366; color:white; font-weight:bold;">
                                Comunicar Barbeiro
                            </a>
                        </div>
                        <button class="btn btn-secondary" style="margin-top: 1rem;" onclick="location.reload()">Fechar</button>
                    </div>
                `;
            } else {
                if (res.error === 'login_required') {
                    showToast("Você precisa fazer login.", "error");
                    setTimeout(() => window.location.href = "/login", 1500);
                } else if (res.error === 'slot_taken') {
                    showToast("Este horário acabou de ser ocupado. Tente outro.", "error");
                    setTimeout(() => location.reload(), 1500);
                } else {
                    showToast("Erro: " + res.error, "error");
                }
            }
        }).catch(() => showToast("Erro na requisição", "error"));
    }

    // --- Fim Agenda Barbeiro (/agenda) ---
});
