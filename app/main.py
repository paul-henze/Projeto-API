from datetime import datetime, timezone
from typing import List, Optional
from fastapi import Depends, FastAPI, HTTPException, Query, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from app.auth import (
    criar_access_token,
    get_current_user,
    hash_senha,
    verificar_senha,
)
from app.database import Base, engine, get_db
from app.models import Estoque, Pedido, Produto, Unidade, Usuario
from app.schemas import (
    ErroResponse,
    EstoqueCreate,
    EstoqueResponse,
    SaldoFidelidadeResponse,
    LoginRequest,
    PagamentoRequest,
    PagamentoResponse,
    PedidoCreate,
    PedidoResponse,
    ProdutoCreate,
    ProdutoResponse,
    TokenResponse,
    UnidadeCreate,
    UnidadeResponse,
    UsuarioCreate,
    UsuarioResponse,
)
from app.services import criar_pedido, processar_pagamento, validar_canal

# Cria as tabelas de forma automática.
Base.metadata.create_all(bind=engine)

# Realiza a instância do FastAPI.
app = FastAPI(
    title=" Projeto Raízes do Nordeste — API",
    description=(
        "API REST para gerenciamento de pedidos "
        "Autenticação: Use `POST /auth/login` para obter o token JWT e clique no botão "
        "**Authorize** para inserir o token no formato `Bearer <token>`."
    ),
    version="1.1.0",
    contact={"name": "Suporte", "email": "suporte@raizesnordeste.com.br"},
    swagger_ui_parameters={"persistAuthorization": True},
)

def _erro(
    request: Request,
    http_status: int,
    error_label: str,
    message: str,
) -> JSONResponse:
    "Gera resposta de erro padronizada."
    return JSONResponse(
        status_code=http_status,
        content={
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "status": http_status,
            "error": error_label,
            "message": message,
            "path": str(request.url.path),
        },
    )

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    labels = {
        400: "Requisição Inválida",
        401: "Não Autorizado",
        403: "Proibido",
        404: "Não encontrado",
        409: "Conflito",
        422: "Entidade não processável",
        500: "Erro Interno do Servidor",
    }
    label = labels.get(exc.status_code, "Erro")
    return _erro(request, exc.status_code, label, str(exc.detail))

@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    return _erro(request, 500, "Erro interno do servidor", "Erro interno inesperado.")

# Dependência: controla acesso a funções administrativas.
ROLES_ADMIN = {"GERENTE", "ADMIN"}

def require_admin(usuario: Usuario = Depends(get_current_user)) -> Usuario:
    "Autoriza somente perfis ADMIN e GERENTE."

    if usuario.role not in ROLES_ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acesso restrito a ADMIN e GERENTE.",
        )
    return usuario

##  ENDPOINTS
 
# Usuários 
@app.post(
    "/usuarios",
    response_model=UsuarioResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Usuários"],
    summary="Cria um novo usuário",
)
def criar_usuario(dados: UsuarioCreate, request: Request, db: Session = Depends(get_db)):
    existente = db.query(Usuario).filter(Usuario.email == dados.email).first()
    if existente:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"E-mail '{dados.email}' cadastrado.",
        )
    usuario = Usuario(
        email=dados.email,
        senha_hash=hash_senha(dados.senha),
        role=dados.role,
        consentimento_lgpd=dados.consentimento_lgpd,
    )
    db.add(usuario)
    db.commit()
    db.refresh(usuario)
    return usuario

# Autenticação
@app.post(
    "/auth/login",
    response_model=TokenResponse,
    tags=["Autenticação"],
    summary="Autentica e retorna token JWT.",
)
def login(dados: LoginRequest, request: Request, db: Session = Depends(get_db)):
    usuario = db.query(Usuario).filter(Usuario.email == dados.email).first()
    if not usuario or not verificar_senha(dados.senha, usuario.senha_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuário ou senha inválidos.",
        )
    token = criar_access_token({"sub": str(usuario.id), "role": usuario.role})
    return TokenResponse(accessToken=token)

# Unidades
@app.post(
    "/unidades",
    response_model=UnidadeResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Unidades"],
    summary="Cadastra uma Unidade (requer perfis GERENTE ou ADMIN)",
)
def criar_unidade(
    dados: UnidadeCreate,
    request: Request,
    _: Usuario = Depends(require_admin),
    db: Session = Depends(get_db),
):
    unidade = Unidade(nome=dados.nome, cidade=dados.cidade)
    db.add(unidade)
    db.commit()
    db.refresh(unidade)
    return unidade

@app.get(
    "/unidades",
    response_model=List[UnidadeResponse],
    tags=["Unidades"],
    summary="Listar todas as Unidades",
)
def listar_unidades(db: Session = Depends(get_db)):
    return db.query(Unidade).filter(Unidade.ativo == True).all()  # noqa: E712

@app.get(
    "/unidades/{unidade_id}/produtos",
    response_model=List[ProdutoResponse],
    tags=["Unidades"],
    summary="Listar produtos disponíveis em estoque em uma Unidade",
)
def produtos_por_unidade(unidade_id: int, request: Request, db: Session = Depends(get_db)):
    unidade = db.query(Unidade).filter(Unidade.id == unidade_id).first()
    if not unidade:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Unidade id={unidade_id} não encontrada.",
        )

    estoques = (
        db.query(Estoque)
        .filter(Estoque.unidade_id == unidade_id, Estoque.quantidade > 0)
        .all()
    )
    produto_ids = {e.produto_id for e in estoques}
    produtos = (
        db.query(Produto)
        .filter(Produto.id.in_(produto_ids), Produto.disponivel == True)  # noqa: E712
        .all()
    )
    return produtos

# Produtos
@app.post(
    "/produtos",
    response_model=ProdutoResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Produtos"],
    summary="Cadastra um produto (requer perfis GERENTE ou ADMIN)",
)
def criar_produto(
    dados: ProdutoCreate,
    request: Request,
    _: Usuario = Depends(require_admin),
    db: Session = Depends(get_db),
):
    produto = Produto(
        nome=dados.nome,
        descricao=dados.descricao,
        preco=dados.preco,
        disponivel=dados.disponivel,
    )
    db.add(produto)
    db.commit()
    db.refresh(produto)
    return produto


@app.get(
    "/produtos",
    response_model=List[ProdutoResponse],
    tags=["Produtos"],
    summary="Listar todos os produtos",
)
def listar_produtos(
    disponivel: Optional[bool] = Query(None, description="Filtrar por disponibilidade"),
    db: Session = Depends(get_db),
):
    query = db.query(Produto)
    if disponivel is not None:
        query = query.filter(Produto.disponivel == disponivel)
    return query.all()

# Estoque
@app.post(
    "/estoque",
    response_model=EstoqueResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Estoque"],
    summary="Cadastra/Atualiza estoque de produto em uma Unidade (requer perfis GERENTE ou ADMIN)",
)
def criar_ou_atualizar_estoque(
    dados: EstoqueCreate,
    request: Request,
    _: Usuario = Depends(require_admin),  # FIX: protegido
    db: Session = Depends(get_db),
):
    unidade = db.query(Unidade).filter(Unidade.id == dados.unidade_id).first()
    if not unidade:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Unidade id={dados.unidade_id} não encontrada.",
        )

    produto = db.query(Produto).filter(Produto.id == dados.produto_id).first()
    if not produto:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Produto id={dados.produto_id} não encontrado.",
        )

    estoque = db.query(Estoque).filter(
        Estoque.unidade_id == dados.unidade_id,
        Estoque.produto_id == dados.produto_id,
    ).first()

    if estoque:
        estoque.quantidade = dados.quantidade
    else:
        estoque = Estoque(
            unidade_id=dados.unidade_id,
            produto_id=dados.produto_id,
            quantidade=dados.quantidade,
        )
        db.add(estoque)

    db.commit()
    db.refresh(estoque)
    return estoque

@app.get(
    "/estoque",
    response_model=List[EstoqueResponse],
    tags=["Estoque"],
    summary="Listar todo o estoque",
)
def listar_estoque(
    unidade_id: Optional[int] = Query(None, description="Filtrar por Unidade"),
    produto_id: Optional[int] = Query(None, description="Filtrar por produto"),
    db: Session = Depends(get_db),
):
    query = db.query(Estoque)
    if unidade_id:
        query = query.filter(Estoque.unidade_id == unidade_id)
    if produto_id:
        query = query.filter(Estoque.produto_id == produto_id)
    return query.all()


# Pedidos
@app.post(
    "/pedidos",
    response_model=PedidoResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Pedidos"],
    summary="Cria um pedido (autenticado — cliente extraído do JWT)",
)
def novo_pedido(
    dados: PedidoCreate,
    request: Request,
    usuario: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    pedido = criar_pedido(dados, usuario, db)
    return pedido


@app.get(
    "/pedidos",
    response_model=List[PedidoResponse],
    tags=["Pedidos"],
    summary="Lista pedidos com filtros opcionais",
)
def listar_pedidos(
    canal_pedido: Optional[str] = Query(
        None,
        description="Filtrar por canal: APP, BALCAO, PICKUP,TOTEM, WEB",
    ),
    status_pedido: Optional[str] = Query(
        None,
        alias="status",
        description="Filtrar por status do pedido",
    ),
    usuario: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if canal_pedido:
        validar_canal(canal_pedido)

    query = db.query(Pedido)

    if usuario.role == "CLIENTE":
        query = query.filter(Pedido.cliente_id == usuario.id)

    if canal_pedido:
        query = query.filter(Pedido.canal_pedido == canal_pedido)
    if status_pedido:
        query = query.filter(Pedido.status == status_pedido)

    return query.order_by(Pedido.criado_em.desc()).all()


# Pagamento - processamento do pagamento
@app.post(
    "/pagamentos/processar",
    response_model=PagamentoResponse,
    tags=["Pagamento"],
    summary="Processa pagamento (Simula processamento de pagamento via gateway externo).",
)
def processar_pagamento_endpoint(
    dados: PagamentoRequest,
    request: Request,
    usuario: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    resultado = processar_pagamento(dados.pedido_id, dados.metodo, db, usuario)
    return PagamentoResponse(**resultado)


# Fidelidade - verifica o saldo de pontos e LGPD
@app.get(
    "/fidelidade/saldo",
    response_model=SaldoFidelidadeResponse,
    tags=["Fidelidade"],
    summary="Verifica saldo de pontos com autenticação e consentimento LGPD obrigatório",
)
def saldo_fidelidade(
    request: Request,
    usuario: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not usuario.consentimento_lgpd:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "Consentimento LGPD não habilitado para programa de fidelidade. "
            ),
        )

    return SaldoFidelidadeResponse(
        usuario_id=usuario.id,
        email=usuario.email,
        pontos=usuario.pontos_fidelidade,
        mensagem=f"Você tem {usuario.pontos_fidelidade} pontos.",
    )

# StatusCheck - confere se a api está ativa e funcionando
@app.get("/Status", tags=["API"], summary="Verifica o status da API")
def status_check():
    return {
        "status da API": "Ok",
        "API": "Projeto Raizes do Nordeste",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
