import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from app.models import (
    Estoque,
    ItemPedido,
    LogAuditoria,
    Pedido,
    Produto,
    Unidade,
    Usuario,
)
from app.schemas import ItemPedidoCreate, PedidoCreate

# Canais válidos
CANAIS_VALIDOS = {"APP", "TOTEM", "BALCAO", "PICKUP", "WEB"}

def validar_canal(canal: str) -> None:
    
    if canal not in CANAIS_VALIDOS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Canal '{canal}' inválido. "
                f"Selecione um dos canais válidos: {', '.join(sorted(CANAIS_VALIDOS))}."
            ),
        )

# Calcula o total e valida o estoque.
def calcular_total(
    itens: List[ItemPedidoCreate],
    unidade_id: int,
    db: Session,
) -> tuple[float, Dict[int, Produto]]:
    
    total = 0.0
    produtos_map: Dict[int, Produto] = {}

    for item in itens:
        produto = db.query(Produto).filter(
            Produto.id == item.produto_id,
            Produto.disponivel == True,
        ).first()
        if not produto:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Produto id={item.produto_id} não encontrado.",
            )
        estoque = db.query(Estoque).filter(
            Estoque.produto_id == item.produto_id,
            Estoque.unidade_id == unidade_id,
        ).first()
        if not estoque:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    f"Produto '{produto.nome}' não possui estoque"
                    f"na unidade id={unidade_id}."
                ),
            )
        if estoque.quantidade < item.quantidade:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    f"Estoque insuficiente para o produto '{produto.nome}'. "
                    f"Disponível: {estoque.quantidade}, solicitado: {item.quantidade}."
                ),
            )

        produtos_map[produto.id] = produto
        total += produto.preco * item.quantidade

    return round(total, 2), produtos_map


# Cria o pedido
def criar_pedido(
    dados: PedidoCreate,
    usuario: Usuario,
    db: Session,
) -> Pedido:
    validar_canal(dados.canal_pedido)
    unidade = db.query(Unidade).filter(
        Unidade.id == dados.unidade_id,
        Unidade.ativo == True,  # noqa: E712
    ).first()
    if not unidade:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Unidade id={dados.unidade_id} não encontrada.",
        )
    total, produtos_map = calcular_total(dados.itens, dados.unidade_id, db)

    pedido = Pedido(
        cliente_id=usuario.id,
        unidade_id=dados.unidade_id,
        canal_pedido=dados.canal_pedido,
        status="AGUARDANDO_PAGAMENTO",
        total=total,
    )
    db.add(pedido)
    db.flush()

    for item_data in dados.itens:
        produto = produtos_map[item_data.produto_id]
        item = ItemPedido(
            pedido_id=pedido.id,
            produto_id=item_data.produto_id,
            quantidade=item_data.quantidade,
            preco_unitario=produto.preco,
        )
        db.add(item)
    _registrar_log(
        db=db,
        usuario_id=usuario.id,
        acao="PEDIDO_CRIADO",
        descricao=f"Pedido id={pedido.id} criado via {dados.canal_pedido}. Total: R$ {total}",
    )

    db.commit()
    db.refresh(pedido)
    return pedido


# Processamento de pagamento (mock)
def processar_pagamento(
    pedido_id: int,
    metodo: str,
    db: Session,
    usuario: Optional[Usuario] = None,
) -> dict:
    pedido = db.query(Pedido).filter(Pedido.id == pedido_id).first()
    if not pedido:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Pedido id={pedido_id} não encontrado.",
        )
    if pedido.status != "AGUARDANDO_PAGAMENTO":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Pedido id={pedido_id} não está aguardando pagamento "
                f"(status atual: {pedido.status})."
            ),
        )
# Realiza a conferência de estoque antes da baixa
    for item in pedido.itens:
        estoque = db.query(Estoque).filter(
            Estoque.produto_id == item.produto_id,
            Estoque.unidade_id == pedido.unidade_id,
        ).first()
        if not estoque or estoque.quantidade < item.quantidade:
            produto_nome = item.produto.nome if item.produto else f"id={item.produto_id}"
            disponivel = estoque.quantidade if estoque else 0
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    f"Estoque insuficiente para '{produto_nome}' no momento do pagamento. "
                    f"Disponível: {disponivel}, necessário: {item.quantidade}."
                ),
            )
    transacao_id = str(uuid.uuid4())
    pedido.status = "RECEBIDO"
    pedido.transacao_id = transacao_id
    pedido.atualizado_em = datetime.now(timezone.utc)

    # Baixa o estoque após confirmação do pagamento
    _debitar_estoque(pedido, db)

    # Pontos de fidelidade
    if pedido.cliente and pedido.cliente.consentimento_lgpd:
        pontos_ganhos = int(pedido.total)
        pedido.cliente.pontos_fidelidade += pontos_ganhos

    # log de transação
    _registrar_log(
        db=db,
        usuario_id=usuario.id if usuario else pedido.cliente_id,
        acao="PAGAMENTO_APROVADO",
        descricao=(
            f"Pedido id={pedido_id} aprovado. "
            f"Método: {metodo}. Transação: {transacao_id}."
        ),
    )

    db.commit()

    return {
        "transacao_id": transacao_id,
        "pedido_id": pedido_id,
        "status": "APROVADO",
        "mensagem": "Pagamento processado com sucesso. Pedido atualizado para RECEBIDO.",
    }

def _debitar_estoque(pedido: Pedido, db: Session) -> None:
    "Debita o estoque de cada item do pedido na unidade correspondente."
    for item in pedido.itens:
        estoque = db.query(Estoque).filter(
            Estoque.produto_id == item.produto_id,
            Estoque.unidade_id == pedido.unidade_id,
        ).first()
        if estoque:
            estoque.quantidade -= item.quantidade

def _registrar_log(
    db: Session,
    acao: str,
    descricao: Optional[str] = None,
    usuario_id: Optional[int] = None,
    ip: Optional[str] = None,
) -> None:
    log = LogAuditoria(
        usuario_id=usuario_id,
        acao=acao,
        descricao=descricao,
        ip=ip,
    )
    db.add(log)
