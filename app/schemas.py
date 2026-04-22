from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime


from app.models import SaleStatus

# --- Produto ---
class ProductSimple(BaseModel):
    name: str
    is_weighted: bool
    class Config:
        from_attributes = True

class ProductBase(BaseModel):
    name: str
    barcode: Optional[str] = None
    price: float
    cost_price: float
    category: Optional[str] = None
    min_stock: float = 5.0
    is_active: bool = True
    is_weighted: bool = False # <--- NOVO CAMPO


class ProductCreate(ProductBase):
    stock_quantity: float = 0.0 # Estoque inicial opcional

class ProductResponse(ProductBase):
    id: int
    stock_quantity: float
    
    class Config:
        from_attributes = True

class ProductUpdate(BaseModel):
    name: str
    barcode: Optional[str] = None
    price: float
    cost_price: float
    category: Optional[str] = None
    min_stock: float = 5.0
    is_active: Optional[bool] = None
    is_weighted: Optional[bool] = None # <--- NOVO CAMPO

class UserResponse(BaseModel):
    id: int
    name: str
    username: str
    role: str
    is_active: bool

    class Config:
        from_attributes = True

# --- Venda ---
class SaleItemCreate(BaseModel):
    product_id: int
    quantity: float

class SaleCreate(BaseModel):
    payment_method: str
    items: List[SaleItemCreate]

class SaleItemResponse(BaseModel):
    product_id: int
    quantity: float
    unit_price: float
    subtotal: float
    product: Optional[ProductSimple] = None # <--- Traz o nome do produto

    class Config:
        from_attributes = True

class SaleResponse(BaseModel):
    id: int
    total_amount: float
    payment_method: str
    timestamp: datetime
    status: SaleStatus
    items: List[SaleItemResponse]
    seller: Optional[UserResponse] = None
    class Config:
        from_attributes = True

# --- Caixa ---
class CashierOpen(BaseModel):
    initial_balance: float

class CashierClose(BaseModel):
    final_balance: float # Valor conferido pelo operador

class CashierSessionResponse(BaseModel):
    id: int
    terminal_id: str
    user_id: int
    start_time: datetime
    end_time: Optional[datetime]
    initial_balance: float
    final_balance: Optional[float]
    status: str
    # Opcional: Adicionar nome do usuário se quiser fazer join
    
    class Config:
        from_attributes = True