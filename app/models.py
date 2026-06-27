from datetime import datetime, timezone
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import relationship
from app.database import Base

# Categorias enumeradas de domínio
CANAIS_VALIDOS = ("APP", "BALCAO", "PICKUP", "TOTEM", "WEB")

STATUS_PEDIDO = (
    "AGUARDANDO_PAGAMENTO",
    "PEDIDO_RECEBIDO",
    "EM_PREPARACAO",
    "PRONTO",
    "ENTREGUE",
    "CANCELADO",
)

ROLES_VALIDOS = ("CLIENTE", "ATENDENTE", "COZINHA", "GERENTE", "ADMIN_MATRIZ")

# Modelos
class Usuario(Base):
    __tablename__ = "usuarios"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    senha_hash = Column(String(255), nullable=False)
    role = Column(
        Enum(*ROLES_VALIDOS, name="role_enum"),
        nullable=False,
        default="CLIENTE",
    )
    consentimento_lgpd = Column(Boolean, nullable=False, default=False)
    pontos_fidelidade = Column(Integer, nullable=False, default=0)
    criado_em = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    pedidos = relationship("Pedido", back_populates="cliente")

class Unidade(Base):
    __tablename__ = "unidades"

    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String(255), nullable=False)
    cidade = Column(String(100), nullable=True)
    ativo = Column(Boolean, nullable=False, default=True)

    estoques = relationship("Estoque", back_populates="unidade")
    pedidos = relationship("Pedido", back_populates="unidade")

class Produto(Base):
    __tablename__ = "produtos"

    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String(255), nullable=False)
    descricao = Column(Text, nullable=True)
    preco = Column(Float, nullable=False)
    disponivel = Column(Boolean, nullable=False, default=True)

    estoques = relationship("Estoque", back_populates="produto")
    itens = relationship("ItemPedido", back_populates="produto")

class Estoque(Base):
    __tablename__ = "estoques"

    id = Column(Integer, primary_key=True, index=True)
    unidade_id = Column(Integer, ForeignKey("unidades.id"), nullable=False)
    produto_id = Column(Integer, ForeignKey("produtos.id"), nullable=False)
    quantidade = Column(Integer, nullable=False, default=0)

    unidade = relationship("Unidade", back_populates="estoques")
    produto = relationship("Produto", back_populates="estoques")

class Pedido(Base):
    __tablename__ = "pedidos"

    id = Column(Integer, primary_key=True, index=True)
    cliente_id = Column(Integer, ForeignKey("usuarios.id"), nullable=False)
    unidade_id = Column(Integer, ForeignKey("unidades.id"), nullable=False)
    canal_pedido = Column(
        Enum(*CANAIS_VALIDOS, name="canal_enum"),
        nullable=False,
    )
    status = Column(
        Enum(*STATUS_PEDIDO, name="status_enum"),
        nullable=False,
        default="AGUARDANDO_PAGAMENTO",
    )
    total = Column(Float, nullable=False, default=0.0)
    transacao_id = Column(String(255), nullable=True, unique=True)
    criado_em = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    atualizado_em = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    cliente = relationship("Usuario", back_populates="pedidos")
    unidade = relationship("Unidade", back_populates="pedidos")
    itens = relationship("ItemPedido", back_populates="pedido", cascade="all, delete-orphan")

class ItemPedido(Base):
    __tablename__ = "itens_pedido"

    id = Column(Integer, primary_key=True, index=True)
    pedido_id = Column(Integer, ForeignKey("pedidos.id"), nullable=False)
    produto_id = Column(Integer, ForeignKey("produtos.id"), nullable=False)
    quantidade = Column(Integer, nullable=False)
    preco_unitario = Column(Float, nullable=False)

    pedido = relationship("Pedido", back_populates="itens")
    produto = relationship("Produto", back_populates="itens")

class LogAuditoria(Base):
    __tablename__ = "logs_auditoria"

    id = Column(Integer, primary_key=True, index=True)
    usuario_id = Column(Integer, nullable=True)
    acao = Column(String(100), nullable=False)
    descricao = Column(Text, nullable=True)
    ip = Column(String(50), nullable=True)
    criado_em = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
