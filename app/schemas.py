from datetime import datetime
from typing import List, Literal, Optional
from pydantic import BaseModel, EmailStr, Field

# Tipos Fixos de domínio
CanalPedidoEnum = Literal["APP", "BALCAO", "PICKUP", "TOTEM", "WEB"]

StatusPedidoEnum = Literal[
    "AGUARDANDO_PAGAMENTO",
    "RECEBIDO",
    "EM_PREPARACAO",
    "PRONTO",
    "ENTREGUE",
    "CANCELADO",
]

RoleEnum = Literal["CLIENTE", "ATENDENTE", "COZINHA", "GERENTE", "ADMIN"]

# Padrão de erro global
class ErroResponse(BaseModel):
    timestamp: datetime
    status: int
    error: str
    message: str
    path: str

# Usuario
class UsuarioCreate(BaseModel):
    email: EmailStr
    senha: str = Field(min_length=6)
    role: RoleEnum = "CLIENTE"
    consentimento_lgpd: bool = False

class UsuarioResponse(BaseModel):
    id: int
    email: str
    role: str
    consentimento_lgpd: bool
    pontos_fidelidade: int
    criado_em: datetime

    model_config = {"from_attributes": True}

# Token Auth
class LoginRequest(BaseModel):
    email: EmailStr
    senha: str

class TokenResponse(BaseModel):
    accessToken: str
    tipo: str = "Bearer"

# Unidade
class UnidadeCreate(BaseModel):
    nome: str = Field(min_length=2)
    cidade: Optional[str] = None

class UnidadeResponse(BaseModel):
    id: int
    nome: str
    cidade: Optional[str]
    ativo: bool

    model_config = {"from_attributes": True}

# Produto
class ProdutoCreate(BaseModel):
    nome: str = Field(min_length=2)
    descricao: Optional[str] = None
    preco: float = Field(gt=0)
    disponivel: bool = True

class ProdutoResponse(BaseModel):
    id: int
    nome: str
    descricao: Optional[str]
    preco: float
    disponivel: bool

    model_config = {"from_attributes": True}

# Estoque
class EstoqueCreate(BaseModel):
    unidade_id: int
    produto_id: int
    quantidade: int = Field(ge=0)

class EstoqueResponse(BaseModel):
    id: int
    unidade_id: int
    produto_id: int
    quantidade: int

    model_config = {"from_attributes": True}

# Pedido
class ItemPedidoCreate(BaseModel):
    produto_id: int
    quantidade: int = Field(ge=1)

class PedidoCreate(BaseModel):
    canal_pedido: CanalPedidoEnum
    unidade_id: int
    itens: List[ItemPedidoCreate] = Field(min_length=1)

class ItemPedidoResponse(BaseModel):
    id: int
    produto_id: int
    quantidade: int
    preco_unitario: float

    model_config = {"from_attributes": True}

class PedidoResponse(BaseModel):
    id: int
    cliente_id: int
    unidade_id: int
    canal_pedido: str
    status: str
    total: float
    criado_em: datetime
    itens: List[ItemPedidoResponse] = []

    model_config = {"from_attributes": True}

# Pagamento
class PagamentoRequest(BaseModel):
    pedido_id: int
    metodo: str = Field(default="MOCK_PIX", description="Ex.: CARTAO, MOCK_PIX, PIX")

class PagamentoResponse(BaseModel):
    transacao_id: str
    pedido_id: int
    status: str
    mensagem: str

# Fidelidade
class SaldoFidelidadeResponse(BaseModel):
    usuario_id: int
    email: str
    pontos: int
    mensagem: str
