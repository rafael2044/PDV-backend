from sqlalchemy import String, Float, ForeignKey, DateTime, Boolean, Enum
import enum
from datetime import datetime
from sqlalchemy.orm._orm_constructors import backref
from sqlalchemy.orm import relationship, Mapped, mapped_column
from sqlalchemy.sql import func


from app.database import Base

# Enums para status e tipos
class SaleStatus(str, enum.Enum):
    COMPLETED = "completed"
    CANCELED = "canceled"

class StockMovementType(str, enum.Enum):
    ENTRY = "entry"       # Compra/Reposição
    SALE = "sale"         # Saída por venda
    ADJUSTMENT = "loss"   # Perda/Quebra/Ajuste

class UserRole(str, enum.Enum):
    ADMIN = "admin"
    MANAGER = "manager"
    SELLER = "seller"

class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String, index=True)
    username: Mapped[str] = mapped_column(String, unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String)
    role: Mapped[UserRole] = mapped_column(Enum(UserRole), default=UserRole.SELLER)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Relacionamentos
    sales = relationship("Sale", back_populates="seller")
    sessions = relationship("CashierSession", back_populates="user")

class Product(Base):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String, index=True)
    barcode: Mapped[str] = mapped_column(String, unique=True, index=True, nullable=True)
    price: Mapped[float] = mapped_column(Float) # Preço de Venda
    cost_price: Mapped[float] = mapped_column(Float) # Preço de Custo
    stock_quantity: Mapped[float] = mapped_column(Float, default=0.0)
    category: Mapped[str] = mapped_column(String, nullable=True)
    min_stock: Mapped[float] = mapped_column(Float, default=5.0) # Para alertas
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_weighted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=True)

class CashierSession(Base):
    __tablename__ = "cashier_sessions"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    terminal_id: Mapped[str] = mapped_column(String, index=True, nullable=False)
    start_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    end_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    initial_balance: Mapped[float] = mapped_column(Float, default=0.0) # Fundo de caixa
    final_balance: Mapped[float] = mapped_column(Float, nullable=True) # Valor no fechamento
    status: Mapped[str] = mapped_column(String, default="open") # open, closed

    user = relationship("User", back_populates="sessions")
    sales = relationship("Sale", back_populates="session")

class Sale(Base):
    __tablename__ = "sales"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id")) # Quem vendeu
    session_id: Mapped[int] = mapped_column(ForeignKey("cashier_sessions.id")) # Qual turno
    total_amount: Mapped[float] = mapped_column(Float)
    payment_method: Mapped[str] = mapped_column(String) # dinheiro, credito, debito, pix
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    status: Mapped[SaleStatus] = mapped_column(Enum(SaleStatus), default=SaleStatus.COMPLETED)

    seller = relationship("User", back_populates="sales")
    session = relationship("CashierSession", back_populates="sales")
    items = relationship("SaleItem", back_populates="sale")

class SaleItem(Base):
    __tablename__ = "sale_items"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    sale_id: Mapped[int] = mapped_column(ForeignKey("sales.id"))
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"))
    quantity: Mapped[float] = mapped_column(Float)
    unit_price: Mapped[float] = mapped_column(Float) # Preço NA HORA da venda (histórico)
    subtotal: Mapped[float] = mapped_column(Float)
    product = relationship("Product", backref="sales")
    sale = relationship("Sale", back_populates="items")
    # Não criamos relacionamento direto com Product para evitar carregar dados desnecessários, 
    # mas em queries complexas podemos fazer join.

class StockMovement(Base):
    """Tabela de Auditoria de Estoque"""
    __tablename__ = "stock_movements"
    
    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"))
    quantity_change: Mapped[float] = mapped_column(Float) # Pode ser positivo ou negativo
    movement_type: Mapped[StockMovementType] = mapped_column(Enum(StockMovementType))
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    description: Mapped[str] = mapped_column(String, nullable=True)