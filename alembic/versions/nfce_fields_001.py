"""add_nfce_fields

Revision ID: nfce_fields_001
Revises: 304b6ac536eb
Create Date: 2026-08-07 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'nfce_fields_001'
down_revision: Union[str, None] = '304b6ac536eb'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Adicionar campos fiscais na tabela products
    op.add_column('products', sa.Column('ncm', sa.String(8), nullable=True))
    op.add_column('products', sa.Column('cest', sa.String(7), nullable=True))
    op.add_column('products', sa.Column('cfop', sa.String(4), server_default='5102'))
    op.add_column('products', sa.Column('unidade_medida', sa.String(4), server_default='UN'))
    op.add_column('products', sa.Column('origem', sa.String(1), server_default='0'))
    op.add_column('products', sa.Column('csosn_icms', sa.String(3), server_default='102'))

    # Adicionar campos de retorno NFC-e na tabela sales
    op.add_column('sales', sa.Column('nfce_chave', sa.String(), nullable=True))
    op.add_column('sales', sa.Column('nfce_numero', sa.Integer(), nullable=True))
    op.add_column('sales', sa.Column('nfce_protocolo', sa.String(), nullable=True))
    op.add_column('sales', sa.Column('nfce_status', sa.String(), server_default='pendente'))
    op.add_column('sales', sa.Column('nfce_xml', sa.String(), nullable=True))
    
    # Criar índice para nfce_chave
    op.create_index(op.f('ix_sales_nfce_chave'), 'sales', ['nfce_chave'], unique=False)


def downgrade() -> None:
    # Remover índice
    op.drop_index(op.f('ix_sales_nfce_chave'), table_name='sales')
    
    # Remover campos da tabela sales
    op.drop_column('sales', 'nfce_xml')
    op.drop_column('sales', 'nfce_status')
    op.drop_column('sales', 'nfce_protocolo')
    op.drop_column('sales', 'nfce_numero')
    op.drop_column('sales', 'nfce_chave')
    
    # Remover campos da tabela products
    op.drop_column('products', 'csosn_icms')
    op.drop_column('products', 'origem')
    op.drop_column('products', 'unidade_medida')
    op.drop_column('products', 'cfop')
    op.drop_column('products', 'cest')
    op.drop_column('products', 'ncm')
